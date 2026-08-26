import threading
import time

from fastapi.testclient import TestClient

from web import jobs
from web.schemas import CreateJobRequest, JobParams
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


def test_a_job_created_beside_a_sweep_keeps_its_key(monkeypatch):
    """Regression test cho cuoc dua "tao job / quet key".

    _pump_and_sweep() tinh _active_job_ids() roi goi keys.sweep(). Truoc khi
    sua, hai lenh do chay NGOAI moi khoa, nen mot create_job dap dung vao khe
    giua chung khong kip co mat trong anh chup - sweep() quen mat key vua
    nho, va luot bom ke tiep bao hong chinh job vua tao. Nguoi dung nhan 201
    roi thay job "Hong" ngay lap tuc.

    Cach lam bai test nay TAT DINH thay vi phu thuoc thoi gian: khong co
    sleep nao quyet dinh ket qua, va khong co "hy vong hai luong dap trung
    nhau". Cuoc dua duoc DAT dung vao khe can kiem tra - `_active_job_ids`
    bi thay bang mot ham chup anh that truoc, roi moi cho mot luong khac goi
    create_job, roi moi tra anh chup ve cho sweep(). Do la dung thu tu
    "snapshot -> create -> sweep" cua loi.

    Voi ban da sua, ham thay the nay chay khi khoa dang duoc giu, nen:
      - `pump_lock().acquire(blocking=False)` that bai. Day la bang chung
        cau truc, khong dinh gi toi dong ho: neu khoa bi go ra khoi
        _pump_and_sweep(), lenh nay thanh cong va bai test hong ngay.
      - luong tao job khong the vao duoc, nen `create_done` khong bao gio
        duoc dat trong cua so nay - va sau khi nha khoa, key cua job moi con
        nguyen.
    Voi ban chua sua, luong tao job chay lot vao giua va key bi quet mat -
    khang dinh cuoi cung that bai. Ca hai chieu deu do trang thai quyet dinh,
    khong do toc do.
    """
    from web import keys, server

    # Luot bom cuoi bai se that su phong tien trinh cho job nay (key con
    # nguyen thi pump() chay no) - cho no chay pipeline gia de khong goi API
    # nao va ket thuc ngay.
    monkeypatch.setenv("SB_FAKE_PIPELINE", "1")

    request = CreateJobRequest(
        params=JobParams(context="Sweep race"), api_key="AIzaSyRACEKEYRACEKEYRACEKEY"
    )
    created: dict[str, str] = {}
    create_done = threading.Event()
    observations: dict[str, object] = {}

    def create_the_job() -> None:
        with jobs.pump_lock():
            job = jobs.create_job(request, key_source="user")
            created["id"] = job["id"]
            keys.remember(job["id"], request.api_key)
        create_done.set()

    real_active_job_ids = server._active_job_ids
    raced = threading.Event()

    def active_ids_with_a_create_landing_beside_it() -> set[str]:
        if raced.is_set():
            return real_active_job_ids()
        raced.set()

        # 1. Anh chup, dung nhu ban that chup no.
        snapshot = real_active_job_ids()

        # 2. Khoa co dang duoc giu quanh cua so nay khong? Kiem bang mot lan
        #    thu lay khong-cho: khong sleep, khong doi, khong may rui.
        lock = jobs.pump_lock()
        acquired = lock.acquire(blocking=False)
        observations["lock_held_during_sweep"] = not acquired
        if acquired:
            lock.release()

        # 3. Mot create_job dap xuong ngay day. Neu khoa dang duoc giu no se
        #    phai doi den sau khi sweep() xong; neu khong, no chay tron ven
        #    va sweep() se quet mat key cua no.
        worker = threading.Thread(target=create_the_job)
        worker.start()
        observations["worker"] = worker
        observations["create_finished_inside_window"] = create_done.wait(0.5)

        return snapshot

    monkeypatch.setattr(server, "_active_job_ids", active_ids_with_a_create_landing_beside_it)
    try:
        server._pump_and_sweep()
    finally:
        worker = observations.get("worker")
        if isinstance(worker, threading.Thread):
            worker.join(timeout=10)

    assert observations["lock_held_during_sweep"], (
        "_pump_and_sweep() tinh anh chup va quet key ngoai khoa bom - "
        "mot create_job van chen vao giua duoc"
    )
    assert observations["create_finished_inside_window"] is False, (
        "create_job chay xong ngay trong cua so snapshot->sweep, tuc la no "
        "khong bi khoa bom chan"
    )

    job_id = created["id"]
    assert keys.is_remembered(job_id), "sweep() da quen key cua mot job vua duoc tao"

    # Va hau qua that su cua loi: luot bom ke tiep khong duoc bao hong job do.
    monkeypatch.setattr(server, "_active_job_ids", real_active_job_ids)
    server._pump_and_sweep()
    status = jobs.read_job(job_id)["status"]
    assert status != "failed", "job vua tao bi bao hong vi key da bi quet mat"

    try:
        jobs.cancel(job_id)
    except jobs.InvalidTransition:
        pass
    jobs.reap_orphans()
    keys.forget(job_id)
