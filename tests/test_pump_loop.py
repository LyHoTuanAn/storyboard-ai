import time

from fastapi.testclient import TestClient

from web import jobs
from web.server import PUMP_INTERVAL_SECONDS, app

BODY = {"params": {"context": "Pump loop topic"}, "api_key": "AIzaSyFAKE"}


def wait_for_terminal(job_id, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = jobs.read_job(job_id)["status"]
        if status in jobs.TERMINAL:
            return status
        time.sleep(0.1)
    raise AssertionError(f"{job_id} khong ket thuc trong {timeout}s")


def test_second_queued_job_starts_on_its_own_after_the_first_finishes(monkeypatch):
    """Regression test for the queue-drain bug: web/jobs.py's pump() was only
    ever called as a side effect of the create-job and cancel-job routes, so
    a job that finished on its own (not via another API call) never
    triggered the next queued job to start - it stayed "queued" forever.
    Reproduces the exact repro from the bug report: SB_MAX_CONCURRENT=1
    (the tests/conftest.py default), two jobs created back-to-back in fake
    mode.

    Uses `with TestClient(app)` - not the bare `TestClient(app)` most other
    tests in this suite use - because only the context-manager form runs the
    app's lifespan, and it is the lifespan's background pump loop, not this
    test, that must drain job B. After creating both jobs, this test makes
    no further API call at all: job B's status is read directly via
    jobs.read_job(), so if it ever leaves "queued" it can only be the
    background loop's doing.

    The wait for B is bounded to a small real-time multiple of the loop's
    own interval - the same "bound a real-time wait so a regression fails
    fast instead of hanging the suite" concern tests/test_sse.py guards with
    a thread + join(timeout). If the loop were not running at all (the bug
    this guards against), this test fails in seconds instead of hanging
    pytest.
    """
    monkeypatch.setenv("SB_FAKE_PIPELINE", "1")

    with TestClient(app) as local_client:
        job_a = local_client.post("/api/jobs", json=BODY).json()["id"]
        job_b = local_client.post("/api/jobs", json=BODY).json()["id"]

        # SB_MAX_CONCURRENT=1 (conftest default): the first job starts right
        # away as a side effect of its own create-job request, the second is
        # left queued behind it as a side effect of its own.
        assert jobs.read_job(job_a)["status"] == "running"
        assert jobs.read_job(job_b)["status"] == "queued"

        wait_for_terminal(job_a)

        deadline = time.time() + PUMP_INTERVAL_SECONDS * 4 + 5.0
        drained = False
        while time.time() < deadline:
            if jobs.read_job(job_b)["status"] != "queued":
                drained = True
                break
            time.sleep(0.1)

        assert drained, (
            f"{job_b} van 'queued' sau khi {job_a} ket thuc, khong co API call "
            "nao khac duoc goi - vong lap bom (pump loop) nen tu rut hang doi"
        )

        wait_for_terminal(job_b)


def test_pump_task_is_cancelled_cleanly_on_shutdown():
    """lifespan() starts _pump_loop() as a background asyncio task and must
    cancel it on shutdown and await that cancellation - otherwise the app
    leaves a pending task behind, which asyncio logs as "Task was destroyed
    but it is pending!" when it is later garbage collected. Exiting the
    `with TestClient(app)` block runs the app's shutdown lifecycle
    synchronously (TestClient.__exit__ blocks on wait_shutdown()), so by the
    time it returns, lifespan()'s `finally` block - which cancels the task
    and awaits it - has already completed. If shutdown raised (e.g. the
    await surfaced something other than CancelledError), that exception
    would propagate out of this `with` block and fail this test on its own.
    """
    with TestClient(app) as local_client:
        pump_task = local_client.app.state.pump_task
        assert pump_task is not None
        assert not pump_task.done()

    assert pump_task.cancelled()
