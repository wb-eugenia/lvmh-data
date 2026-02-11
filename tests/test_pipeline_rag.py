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
    confidence = 0.95
    priority = "low"
    reasons = ["test"]
    score = _DummyScore()


class _DummyRouter:
    def route_ml(self, text, language, metadata=None):
        return _DummyDecision()


class _DummyTier1:
    def extract(self, text, language):
        return ExtractionResult(
            pilier_1_univers_produit=Pilier1Product(categories=["leather_goods"]),
            pilier_2_profil_client=Pilier2Client(),
            pilier_3_hospitalite_care=Pilier3Care(),
            pilier_4_action_business=Pilier4Business(),
            meta_analysis=MetaAnalysis(),
            confidence=0.9,
        )


class _DummyMatcher:
    enabled = True

    def match(self, query, top_k=3, threshold=0.35):
        return [
            {
                "sku": "SKU-001",
                "name": "Capucines MM",
                "price": 6000.0,
                "url": "",
                "match_score": 0.91,
            }
        ]


@pytest.mark.asyncio
async def test_pipeline_attaches_rag_matches_before_output():
    pipeline = AsyncPipeline(use_cache=False, use_semantic_cache=False, use_cross_validation=False)
    pipeline.router = _DummyRouter()
    pipeline.tier1 = _DummyTier1()
    pipeline.matcher = _DummyMatcher()

    result = await pipeline.process_note(
        {"ID": "T-RAG-001", "Transcription": "Je cherche un Capucines noir", "Language": "FR"}
    )

    assert result is not None
    matches = result.extraction.pilier_1_univers_produit.matched_products
    assert len(matches) == 1
    assert matches[0]["name"] == "Capucines MM"
    assert pipeline.get_summary()["rag"]["hits"] >= 1
