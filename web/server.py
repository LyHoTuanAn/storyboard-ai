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


@app.get("/api/jobs/{job_id}/file")
def job_file(job_id: str, path: str):
    try:
        jobs.read_job(job_id)
        return FileResponse(artifacts.safe_path(job_id, path))
    except jobs.JobNotFound:
        return error(404, "not_found", f"Khong co job {job_id}")
    except artifacts.Forbidden:
        return error(403, "forbidden", "Duong dan nam ngoai thu muc job")


@app.delete("/api/jobs/{job_id}", status_code=204)
def delete_job(job_id: str):
    try:
        job = jobs.read_job(job_id)
    except jobs.JobNotFound:
        return error(404, "not_found", f"Khong co job {job_id}")
    if job["status"] not in jobs.TERMINAL:
        return error(409, "still_running", "Huy job truoc khi xoa")
    shutil.rmtree(jobs.job_dir(job_id), ignore_errors=True)
    keys.forget(job_id)
    return Response(status_code=204)


from fastapi.staticfiles import StaticFiles

from web.settings import get_settings

_DIST = get_settings().repo_root / "web" / "frontend" / "dist"
if _DIST.exists():
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="frontend")
