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

from web import keys
from web.progress import redact
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
    try:
        job = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # job.json ton tai nhung khong doc duoc (ghi do dang, dia hong, bi
        # sua tay...). Tra ve dung "hinh dang rut gon" ma list_jobs() da
        # dung cho truong hop nay, de GET /api/jobs va GET /api/jobs/{id}
        # luon nhat quan - khong bao gio mot ben tra ve OK con ben kia nem
        # loi 500 cho cung mot job. Moi noi goi read_job() phai tu coi
        # status == "corrupt" la mot trang thai khong the chuyen doi (xem
        # set_status/spawn ben duoi).
        return {"id": job_id, "status": "corrupt"}
    # Loc key mot lan nua o duong DOC, khong chi o duong ghi: mot job.json
    # duoc ghi boi phien ban truoc (hoac boi tay) van co the con key trong
    # truong "error", va gia tri do di thang ra GET /api/jobs/{id} roi len
    # man hinh. redact() la ham thuan tuy va re, chay no o day de moi nguoi
    # doc job.json deu nhan duoc ban da loc.
    if isinstance(job.get("error"), str):
        job["error"] = redact(job["error"])
    return job


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
    if job["status"] == "corrupt":
        # job.json khong doc duoc - khong co gi de doc truong ("started_at",
        # "models"...) ma doan code ben duoi can, va viec ghi de mot trang
        # thai "sach" len tren mot ban ghi da hong se che mat that su co
        # chuyen gi xay ra. Tu choi chuyen doi thay vi lang le "hoi sinh" no.
        raise InvalidTransition(f"{job_id} co job.json khong doc duoc, khong the chuyen trang thai")
    if job["status"] in TERMINAL:
        raise InvalidTransition(f"{job_id} da o trang thai {job['status']}")
    job["status"] = status
    if status == "running" and not job["started_at"]:
        job["started_at"] = _now()
    if status in TERMINAL:
        job["finished_at"] = _now()
    # Diem nghen duy nhat ma moi thu di vao job.json phai di qua. Loc key o
    # day, khong phai o tung noi goi: spec noi key khong bao gio duoc ghi vao
    # job.json, va mot thong bao loi cua google.genai co the chua ca URL yeu
    # cau kem "?key=AIza...". Loc ca cac truong chuoi khac vi cung mot ly do -
    # chi phi la mot vai regex tren mot ban ghi nho.
    for name, value in list(fields.items()):
        if isinstance(value, str):
            fields[name] = redact(value)
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
    env["SB_REPO_ROOT"] = str(settings.repo_root)
    # code_root (noi goi `web` nam), khong phai repo_root: tien trinh con chay
    # `python -m web.runner`, nen PYTHONPATH phai tro vao thu muc chua goi
    # `web` - dieu do dung ke ca khi repo_root bi tro di cho khac (test).
    env["PYTHONPATH"] = os.pathsep.join(
        [str(settings.code_root), str(settings.repo_root / "genai-pipeline")]
    )
    # .get(..., {}) chu khong phai job["models"]: mot job "corrupt" (job.json
    # khong doc duoc) khong co khoa nay. spawn() da chan job corrupt truoc
    # khi goi ham nay, nhung giu ham nay tu ve phong khi co loi goi truc
    # tiep khac trong tuong lai.
    for name, value in job.get("models", {}).items():
        if value:
            env[f"SB_{name}"] = value
    return env


