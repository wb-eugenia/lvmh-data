import os
import sys

sys.path.append(os.getcwd())

from src.smart_router import SmartRouterV3


class _DummyScaler:
    def transform(self, features):
        return features


class _DummyModel:
    def predict(self, features):
        return [2]

    def predict_proba(self, features):
        return [[0.0, 1.0, 0.0]]


class _RouterNoDiskLoad(SmartRouterV3):
    def _load_model(self):
        # Prevent loading persisted model/scaler so the test is deterministic.
        return


def test_ml_router_does_not_downgrade_critical_heuristic_tier():
    router = _RouterNoDiskLoad()
    router._init_ml()
    router.ml_model = _DummyModel()
    router.ml_scaler = _DummyScaler()
    router.ml_confidence_threshold = 0.1

    text = "Client VIC, plainte sévère, urgence aujourd'hui, très insatisfait"
    heuristic = router.route(text, "FR", {})
    decision = router.route_ml(text, "FR", {})

    assert heuristic.tier == 3
    assert decision.tier == 3
    assert any("Safety floor applied" in reason for reason in decision.reasons)
