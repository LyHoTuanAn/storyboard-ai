import pytest

from web.settings import get_settings


@pytest.fixture(autouse=True)
def isolated_jobs_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SB_JOBS_DIR", str(tmp_path / "jobs"))
    monkeypatch.setenv("SB_MAX_CONCURRENT", "1")
    # Goc du an cung phai duoc cach ly, khong chi thu muc job: neu khong,
    # keys.server_key() doc `genai-pipeline/.env` that cua may dang chay, va
    # bo test se cho ket qua khac nhau tuy may co file do hay khong. Tro vao
    # mot thu muc tam (khong ton tai) de server_key() luon la None tru khi
    # chinh bai test tu tao file .env trong do.
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SB_REPO_ROOT", str(repo_root))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
