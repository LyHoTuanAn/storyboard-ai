import json
import os
import secrets
import signal
import subprocess
import sys
import tempfile
import threading
import time
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
    if not JOB_ID_RE.fullmatch(job_id):
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
    job_id = None
    for attempt in range(10):
        candidate = new_job_id()
        if not job_dir(candidate).exists():
            job_id = candidate
            break
    if job_id is None:
        raise RuntimeError("Could not generate unique job ID after 10 attempts")

    job = {
        "id": job_id,
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


# Popen objects for children spawned by *this* process, keyed by job id. Used
# by reap_orphans() to detect exit via poll() instead of relying on pid_alive,
# which cannot see a zombie (see the comment on pid_alive below).
_PROCESSES: dict[str, subprocess.Popen] = {}


def build_env(job: dict, api_key: str) -> dict:
    settings = get_settings()
    env = dict(os.environ)
    for name in [n for n in env if n.endswith(("_API_KEY", "_TOKEN", "_SECRET"))]:
        del env[name]
    env["GEMINI_API_KEY"] = api_key
    env["SB_JOBS_DIR"] = str(settings.jobs_dir)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(settings.repo_root), str(settings.repo_root / "genai-pipeline")]
    )
    for name, value in job["models"].items():
        if value:
            env[f"SB_{name}"] = value
    return env


def spawn(job_id: str, api_key: str) -> int:
    directory = job_dir(job_id)
    job = read_job(job_id)
    log_path = directory / "log.txt"
    with log_path.open("ab") as log:
        process = subprocess.Popen(
            [sys.executable, "-u", "-m", "web.runner", job_id],
            cwd=directory,
            env=build_env(job, api_key),
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    _PROCESSES[job_id] = process
    set_status(job_id, "running", pid=process.pid)
    return process.pid


def pid_alive(pid: int) -> bool:
    """Chi dang tin cay cho tien trinh KHONG do server nay spawn.

    Voi mot tien trinh con thuc su cua process nay, sau khi no thoat no tro
    thanh zombie cho toi khi bi wait()/poll() - va os.kill(pid, 0) van thanh
    cong tren mot zombie, nen se tra ve True mai mai. Doi voi job co Popen
    duoc theo doi trong _PROCESSES, reap_orphans() dung process.poll() thay
    vi ham nay. Ham nay chi dung dung cho truong hop pid khong con trong
    _PROCESSES (vi du sau khi server restart: tien trinh do da duoc init
    "nhan nuoi" va reap, nen os.kill se thuc su bao ProcessLookupError).
    """
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def log_tail(job_id: str, lines: int = 50) -> str:
    log_path = job_dir(job_id) / "log.txt"
    if not log_path.exists():
        return ""
    content = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(content[-lines:])


def reap_orphans() -> list[str]:
    reaped = []

    # Phase 0: sweep every tracked child regardless of the job's current
    # status. A job that finished on its own (e.g. reached "done") stops
    # appearing in list_jobs(status="running"), so phase 1 below would never
    # visit it again - without this sweep its Popen would stay in
    # _PROCESSES forever and its OS process would stay a zombie until this
    # server exits. Reap here; remember the exit code for phase 1 to use for
    # jobs that are still "running" (that is the crash-without-reporting
    # case reap_orphans exists for).
    exit_codes: dict[str, int] = {}
    for job_id, process in list(_PROCESSES.items()):
        exit_code = process.poll()
        if exit_code is None:
            continue
        del _PROCESSES[job_id]
        exit_codes[job_id] = exit_code

    for job in list_jobs(status="running"):
        job_id = job["id"]

        if job_id in exit_codes:
            exit_code = exit_codes[job_id]
            status = "failed" if exit_code else "interrupted"
            set_status(
                job_id,
                status,
                exit_code=exit_code,
                error="Tien trinh chay job da chet ma khong bao ket qua.\n\n"
                + log_tail(job_id),
            )
            reaped.append(job_id)
            continue

        pid = job.get("pid")
        if pid is None or not pid_alive(pid):
            set_status(
                job_id,
                "interrupted",
                error="Tien trinh chay job da chet ma khong bao ket qua.\n\n"
                + log_tail(job_id),
            )
            reaped.append(job_id)
    return reaped


def count_running() -> int:
    return len(list_jobs(status="running"))


def cancel(job_id: str) -> dict:
    job = read_job(job_id)
    if job["status"] in TERMINAL:
        raise InvalidTransition(f"{job_id} da o trang thai {job['status']}")

    pid = job.get("pid")
    if job["status"] == "running" and pid:
        process = _PROCESSES.get(job_id)

        def _still_alive() -> bool:
            if process is not None:
                return process.poll() is None
            return pid_alive(pid)

        try:
            group = os.getpgid(pid)
            os.killpg(group, signal.SIGTERM)
            for _ in range(50):
                if not _still_alive():
                    break
                time.sleep(0.1)
            if _still_alive():
                os.killpg(group, signal.SIGKILL)
        except ProcessLookupError:
            pass
        finally:
            _PROCESSES.pop(job_id, None)

    return set_status(job_id, "cancelled")


# Serializes pump() so two concurrent callers (e.g. two FastAPI request
# threads) cannot both observe count_running() < max_concurrent and both
# spawn - the reap, the count, and the spawn loop all happen inside one
# critical section. Scoped to pump() only; cancel()/set_status() are
# unaffected.
_PUMP_LOCK = threading.Lock()


def pump(key_resolver) -> list[str]:
    with _PUMP_LOCK:
        settings = get_settings()
        reap_orphans()  # tien trinh chet dot ngot van dang chiem cho, phai don truoc
        started = []
        for job in sorted(
            list_jobs(status="queued"), key=lambda item: item.get("created_at", "")
        ):
            if count_running() >= settings.max_concurrent:
                break
            api_key = key_resolver(job)
            if not api_key:
                continue
            spawn(job["id"], api_key)
            started.append(job["id"])
        return started
