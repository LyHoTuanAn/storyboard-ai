"""keys.server_key() va viec cach ly no khoi may dang chay.

Truoc khi sua, tests/conftest.py chi cach ly SB_JOBS_DIR chu khong cach ly
goc du an, nen ca bo test doc `genai-pipeline/.env` THAT cua may lap trinh
vien: tren may co file do thi server_key() tra ve key that, tren may khac
tra ve None, va khong bai test nao noi duoc no dang kiem tra dieu gi.
"""

from fastapi.testclient import TestClient

from web import keys
from web.server import app
from web.settings import get_settings

client = TestClient(app)


def test_server_key_is_isolated_from_the_developers_env_file():
    """Fixture trong conftest phai tro goc du an vao mot thu muc tam. Neu
    khong, gia tri duoi day tuy thuoc vao may dang chay."""
    assert get_settings().repo_root != get_settings().code_root
    assert not keys.env_file().exists()
    assert keys.server_key() is None


def test_server_key_reads_the_key_from_the_isolated_env_file():
    target = keys.env_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('GEMINI_API_KEY="AIzaSyTESTONLY"\n', encoding="utf-8")
    assert keys.server_key() == "AIzaSyTESTONLY"


def test_server_key_returns_none_for_a_non_utf8_env_file():
    """Mot .env khong doc duoc bang UTF-8 lam read_text() nem
    UnicodeDecodeError. Truoc khi sua, ngoai le do di thang ra ngoai va bien
    GET /api/health cung POST /api/jobs thanh loi 500."""
    target = keys.env_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"GEMINI_API_KEY=\xff\xfe\x00binary\n")

    assert keys.server_key() is None
    assert client.get("/api/health").status_code == 200


def test_health_survives_an_unreadable_env_file():
    target = keys.env_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    # Mot thu muc mang ten .env: exists() la True, read_text() nem OSError
    # (IsADirectoryError).
    target.mkdir()

    assert keys.server_key() is None
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["server_key"] is False


def test_create_job_returns_400_instead_of_500_when_the_env_file_is_broken():
    target = keys.env_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.mkdir()

    resp = client.post("/api/jobs", json={"params": {"context": "No key"}})

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "missing_api_key"
