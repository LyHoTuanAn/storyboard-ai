import os
import subprocess
import sys
from pathlib import Path

from web import jobs
from web.schemas import CreateJobRequest, JobParams
from web.settings import get_settings


def test_fake_runner_completes_and_writes_artifacts():
    job = jobs.create_job(
        CreateJobRequest(params=JobParams(context="Fake topic")), key_source="server"
    )
    directory = jobs.job_dir(job["id"])

    env = dict(os.environ)
    env["SB_FAKE_PIPELINE"] = "1"
    env["SB_JOBS_DIR"] = str(get_settings().jobs_dir)
    env["PYTHONPATH"] = str(get_settings().repo_root)

    with (directory / "log.txt").open("ab") as log:
        exit_code = subprocess.call(
            [sys.executable, "-u", "-m", "web.runner", job["id"]],
            cwd=directory,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )

    assert exit_code == 0

    updated = jobs.read_job(job["id"])
    assert updated["status"] == "done"
    assert updated["result_video"]
    assert Path(directory / updated["result_video"]).exists()

    log_text = (directory / "log.txt").read_text()
    assert "Step 1:" in log_text
    assert "--- Processing Scene 1/2 ---" in log_text
    assert "--- Processing Scene 2/2 ---" in log_text


def test_fake_runner_emits_a_skipped_scene_warning():
    job = jobs.create_job(
        CreateJobRequest(params=JobParams(context="Fake topic")), key_source="server"
    )
    directory = jobs.job_dir(job["id"])
    env = dict(os.environ)
    env["SB_FAKE_PIPELINE"] = "1"
    env["SB_FAKE_SKIP_SCENE"] = "2"
    env["SB_JOBS_DIR"] = str(get_settings().jobs_dir)
    env["PYTHONPATH"] = str(get_settings().repo_root)

    with (directory / "log.txt").open("ab") as log:
        subprocess.call(
            [sys.executable, "-u", "-m", "web.runner", job["id"]],
            cwd=directory,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )

    assert "[X] SKIPPING Scene 2:" in (directory / "log.txt").read_text()
