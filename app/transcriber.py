import threading
from pathlib import Path


class Transcriber:
    def __init__(self, model_size: str = "base"):
        self.model_size = model_size
        self._model = None
        self._lock = threading.Lock()

    def _load_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            print(f"[muesli] Loading Whisper model '{self.model_size}' (first run downloads it)...")
            self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
            print("[muesli] Whisper model ready.")

    def transcribe(self, audio_path: Path) -> str:
        with self._lock:
            self._load_model()
            segments, _ = self._model.transcribe(
                str(audio_path),
                beam_size=5,
                vad_filter=True,  # skip silent gaps
                vad_parameters={"min_silence_duration_ms": 500},
            )
            return " ".join(seg.text.strip() for seg in segments).strip()

    def preload(self):
        """Call at startup to download/load model in background."""
        thread = threading.Thread(target=self._load_model, daemon=True)
        thread.start()
