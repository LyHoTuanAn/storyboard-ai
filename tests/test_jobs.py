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


def test_job_dir_rejects_id_with_trailing_newline():
    with pytest.raises(jobs.JobNotFound):
        jobs.job_dir("j_20260101_000000_dead\n")


def _corrupt(job_id):
    (jobs.job_dir(job_id) / "job.json").write_text("{not valid json", encoding="utf-8")


def test_read_job_returns_corrupt_shape_instead_of_raising():
    """Regression: read_job() used to let json.JSONDecodeError escape
    uncaught for an unreadable job.json, which is what turned GET
    /api/jobs/{id} into a 500 while GET /api/jobs (via list_jobs, which
    already caught this) returned 200. read_job() must now return the same
    reduced shape list_jobs() has always produced for this case."""
    job = jobs.create_job(make_request(), key_source="server")
    _corrupt(job["id"])
    assert jobs.read_job(job["id"]) == {"id": job["id"], "status": "corrupt"}


def test_list_jobs_and_read_job_agree_on_a_corrupt_job():
    job = jobs.create_job(make_request(), key_source="server")
    _corrupt(job["id"])
    from_list = next(j for j in jobs.list_jobs() if j["id"] == job["id"])
    assert from_list == jobs.read_job(job["id"]) == {"id": job["id"], "status": "corrupt"}


def test_set_status_refuses_a_corrupt_job():
    """A corrupt job must not be silently transitioned - set_status() has no
    started_at/models/etc to work with, and overwriting a broken record with
    a clean-looking status would hide that anything went wrong."""
    job = jobs.create_job(make_request(), key_source="server")
    _corrupt(job["id"])
    with pytest.raises(jobs.InvalidTransition):
        jobs.set_status(job["id"], "running", pid=1)
    # Still corrupt afterwards - the failed attempt must not have written
    # anything.
    assert jobs.read_job(job["id"])["status"] == "corrupt"


def test_create_job_retries_on_collision(monkeypatch):
    # Create first job
    first = jobs.create_job(make_request("first"), key_source="server")
    first_context = first["params"]["context"]

    # Monkeypatch new_job_id to return first's ID for one call, then a new ID
    call_count = [0]
    original_new_job_id = jobs.new_job_id

    def colliding_new_job_id():
        call_count[0] += 1
        if call_count[0] == 1:
            return first["id"]  # Collide with existing job
        return original_new_job_id()  # Generate new ID on retry

    monkeypatch.setattr(jobs, "new_job_id", colliding_new_job_id)

    # Try to create second job - should retry and succeed
    second = jobs.create_job(make_request("second"), key_source="server")

    # Verify first job is unchanged
    first_reread = jobs.read_job(first["id"])
    assert first_reread["params"]["context"] == first_context

    # Verify second job is different
    assert second["id"] != first["id"]
    assert second["params"]["context"] == "second"
