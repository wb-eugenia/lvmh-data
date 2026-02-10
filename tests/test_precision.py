import os
import sys

import pytest

sys.path.append(os.getcwd())

from src.tier1_rules import Tier1RulesEngine
from src.tier2_mistral import Tier2Mistral


def _integration_enabled() -> bool:
    return os.getenv("RUN_INTEGRATION_TESTS") == "1"


def test_tier1_basic_tags_and_budget():
    engine = Tier1RulesEngine()
    text = "Je cherche un sac et une ceinture. Budget 5000 euros."

    res = engine.extract(text)

    assert res is not None
    assert "leather_goods" in res.tags
    assert "belts" in res.tags
    assert res.pilier_4_action_business.budget_specific == 5000


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tier2_mistral_smoke():
    if not _integration_enabled():
        pytest.skip("Integration tests disabled. Set RUN_INTEGRATION_TESTS=1.")
    if not os.getenv("MISTRAL_API_KEY"):
        pytest.skip("Missing MISTRAL_API_KEY.")

    t2 = Tier2Mistral(model_tier="fast")
    text = "Client VIC cherche un cadeau. Budget flexible."
    res = await t2.extract(text)

    assert res is not None
    assert res.processing_tier == "tier2"
