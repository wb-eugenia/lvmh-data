from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_feedback_flow():
    payload = {
        "note_id": "TEST_NOTE_001",
        "original_text": "Mme Dupont veut un sac noir en cuir.",
        "predicted_tags": ["sac", "rouge"],
        "corrected_tags": ["sac", "noir"],
        "corrections": {"couleur": "noir"},
        "rating": 4,
        "comment": "Couleur incorrecte",
        "processing_tier": 2
    }

    resp = client.post("/api/feedback", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "success"

    stats = client.get("/api/feedback/stats")
    assert stats.status_code == 200
    stats_data = stats.json()
    assert "total_feedback" in stats_data

    recent = client.get("/api/feedback/recent")
    assert recent.status_code == 200
    recent_data = recent.json()
    assert "feedback" in recent_data
