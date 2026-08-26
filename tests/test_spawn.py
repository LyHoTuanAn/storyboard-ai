import os
import signal
import subprocess
import sys
import time

import pytest

from web import jobs
from web.schemas import CreateJobRequest, JobModels, JobParams


def make_job(models=None):
    return jobs.create_job(
        CreateJobRequest(params=JobParams(context="Spawn topic"), models=models or JobModels()),
        key_source="server",
    )


def test_build_env_carries_key_and_model_overrides():
    job = make_job(JobModels(MODEL_NAME="gemini-2.5-flash", IMAGE_GEN_MODEL="img-x"))
    env = jobs.build_env(job, api_key="AIzaSyFAKE")
    assert env["GEMINI_API_KEY"] == "AIzaSyFAKE"
    assert env["SB_MODEL_NAME"] == "gemini-2.5-flash"
    assert env["SB_IMAGE_GEN_MODEL"] == "img-x"
    assert "SB_TTS_MODEL" not in env
    assert "genai-pipeline" in env["PYTHONPATH"]


def test_build_env_strips_decoy_secrets_but_keeps_gemini_key(monkeypatch):
    monkeypatch.setenv("OTHER_API_KEY", "leaked-secret")
    monkeypatch.setenv("SOME_TOKEN", "leaked-token")
    monkeypatch.setenv("MY_SECRET", "leaked-secret-2")
    job = make_job()
    env = jobs.build_env(job, api_key="AIzaSyFAKE")
    assert "OTHER_API_KEY" not in env
    assert "SOME_TOKEN" not in env
    assert "MY_SECRET" not in env
    assert env["GEMINI_API_KEY"] == "AIzaSyFAKE"


def test_build_env_tolerates_a_corrupt_job_dict():
    """A corrupt job (as returned by jobs.read_job() for an unreadable
    job.json) has no "models" key. build_env() must not KeyError on it -
    spawn() already refuses to reach build_env() with such a job, but this
    keeps build_env() itself safe for any other/future direct caller."""
    env = jobs.build_env({"id": "j_x", "status": "corrupt"}, api_key="AIzaSyFAKE")
    assert env["GEMINI_API_KEY"] == "AIzaSyFAKE"
    assert "SB_MODEL_NAME" not in env
    assert "SB_IMAGE_GEN_MODEL" not in env
    assert "SB_TTS_MODEL" not in env


def test_spawn_refuses_a_corrupt_job():
    job = make_job()
    (jobs.job_dir(job["id"]) / "job.json").write_text("{not valid json", encoding="utf-8")
    with pytest.raises(jobs.InvalidTransition):
        jobs.spawn(job["id"], api_key="AIzaSyFAKE")
    assert job["id"] not in jobs._PROCESSES


def test_spawn_runs_fake_pipeline_to_completion(monkeypatch):
    monkeypatch.setenv("SB_FAKE_PIPELINE", "1")
    job = make_job()
    pid = jobs.spawn(job["id"], api_key="AIzaSyFAKE")
    assert pid > 0
    assert jobs.read_job(job["id"])["status"] == "running"

    for _ in range(100):
        if jobs.read_job(job["id"])["status"] in jobs.TERMINAL:
            break
        time.sleep(0.1)

    assert jobs.read_job(job["id"])["status"] == "done"


def _reap_until(predicate, attempts=50, delay=0.05):
    """Retry jobs.reap_orphans() (the real production path, which reaps via
    process.poll() internally) until predicate() is true or we give up.
    Returns the last reaped list. Used instead of calling process.wait()/
    process.poll() directly from a test, so these tests exercise the same
    timing production code sees: the child may take a moment after exiting
    before the OS makes it reapable."""
    reaped = []
    for _ in range(attempts):
        reaped = jobs.reap_orphans()
        if predicate():
            break
        time.sleep(delay)
    return reaped


def test_reap_orphans_detects_zombie_child_even_when_job_still_says_running(monkeypatch):
    """Before the fix, os.kill(pid, 0) on an un-reaped zombie always returns
    True, so pid_alive() (and thus the old reap_orphans) could never detect
    that the child had actually exited. reap_orphans() must instead use the
    tracked Popen's poll() (which reaps the zombie), so detection no longer
    depends on os.kill against a zombie pid."""
    monkeypatch.setenv("SB_FAKE_PIPELINE", "1")
    job = make_job()
    jobs.spawn(job["id"], api_key="AIzaSyFAKE")

    for _ in range(100):
        if jobs.read_job(job["id"])["status"] == "done":
            break
        time.sleep(0.1)
    else:
        raise AssertionError("fake pipeline never reached 'done'")

    # Simulate the "child died without reporting" case the finding is about:
    # force the job back to "running" as if the child never got to write its
    # own terminal status before exiting. Note: we never call process.wait()
    # or process.poll() ourselves anywhere in this test - only reap_orphans()
    # (via _reap_until) touches the child, exactly like production.
    stuck = jobs.read_job(job["id"])
    stuck["status"] = "running"
    stuck["finished_at"] = None
    jobs.write_job(stuck)

    reaped = _reap_until(lambda: job["id"] not in jobs._PROCESSES)

    assert job["id"] in reaped
    assert jobs.read_job(job["id"])["status"] in jobs.TERMINAL
    assert job["id"] not in jobs._PROCESSES


