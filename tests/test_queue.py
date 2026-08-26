import threading
import time

import pytest

from web import jobs
from web.schemas import CreateJobRequest, JobParams
from web.settings import get_settings


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


def test_pump_starts_queued_jobs_in_created_at_order(monkeypatch):
    # job ids embed only second-granularity timestamps plus a random hex
    # suffix, so id order and creation order can disagree. Force that
    # disagreement explicitly (instead of hoping for a same-second race) so
    # the test is deterministic: pump() must follow created_at, not id.
    monkeypatch.setenv("SB_FAKE_PIPELINE", "1")
    monkeypatch.setenv("SB_MAX_CONCURRENT", "3")
    get_settings.cache_clear()

    made = [make_job(f"job-{i}") for i in range(3)]

    id_sorted = sorted(job["id"] for job in made)
    created_at_order = list(reversed(id_sorted))  # disagrees with id order
    for rank, job_id in enumerate(created_at_order):
        job = jobs.read_job(job_id)
        job["created_at"] = f"2020-01-01T00:00:{rank:02d}+00:00"
        jobs.write_job(job)

    started = jobs.pump(lambda job: "AIzaSyFAKE")

    assert started == created_at_order
    for job_id in started:
        wait_for_terminal(job_id)


def test_pump_is_safe_under_concurrent_callers(monkeypatch):
    # Task 7 calls jobs.pump() from FastAPI route handlers, which FastAPI
    # runs in a threadpool - so concurrent pump() calls are real. Without a
    # lock around the whole reap+count+spawn body, two threads can both
    # observe count_running() < max_concurrent and both spawn, exceeding
    # SB_MAX_CONCURRENT. Use a Barrier so the threads genuinely contend
    # instead of running one after another by luck.
    monkeypatch.setenv("SB_FAKE_PIPELINE", "1")
    monkeypatch.setenv("SB_FAKE_SLEEP", "2")
    monkeypatch.setenv("SB_MAX_CONCURRENT", "1")
    get_settings.cache_clear()

    for i in range(5):
        make_job(f"concurrent-{i}")

    n_threads = 8
    barrier = threading.Barrier(n_threads)
    results = [None] * n_threads

    def worker(index):
        barrier.wait(timeout=5)
        results[index] = jobs.pump(lambda job: "AIzaSyFAKE")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
        assert not thread.is_alive()

    all_started = [job_id for result in results for job_id in (result or [])]
    try:
        assert len(all_started) == 1
    finally:
        for job_id in all_started:
            try:
                jobs.cancel(job_id)
            except jobs.InvalidTransition:
                pass
