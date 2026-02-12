import os
from fastapi.testclient import TestClient

os.environ.setdefault("SEMANTIC_CACHE_DISABLED", "1")

from api.main import app

client = TestClient(app)


def _auth_headers(email: str, password: str = "lvmh") -> dict[str, str]:
    login_resp = client.post(
        "/api/auth/login",
        data={"username": email, "password": password},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_dashboard_segments_manager_ok():
    resp = client.get(
        "/api/dashboard/segments?window=7d&n_clusters=5&limit=300",
        headers=_auth_headers("manager@lvmh.com"),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "total_notes" in data
    assert "segments" in data
    assert "filters" in data
    assert "window" in data
    assert data["filters"]["window"] == "7d"
    assert isinstance(data["segments"], list)


def test_dashboard_segments_forbidden_for_advisor():
    resp = client.get(
        "/api/dashboard/segments?window=7d",
        headers=_auth_headers("advisor@lvmh.com"),
    )
    assert resp.status_code == 403