def test_reap_orphans_detects_externally_sigkilled_child():
    job = make_job()
    # A real, trackable child (mirrors what spawn() would register), killed
    # externally before it can report anything back into job.json.
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        start_new_session=True,
    )
    jobs._PROCESSES[job["id"]] = process
    jobs.set_status(job["id"], "running", pid=process.pid)

    os.kill(process.pid, signal.SIGKILL)
    # No process.wait()/process.poll() here - reap_orphans() itself must be
    # the one to observe and reap the exit, as it would in production.

    reaped = _reap_until(lambda: job["id"] not in jobs._PROCESSES)

    assert job["id"] in reaped
    status = jobs.read_job(job["id"])["status"]
    assert status != "running"
    assert status in jobs.TERMINAL


def test_reap_orphans_reaps_processes_of_jobs_that_finished_on_their_own(monkeypatch):
    """Regression test: a job that reaches a terminal status by itself (the
    child wrote "done" to job.json before exiting) stops appearing in
    list_jobs(status="running"). If reap_orphans() only looked at that list,
    it would never poll() such a child again - leaking its entry in
    _PROCESSES and leaving its OS process a zombie for the server's
    lifetime. reap_orphans() must sweep _PROCESSES independently of job
    status to reap it, without touching the job's already-correct status."""
    monkeypatch.setenv("SB_FAKE_PIPELINE", "1")
    job = make_job()
    jobs.spawn(job["id"], api_key="AIzaSyFAKE")

    for _ in range(100):
        if jobs.read_job(job["id"])["status"] == "done":
            break
        time.sleep(0.1)
    else:
        raise AssertionError("fake pipeline never reached 'done'")

    _reap_until(lambda: job["id"] not in jobs._PROCESSES)

    assert job["id"] not in jobs._PROCESSES
    assert jobs.read_job(job["id"])["status"] == "done"


def test_reap_orphans_marks_dead_running_jobs_interrupted():
    job = make_job()
    jobs.set_status(job["id"], "running", pid=999999)
    reaped = jobs.reap_orphans()
    assert job["id"] in reaped
    assert jobs.read_job(job["id"])["status"] == "interrupted"


def test_reap_orphans_leaves_queued_jobs_alone():
    job = make_job()
    jobs.reap_orphans()
    assert jobs.read_job(job["id"])["status"] == "queued"


def test_spawn_gives_the_child_no_stdin():
    """Pipeline duoc boc lai von la chuong trinh tuong tac. Neu con sot mot
    loi goi input(), viec ke thua stdin cua server lam job treo vinh vien -
    giu cho chay, khong in ra gi, khong ai biet tai sao. stdin phai la
    DEVNULL de tinh huong do thanh EOF (job hong ngay) thay vi treo."""
    job = make_job()
    captured = {}
    original_popen = subprocess.Popen

    def recording_popen(*args, **kwargs):
        captured.update(kwargs)
        return original_popen(*args, **kwargs)

    import web.jobs as jobs_module

    original = jobs_module.subprocess.Popen
    jobs_module.subprocess.Popen = recording_popen
    try:
        pid = jobs.spawn(job["id"], api_key="AIzaSyFAKE")
    finally:
        jobs_module.subprocess.Popen = original

    assert captured.get("stdin") is subprocess.DEVNULL
    # Va van phai o nhom tien trinh rieng, neu khong Huy se ban tin hieu vao
    # ca nhom cua server.
    assert captured.get("start_new_session") is True
    assert os.getpgid(pid) == pid
    jobs.cancel(job["id"])


def test_spawn_records_the_process_start_time(monkeypatch):
    """Chi so PID thi khong dinh danh duoc mot tien trinh (he dieu hanh tai
    su dung PID). spawn() phai luu kem thoi diem bat dau de sau nay con doi
    chieu."""
    monkeypatch.setenv("SB_FAKE_PIPELINE", "1")
    monkeypatch.setenv("SB_FAKE_SLEEP", "30")
    job = make_job()
    pid = jobs.spawn(job["id"], api_key="AIzaSyFAKE")

    stored = jobs.read_job(job["id"])
    assert stored["pid"] == pid
    assert stored["pid_start"]
    assert stored["pid_start"] == jobs.process_start_time(pid)
    assert jobs.pid_is_ours(stored)

    jobs.cancel(job["id"])


def test_reap_orphans_does_not_trust_a_recycled_pid():
    """Sau khi server khoi dong lai, _PROCESSES rong nen chi con PID tren
    dia de doi chieu. Mot PID da bi tai su dung doc ra la "con song", va
    truoc khi sua thi job dung nguyen "running" mai mai, giu mat cho chay duy
    nhat. Thoi diem bat dau khong khop thi phai coi la khong phai cua minh."""
    job = make_job()
    intruder = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        jobs.set_status(
            job["id"],
            "running",
            pid=intruder.pid,
            pid_start="Mon Jan  1 00:00:00 2001",  # khong the la thoi diem that
        )

        reaped = jobs.reap_orphans()

        assert job["id"] in reaped
        assert jobs.read_job(job["id"])["status"] == "interrupted"
        # Va khong duoc dong vao tien trinh la do.
        assert intruder.poll() is None
    finally:
        intruder.kill()
        intruder.wait()


def test_cancel_does_not_signal_a_recycled_pid():
    """Cung goc van de, o phia nguy hiem hon: Huy chay os.killpg vao bat cu
    ai dang giu PID do. Neu thoi diem bat dau khong khop, tuyet doi khong
    duoc gui tin hieu - chi ghi trang thai "cancelled"."""
    job = make_job()
    intruder = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True
    )
    try:
        jobs.set_status(
            job["id"], "running", pid=intruder.pid, pid_start="Mon Jan  1 00:00:00 2001"
        )

        cancelled = jobs.cancel(job["id"])

        assert cancelled["status"] == "cancelled"
        time.sleep(0.3)
        assert intruder.poll() is None, "Huy da giet nham mot tien trinh khong phai cua job"
    finally:
        intruder.kill()
        intruder.wait()
