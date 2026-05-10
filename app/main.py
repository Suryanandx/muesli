import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

from app.audio import AudioRecorder
from app.transcriber import Transcriber
from app.summarizer import Summarizer, from_env as summarizer_from_env
from app import storage

BASE_DIR = Path(__file__).parent.parent
RECORDINGS_DIR = BASE_DIR / "recordings"

# Singletons
_recorder: Optional[AudioRecorder] = None
_transcriber: Optional[Transcriber] = None
_summarizer: Optional[Summarizer] = None
_active_device: Optional[str] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    await storage.init_db()
    get_transcriber().preload()
    yield
    # Graceful shutdown
    from app.database import close_pool
    from app.cache import close_redis
    await close_pool()
    await close_redis()


app = FastAPI(title="Muesli", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


# ── Singletons ────────────────────────────────────────────────────────────────

def get_recorder() -> AudioRecorder:
    global _recorder, _active_device
    device = _active_device or os.getenv("AUDIO_DEVICE", "").strip() or None
    if _recorder is None or _recorder.device != device:
        _recorder = AudioRecorder(RECORDINGS_DIR, device=device)
    return _recorder


def get_transcriber() -> Transcriber:
    global _transcriber
    if _transcriber is None:
        _transcriber = Transcriber(model_size=os.getenv("WHISPER_MODEL", "base"))
    return _transcriber


def get_summarizer() -> Summarizer:
    global _summarizer
    if _summarizer is None:
        try:
            _summarizer = summarizer_from_env()
        except ValueError as e:
            raise HTTPException(status_code=500, detail=str(e))
    return _summarizer


# ── Pages ─────────────────────────────────────────────────────────────────────

@app.get("/")
async def landing():
    return FileResponse(BASE_DIR / "static" / "landing.html")


@app.get("/app")
async def app_page():
    return FileResponse(BASE_DIR / "static" / "index.html")


# ── Config & provider ─────────────────────────────────────────────────────────

@app.get("/api/config")
async def get_config():
    provider = os.getenv("PROVIDER", "anthropic").lower()
    device = _active_device or os.getenv("AUDIO_DEVICE", "").strip() or None

    model = {
        "anthropic": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        "ollama": os.getenv("OLLAMA_MODEL", "llama3.2"),
        "openrouter": os.getenv("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet"),
    }.get(provider, "—")

    return {
        "provider": provider,
        "model": model,
        "whisper_model": os.getenv("WHISPER_MODEL", "base"),
        "audio_device": device or "default mic",
    }


@app.post("/api/provider/test")
async def test_provider():
    """Quick call to verify the LLM provider is reachable."""
    try:
        s = get_summarizer()
        if s.provider == "anthropic":
            s._client.messages.create(
                model=s._model, max_tokens=5,
                messages=[{"role": "user", "content": "hi"}],
            )
        else:
            s._client.chat.completions.create(
                model=s._model, max_tokens=5,
                messages=[{"role": "user", "content": "hi"}],
            )
        return {"ok": True, "provider": s.provider, "model": s._model}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


class DeviceUpdate(BaseModel):
    device: Optional[str] = None


@app.post("/api/config/device")
async def set_device(body: DeviceUpdate):
    global _active_device, _recorder
    _active_device = body.device or None
    _recorder = None  # force recreate on next use
    return {"ok": True, "device": _active_device or "default mic"}


# ── Meetings ──────────────────────────────────────────────────────────────────

@app.get("/api/meetings")
async def list_meetings():
    return await storage.list_meetings()


@app.get("/api/meetings/{meeting_id}")
async def get_meeting(meeting_id: int):
    meeting = await storage.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting


@app.delete("/api/meetings/{meeting_id}")
async def delete_meeting(meeting_id: int):
    ok = await storage.delete_meeting(meeting_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return {"ok": True}


# ── Recording ─────────────────────────────────────────────────────────────────

@app.post("/api/record/start")
async def start_recording():
    recorder = get_recorder()
    if recorder.is_recording:
        raise HTTPException(status_code=400, detail="Already recording")
    recorder.start()
    return {"ok": True, "device": recorder.device or "default mic"}


class StopRequest(BaseModel):
    user_notes: Optional[str] = ""


@app.post("/api/record/stop")
async def stop_recording(body: StopRequest):
    recorder = get_recorder()
    if not recorder.is_recording:
        raise HTTPException(status_code=400, detail="Not recording")

    wav_path, duration = recorder.stop()
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    try:
        transcript = get_transcriber().transcribe(wav_path)
    except Exception as e:
        transcript = ""
        print(f"[muesli] Transcription error: {e}")

    try:
        notes, title = get_summarizer().summarize(
            transcript=transcript,
            user_notes=body.user_notes,
            duration_seconds=duration,
        )
    except Exception as e:
        notes = f"## Untitled Meeting\n\n*Could not generate notes: {e}*"
        title = "Untitled Meeting"

    meeting_id = await storage.save_meeting(
        title=title,
        date=date_str,
        duration=duration,
        transcript=transcript,
        notes=notes,
        user_notes=body.user_notes,
        audio_path=str(wav_path),
    )

    return {"id": meeting_id, "title": title, "duration": duration, "notes": notes}


@app.get("/api/record/status")
async def record_status():
    recorder = get_recorder()
    return {
        "recording": recorder.is_recording,
        "elapsed": recorder.elapsed() if recorder.is_recording else 0,
        "device": recorder.device or "default mic",
    }


@app.get("/api/devices")
async def list_devices():
    devices = AudioRecorder.list_devices()
    current = _active_device or os.getenv("AUDIO_DEVICE", "").strip() or None
    for d in devices:
        d["active"] = (d["name"] == current) if current else False
    return devices


@app.get("/api/health")
async def health():
    from app import storage as s
    db_ok = True
    try:
        await s.list_meetings()
    except Exception:
        db_ok = False
    from app.cache import get_redis
    redis_ok = await get_redis() is not None
    return {
        "status": "ok" if db_ok else "degraded",
        "db": "ok" if db_ok else "error",
        "cache": "ok" if redis_ok else "unavailable",
        "built_by": "Suryanand — suryanand.com",
    }


# ── Entry ─────────────────────────────────────────────────────────────────────

def run():
    port = int(os.getenv("PORT", 7474))
    print(f"\n  🥣 muesli  →  http://localhost:{port}\n")
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    run()
