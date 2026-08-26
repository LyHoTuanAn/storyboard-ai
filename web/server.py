import asyncio
import contextlib
import logging
import shutil
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse

from web import artifacts, events, jobs, keys
from web.progress import redact
from web.schemas import CreateJobRequest

logger = logging.getLogger(__name__)

# Nothing calls jobs.pump() when a job finishes on its own - it is only
# invoked from the create-job and cancel-job routes above, as a side effect
# of *those* requests. Without something else draining the queue, a queued
# job started behind a still-running one at SB_MAX_CONCURRENT stays "queued"
# forever unless a user happens to create or cancel another job. _pump_loop()
# below is that something else: a background task, owned by the app's
# lifespan, that calls the same _pump_and_sweep() the routes use.
#
# 3 seconds: a queued job should not need a human to nudge the queue, but it
# also does not need sub-second responsiveness the way SSE log streaming does
# (events.py polls log.txt every 0.25s because a human is watching it live).
# Nobody is staring at the queue waiting on this tick; a few seconds of extra
# wait after a job finishes is unnoticeable, and anything sub-second would
# turn this into a busy loop that reaps/lists/locks (jobs.pump() takes
# _PUMP_LOCK and touches the filesystem) far more often than useful.
PUMP_INTERVAL_SECONDS = 3.0

# Xoa duoc: cac trang thai ket thuc that su, CONG them "corrupt". Mot job
# corrupt (job.json khong doc duoc) khong nam trong jobs.TERMINAL - co y nhu
# vay, vi TERMINAL con dieu khien cac vong chan cua set_status()/spawn() va
# khong duoc noi rong o do. Nhung tu goc nhin cua route xoa thi no chac chan
# la khong con chay: khong co tien trinh nao, va khong bao gio co nua. Neu
# khong liet ke o day thi mot job corrupt se khong bao gio xoa duoc bang API,
# va cach duy nhat de don no la xoa thu muc bang tay.
DELETABLE = jobs.TERMINAL | {"corrupt"}

# Nhung duoi file ma GET /api/jobs/{id}/file duoc phep phuc vu tho tu dia.
# Route nay ton tai de dua ket qua sinh ra (anh, audio, video) len trinh
# duyet, khong phai de doc bat cu file nao nam trong thu muc job. Truoc khi
# co danh sach nay, `path=job.json` roi thang xuong FileResponse va tra ve
# ban ghi tho - ke ca truong "error" con chua "?key=AIza..." ma
# GET /api/jobs/{id} da loc ky. Chan theo DANH SACH CHO PHEP thay vi loc
# rieng job.json: no dong ca mot lop ro ri tuong lai (file .env, file tam,
# bat cu thu gi pipeline vo tinh ghi vao thu muc job) chu khong chi mot
# truong.
#
# Lay thang tu web/artifacts.py de danh sach nay khong bao gio lech voi thu
# ma collect() that su co the tra ve: them mot duoi anh moi o do la route
# nay phuc vu duoc ngay, khong can nho sua hai cho.
SERVABLE_SUFFIXES = artifacts.IMAGE_SUFFIXES | artifacts.AUDIO_SUFFIXES | artifacts.VIDEO_SUFFIXES

# log.txt khong nam trong danh sach tren (no la .txt) nhung van phai lay
# duoc: web/README.md chi cach doc nhat ky qua route nay, va no da co duong
# rieng ben duoi - doc vao bo nho roi loc key, khong bao gio FileResponse.
LOG_FILE_NAME = "log.txt"


