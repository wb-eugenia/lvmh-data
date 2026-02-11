import os
import sys

sys.path.append(os.getcwd())

from src.models import (
    Allergies,
    ExtractionResult,
    MetaAnalysis,
    Pilier1Product,
    Pilier2Client,
    Pilier3Care,
    Pilier4Business,
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
