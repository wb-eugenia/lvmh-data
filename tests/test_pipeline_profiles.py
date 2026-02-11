from collections import defaultdict, deque

from src.pipeline_async import AsyncPipeline
from src.tier1_rules import Tier1RulesEngine
from src.models import (
    ExtractionResult,
    Pilier1Product,
    Pilier2Client,
    Pilier3Care,
    Pilier4Business,
    MetaAnalysis,
)


def _make_empty_extraction() -> ExtractionResult:
    return ExtractionResult(
        pilier_1_univers_produit=Pilier1Product(),
        pilier_2_profil_client=Pilier2Client(),
        pilier_3_hospitalite_care=Pilier3Care(),
        pilier_4_action_business=Pilier4Business(),
        meta_analysis=MetaAnalysis(),
    )


def _make_min_pipeline() -> AsyncPipeline:
    pipeline = AsyncPipeline.__new__(AsyncPipeline)
    pipeline.tier1 = Tier1RulesEngine()
    pipeline.profile_runtime_stats = defaultdict(
        lambda: {
            "count": 0,
            "latencies_ms": deque(maxlen=1000),
            "fallback_count": 0,
            "notes_without_tags": 0,
            "stage_totals_ms": defaultdict(float),
        }
    )
    return pipeline


def test_deterministic_minimum_tag_prefers_product_signal():
    pipeline = _make_min_pipeline()
    assert pipeline._deterministic_minimum_tag("Client cherche une montre de luxe") == "watches"
    assert pipeline._deterministic_minimum_tag("Besoin d'un parfum cadeau") == "fragrance"


def test_quality_fallback_forces_non_empty_tags():
    pipeline = _make_min_pipeline()
    extraction = _make_empty_extraction()

    enriched, fallbacks = pipeline._apply_quality_fallback(
        extraction,
        text="Client demande un sac noir pour voyage",
        language="FR",
        require_non_empty_tags=True,
    )

    assert enriched is not None
    assert len(enriched.tags) > 0
    assert len(fallbacks) > 0


def test_profile_metrics_include_stage_averages():
    pipeline = _make_min_pipeline()
    pipeline._record_profile_runtime(
        "single_note",
        processing_time_ms=1200.0,
        stage_timings_ms={"routing": 100.0, "rag": 200.0},
        tags_count=4,
        fallback_used=True,
    )
    pipeline._record_profile_runtime(
        "single_note",
        processing_time_ms=1400.0,
        stage_timings_ms={"routing": 120.0, "rag": 220.0},
        tags_count=0,
        fallback_used=False,
    )

    metrics = pipeline.get_profile_metrics()["single_note"]
    assert metrics["count"] == 2
    assert metrics["notes_without_tags"] == 1
    assert metrics["fallback_rate_pct"] == 50.0
    assert metrics["stage_avg_ms"]["routing"] == 110.0
