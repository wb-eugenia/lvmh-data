import os
import json
import time
from fastapi.testclient import TestClient

# Avoid heavy semantic cache init in CI/local tests
os.environ.setdefault("SEMANTIC_CACHE_DISABLED", "1")

from api.main import app
from api.routers import dashboard as dashboard_router
from api.database import SessionLocal
from api.models_sql import Note, User, Client

client = TestClient(app)


def _auth_headers(email: str, password: str = "lvmh") -> dict[str, str]:
    login_resp = client.post(
        "/api/auth/login",
        data={"username": email, "password": password},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _get_or_create_note_id() -> int:
    db = SessionLocal()
    try:
        existing = db.query(Note).order_by(Note.id.desc()).first()
        if existing:
            return existing.id

        suffix = str(int(time.time() * 1000))
        user = User(
            email=f"dashboard-test-{suffix}@lvmh.com",
            hashed_password="test",
            full_name="Dashboard Test",
            role="advisor",
            store="QA Store",
        )
        client_row = Client(
            name=f"Client Test {suffix}",
            vic_status="Standard",
        )
        db.add(user)
        db.add(client_row)
        db.commit()
        db.refresh(user)
        db.refresh(client_row)

        analysis = {
            "routing": {"tier": 2, "confidence": 0.91, "reasons": ["complexity"]},
            "rgpd": {"contains_sensitive": False, "categories_detected": []},
            "extraction": {
                "pilier_1_univers_produit": {
                    "categories": ["sacs"],
                    "styles": ["classique"],
                    "matched_products": [
                        {"name": "Capucines Test", "url": "https://example.com/capucines"}
                    ],
                },
                "pilier_2_profil_client": {},
                "pilier_3_hospitalite_care": {},
                "pilier_4_action_business": {
                    "next_best_action": {
                        "title": "Follow-up call",
                        "description": "Call the client within 48h",
                        "channel": "phone",
                    }
                },
                "meta_analysis": {
                    "quality_score": 0.88,
                    "advisor_feedback": "Good note",
                    "missing_info": [],
                    "risk_flags": [],
                },
            },
        }

        note = Note(
            advisor_id=user.id,
            client_id=client_row.id,
            transcription="Cliente interessee par un sac Capucines noir.",
            analysis_json=json.dumps(analysis),
            points_awarded=10,
        )
        db.add(note)
        db.commit()
        db.refresh(note)
        return note.id
    finally:
        db.close()


def test_dashboard_metrics():
    resp = client.get("/api/dashboard/metrics", headers=_auth_headers("manager@lvmh.com"))
    assert resp.status_code == 200
    data = resp.json()
    assert "pipeline_stats" in data
    assert "cache_stats" in data
    assert "cost_stats" in data
    assert "quality_metrics" in data
    assert "alerts" in data


def test_dashboard_summary():
    resp = client.get("/api/dashboard/metrics/summary", headers=_auth_headers("manager@lvmh.com"))
    assert resp.status_code == 200
    data = resp.json()
    assert "health_score" in data
    assert "summary" in data


def test_components_status():
    resp = client.get("/api/dashboard/components/status", headers=_auth_headers("admin@lvmh.com"))
    assert resp.status_code == 200
    data = resp.json()
    assert "ml_router" in data
    assert "semantic_cache" in data
    assert "cross_validator" in data


def test_components_status_forbidden_for_manager():
    resp = client.get("/api/dashboard/components/status", headers=_auth_headers("manager@lvmh.com"))
    assert resp.status_code == 403


def test_export_metrics_json_admin():
    resp = client.get(
        "/api/dashboard/metrics/export?format=json&days=7",
        headers=_auth_headers("admin@lvmh.com"),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "generated_at" in data
    assert "pipeline_stats" in data
    assert data["window"]["days"] == "7"


def test_export_metrics_csv_forbidden_for_manager():
    resp = client.get(
        "/api/dashboard/metrics/export?format=csv&days=7",
        headers=_auth_headers("manager@lvmh.com"),
    )
    assert resp.status_code == 403


def test_metrics_timeseries_manager():
    resp = client.get(
        "/api/dashboard/metrics/timeseries?days=7",
        headers=_auth_headers("manager@lvmh.com"),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "series" in data
    assert "totals" in data
    assert data["window"]["days"] == "7"
    assert isinstance(data["series"], list)
    if data["series"]:
        first = data["series"][0]
        assert "date" in first
        assert "cost_eur" in first
        assert "avg_processing_time_ms" in first
        assert "alerts_count" in first


def test_metrics_timeseries_forbidden_for_advisor():
    resp = client.get(
        "/api/dashboard/metrics/timeseries?days=7",
        headers=_auth_headers("advisor@lvmh.com"),
    )
    assert resp.status_code == 403


def test_metrics_day_details_manager():
    resp = client.get(
        "/api/dashboard/metrics/day-details?date=2026-01-01&limit=10",
        headers=_auth_headers("manager@lvmh.com"),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["date"] == "2026-01-01"
    assert "summary" in data
    assert "notes" in data
    assert "total_notes" in data["summary"]


def test_metrics_day_details_forbidden_for_advisor():
    resp = client.get(
        "/api/dashboard/metrics/day-details?date=2026-01-01",
        headers=_auth_headers("advisor@lvmh.com"),
    )
    assert resp.status_code == 403


def test_metrics_day_details_invalid_date():
    resp = client.get(
        "/api/dashboard/metrics/day-details?date=2026-13-40",
        headers=_auth_headers("manager@lvmh.com"),
    )
    assert resp.status_code == 400


def test_metrics_note_details_manager():
    note_id = _get_or_create_note_id()
    resp = client.get(
        f"/api/dashboard/metrics/note-details/{note_id}",
        headers=_auth_headers("manager@lvmh.com"),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["note"]["id"] == note_id
    assert "tags" in data
    assert "next_best_action" in data
    assert "matched_products" in data
    assert "audio" in data


def test_metrics_note_details_forbidden_for_advisor():
    note_id = _get_or_create_note_id()
    resp = client.get(
        f"/api/dashboard/metrics/note-details/{note_id}",
        headers=_auth_headers("advisor@lvmh.com"),
    )
    assert resp.status_code == 403


def test_metrics_note_details_not_found():
    resp = client.get(
        "/api/dashboard/metrics/note-details/999999999",
        headers=_auth_headers("manager@lvmh.com"),
    )
    assert resp.status_code == 404


def test_opportunity_actions_upsert_and_get():
    note_id = _get_or_create_note_id()
    manager_headers = _auth_headers("manager@lvmh.com")

    upsert_resp = client.post(
        "/api/dashboard/opportunities/actions",
        headers=manager_headers,
        json={
            "note_id": note_id,
            "action_type": "call",
            "status": "planned",
            "details": "Client callback booked for tomorrow",
        },
    )
    assert upsert_resp.status_code == 200
    upsert_payload = upsert_resp.json()
    assert upsert_payload["status"] == "ok"
    assert upsert_payload["action"]["note_id"] == note_id
    assert upsert_payload["action"]["action_type"] == "call"
    assert upsert_payload["action"]["status"] == "planned"

    list_resp = client.get(
        f"/api/dashboard/opportunities/actions?note_ids={note_id}&status=planned",
        headers=manager_headers,
    )
    assert list_resp.status_code == 200
    list_payload = list_resp.json()
    assert list_payload["count"] >= 1
    assert any(a["note_id"] == note_id for a in list_payload["actions"])


def test_opportunity_actions_forbidden_for_advisor():
    note_id = _get_or_create_note_id()
    resp = client.post(
        "/api/dashboard/opportunities/actions",
        headers=_auth_headers("advisor@lvmh.com"),
        json={
            "note_id": note_id,
            "action_type": "schedule",
            "status": "planned",
        },
    )
    assert resp.status_code == 403


def test_opportunity_actions_invalid_status():
    note_id = _get_or_create_note_id()
    resp = client.post(
        "/api/dashboard/opportunities/actions",
        headers=_auth_headers("manager@lvmh.com"),
        json={
            "note_id": note_id,
            "action_type": "call",
            "status": "invalid-status",
        },
    )
    assert resp.status_code == 400


def test_opportunity_export_csv_manager():
    note_id = _get_or_create_note_id()
    manager_headers = _auth_headers("manager@lvmh.com")
    resp = client.get(
        f"/api/dashboard/opportunities/export?format=csv&note_ids={note_id}&limit=10",
        headers=manager_headers,
    )
    assert resp.status_code == 200
    assert resp.headers.get("content-type", "").startswith("text/csv")
    payload = resp.text
    assert "note_id" in payload
    assert str(note_id) in payload


def test_opportunity_export_forbidden_for_advisor():
    resp = client.get(
        "/api/dashboard/opportunities/export?format=csv&limit=10",
        headers=_auth_headers("advisor@lvmh.com"),
    )
    assert resp.status_code == 403


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

    resp = client.get("/api/dashboard/metrics/summary", headers=_auth_headers("manager@lvmh.com"))
    assert resp.status_code == 200
    data = resp.json()
    assert data["summary"]["accuracy"] is None
    assert data["summary"]["accuracy_available"] is False
    assert data["health_status"] == "healthy"
