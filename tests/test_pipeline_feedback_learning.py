import os
import sys

import pytest

sys.path.append(os.getcwd())

from config.production import settings
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
    def __init__(self):
        self.feedback_calls = []

    def route_ml(self, text, language, metadata=None):
        return _DummyDecision()

    def record_feedback(
        self,
        text,
        predicted_tier,
        executed_tier,
        confidence_achieved,
        was_escalated=False,
        final_tier=None,
        final_confidence=None,
    ):
        self.feedback_calls.append(
            {
                "predicted_tier": predicted_tier,
                "executed_tier": executed_tier,
                "confidence_achieved": confidence_achieved,
                "was_escalated": was_escalated,
                "final_tier": final_tier,
                "final_confidence": final_confidence,
            }
        )


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


@pytest.mark.asyncio
async def test_pipeline_records_router_feedback_automatically():
    pipeline = AsyncPipeline(use_cache=False, use_semantic_cache=False, use_cross_validation=False)
    router = _DummyRouter()
    pipeline.router = router
    pipeline.tier1 = _DummyTier1()
    pipeline.matcher.enabled = False

    result = await pipeline.process_note(
        {"ID": "T-FEEDBACK-001", "Transcription": "Client cherche un sac noir", "Language": "FR"}
    )

    assert result is not None
    assert len(router.feedback_calls) == 1
    call = router.feedback_calls[0]
    assert call["predicted_tier"] == 1
    assert call["final_tier"] == 1
    assert call["was_escalated"] is False


def test_pipeline_uses_configured_tier_concurrency():
    pipeline = AsyncPipeline(use_cache=False, use_semantic_cache=False, use_cross_validation=False)
    assert pipeline.tier2_semaphore._value == settings.max_concurrent_tier2_calls
    assert pipeline.openai_semaphore._value == settings.max_concurrent_tier3_calls
