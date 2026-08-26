"""Giu API key trong bo nho tien trinh server. Khong bao gio ghi xuong dia.

Khong ham nao trong module nay duoc de key lot vao thu gi bi log hay serialize
(response, exception message, repr trong log...). `_KEYS` khong bao gio duoc
tra ve nguyen ven hay expose qua route - chi truy cap gian tiep qua
remember/forget/resolve.
"""

from pathlib import Path

from web.settings import get_settings

_KEYS: dict[str, str] = {}


def env_file() -> Path:
    return get_settings().repo_root / "genai-pipeline" / ".env"


def server_key() -> str | None:
    """Doc GEMINI_API_KEY tu genai-pipeline/.env, hoac None neu khong co.

    Moi loi doc file deu quy ve None thay vi nem ra ngoai: ham nay duoc goi
    tren duong di cua GET /api/health va POST /api/jobs, va mot file .env
    khong doc duoc (thieu quyen, khong phai UTF-8, la thu muc, dia hong...)
    khong duoc phep bien hai route do thanh loi 500. "Khong co key server" la
    cau tra loi dung cho moi truong hop do - giao dien da co san duong xu ly:
    banner canh bao va o nhap key rieng.
    """
    target = env_file()
    try:
        if not target.exists():
            return None
        content = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    for line in content.splitlines():
        if line.startswith("GEMINI_API_KEY="):
            value = line.split("=", 1)[1].strip().strip('"').strip("'")
            return value or None
    return None


def remember(job_id: str, api_key: str) -> None:
    _KEYS[job_id] = api_key


def forget(job_id: str) -> None:
    _KEYS.pop(job_id, None)


def is_remembered(job_id: str) -> bool:
    """True neu con giu key trong bo nho cho job nay.

    Tra ve bool chu KHONG tra ve key - dung cho pump() phan biet "job nay
    khong con key nen phai bao hong" voi "key nay von la key server".
    """
    return job_id in _KEYS


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
