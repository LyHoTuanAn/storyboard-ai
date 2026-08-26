import time

import pytest

from web import jobs
from web.schemas import CreateJobRequest, JobParams


def make_job(context="Queue topic"):
    return jobs.create_job(
        CreateJobRequest(params=JobParams(context=context)), key_source="server"
    )


def wait_for_terminal(job_id, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if jobs.read_job(job_id)["status"] in jobs.TERMINAL:
            return jobs.read_job(job_id)
        time.sleep(0.1)
    raise AssertionError(f"{job_id} khong ket thuc trong {timeout}s")


def test_cancel_queued_job_needs_no_process():
    job = make_job()
    cancelled = jobs.cancel(job["id"])
    assert cancelled["status"] == "cancelled"


def test_cancel_terminal_job_raises():
    job = make_job()
    jobs.cancel(job["id"])
    with pytest.raises(jobs.InvalidTransition):
        jobs.cancel(job["id"])


def test_cancel_running_job_kills_the_process_group(monkeypatch):
    monkeypatch.setenv("SB_FAKE_PIPELINE", "1")
    monkeypatch.setenv("SB_FAKE_SLEEP", "30")
    job = make_job()
    pid = jobs.spawn(job["id"], api_key="AIzaSyFAKE")
    time.sleep(0.5)

    jobs.cancel(job["id"])

    assert jobs.read_job(job["id"])["status"] == "cancelled"
    time.sleep(0.5)
    assert not jobs.pid_alive(pid)


def test_pump_starts_only_up_to_max_concurrent(monkeypatch):
    monkeypatch.setenv("SB_FAKE_PIPELINE", "1")
    first = make_job("first")
    second = make_job("second")

    started = jobs.pump(lambda job: "AIzaSyFAKE")
    assert len(started) == 1

    wait_for_terminal(started[0])
    started_again = jobs.pump(lambda job: "AIzaSyFAKE")
    assert len(started_again) == 1
    assert started_again[0] != started[0]
    assert {first["id"], second["id"]} == {started[0], started_again[0]}


def test_pump_skips_jobs_without_a_key():
    make_job()
    assert jobs.pump(lambda job: None) == []
