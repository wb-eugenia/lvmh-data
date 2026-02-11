"""
Legacy Groq Whisper adapter (deprecated).

Active audio transcription endpoint is:
- `POST /api/transcribe` in `api/routers/transcribe.py` (OpenAI Whisper-1).

Legacy code moved to:
- `archive/legacy_groq/tier2_whisper_legacy.py`
"""


def transcribe_audio(audio_file) -> str:
    raise RuntimeError(
        "tier2_whisper is deprecated. Use /api/transcribe (OpenAI Whisper-1). "
        "Legacy code is in archive/legacy_groq/tier2_whisper_legacy.py."
    )
