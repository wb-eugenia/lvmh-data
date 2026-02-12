import os
from datetime import datetime

from fastapi.testclient import TestClient

import api.routers.analyze as analyze_router
from api.main import app
from config.production import settings
from src.models import (
    ExtractionResult as PipelineExtractionResult,
    MetaAnalysis,
    Pilier1Product,
    Pilier2Client,
    Pilier3Care,
    Pilier4Business,
    PipelineOutput,
    RGPDResult,
    RoutingDecision,
)


os.environ.setdefault("SEMANTIC_CACHE_DISABLED", "1")
client = TestClient(app)


def _auth_headers(email: str, password: str = "lvmh") -> dict[str, str]:
    login_resp = client.post(
        "/api/auth/login",
        data={"username": email, "password": password},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _make_pipeline_output(note_id: str) -> PipelineOutput:
    extraction = PipelineExtractionResult(
        pilier_1_univers_produit=Pilier1Product(categories=["leather_goods", "capucines"]),
        pilier_2_profil_client=Pilier2Client(),
        pilier_3_hospitalite_care=Pilier3Care(),
        pilier_4_action_business=Pilier4Business(budget_potential="5000-10000"),
        meta_analysis=MetaAnalysis(
            quality_score=0.92,
            advisor_feedback="Super note",
            missing_info=[],
            risk_flags=[],
        ),
    )
    return PipelineOutput(
        id=note_id,
        original_text="Cliente VIP cherche un sac noir.",
        processed_text="Cliente VIP cherche un sac noir.",
        language="FR",
        timestamp=datetime.now(),
        routing=RoutingDecision(tier=2, reasons=["test"], confidence=0.88, priority="Medium"),
        rgpd=RGPDResult(
            contains_sensitive=True,
            categories_detected=["[EMAIL]"],
            safe_to_store=True,
            anonymized_text="Cliente VIP cherche un sac noir.",
        ),
        extraction=extraction,
        profile="single_note",
        processing_time_ms=12.0,
        from_cache=False,
    )


class FakePipeline:
    async def process_note(self, note, on_progress=None, **kwargs):
        return _make_pipeline_output(str(note.get("ID", "TEST_PARITY")))


def test_parity_probe_forbidden_for_advisor(monkeypatch):
    monkeypatch.setattr(settings, "enable_parity_probe", True)
    monkeypatch.setattr(analyze_router, "get_pipeline", lambda: FakePipeline())

    response = client.post(
        "/api/analyze/parity-probe",
        headers=_auth_headers("advisor@lvmh.com"),
        json={"text": "Cliente VIP cherche un sac noir en cuir.", "language": "FR", "profile": "single_note"},
    )
    assert response.status_code == 403


def test_parity_probe_allowed_for_manager_and_admin(monkeypatch):
    monkeypatch.setattr(settings, "enable_parity_probe", True)
    monkeypatch.setattr(analyze_router, "get_pipeline", lambda: FakePipeline())

    payload = {"text": "Cliente VIP cherche un sac noir en cuir.", "language": "FR", "profile": "single_note"}
    for email in ["manager@lvmh.com", "admin@lvmh.com"]:
        response = client.post("/api/analyze/parity-probe", headers=_auth_headers(email), json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "api_projection" in data
        assert "runtime_projection" in data
        assert "diff" in data
        assert "meta" in data
        assert data["api_projection"]["tier"] == 2
        assert data["runtime_projection"]["tier"] == 2
        assert 0 <= float(data["diff"]["tag_jaccard"]) <= 1


def test_analyze_contract_required_fields_unchanged(monkeypatch):
    monkeypatch.setattr(analyze_router, "get_pipeline", lambda: FakePipeline())
    monkeypatch.setattr(analyze_router, "persist_note_single_transaction", lambda *args, **kwargs: None)

    response = client.post(
        "/api/analyze",
        headers=_auth_headers("manager@lvmh.com"),
        json={"text": "Cliente VIP cherche un sac noir en cuir.", "language": "FR"},
    )
    assert response.status_code == 200
    data = response.json()
    required = [
        "id",
        "tags",
        "routing",
        "rgpd",
        "meta_analysis",
        "pilier_1_univers_produit",
        "pilier_2_profil_client",
        "pilier_3_hospitalite_care",
        "pilier_4_action_business",
        "processing_time_ms",
    ]
    for field in required:
        assert field in data
