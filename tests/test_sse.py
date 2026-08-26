import json
import threading
import time

from fastapi.testclient import TestClient

from web import events, jobs
from web.events import format_sse
from web.schemas import CreateJobRequest, JobParams
from web.server import app

client = TestClient(app)

BODY = {"params": {"context": "SSE topic"}, "api_key": "AIzaSyFAKE"}


def parse_stream(text):
    """Return a list of (event_name, data, (offset, index)) tuples. The SSE
    id is `<offset>:<index>` - parsed here into a tuple so callers can
    compare/order ids without re-parsing strings. A frame may legitimately
    carry NO id line at all (a `status` frame emitted before this connection
    has sent any log-derived event); such a frame gets an id of None."""
    events = []
    for block in text.split("\n\n"):
        if not block.strip():
            continue
        record = {}
        for line in block.splitlines():
            key, _, value = line.partition(": ")
            record[key] = value
        if "event" in record:
            event_id = None
            if "id" in record:
                offset_str, _, index_str = record["id"].partition(":")
                event_id = (int(offset_str), int(index_str))
            events.append((record["event"], json.loads(record["data"]), event_id))
    return events


def wait_for_terminal(job_id):
    for _ in range(100):
        if jobs.read_job(job_id)["status"] in jobs.TERMINAL:
            return
        time.sleep(0.1)
    raise AssertionError(f"{job_id} khong ket thuc")


def test_format_sse_shape():
    out = format_sse("step", {"n": 1}, 42, 0)
    assert out == 'id: 42:0\nevent: step\ndata: {"n": 1}\n\n'


