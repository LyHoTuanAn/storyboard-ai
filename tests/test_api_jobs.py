import time

from fastapi.testclient import TestClient

from web import jobs
from web.server import app

client = TestClient(app)

BODY = {"params": {"context": "API topic", "language": "vietnamese"}, "api_key": "AIzaSyFAKE"}


def wait_for_terminal(job_id, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = client.get(f"/api/jobs/{job_id}").json()["status"]
        if status in jobs.TERMINAL:
            return status
        time.sleep(0.1)
    raise AssertionError("job khong ket thuc")


def test_create_job_returns_201_and_id(monkeypatch):
    monkeypatch.setenv("SB_FAKE_PIPELINE", "1")
    resp = client.post("/api/jobs", json=BODY)
    assert resp.status_code == 201
    assert resp.json()["id"].startswith("j_")


def test_create_job_rejects_blank_context():
    resp = client.post("/api/jobs", json={"params": {"context": "   "}, "api_key": "AIzaSyFAKE"})
    assert resp.status_code == 422


def test_create_job_rejects_missing_key(monkeypatch):
    monkeypatch.setattr("web.keys.server_key", lambda: None)
    resp = client.post("/api/jobs", json={"params": {"context": "No key"}})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "missing_api_key"


def test_response_never_contains_the_api_key(monkeypatch):
    monkeypatch.setenv("SB_FAKE_PIPELINE", "1")
    job_id = client.post("/api/jobs", json=BODY).json()["id"]
    detail = client.get(f"/api/jobs/{job_id}")
    assert "AIzaSyFAKE" not in detail.text


def test_job_reaches_done(monkeypatch):
    monkeypatch.setenv("SB_FAKE_PIPELINE", "1")
    job_id = client.post("/api/jobs", json=BODY).json()["id"]
    assert wait_for_terminal(job_id) == "done"


def test_cancel_then_cancel_again_returns_409(monkeypatch):
    monkeypatch.setenv("SB_FAKE_PIPELINE", "1")
    monkeypatch.setenv("SB_FAKE_SLEEP", "30")
    job_id = client.post("/api/jobs", json=BODY).json()["id"]
    time.sleep(0.5)
    assert client.post(f"/api/jobs/{job_id}/cancel").status_code == 200
    assert client.post(f"/api/jobs/{job_id}/cancel").status_code == 409


def test_get_unknown_job_returns_404():
    assert client.get("/api/jobs/j_20260101_000000_beef").status_code == 404


def test_malformed_job_id_returns_404():
    assert client.get("/api/jobs/..%2f..%2fetc").status_code == 404


def test_delete_running_job_returns_409(monkeypatch):
    monkeypatch.setenv("SB_FAKE_PIPELINE", "1")
    monkeypatch.setenv("SB_FAKE_SLEEP", "30")
    job_id = client.post("/api/jobs", json=BODY).json()["id"]
    time.sleep(0.5)
    assert client.delete(f"/api/jobs/{job_id}").status_code == 409
    client.post(f"/api/jobs/{job_id}/cancel")


def test_delete_finished_job_removes_directory(monkeypatch):
    monkeypatch.setenv("SB_FAKE_PIPELINE", "1")
    job_id = client.post("/api/jobs", json=BODY).json()["id"]
    wait_for_terminal(job_id)
    assert client.delete(f"/api/jobs/{job_id}").status_code == 204
    assert not jobs.job_dir(job_id).exists()