async def _pump_loop() -> None:
    """Background task started by lifespan(): periodically drains the job
    queue so a job that finishes on its own (not via a create/cancel API
    call) still lets the next queued job start. jobs.pump() does blocking
    filesystem work and holds a lock (web/jobs.py's _PUMP_LOCK), so it is run
    off the event loop via asyncio.to_thread - the same pattern web/events.py
    already uses for its blocking log reads (see _read_new_lines there).

    One bad iteration must not kill the loop for every job after it: if
    _pump_and_sweep() raises, log it and keep going rather than letting the
    exception propagate out of the task and silently end the drain.
    """
    while True:
        try:
            await asyncio.to_thread(_pump_and_sweep)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("pump loop: mot vong lap that bai, se thu lai")
        await asyncio.sleep(PUMP_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    jobs.reap_orphans()
    pump_task = asyncio.create_task(_pump_loop())
    app.state.pump_task = pump_task  # exposed for tests (see tests/test_pump_loop.py)
    try:
        yield
    finally:
        pump_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await pump_task


app = FastAPI(title="Storyboard AI", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Same shape as FastAPI's default 422 handler, but with any submitted
    `api_key` value scrubbed - the default handler echoes the raw `input`
    verbatim, which would leak a key sent with the wrong type straight into
    the response body."""
    errors = jsonable_encoder(exc.errors())
    for err in errors:
        loc = err.get("loc", [])
        if "input" in err and any(str(part) == "api_key" for part in loc):
            err["input"] = "***"
    return JSONResponse(status_code=422, content={"detail": errors})


def error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def _active_job_ids() -> set[str]:
    return {job["id"] for job in jobs.list_jobs() if job["status"] not in jobs.TERMINAL}


def _pump_and_sweep() -> None:
    jobs.pump(keys.resolve)
    # Anh chup danh sach job va lenh quet key phai nam TRONG cung mot vung
    # tranh chap. Truoc khi sua, hai lenh nay chay ngoai moi khoa: mot
    # create_job dap dung vao khe giua chung (job da tren dia, key da nho)
    # khong kip co mat trong anh chup, nen sweep() quen mat key vua nho - va
    # luot bom ke tiep bao hong chinh job vua tao ("key khong con nua").
    # Nguoi dung nhan 201 roi thay job hong ngay lap tuc.
    #
    # jobs.pump() o tren tu lay va nha khoa nay ben trong, nen no phai nam
    # NGOAI khoi `with` - threading.Lock khong vao lai duoc. Voi khoa giu o
    # day, moi create_job hoac la xong han truoc anh chup (job co trong anh
    # chup, key duoc giu), hoac la chua bat dau khi sweep chay xong (khong co
    # key nao de quen). Khong con khe o giua.
    with jobs.pump_lock():
        keys.sweep(_active_job_ids())


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


@app.get("/api/health")
def health() -> dict:
    return {
        "ffmpeg": ffmpeg_available(),
        "server_key": keys.server_key() is not None,
        "running": jobs.count_running(),
    }


@app.post("/api/jobs", status_code=201)
def create_job(req: CreateJobRequest) -> dict:
    api_key = req.api_key or keys.server_key()
    if not api_key:
        return error(400, "missing_api_key", "Chua co API key. Nhap key hoac dat GEMINI_API_KEY trong .env")

    key_source = "user" if req.api_key else "server"
    # Tao job va nho key phai la MOT buoc khong the chen vao giua: pump() bao
    # hong mot job "queued" dung key rieng ma no khong phan giai duoc key, va
    # vong lap bom nen chay moi 3 giay. Neu no lot vao dung khe giua
    # create_job() (job.json da nam tren dia, trang thai "queued") va
    # remember() (key chua kip vao bo nho), no se bao hong mot job vua duoc
    # tao dung cach. Giu chung trong cung mot vung tranh chap voi pump().
    with jobs.pump_lock():
        job = jobs.create_job(req, key_source=key_source)
        if key_source == "user":
            keys.remember(job["id"], req.api_key)

    _pump_and_sweep()
    return {"id": job["id"]}


@app.get("/api/jobs")
def list_jobs(status: str | None = None) -> list[dict]:
    return jobs.list_jobs(status=status)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    try:
        return jobs.read_job(job_id)
    except jobs.JobNotFound:
        return error(404, "not_found", f"Khong co job {job_id}")


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    try:
        job = jobs.cancel(job_id)
    except jobs.JobNotFound:
        return error(404, "not_found", f"Khong co job {job_id}")
    except jobs.InvalidTransition as exc:
        return error(409, "already_finished", str(exc))
    keys.forget(job_id)
    _pump_and_sweep()
    return job


@app.get("/api/jobs/{job_id}/events")
def job_events(job_id: str, request: Request):
    try:
        jobs.read_job(job_id)
    except jobs.JobNotFound:
        return error(404, "not_found", f"Khong co job {job_id}")

    start_offset, skip_count = events.parse_resume_id(request.headers.get("Last-Event-ID"))

    return StreamingResponse(
        events.stream_job(job_id, start_offset, skip_count),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/jobs/{job_id}/artifacts")
def job_artifacts(job_id: str):
    try:
        jobs.read_job(job_id)
    except jobs.JobNotFound:
        return error(404, "not_found", f"Khong co job {job_id}")
    return artifacts.collect(job_id)


def _refuse_file() -> JSONResponse:
    """Loi tu choi DUY NHAT cua route tai file.

    Ca hai vong chan (duong dan ra ngoai thu muc job, va file khong phai ket
    qua) tra ve dung mot cau tra loi: nguoi goi khong doan duoc file nao co
    that trong thu muc job qua viec so hai thong bao khac nhau, va giao dien
    chi phai xu ly mot truong hop.
    """
    return error(
        403,
        "forbidden",
        "Route nay chi phuc vu file ket qua cua job (anh, audio, video) va log.txt",
    )


@app.get("/api/jobs/{job_id}/file")
def job_file(job_id: str, path: str):
    try:
        jobs.read_job(job_id)
        target = artifacts.safe_path(job_id, path)
    except jobs.JobNotFound:
        return error(404, "not_found", f"Khong co job {job_id}")
    except artifacts.Forbidden:
        return _refuse_file()

    # log.txt la mot duong ra rieng cua noi dung log, khong di qua SSE - nen
    # no phai duoc loc key o day nua. Doc va loc trong bo nho thay vi
    # FileResponse (gui thang file tho tu dia).
    if target == jobs.job_dir(job_id).resolve() / LOG_FILE_NAME:
        try:
            content = target.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return error(404, "not_found", "Khong doc duoc file nhat ky")
        return Response(content=redact(content), media_type="text/plain; charset=utf-8")

    # Nam trong thu muc job van chua du. FileResponse gui file tho tu dia,
    # khong qua bat cu bo loc nao - nen chi nhung file ma route nay ton tai
    # de phuc vu moi duoc di qua. job.json la vi du cu the: no nam dung trong
    # thu muc job, va truong "error" cua no co the con "?key=AIza...".
    if target.suffix.lower() not in SERVABLE_SUFFIXES:
        return _refuse_file()

    return FileResponse(target)


@app.delete("/api/jobs/{job_id}", status_code=204)
def delete_job(job_id: str):
    try:
        job = jobs.read_job(job_id)
    except jobs.JobNotFound:
        return error(404, "not_found", f"Khong co job {job_id}")
    if job["status"] not in DELETABLE:
        return error(409, "still_running", "Huy job truoc khi xoa")
    shutil.rmtree(jobs.job_dir(job_id), ignore_errors=True)
    keys.forget(job_id)
    return Response(status_code=204)


from fastapi.staticfiles import StaticFiles

from web.settings import get_settings

_DIST = get_settings().repo_root / "web" / "frontend" / "dist"
if _DIST.exists():
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="frontend")