def process_start_time(pid: int) -> str | None:
    """Thoi diem tien trinh `pid` bat dau chay (chuoi tho tu `ps`), hoac None.

    Rieng PID thi KHONG dinh danh duoc mot tien trinh: he dieu hanh tai su
    dung PID, nen sau khi server restart, PID ghi trong job.json co the dang
    thuoc ve mot tien trinh hoan toan khac cua nguoi khac. Cap (pid, thoi
    diem bat dau) thi khong bi tai su dung - ghi kem gia tri nay khi spawn va
    doi no khop lai truoc khi coi PID do la tien trinh cua job (pid_is_ours).
    """
    try:
        result = subprocess.run(
            ["ps", "-o", "lstart=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def pid_is_ours(job: dict) -> bool:
    """True neu PID ghi trong job.json van dung la tien trinh cua job nay.

    Doi hoi CA hai: PID con song, VA thoi diem bat dau cua no khop voi gia
    tri da ghi luc spawn. Mot ban ghi khong co "pid_start" (job.json viet boi
    phien ban truoc) khong the xac minh duoc, nen bi coi la khong phai cua
    minh - tha danh dau job do "Bi ngat" (nguoi dung tao lai duoc) con hon de
    no giu cho chay mai mai, hoac te hon la de Huy ban SIGKILL vao mot tien
    trinh la dang tinh co mang dung PID do.
    """
    pid = job.get("pid")
    if not pid:
        return False
    if not pid_alive(pid):
        return False
    recorded = job.get("pid_start")
    if not recorded:
        return False
    return process_start_time(pid) == recorded


def _terminate_group(pid: int, process: subprocess.Popen | None = None) -> None:
    """SIGTERM ca nhom tien trinh, doi toi 5s, roi SIGKILL neu con song."""

    def still_alive() -> bool:
        if process is not None:
            return process.poll() is None
        return pid_alive(pid)

    try:
        group = os.getpgid(pid)
        os.killpg(group, signal.SIGTERM)
        for _ in range(50):
            if not still_alive():
                break
            time.sleep(0.1)
        if still_alive():
            os.killpg(group, signal.SIGKILL)
    except ProcessLookupError:
        pass


def spawn(job_id: str, api_key: str) -> int:
    directory = job_dir(job_id)
    job = read_job(job_id)
    if job["status"] == "corrupt":
        # pump() chi spawn tu list_jobs(status="queued"), nen mot job corrupt
        # (status "corrupt") se khong bao gio lot vao day qua duong di binh
        # thuong - day la vong chan phong ve cho nguoi goi truc tiep khac.
        raise InvalidTransition(f"{job_id} co job.json khong doc duoc, khong the spawn")
    if job["status"] != "queued":
        # Kiem tra lai NGAY TRUOC khi phong tien trinh, khong tin vao anh chup
        # cua list_jobs() ma pump() dang duyet: giua luc chup va luc toi day,
        # job co the da bi Huy. Neu van phong, nguoi dung se thay "Da huy"
        # trong khi mot tien trinh that van dang dot quota API va khong con
        # cach nao huy tu giao dien nua.
        raise InvalidTransition(
            f"{job_id} khong con o trang thai queued (dang la {job['status']}), khong spawn"
        )
    log_path = directory / "log.txt"
    with log_path.open("ab") as log:
        process = subprocess.Popen(
            [sys.executable, "-u", "-m", "web.runner", job_id],
            cwd=directory,
            env=build_env(job, api_key),
            stdout=log,
            stderr=subprocess.STDOUT,
            # Pipeline duoc boc lai von la chuong trinh tuong tac. Neu con sot
            # mot loi goi input() nao do, viec ke thua stdin cua server se lam
            # job treo vinh vien, giu cho chay ma khong in ra gi. DEVNULL bien
            # tinh huong do thanh EOF - job hong ngay va nha cho ra.
            stdin=subprocess.DEVNULL,
            # Nhom tien trinh rieng: Huy job phai giet duoc CA cay tien trinh
            # con (ffmpeg...), va tuyet doi khong duoc cham vao nhom cua
            # chinh server. Bo co nay di la os.killpg() trong cancel() se ban
            # vao nhom cua server.
            start_new_session=True,
        )
    _PROCESSES[job_id] = process
    try:
        set_status(
            job_id,
            "running",
            pid=process.pid,
            pid_start=process_start_time(process.pid),
        )
    except BaseException:
        # Job da roi khoi "queued" trong luc ta phong tien trinh (thuong la bi
        # Huy). Tien trinh con vua sinh ra khong con ai so huu - giet no thay
        # vi de no chay mo coi.
        _PROCESSES.pop(job_id, None)
        _terminate_group(process.pid, process)
        raise
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
    """Cac dong cuoi cua log, DA loc key.

    Gia tri tra ve di thang vao truong "error" cua job.json, roi ra
    GET /api/jobs/{id} va len man hinh - nen no phai da sach truoc khi roi
    khoi ham nay, khong phu thuoc vao viec nguoi goi co nho loc hay khong.
    """
    log_path = job_dir(job_id) / "log.txt"
    if not log_path.exists():
        return ""
    content = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return redact("\n".join(content[-lines:]))


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

        # list_jobs(status="running") da loai job "corrupt" (status cua no
        # khong phai "running"), nen nhanh nay chi xu ly duoc job ma
        # set_status() con chap nhan. Nhung job.json van co the hong DUNG LUC
        # giua thoi diem snapshot list_jobs() o tren va lenh set_status() ben
        # duoi (vi du bi sua tay); khi do set_status se nem InvalidTransition.
        # Bat no o day de mot job hong khong lam sap ca vong quet - bo qua
        # job do va tiep tuc voi cac job con lai.
        try:
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

            if job_id in _PROCESSES:
                # Con duoc theo doi va phase 0 khong reap duoc no, tuc la
                # process.poll() la None: tien trinh chac chan la cua ta va
                # dang song. Khong can hoi lai he dieu hanh (pid_is_ours goi
                # `ps`, mot tien trinh con nua, moi 3 giay mot lan).
                continue

            if not pid_is_ours(job):
                set_status(
                    job_id,
                    "interrupted",
                    error="Tien trinh chay job da chet ma khong bao ket qua.\n\n"
                    + log_tail(job_id),
                )
                reaped.append(job_id)
        except InvalidTransition:
            continue
    return reaped


def count_running() -> int:
    return len(list_jobs(status="running"))


# Serializes the whole queue critical section - pump()'s reap + count + spawn
# loop, and cancel(). Two concurrent pump() callers (FastAPI runs route
# handlers in a threadpool, and a background task calls pump() too) must not
# both observe count_running() < max_concurrent and both spawn. cancel() takes
# the SAME lock, not a separate one: otherwise a cancel landing in the middle
# of a pump iteration writes "cancelled" while pump is already committed to
# launching that job, and the user ends up watching a "cancelled" job whose
# real child keeps running.
_PUMP_LOCK = threading.Lock()


def pump_lock():
    """The queue critical section, for callers that must be atomic against it.

    web/server.py's create-job route uses this to create a job and remember
    its key as one indivisible step: pump() fails a queued user-key job whose
    key it cannot resolve, so a pump iteration must never be able to run in
    the gap between "job.json written" and "key remembered".
    """
    return _PUMP_LOCK


def cancel(job_id: str) -> dict:
    with _PUMP_LOCK:
        job = read_job(job_id)
        if job["status"] in TERMINAL:
            raise InvalidTransition(f"{job_id} da o trang thai {job['status']}")

        pid = job.get("pid")
        if job["status"] == "running" and pid:
            process = _PROCESSES.get(job_id)
            # process is not None: tien trinh nay do chinh server dang chay
            # sinh ra, chac chan la cua job nay. Nguoc lai (sau khi server
            # restart) chi con PID tren dia, va PID thi bi he dieu hanh tai su
            # dung - phai doi thoi diem bat dau khop moi duoc ban tin hieu,
            # neu khong Huy se SIGKILL nham mot tien trinh la.
            if process is not None or pid_is_ours(job):
                try:
                    _terminate_group(pid, process)
                finally:
                    _PROCESSES.pop(job_id, None)

        return set_status(job_id, "cancelled")


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
                if job.get("key_source") == "user" and not keys.is_remembered(job["id"]):
                    # Key rieng cua nguoi dung chi song trong bo nho server.
                    # Job van con tren dia sau khi server restart, key thi
                    # khong - khong co gi se lam no xuat hien tro lai, nen
                    # "cho tiep" o day nghia la cho mai mai va im lang. Bao
                    # hong ngay, kem ly do, de nguoi dung biet phai tao lai.
                    #
                    # Rieng key_source == "server" thi khong: key server nam
                    # trong genai-pipeline/.env, nguoi dung co the them vao
                    # trong luc job dang cho va job chay tiep binh thuong.
                    try:
                        set_status(
                            job["id"],
                            "failed",
                            error="API key rieng cua job nay khong con nua "
                            "(key chi duoc giu trong bo nho server, va server "
                            "da khoi dong lai). Hay tao lai job voi key moi.",
                        )
                    except InvalidTransition:
                        pass
                continue
            try:
                spawn(job["id"], api_key)
            except InvalidTransition:
                # job.json bi hong, hoac job da chuyen trang thai o noi khac
                # (vi du bi huy) giua luc list_jobs() chup snapshot va luc
                # spawn() o day - bo qua job do, dung de no lam sap ca vong
                # pump.
                continue
            started.append(job["id"])
        return started