def test_stream_delivers_step_scene_and_status(monkeypatch):
    monkeypatch.setenv("SB_FAKE_PIPELINE", "1")
    job_id = client.post("/api/jobs", json=BODY).json()["id"]
    wait_for_terminal(job_id)

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
    wait_for_terminal(job_id)

    with client.stream("GET", f"/api/jobs/{job_id}/events") as resp:
        full = "".join(resp.iter_text())
    events = parse_stream(full)
    midpoint_offset, midpoint_index = events[len(events) // 2][2]

    with client.stream(
        "GET",
        f"/api/jobs/{job_id}/events",
        headers={"Last-Event-ID": f"{midpoint_offset}:{midpoint_index}"},
    ) as resp:
        resumed = "".join(resp.iter_text())

    resumed_ids = [
        event_id
        for _, _, event_id in parse_stream(resumed)
        if event_id is not None and event_id != (0, 0)
    ]
    assert all(event_id > (midpoint_offset, midpoint_index) for event_id in resumed_ids)


def test_resume_mid_line_delivers_the_second_event_of_that_line(monkeypatch):
    """A line that parses into a progress event produces two SSE events - a
    `log` event (sub-index 0) and the derived event (sub-index 1), both
    sharing the same offset. If the client disconnects right after receiving
    the first of the two and reconnects with that event's id, the second
    event (same offset, next sub-index) must still arrive - not be skipped
    just because it shares an id-offset with an event already received."""
    monkeypatch.setenv("SB_FAKE_PIPELINE", "1")
    job_id = client.post("/api/jobs", json=BODY).json()["id"]
    wait_for_terminal(job_id)

    with client.stream("GET", f"/api/jobs/{job_id}/events") as resp:
        full = "".join(resp.iter_text())
    all_events = parse_stream(full)

    pair = None
    for i in range(len(all_events) - 1):
        name, _, (offset, index) = all_events[i]
        next_name, next_data, (next_offset, next_index) = all_events[i + 1]
        if name == "log" and index == 0 and next_offset == offset and next_index == 1:
            pair = (all_events[i], all_events[i + 1])
            break
    assert pair is not None, "expected a line producing a log + derived event pair"

    first_event, second_event = pair
    first_offset, first_index = first_event[2]

    with client.stream(
        "GET",
        f"/api/jobs/{job_id}/events",
        headers={"Last-Event-ID": f"{first_offset}:{first_index}"},
    ) as resp:
        resumed = "".join(resp.iter_text())
    resumed_events = parse_stream(resumed)

    assert second_event in resumed_events
    assert first_event not in resumed_events


def test_events_stream_ends_promptly_for_a_corrupt_job():
    """Regression guard: "corrupt" is not a member of jobs.TERMINAL (by
    design - see web/jobs.py), so before this fix stream_job() fell through
    to its polling loop for a corrupt job and only returned after
    IDLE_TIMEOUT (600s), even though nothing will ever write another log
    line for it. Bound this test's real wall-clock time instead of just
    asserting on the eventual result: if stream_job() ever regresses back
    to treating "corrupt" as a non-end status, this test must fail within a
    few seconds, not hang the whole suite for ten minutes. Run the request
    on a background thread and .join() it with a timeout well under
    IDLE_TIMEOUT; a thread still alive after the timeout means the server
    is still polling, so we fail immediately instead of waiting for it.
    """
    job = jobs.create_job(
        CreateJobRequest(params=JobParams(context="Corrupt SSE")), key_source="server"
    )
    (jobs.job_dir(job["id"]) / "job.json").write_text("{not valid json", encoding="utf-8")

    result: dict = {}

    def fetch():
        with client.stream("GET", f"/api/jobs/{job['id']}/events") as resp:
            result["status_code"] = resp.status_code
            result["body"] = "".join(resp.iter_text())

    started = time.time()
    thread = threading.Thread(target=fetch, daemon=True)
    thread.start()
    thread.join(timeout=5.0)
    elapsed = time.time() - started

    assert not thread.is_alive(), (
        f"events stream for a corrupt job was still open after {elapsed:.1f}s - "
        '"corrupt" must be treated as an end condition in stream_job(), not left '
        "to fall through to the IDLE_TIMEOUT poll loop"
    )

    assert result["status_code"] == 200
    events = parse_stream(result["body"])
    assert events[-1][0] == "status"
    assert events[-1][1]["status"] == "corrupt"
    # Ended via the corrupt short-circuit, not via the idle-timeout path.
    assert "stalled" not in events[-1][1]


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


def test_stalled_event_does_not_carry_an_unsent_line_id(monkeypatch):
    """Truoc khi sua, su kien "stalled" mang id `<cursor>:0`, ma cursor tro
    toi dong KE TIEP - dong chua he duoc gui. Trinh duyet luu id do lam
    Last-Event-ID, va khi no tu ket noi lai, logic resume bo qua "su kien so
    0 cua dong tai offset do" - tuc dung cai `log` event cua dong tiep theo.
    Moi lan im lang la mat dung mot dong nhat ky, trong khi spec (muc 7) hua
    khong mat va khong lap. Su kien "stalled" phai mang id cua su kien CUOI
    CUNG that su da gui."""
    monkeypatch.setattr(events, "IDLE_TIMEOUT", 0.4)
    monkeypatch.setattr(events, "POLL_SECONDS", 0.05)

    job = jobs.create_job(
        CreateJobRequest(params=JobParams(context="Stall topic")), key_source="server"
    )
    log_path = jobs.job_dir(job["id"]) / "log.txt"
    first_line = "Step 1: Performing Web-Grounded Research (Fast)...\n"
    log_path.write_text(first_line, encoding="utf-8")
    jobs.set_status(job["id"], "running", pid=999999)

    with client.stream("GET", f"/api/jobs/{job['id']}/events") as resp:
        body = "".join(resp.iter_text())
    first_pass = parse_stream(body)

    stalled_name, stalled_data, stalled_id = first_pass[-1]
    assert stalled_name == "status"
    assert stalled_data.get("stalled") is True

    delivered = [event_id for _, _, event_id in first_pass[:-1]]
    assert delivered, "vong dau phai gui duoc it nhat mot su kien log"
    assert stalled_id == delivered[-1], (
        "su kien stalled mang id cua mot dong chua he duoc gui - lan ket noi "
        "lai se bo qua dung dong do"
    )

    # Dong thu hai xuat hien sau khi luong da dong, dung nhu khi job im lang
    # mot luc roi in tiep.
    with log_path.open("a", encoding="utf-8") as stream:
        stream.write("--- Processing Scene 1/2 ---\n")
    jobs.set_status(job["id"], "done")

    with client.stream(
        "GET",
        f"/api/jobs/{job['id']}/events",
        headers={"Last-Event-ID": f"{stalled_id[0]}:{stalled_id[1]}"},
    ) as resp:
        resumed_body = "".join(resp.iter_text())
    resumed = parse_stream(resumed_body)

    log_lines = [data["line"] for name, data, _ in resumed if name == "log"]
    assert "--- Processing Scene 1/2 ---" in log_lines, (
        "dong log ke tiep bi mat khi ket noi lai tu su kien stalled"
    )
    # Va khong gui lai dong da nhan o vong truoc.
    assert first_line.rstrip("\n") not in log_lines
