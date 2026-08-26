import asyncio
import json

from web import jobs
from web.progress import parse_line, redact

POLL_SECONDS = 0.25
IDLE_TIMEOUT = 600.0

# "corrupt" (job.json khong doc duoc - xem web/jobs.py:read_job) khong nam
# trong jobs.TERMINAL - co y nhu vay, vi TERMINAL con dieu khien cac vong
# chan cua set_status()/spawn() va khong nen bi noi rong o do. Nhung doi
# voi vong lap stream ben duoi, mot job corrupt CUNG la diem ket thuc: se
# khong bao gio co dong log moi nao duoc ghi cho no, nen cho toi IDLE_TIMEOUT
# (600s) la lang phi thuan tuy. Dinh nghia mot tap hop rieng o day thay vi
# viet chuoi "corrupt" lap lai trong dieu kien.
END_STATUSES = jobs.TERMINAL | {"corrupt"}


def format_sse(event: str, data: dict, offset: int, index: int = 0) -> str:
    """`id:` is `<offset>:<index>` - offset is the byte position of the
    START of the log line this event was derived from, index is this
    event's 0-based position among the (possibly several) events produced
    for that same line (the `log` event itself, plus 0-1 derived
    step/scene/activity/warning events). Giving every event its own id -
    not just every line - lets a client resume from the exact event it last
    received instead of only from the last fully-consumed line."""
    payload = json.dumps(data, ensure_ascii=False, separators=(", ", ": "))
    return f"id: {offset}:{index}\nevent: {event}\ndata: {payload}\n\n"


def parse_resume_id(raw: str | None) -> tuple[int, int]:
    """Parse a `Last-Event-ID` header value into `(offset, skip_count)`.

    `offset` is where to seek in log.txt - the start of the log line whose
    events the client was mid-way through (or 0 for a fresh connection).
    `skip_count` is how many of that line's events (in emission order) have
    already reached the client and must not be re-sent.

    - No header (fresh connection): (0, 0) - start at the top, skip nothing.
    - `"<offset>:<n>"`: the client's last received event was sub-index `n`
      of the line starting at `offset`, so skip the first `n + 1` events
      produced for that line.
    - A bare `"<offset>"` (no colon) is accepted for backward compatibility
      and treated as sub-index 0, i.e. skip the first 1 event.
    - Anything else unparseable: treated the same as no header - start over
      from offset 0 rather than raising.
    """
    if raw is None:
        return 0, 0

    offset_part, sep, index_part = raw.partition(":")
    if not sep:
        if offset_part.isdigit():
            return int(offset_part), 1
        return 0, 0

    if offset_part.isdigit() and index_part.isdigit():
        return int(offset_part), int(index_part) + 1
    return 0, 0


def _read_new_lines(log_path, offset: int) -> list[tuple[str, int, int]]:
    """Blocking: doc log.txt tu offset, tra ve cac dong da hoan chinh dang
    (dong, offset-bat-dau-dong, offset-sau-dong). offset-bat-dau-dong la id
    goc dung cho tat ca cac su kien sinh ra tu dong do; offset-sau-dong la vi
    tri con tro doc se tiep tuc cho dong ke tiep. Chay trong thread rieng qua
    asyncio.to_thread vi day la I/O dong bo.
    """
    result: list[tuple[str, int, int]] = []
    if not log_path.exists():
        return result

    with log_path.open("r", encoding="utf-8", errors="replace") as stream:
        stream.seek(offset)
        while True:
            # readline() (not `for raw in stream`) - iterating a text file
            # uses read-ahead buffering, which makes stream.tell() raise
            # "OSError: telling position disabled by next() call".
            # readline() reads exactly one line at a time and keeps tell()
            # valid before and after each call.
            line_start = stream.tell()
            raw = stream.readline()
            if not raw:
                break
            if not raw.endswith("\n"):
                break  # dong con dang duoc ghi, cho luot sau
            result.append((raw.rstrip("\n"), line_start, stream.tell()))
    return result


async def stream_job(job_id: str, start_offset: int = 0, skip_count: int = 0):
    """Doc log.txt theo byte offset. Moi su kien mang mot id `<offset>:<n>`
    rieng - offset la vi tri bat dau cua dong log sinh ra no, n la thu tu
    cua su kien do trong so cac su kien cua chinh dong do. skip_count (chi
    ap dung cho dong DAU TIEN gap phai, khi resume giua chung mot dong) bo
    qua nhung su kien dong do ma client da nhan trong lan ket noi truoc."""
    log_path = jobs.job_dir(job_id) / "log.txt"
    cursor = start_offset
    pending_skip = skip_count
    idle = 0.0

    while True:
        job = await asyncio.to_thread(jobs.read_job, job_id)

        new_lines = await asyncio.to_thread(_read_new_lines, log_path, cursor)
        for raw_line, line_offset, line_end in new_lines:
            line = redact(raw_line)
            produced = [("log", {"line": line})]
            parsed = parse_line(line)
            if parsed:
                produced.append((parsed["event"], parsed["data"]))

            skip_here = pending_skip
            pending_skip = 0  # skip only applies to the first line after resume
            for index, (name, data) in enumerate(produced):
                if index < skip_here:
                    continue
                yield format_sse(name, data, line_offset, index)

            cursor = line_end
            idle = 0.0

        if job["status"] in END_STATUSES:
            yield format_sse(
                "status",
                {
                    "status": job["status"],
                    "exit_code": job.get("exit_code"),
                    "result_video": job.get("result_video"),
                    "error": redact(job["error"]) if job.get("error") else None,
                },
                cursor,
            )
            return

        await asyncio.sleep(POLL_SECONDS)
        idle += POLL_SECONDS
        if idle >= IDLE_TIMEOUT:
            yield format_sse("status", {"status": job["status"], "stalled": True}, cursor)
            return
