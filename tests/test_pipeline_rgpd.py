import os
import sys

import pytest

sys.path.append(os.getcwd())

from src.models import (
    ExtractionResult,
    MetaAnalysis,
    Pilier1Product,
    Pilier2Client,
    Pilier3Care,
    Pilier4Business,
)
from src.pipeline_async import AsyncPipeline


class _DummyScore:
    total = 10


class _DummyDecision:
    tier = 1
    confidence = 0.9
    priority = "low"
    reasons = ["test"]
    score = _DummyScore()


class _DummyRouter:
    def route_ml(self, text, language, metadata=None):
        return _DummyDecision()

    def record_feedback(self, *args, **kwargs):
        return None


class _DummyTier1:
    def extract(self, text, language):
        return ExtractionResult(
            pilier_1_univers_produit=Pilier1Product(categories=["leather_goods"]),
            pilier_2_profil_client=Pilier2Client(),
            pilier_3_hospitalite_care=Pilier3Care(),
            pilier_4_action_business=Pilier4Business(),
            meta_analysis=MetaAnalysis(),
            confidence=0.88,
        )


class _DummyRGPDFilter:
    def process_note(self, note):
        return {
            "anonymized_text": "Client [RGPD_HEALTH_MENTAL_REDACTED] cherche un sac noir.",
            "rgpd_result": {
                "contains_sensitive": True,
                "categories_detected": ["health_mental"],
                "safe_to_store": False,
                "reasoning": "Sensitive health signal found.",
                "sensitive_spans": [
                    {"text": "burnout", "category": "health_mental", "severity": "high"}
                ],
            },
        }


@pytest.mark.asyncio
async def test_pipeline_uses_llm_rgpd_when_available():
    pipeline = AsyncPipeline(use_cache=False, use_semantic_cache=False, use_cross_validation=False)
    pipeline.router = _DummyRouter()
    pipeline.tier1 = _DummyTier1()
    pipeline.matcher.enabled = False
    pipeline.rgpd_enabled = True
    pipeline.rgpd_filter = _DummyRGPDFilter()

    result = await pipeline.process_note(
        {"ID": "T-RGPD-001", "Transcription": "Client en burnout, cherche un sac.", "Language": "FR"}
    )

    assert result is not None
    assert result.processed_text == "Client [RGPD_HEALTH_MENTAL_REDACTED] cherche un sac noir."
    assert result.rgpd.contains_sensitive is True
    assert "health_mental" in result.rgpd.categories_detected
    assert result.rgpd.safe_to_store is False
    assert result.rgpd.severity == "high"


@pytest.mark.asyncio
async def test_pipeline_rgpd_fallback_detects_pii_markers():
    pipeline = AsyncPipeline(use_cache=False, use_semantic_cache=False, use_cross_validation=False)
    pipeline.router = _DummyRouter()
    pipeline.tier1 = _DummyTier1()
    pipeline.matcher.enabled = False
    pipeline.rgpd_enabled = False
    pipeline.rgpd_filter = None

    result = await pipeline.process_note(
        {"ID": "T-RGPD-002", "Transcription": "Mon téléphone est 06 12 34 56 78.", "Language": "FR"}
    )

    assert result is not None
    assert "[PHONE]" in result.processed_text
    assert result.rgpd.contains_sensitive is True
    assert "[PHONE]" in result.rgpd.categories_detected
