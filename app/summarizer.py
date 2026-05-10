"""
LLM provider abstraction.

Set PROVIDER in .env:
  anthropic   → ANTHROPIC_API_KEY, ANTHROPIC_MODEL
  ollama      → OLLAMA_BASE_URL (default http://localhost:11434), OLLAMA_MODEL
  openrouter  → OPENROUTER_API_KEY, OPENROUTER_MODEL
"""
from typing import Optional

SYSTEM_PROMPT = """You are an expert meeting note-taker. Given a meeting transcript and optional rough notes, produce clean structured notes in markdown.

Use this format exactly:

## [Descriptive meeting title inferred from content]

### Key Points
- ...

### Decisions Made
- ...

### Action Items
- [ ] [owner if mentioned] — [specific task]

### Open Questions
- ...

Rules:
- Be concise — every bullet must earn its place
- Action items must be specific and actionable; omit this section if none
- Decisions Made: omit if none
- Open Questions: omit if none
- Integrate the participant's rough notes naturally — don't repeat them verbatim
- Infer a sharp, descriptive title from the content (not "Meeting Notes")
- Output only the markdown, no preamble"""


class Summarizer:
    def __init__(self, provider: str, **kwargs):
        self.provider = provider.lower()
        self._client = None
        self._model: str = ""
        self._cfg = kwargs
        self._build_client()

    def _build_client(self):
        if self.provider == "anthropic":
            import anthropic
            api_key = self._cfg.get("api_key", "")
            if not api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY is missing. Add it to your .env file.\n"
                    "Get a key at https://console.anthropic.com"
                )
            self._client = anthropic.Anthropic(api_key=api_key)
            self._model = self._cfg.get("model", "claude-sonnet-4-6")

        elif self.provider == "ollama":
            from openai import OpenAI
            base_url = self._cfg.get("base_url", "http://localhost:11434").rstrip("/")
            self._client = OpenAI(
                base_url=f"{base_url}/v1",
                api_key="ollama",          # Ollama ignores this but OpenAI SDK requires it
                timeout=120.0,
            )
            self._model = self._cfg.get("model", "llama3.2")

        elif self.provider == "openrouter":
            from openai import OpenAI
            api_key = self._cfg.get("api_key", "")
            if not api_key:
                raise ValueError(
                    "OPENROUTER_API_KEY is missing. Add it to your .env file.\n"
                    "Get a key at https://openrouter.ai/keys"
                )
            self._client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
                default_headers={
                    "HTTP-Referer": "https://github.com/suryanandx/muesli",
                    "X-Title": "Muesli",
                },
                timeout=120.0,
            )
            self._model = self._cfg.get("model", "anthropic/claude-3.5-sonnet")

        else:
            raise ValueError(
                f"Unknown PROVIDER='{self.provider}'. "
                "Valid options: anthropic, ollama, openrouter"
            )

    def summarize(
        self,
        transcript: str,
        user_notes: Optional[str] = None,
        duration_seconds: float = 0,
    ) -> tuple[str, str]:
        """Returns (notes_markdown, title)."""
        if not transcript.strip():
            notes = "## Untitled Meeting\n\n*No speech detected in the recording.*"
            return notes, "Untitled Meeting"

        content = f"Transcript:\n{transcript}"
        if user_notes and user_notes.strip():
            content += f"\n\nMy rough notes:\n{user_notes}"

        try:
            if self.provider == "anthropic":
                notes = self._call_anthropic(content)
            else:
                notes = self._call_openai_compat(content)
        except Exception as e:
            err = _friendly_error(self.provider, e)
            raise RuntimeError(err) from e

        return notes.strip(), _extract_title(notes)

    def _call_anthropic(self, content: str) -> str:
        message = self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
        )
        return message.content[0].text

    def _call_openai_compat(self, content: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=2048,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
        )
        return response.choices[0].message.content


def _extract_title(notes: str) -> str:
    for line in notes.splitlines():
        s = line.strip()
        if s.startswith("## "):
            return s[3:].strip()
    return "Untitled Meeting"


def _friendly_error(provider: str, exc: Exception) -> str:
    msg = str(exc)
    if provider == "ollama":
        if "connection" in msg.lower() or "refused" in msg.lower():
            return (
                "Cannot reach Ollama. Make sure it's running:\n"
                "  ollama serve\n"
                f"Then confirm your model is pulled:\n"
                f"  ollama pull {os.getenv('OLLAMA_MODEL', 'llama3.2')}"
            )
    if provider == "openrouter":
        if "401" in msg or "auth" in msg.lower():
            return "OpenRouter authentication failed. Check your OPENROUTER_API_KEY in .env."
        if "404" in msg:
            return (
                f"OpenRouter model not found: {os.getenv('OPENROUTER_MODEL')}. "
                "Check available models at https://openrouter.ai/models"
            )
    if provider == "anthropic":
        if "401" in msg or "auth" in msg.lower():
            return "Anthropic authentication failed. Check your ANTHROPIC_API_KEY in .env."
    return msg


def from_env() -> "Summarizer":
    import os
    provider = os.getenv("PROVIDER", "anthropic").lower()

    if provider == "anthropic":
        return Summarizer(
            provider="anthropic",
            api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        )
    elif provider == "ollama":
        return Summarizer(
            provider="ollama",
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            model=os.getenv("OLLAMA_MODEL", "llama3.2"),
        )
    elif provider == "openrouter":
        return Summarizer(
            provider="openrouter",
            api_key=os.getenv("OPENROUTER_API_KEY", ""),
            model=os.getenv("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet"),
        )
    else:
        raise ValueError(
            f"Unknown PROVIDER='{provider}'. Valid options: anthropic, ollama, openrouter"
        )


import os  # noqa: E402 — needed by _friendly_error
