import os
import sys

sys.path.append(os.getcwd())

from src.models import (
    Allergies,
    ExtractionResult,
    Lifestyle,
    MetaAnalysis,
    Pilier1Product,
    Pilier2Client,
    Pilier3Care,
    Pilier4Business,
    Profession,
    ProductPreferences,
    PurchaseContext,
)
from src.recommender import RecommenderEngine


def test_recommender_sets_next_best_action_and_quality():
    extraction = ExtractionResult(
        pilier_1_univers_produit=Pilier1Product(
            categories=["leather_goods"],
            preferences=ProductPreferences(colors=["black"]),
        ),
        pilier_2_profil_client=Pilier2Client(
            purchase_context=PurchaseContext(type="gift", behavior="vip"),
        ),
        pilier_3_hospitalite_care=Pilier3Care(
            occasion="birthday",
            allergies=Allergies(contact=["nickel"]),
        ),
        pilier_4_action_business=Pilier4Business(urgency="this_week", budget_potential="high"),
        meta_analysis=MetaAnalysis(),
    )

    engine = RecommenderEngine()
    enriched = engine.generate_recommendation(extraction)

    assert enriched.pilier_4_action_business.next_best_action is not None
    assert enriched.meta_analysis.quality_score > 0


def test_recommender_does_not_infer_diplomacy_from_generic_tokens():
    extraction = ExtractionResult(
        pilier_1_univers_produit=Pilier1Product(categories=["leather_goods"]),
        pilier_2_profil_client=Pilier2Client(
            purchase_context=PurchaseContext(type=None, behavior="vip"),
            profession=Profession(sector=None, status=None),
            lifestyle=Lifestyle(),
        ),
        pilier_3_hospitalite_care=Pilier3Care(),
        pilier_4_action_business=Pilier4Business(),
        meta_analysis=MetaAnalysis(),
    )

    engine = RecommenderEngine()
    result = engine.generate_recommendation(
        extraction,
        source_text="Cliente VIP Hong Kong cherche un sac Capucines noir.",
    )

    assert result.pilier_2_profil_client.profession.sector is None


def test_recommender_keeps_diplomacy_when_explicit_signal_exists():
    extraction = ExtractionResult(
        pilier_1_univers_produit=Pilier1Product(categories=["leather_goods"]),
        pilier_2_profil_client=Pilier2Client(
            purchase_context=PurchaseContext(type=None, behavior="vip"),
            profession=Profession(sector=None, status=None),
            lifestyle=Lifestyle(),
        ),
        pilier_3_hospitalite_care=Pilier3Care(),
        pilier_4_action_business=Pilier4Business(),
        meta_analysis=MetaAnalysis(),
    )

    engine = RecommenderEngine()
    result = engine.generate_recommendation(
        extraction,
        source_text="Client diplomate ONU cherche un cadeau.",
    )

    assert result.pilier_2_profil_client.profession.sector == "diplomacy"
