import time

from fastapi.testclient import TestClient

from web import jobs, keys
from web.schemas import CreateJobRequest, JobParams
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


def _make_local_job(context="Corrupt topic"):
    """Create a job straight through jobs.create_job(), bypassing POST
    /api/jobs, so nothing ever spawns a subprocess for it - keeps these
    tests deterministic (a real runner process concurrently rewriting
    job.json would race with the corruption below)."""
    return jobs.create_job(CreateJobRequest(params=JobParams(context=context)), key_source="server")


def _corrupt(job_id):
    (jobs.job_dir(job_id) / "job.json").write_text("{not valid json", encoding="utf-8")


def test_get_corrupt_job_returns_200_with_corrupt_shape():
    """The reported bug: GET /api/jobs/{id} used to raise an uncaught
    json.JSONDecodeError for a job whose job.json is unreadable, returning a
    500. It must now return the same reduced shape GET /api/jobs already
    produced for this case."""
    job = _make_local_job()
    _corrupt(job["id"])

    resp = client.get(f"/api/jobs/{job['id']}")

    assert resp.status_code == 200
    assert resp.json() == {"id": job["id"], "status": "corrupt"}


def test_list_and_get_agree_for_a_corrupt_job():
    """The actual user-facing failure mode: the job renders fine in the
    list, the user clicks into it, and the detail call must not disagree
    with the list call for the same job."""
    job = _make_local_job()
    _corrupt(job["id"])

    from_list = next(item for item in client.get("/api/jobs").json() if item["id"] == job["id"])
    from_get = client.get(f"/api/jobs/{job['id']}").json()

    assert from_list == from_get == {"id": job["id"], "status": "corrupt"}


def test_cancel_corrupt_job_returns_409_not_500():
    job = _make_local_job()
    _corrupt(job["id"])

    resp = client.post(f"/api/jobs/{job['id']}/cancel")

    assert resp.status_code == 409


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


def test_sweep_forgets_key_once_job_is_terminal(monkeypatch):
    monkeypatch.setenv("SB_FAKE_PIPELINE", "1")
    job_id = client.post("/api/jobs", json=BODY).json()["id"]
    wait_for_terminal(job_id)
    assert job_id in keys._KEYS

    # Any route that runs _pump_and_sweep() should now forget the key for
    # the job that just went terminal - creating a second job is enough to
    # trigger that cycle.
    client.post("/api/jobs", json=BODY)

    assert job_id not in keys._KEYS


def test_validation_error_scrubs_api_key_value():
    secret = "AIzaSySECRETLOOKINGVALUE12345"
    resp = client.post(
        "/api/jobs",
        json={"params": {"context": "Scrub test"}, "api_key": [secret]},
    )
    assert resp.status_code == 422
    assert secret not in resp.text


def test_delete_corrupt_job_removes_directory():
    """"corrupt" khong nam trong jobs.TERMINAL (co y nhu vay - TERMINAL con
    dieu khien set_status/spawn), nen truoc khi sua, route xoa tu choi mot
    job loi file voi 409 va khong co cach nao don no bang API."""
    job = _make_local_job()
    _corrupt(job["id"])

    assert client.delete(f"/api/jobs/{job['id']}").status_code == 204
    assert not jobs.job_dir(job["id"]).exists()


def test_delete_still_refuses_a_queued_job():
    job = _make_local_job()
    assert client.delete(f"/api/jobs/{job['id']}").status_code == 409
    assert jobs.job_dir(job["id"]).exists()


def test_pump_cannot_fail_a_job_created_in_the_same_request(monkeypatch):
    """pump() bao hong mot job "queued" dung key rieng ma no khong phan giai
    duoc key. Vong lap bom nen chay moi 3 giay, nen no co that su co the roi
    vao khe giua create_job() (job.json da nam tren dia) va keys.remember()
    (key chua kip vao bo nho) - va bao hong mot job vua duoc tao dung cach.
    Route tao job phai giu ca hai buoc trong vung tranh chap cua pump()."""
    import threading

    monkeypatch.setenv("SB_FAKE_PIPELINE", "1")

    pump_done = threading.Event()
    worker: dict = {}
    original_create = jobs.create_job

    def create_then_let_a_pump_tick_race(req, key_source):
        job = original_create(req, key_source=key_source)

        def run_pump():
            from web import keys as keys_module

            jobs.pump(keys_module.resolve)
            pump_done.set()

        thread = threading.Thread(target=run_pump)
        thread.start()
        worker["thread"] = thread
        # Dung o day la dung khe nguy hiem: job da "queued" tren dia, key
        # chua duoc nho. Luot bom kia phai bi chan ngoai vung tranh chap.
        assert not pump_done.wait(0.5), (
            "mot luot pump() da chay duoc vao giua create_job() va keys.remember()"
        )
        return job

    monkeypatch.setattr(jobs, "create_job", create_then_let_a_pump_tick_race)

    job_id = client.post("/api/jobs", json=BODY).json()["id"]

    worker["thread"].join(timeout=10)
    assert pump_done.is_set()
    assert jobs.read_job(job_id)["status"] != "failed"
    wait_for_terminal(job_id)
