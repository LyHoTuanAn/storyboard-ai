import pytest

from web.settings import get_settings


@pytest.fixture(autouse=True)
def isolated_jobs_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SB_JOBS_DIR", str(tmp_path / "jobs"))
    monkeypatch.setenv("SB_MAX_CONCURRENT", "1")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
