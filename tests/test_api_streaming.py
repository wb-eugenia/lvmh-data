from datetime import datetime
from fastapi.testclient import TestClient
import api.routers.streaming as streaming
from api.main import app
from src.models import PipelineOutput, RoutingDecision, RGPDResult


class FakePipeline:
    def __init__(self, *args, **kwargs):
        pass

    async def process_note(self, note, on_progress=None, **kwargs):
        if on_progress:
            await on_progress({"step": "cleaning", "tokens_saved": 0})
            await on_progress({"step": "routing", "tier": 1, "confidence": 0.9})
        return PipelineOutput(
            id=note.get("ID", "TEST"),
            original_text=note.get("Transcription"),
            processed_text=note.get("Transcription", ""),
            language=note.get("Language", "FR"),
            timestamp=datetime.now(),
            routing=RoutingDecision(tier=1, reasons=["test"], confidence=0.9, priority="Medium"),
            rgpd=RGPDResult(contains_sensitive=False, categories_detected=[], safe_to_store=True, anonymized_text=note.get("Transcription")),
            extraction=None,
            processing_time_ms=5.0,
            from_cache=False
        )


def test_streaming_endpoint():
    streaming.AsyncPipeline = FakePipeline
    client = TestClient(app)
    with client.stream("POST", "/api/analyze/stream", json={"text": "Bonjour", "language": "FR"}) as response:
        assert response.status_code == 200
        body = "".join(list(response.iter_text()))
    assert "complete" in body
