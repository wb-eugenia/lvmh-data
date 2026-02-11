"""
Legacy Groq adapter (deprecated).

This project runtime now uses `Tier2Mistral` in `src/pipeline_async.py`.
The original Groq implementation was moved to:
`archive/legacy_groq/tier2_groq_legacy.py`
"""

from src.models import ExtractionResult


class Tier2Groq:
    """
    Deprecated class kept only to fail fast on accidental usage.
    """

    def __init__(self, *args, **kwargs):
        raise RuntimeError(
            "Tier2Groq is deprecated and not used by the active pipeline. "
            "Use Tier2Mistral (src/tier2_mistral.py). "
            "Legacy code is in archive/legacy_groq/tier2_groq_legacy.py."
        )

    async def extract(self, text: str, language: str = "FR") -> ExtractionResult:
        raise RuntimeError("Tier2Groq.extract is deprecated.")
