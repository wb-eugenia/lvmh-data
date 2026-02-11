import os
from fastapi.testclient import TestClient

# Avoid heavy semantic cache init in CI/local tests
os.environ.setdefault("SEMANTIC_CACHE_DISABLED", "1")

from api.main import app
from api.routers import dashboard as dashboard_router

client = TestClient(app)


def test_dashboard_metrics():
    resp = client.get("/api/dashboard/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "pipeline_stats" in data
    assert "cache_stats" in data
    assert "cost_stats" in data
    assert "quality_metrics" in data
    assert "alerts" in data


def test_dashboard_summary():
    resp = client.get("/api/dashboard/metrics/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "health_score" in data
    assert "summary" in data


def test_components_status():
    resp = client.get("/api/dashboard/components/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "ml_router" in data
    assert "semantic_cache" in data
    assert "cross_validator" in data


def test_summary_does_not_penalize_missing_feedback(monkeypatch):
    monkeypatch.setattr(
        dashboard_router,
        "_get_pipeline_stats",
        lambda db: {
            "total_processed": 10,
            "success_rate": 100.0,
            "tier_distribution": {"tier1": 5, "tier2": 4, "tier3": 1},
            "avg_processing_time_ms": 1200.0,
            "avg_confidence": 0.92,
            "cache_hit_rate": 0.0,
            "active_processes": 0,
        },
    )
    monkeypatch.setattr(
        dashboard_router,
        "_get_quality_metrics",
        lambda db: {
            "accuracy_rate": None,
            "accuracy_available": False,
            "avg_rating": None,
            "total_feedback": 0,
        },
    )
    monkeypatch.setattr(
        dashboard_router,
        "_get_cost_stats",
        lambda db: {
            "total_cost_eur": 0.0,
            "cost_per_note": 0.0,
            "tier_costs": {"tier1": 0.0, "tier2": 0.0, "tier3": 0.0},
            "currency": "EUR",
            "estimated_monthly": 0.0,
        },
    )

    resp = client.get("/api/dashboard/metrics/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["summary"]["accuracy"] is None
    assert data["summary"]["accuracy_available"] is False
    assert data["health_status"] == "healthy"
