import shutil
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response

from web import jobs, keys
from web.schemas import CreateJobRequest


@asynccontextmanager
async def lifespan(app: FastAPI):
    jobs.reap_orphans()
    yield


app = FastAPI(title="Storyboard AI", lifespan=lifespan)


def error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


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

    jobs.pump(keys.resolve)
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
    jobs.pump(keys.resolve)
    return job


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
