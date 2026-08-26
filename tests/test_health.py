from fastapi.testclient import TestClient

from web.server import app

client = TestClient(app)


def test_health_reports_shape():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"ffmpeg", "server_key", "running"}
    assert isinstance(body["ffmpeg"], bool)
    assert isinstance(body["server_key"], bool)
    assert isinstance(body["running"], int)
