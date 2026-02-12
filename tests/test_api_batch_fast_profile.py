import os
from fastapi.testclient import TestClient

os.environ.setdefault("SEMANTIC_CACHE_DISABLED", "1")

from api.main import app
from api.routers import batch as batch_router

client = TestClient(app)


class _DummyQueue:
    def __init__(self):
        self.maxsize = 10
        self._items = []

    def full(self):
        return False

    def qsize(self):
        return len(self._items)

    async def put(self, item):
        self._items.append(item)


def test_batch_start_accepts_fast_profile(monkeypatch):
    queue = _DummyQueue()
    monkeypatch.setattr(batch_router, "ensure_batch_workers", lambda: None)
    monkeypatch.setattr(batch_router, "_get_batch_queue", lambda: queue)

    csv_content = "Transcription\nClient cherche un sac noir\n"
    response = client.post(
        "/api/batch?profile=fast_batch",
        files={"file": ("notes.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["profile"] == "fast_batch"
    assert queue._items
    assert queue._items[0][2] == "fast_batch"


def test_batch_start_rejects_invalid_profile():
    csv_content = "Transcription\nClient cherche une montre\n"
    response = client.post(
        "/api/batch?profile=invalid_mode",
        files={"file": ("notes.csv", csv_content, "text/csv")},
    )
    assert response.status_code == 400
    assert "Invalid profile" in response.text

