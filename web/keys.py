"""Giu API key trong bo nho tien trinh server. Khong bao gio ghi xuong dia.

Khong ham nao trong module nay duoc de key lot vao thu gi bi log hay serialize
(response, exception message, repr trong log...). `_KEYS` khong bao gio duoc
tra ve nguyen ven hay expose qua route - chi truy cap gian tiep qua
remember/forget/resolve.
"""

from web.settings import get_settings

_KEYS: dict[str, str] = {}


def server_key() -> str | None:
    env_file = get_settings().repo_root / "genai-pipeline" / ".env"
    if not env_file.exists():
        return None
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("GEMINI_API_KEY="):
            value = line.split("=", 1)[1].strip().strip('"').strip("'")
            return value or None
    return None


def remember(job_id: str, api_key: str) -> None:
    _KEYS[job_id] = api_key


def forget(job_id: str) -> None:
    _KEYS.pop(job_id, None)


def sweep(active_job_ids) -> None:
    """Drop every remembered key whose job id is not in `active_job_ids`.

    Once a job is terminal, resolve() will never be called for it again, so
    keeping its key around is pure exposure with no benefit. Only deletes
    from `_KEYS` - never returns a key or `_KEYS` itself.
    """
    active = set(active_job_ids)
    for job_id in list(_KEYS):
        if job_id not in active:
            _KEYS.pop(job_id, None)


def resolve(job: dict) -> str | None:
    if job["key_source"] == "user":
        return _KEYS.get(job["id"])
    return server_key()
