import os
from fastapi.testclient import TestClient

# Avoid heavy semantic cache init in CI/local tests
os.environ.setdefault("SEMANTIC_CACHE_DISABLED", "1")

from api.main import app

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
