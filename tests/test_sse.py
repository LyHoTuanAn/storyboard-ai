import json
import time

from fastapi.testclient import TestClient

from web import jobs
from web.events import format_sse
from web.server import app

client = TestClient(app)

BODY = {"params": {"context": "SSE topic"}, "api_key": "AIzaSyFAKE"}


def parse_stream(text):
    events = []
    for block in text.split("\n\n"):
        if not block.strip():
            continue
        record = {}
        for line in block.splitlines():
            key, _, value = line.partition(": ")
            record[key] = value
        if "event" in record:
            events.append((record["event"], json.loads(record["data"]), int(record["id"])))
    return events


def test_format_sse_shape():
    out = format_sse("step", {"n": 1}, 42)
    assert out == 'id: 42\nevent: step\ndata: {"n": 1}\n\n'


def test_stream_delivers_step_scene_and_status(monkeypatch):
    monkeypatch.setenv("SB_FAKE_PIPELINE", "1")
    job_id = client.post("/api/jobs", json=BODY).json()["id"]

    for _ in range(100):
        if jobs.read_job(job_id)["status"] in jobs.TERMINAL:
            break
        time.sleep(0.1)

    with client.stream("GET", f"/api/jobs/{job_id}/events") as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())

    events = parse_stream(body)
    names = [name for name, _, _ in events]
    assert "step" in names
    assert "scene" in names
    assert names[-1] == "status"

    scene_events = [data for name, data, _ in events if name == "scene"]
    assert {"current": 1, "total": 2} in scene_events
    assert {"current": 2, "total": 2} in scene_events


def test_last_event_id_resumes_without_duplicates(monkeypatch):
    monkeypatch.setenv("SB_FAKE_PIPELINE", "1")
    job_id = client.post("/api/jobs", json=BODY).json()["id"]
    for _ in range(100):
        if jobs.read_job(job_id)["status"] in jobs.TERMINAL:
            break
        time.sleep(0.1)

    with client.stream("GET", f"/api/jobs/{job_id}/events") as resp:
        full = "".join(resp.iter_text())
    events = parse_stream(full)
    midpoint = events[len(events) // 2][2]

    with client.stream(
        "GET", f"/api/jobs/{job_id}/events", headers={"Last-Event-ID": str(midpoint)}
    ) as resp:
        resumed = "".join(resp.iter_text())

    resumed_ids = [event_id for _, _, event_id in parse_stream(resumed) if event_id > 0]
    assert all(event_id > midpoint for event_id in resumed_ids)


def test_log_events_are_redacted(monkeypatch):
    monkeypatch.setenv("SB_FAKE_PIPELINE", "1")
    job_id = client.post("/api/jobs", json=BODY).json()["id"]
    log = jobs.job_dir(job_id) / "log.txt"
    log.write_text("leaking AIzaSyA1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7 here\n")
    jobs.set_status(job_id, "done")

    with client.stream("GET", f"/api/jobs/{job_id}/events") as resp:
        body = "".join(resp.iter_text())

    assert "AIzaSyA1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7" not in body
    assert "***" in body
