import os
import time

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
