import os
import sys

sys.path.append(os.getcwd())

from src.models import (
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


def test_recommender_sets_synthetic_predictions():
    extraction = ExtractionResult(
        pilier_1_univers_produit=Pilier1Product(
            categories=["leather_goods"],
            preferences=ProductPreferences(colors=["black"], materials=["leather"]),
        ),
        pilier_2_profil_client=Pilier2Client(
            purchase_context=PurchaseContext(type="gift", behavior="vic"),
        ),
        pilier_3_hospitalite_care=Pilier3Care(occasion="birthday"),
        pilier_4_action_business=Pilier4Business(urgency="high", budget_potential="20K-50K"),
        meta_analysis=MetaAnalysis(),
    )

    engine = RecommenderEngine()
    result = engine.generate_recommendation(extraction, source_text="Client VIC, budget 25k, relance urgente.")
    p4 = result.pilier_4_action_business

    assert p4.prediction_source == "synthetic_supervised_v1"
    assert p4.churn_risk is not None
    assert p4.churn_level in {"low", "medium", "high"}
    assert p4.clv_estimate is not None
    assert p4.clv_tier in {"silver", "gold", "platinum"}

