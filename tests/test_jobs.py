import json

import pytest

from web import jobs
from web.schemas import CreateJobRequest, JobParams


def make_request(context="Test topic"):
    return CreateJobRequest(params=JobParams(context=context))


def test_new_job_id_matches_pattern():
    from web.schemas import JOB_ID_RE

    assert JOB_ID_RE.match(jobs.new_job_id())


def test_create_job_writes_file_and_starts_queued():
    job = jobs.create_job(make_request(), key_source="server")
    assert job["status"] == "queued"
    assert job["params"]["context"] == "Test topic"
    on_disk = json.loads((jobs.job_dir(job["id"]) / "job.json").read_text())
    assert on_disk == job


def test_create_job_never_stores_api_key():
    req = CreateJobRequest(params=JobParams(context="X"), api_key="AIzaSyFAKEKEYFAKEKEYFAKEKEYFAKEKEY123456")
    job = jobs.create_job(req, key_source="user")
    raw = (jobs.job_dir(job["id"]) / "job.json").read_text()
    assert "AIzaSy" not in raw
    assert job["key_source"] == "user"


def test_read_job_raises_for_unknown_id():
    with pytest.raises(jobs.JobNotFound):
        jobs.read_job("j_20260101_000000_dead")


def test_list_jobs_returns_newest_first():
    first = jobs.create_job(make_request("first"), key_source="server")
    second = jobs.create_job(make_request("second"), key_source="server")
    ids = [j["id"] for j in jobs.list_jobs()]
    assert ids.index(second["id"]) < ids.index(first["id"])


def test_list_jobs_filters_by_status():
    job = jobs.create_job(make_request(), key_source="server")
    jobs.set_status(job["id"], "running", pid=123)
    assert [j["id"] for j in jobs.list_jobs(status="running")] == [job["id"]]
    assert jobs.list_jobs(status="done") == []


def test_terminal_status_is_immutable():
    job = jobs.create_job(make_request(), key_source="server")
    jobs.set_status(job["id"], "running", pid=1)
    jobs.set_status(job["id"], "done")
    with pytest.raises(jobs.InvalidTransition):
        jobs.set_status(job["id"], "running")


def test_write_job_is_atomic_leaves_no_temp_file():
    job = jobs.create_job(make_request(), key_source="server")
    jobs.write_job(job)
    leftovers = [p.name for p in jobs.job_dir(job["id"]).iterdir() if p.suffix == ".tmp"]
    assert leftovers == []
