from src.models import (
    Allergies,
    ExtractionResult,
    Lifestyle,
    MetaAnalysis,
    Pilier1Product,
    Pilier2Client,
    Pilier3Care,
    Pilier4Business,
    ProductPreferences,
    Profession,
    PurchaseContext,
)
from src.recommender import RecommenderEngine


def _base_extraction() -> ExtractionResult:
    return ExtractionResult(
        pilier_1_univers_produit=Pilier1Product(
            categories=["leather_goods"],
            usage=["professional_work"],
            preferences=ProductPreferences(colors=["black"], materials=["smooth_leather"]),
            matched_products=[{"name": "Neverfull MM", "match_score": 0.91}],
        ),
        pilier_2_profil_client=Pilier2Client(
            purchase_context=PurchaseContext(type="self_purchase", behavior="regular"),
            profession=Profession(sector=None, status=None),
            lifestyle=Lifestyle(),
        ),
        pilier_3_hospitalite_care=Pilier3Care(
            diet=[],
            allergies=Allergies(food=[], contact=[]),
            values=[],
            occasion=None,
        ),
        pilier_4_action_business=Pilier4Business(
            budget_potential="high",
            budget_specific=5000,
            urgency=None,
        ),
        meta_analysis=MetaAnalysis(),
        confidence=0.9,
        processing_tier="tier2",
    )


def test_quality_not_penalized_when_no_occasion_or_care_signal():
    engine = RecommenderEngine()
    extraction = _base_extraction()

    res = engine.generate_recommendation(
        extraction,
        source_text="Client cherche un sac pour le travail, prefere le noir, budget 5000 euros.",
    )

    assert res.meta_analysis.quality_score >= 70


def test_quality_drops_when_occasion_is_expected_but_missing():
    engine = RecommenderEngine()
    extraction_missing = _base_extraction()
    extraction_with_occasion = _base_extraction()
    extraction_with_occasion.pilier_3_hospitalite_care.occasion = "birthday_gift"

    missing = engine.generate_recommendation(
        extraction_missing,
        source_text="Cadeau pour un anniversaire avec budget flexible.",
    ).meta_analysis.quality_score
    present = engine.generate_recommendation(
        extraction_with_occasion,
        source_text="Cadeau pour un anniversaire avec budget flexible.",
    ).meta_analysis.quality_score

    assert present > missing
    assert present - missing >= 5


def test_short_sparse_note_has_low_quality():
    engine = RecommenderEngine()
    extraction = _base_extraction()
    extraction.pilier_2_profil_client.purchase_context.type = None
    extraction.pilier_2_profil_client.purchase_context.behavior = None
    extraction.pilier_1_univers_produit.usage = []
    extraction.pilier_1_univers_produit.preferences = ProductPreferences()
    extraction.pilier_1_univers_produit.matched_products = []
    extraction.pilier_4_action_business.budget_potential = None
    extraction.pilier_4_action_business.budget_specific = None

    res = engine.generate_recommendation(extraction, source_text="sac noir")

    assert res.meta_analysis.quality_score < 50
