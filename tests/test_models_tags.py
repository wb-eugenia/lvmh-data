import os
import sys

sys.path.append(os.getcwd())

from src.models import (
    ExtractionResult,
    MetaAnalysis,
    NextBestAction,
    Pilier1Product,
    Pilier2Client,
    Pilier3Care,
    Pilier4Business,
)


def _base_extraction() -> ExtractionResult:
    return ExtractionResult(
        pilier_1_univers_produit=Pilier1Product(categories=["leather_goods", "leather_goods", ""]),
        pilier_2_profil_client=Pilier2Client(),
        pilier_3_hospitalite_care=Pilier3Care(),
        pilier_4_action_business=Pilier4Business(),
        meta_analysis=MetaAnalysis(),
    )


def test_tags_are_unique_and_non_empty():
    ext = _base_extraction()
    assert ext.tags == ["leather_goods"]


def test_tags_include_nba_action_type_when_present():
    ext = _base_extraction()
    ext.pilier_4_action_business.next_best_action = NextBestAction(
        action_type="follow_up",
        description="Relancer le client",
        priority="Medium",
    )
    assert ext.tags == ["leather_goods", "action:follow_up"]
