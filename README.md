# 🥣 Muesli

**Open-source meeting notes. No bots. No cloud. Fully local.**

> Inspired by Granola — but self-hosted, private, and free.

Muesli sits on your computer, captures audio directly (no bot joins your call), transcribes it locally with Whisper, and generates clean structured notes with Claude. Everything stays on your machine.

![Muesli UI](https://placeholder.com/screenshot)

---

## How it works

1. Click **Start Meeting** — Muesli starts recording your mic (or system audio)
2. Jot rough notes in the sidebar as you listen
3. Click **Stop & Summarize** — Whisper transcribes, Claude structures the notes
4. Clean markdown notes appear instantly, stored locally in SQLite

No meeting bot. No shared link. No audio leaving your machine.

---

## Setup

**Requirements:** Python 3.10+, an [Anthropic API key](https://console.anthropic.com)

```bash
git clone https://github.com/yourusername/muesli
cd muesli
bash setup.sh
```

Then add your API key to `.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Start the app:

```bash
.venv/bin/python -m app.main
# Open http://localhost:7474
```

---

## Capture system audio (Zoom, Meet, Teams)

By default Muesli records your microphone. To capture all audio on screen:

```bash
brew install blackhole-2ch
```

Then in **System Settings → Sound → Output**, create a Multi-Output Device combining your speakers + BlackHole 2ch. Set `AUDIO_DEVICE=BlackHole 2ch` in `.env`.

List available devices:
```bash
.venv/bin/python -m app.devices
```

---

## LLM Providers

Set `PROVIDER` in `.env` to switch between backends:

### Anthropic (default)
```env
PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-6
```

### Ollama (fully local, no API key)
```bash
ollama pull llama3.2   # or mistral, qwen2.5, etc.
ollama serve
```
```env
PROVIDER=ollama
OLLAMA_MODEL=llama3.2
OLLAMA_BASE_URL=http://localhost:11434  # default
```

### OpenRouter (50+ models, one API key)
```env
PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet  # or any openrouter model
```
Browse models at [openrouter.ai/models](https://openrouter.ai/models).

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `PROVIDER` | `anthropic` | LLM backend: `anthropic` / `ollama` / `openrouter` |
| `ANTHROPIC_API_KEY` | — | Required for anthropic provider |
| `OPENROUTER_API_KEY` | — | Required for openrouter provider |
| `OLLAMA_MODEL` | `llama3.2` | Model name for ollama |
| `OPENROUTER_MODEL` | `anthropic/claude-3.5-sonnet` | Model for openrouter |
| `AUDIO_DEVICE` | system default mic | Device name for audio capture |
| `WHISPER_MODEL` | `base` | `tiny` / `base` / `small` / `medium` / `large-v3` |
| `PORT` | `7474` | Web UI port |

---

## Privacy

- Audio is transcribed **locally** on your CPU using [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- With `PROVIDER=ollama`, **nothing ever leaves your machine** — fully air-gapped
- With `anthropic` or `openrouter`, only the transcript text is sent to the API
- Recordings and notes are stored in `~/.muesli/meetings.db`
- No telemetry, no accounts, no cloud sync

---

## Stack

- **Audio** — `sounddevice` (Python), BlackHole for system audio
- **Transcription** — `faster-whisper` (runs locally, no API)
- **Summarization** — Claude Sonnet via Anthropic API
- **Backend** — FastAPI + aiosqlite
- **Frontend** — Vanilla JS, no build step

---

## Roadmap

- [ ] Export notes to Notion / Markdown file
- [ ] Speaker diarization (who said what)
- [ ] ScreenCaptureKit support (macOS native, no BlackHole needed)
- [ ] Windows support
- [ ] Local LLM option (Ollama) — no API key needed

---

## Contributing

PRs welcome. This is intentionally minimal — the goal is a tool that works, not a platform.

```bash
git clone https://github.com/yourusername/muesli
cd muesli && bash setup.sh
.venv/bin/python -m app.main
```

---

MIT License
