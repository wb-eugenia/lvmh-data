from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


def test_analyze_requires_authentication():
    payload = {
        "text": "Je cherche un sac noir avec un budget de 5000 euros.",
        "language": "FR",
    }
    response = client.post("/api/analyze", json=payload)
    assert response.status_code == 401


def test_analyze_rejects_invalid_token():
    payload = {
        "text": "Je cherche un sac noir avec un budget de 5000 euros.",
        "language": "FR",
    }
    response = client.post(
        "/api/analyze",
        json=payload,
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert response.status_code == 401


def test_history_requires_authentication():
    response = client.get("/api/history")
    assert response.status_code == 401
