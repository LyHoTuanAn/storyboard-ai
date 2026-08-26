import shutil
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse

from web import artifacts, events, jobs, keys
from web.schemas import CreateJobRequest


@asynccontextmanager
async def lifespan(app: FastAPI):
    jobs.reap_orphans()
    yield


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
