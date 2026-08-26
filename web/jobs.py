import json
import os
import secrets
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from web.schemas import JOB_ID_RE, CreateJobRequest
from web.settings import get_settings

TERMINAL = {"done", "failed", "cancelled", "interrupted"}


class JobNotFound(Exception):
    pass


class InvalidTransition(Exception):
    pass


def new_job_id() -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"j_{stamp}_{secrets.token_hex(2)}"


def job_dir(job_id: str) -> Path:
    if not JOB_ID_RE.match(job_id):
        raise JobNotFound(job_id)
    return get_settings().jobs_dir / job_id


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def write_job(job: dict) -> None:
    directory = job_dir(job["id"])
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "job.json"
    handle, temp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(job, stream, ensure_ascii=False, indent=2)
        os.replace(temp_path, target)
    except BaseException:
        Path(temp_path).unlink(missing_ok=True)
        raise


def read_job(job_id: str) -> dict:
    target = job_dir(job_id) / "job.json"
    if not target.exists():
        raise JobNotFound(job_id)
    return json.loads(target.read_text(encoding="utf-8"))


def create_job(req: CreateJobRequest, key_source: str) -> dict:
    job = {
        "id": new_job_id(),
        "status": "queued",
        "created_at": _now(),
        "started_at": None,
        "finished_at": None,
        "params": req.params.model_dump(),
        "models": req.models.model_dump(),
        "key_source": key_source,
        "pid": None,
        "exit_code": None,
        "result_video": None,
        "error": None,
        "progress": {"step": None, "scene": None, "total_scenes": None},
    }
    write_job(job)
    (job_dir(job["id"]) / "log.txt").touch()
    return job


def list_jobs(status: str | None = None) -> list[dict]:
    root = get_settings().jobs_dir
    if not root.exists():
        return []
    found = []
    for directory in root.iterdir():
        if not JOB_ID_RE.match(directory.name):
            continue
        try:
            found.append(read_job(directory.name))
        except (JobNotFound, json.JSONDecodeError):
            found.append({"id": directory.name, "status": "corrupt"})
    found.sort(key=lambda job: job.get("created_at", ""), reverse=True)
    if status:
        found = [job for job in found if job.get("status") == status]
    return found


def set_status(job_id: str, status: str, **fields) -> dict:
    job = read_job(job_id)
    if job["status"] in TERMINAL:
        raise InvalidTransition(f"{job_id} da o trang thai {job['status']}")
    job["status"] = status
    if status == "running" and not job["started_at"]:
        job["started_at"] = _now()
    if status in TERMINAL:
        job["finished_at"] = _now()
    job.update(fields)
    write_job(job)
    return job
