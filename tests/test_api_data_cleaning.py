from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_data_cleaning_preview():
    csv_data = "Transcription,Language\nBonjour,FR\n,FR\nBonjour,FR\n"
    files = {"file": ("test.csv", csv_data.encode("utf-8"), "text/csv")}
    resp = client.post("/api/data-cleaning/preview", files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert "columns" in data
    assert "row_count" in data
    assert "sample" in data


def test_data_cleaning():
    csv_data = "Transcription,Language\nBonjour,FR\n,FR\nBonjour,FR\n"
    files = {"file": ("test.csv", csv_data.encode("utf-8"), "text/csv")}
    form = {"text_column": "Transcription"}
    resp = client.post("/api/data-cleaning", files=files, data=form)
    assert resp.status_code == 200
    data = resp.json()
    assert "report" in data
    assert "cleaned_csv" in data
