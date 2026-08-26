import asyncio
import json

from web import jobs
from web.progress import parse_line, redact

POLL_SECONDS = 0.25
IDLE_TIMEOUT = 600.0


def format_sse(event: str, data: dict, event_id: int) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(", ", ": "))
    return f"id: {event_id}\nevent: {event}\ndata: {payload}\n\n"


def _read_new_lines(log_path, offset: int) -> list[tuple[str, int]]:
    """Blocking: doc log.txt tu offset, tra ve cac (dong, offset-sau-dong-do) da hoan chinh.

    Offset gan cho tung dong la vi tri byte NGAY SAU khi dong do duoc doc - do
    chinh la gia tri se dung lam SSE id cho dong nay, nen phai giu rieng cho
    tung dong thay vi chi tra ve offset cuoi cung. Chay trong thread rieng qua
    asyncio.to_thread vi day la I/O dong bo.
    """
    result: list[tuple[str, int]] = []
    if not log_path.exists():
        return result

    with log_path.open("r", encoding="utf-8", errors="replace") as stream:
        stream.seek(offset)
        while True:
            # readline() (not `for raw in stream`) - iterating a text file
            # uses read-ahead buffering, which makes stream.tell() raise
            # "OSError: telling position disabled by next() call".
            # readline() reads exactly one line at a time and keeps tell()
            # valid after each call.
            raw = stream.readline()
            if not raw:
                break
            if not raw.endswith("\n"):
                break  # dong con dang duoc ghi, cho luot sau
            result.append((raw.rstrip("\n"), stream.tell()))
    return result


async def stream_job(job_id: str, start_offset: int = 0):
    """Doc log.txt theo byte offset. event_id chinh la offset sau khi doc dong do."""
    log_path = jobs.job_dir(job_id) / "log.txt"
    offset = start_offset
    idle = 0.0

    while True:
        job = await asyncio.to_thread(jobs.read_job, job_id)

        new_lines = await asyncio.to_thread(_read_new_lines, log_path, offset)
        for raw_line, offset in new_lines:
            line = redact(raw_line)
            yield format_sse("log", {"line": line}, offset)
            parsed = parse_line(line)
            if parsed:
                yield format_sse(parsed["event"], parsed["data"], offset)
            idle = 0.0

        if job["status"] in jobs.TERMINAL:
            yield format_sse(
                "status",
                {
                    "status": job["status"],
                    "exit_code": job.get("exit_code"),
                    "result_video": job.get("result_video"),
                    "error": redact(job["error"]) if job.get("error") else None,
                },
                offset,
            )
            return

        await asyncio.sleep(POLL_SECONDS)
        idle += POLL_SECONDS
        if idle >= IDLE_TIMEOUT:
            yield format_sse("status", {"status": job["status"], "stalled": True}, offset)
            return
