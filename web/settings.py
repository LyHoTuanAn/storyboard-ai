import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# Noi goi `web` nam tren dia. Day la mot su that ve VI TRI MA NGUON, khong
# phai mot lua chon cau hinh: tien trinh con duoc spawn bang
# `python -m web.runner`, nen PYTHONPATH cua no phai tro vao day thi moi
# import duoc `web`. Khong bao gio de bien moi truong ghi de gia tri nay.
CODE_ROOT = Path(__file__).resolve().parent.parent

# Goc du lieu cua du an: noi chua `genai-pipeline/.env`, `output/`... Mac dinh
# trung CODE_ROOT, nhung tach rieng ra de test (tests/conftest.py) tro no vao
# mot thu muc tam - neu khong, bo test se doc `genai-pipeline/.env` that cua
# may lap trinh vien va ket qua `keys.server_key()` se phu thuoc vao may dang
# chay.
REPO_ROOT = CODE_ROOT


@dataclass(frozen=True)
class Settings:
    max_concurrent: int
    jobs_dir: Path
    host: str
    port: int
    repo_root: Path
    code_root: Path


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    repo_root = Path(os.getenv("SB_REPO_ROOT", REPO_ROOT))
    jobs_dir = Path(os.getenv("SB_JOBS_DIR", repo_root / "output" / "jobs"))
    return Settings(
        max_concurrent=int(os.getenv("SB_MAX_CONCURRENT", "1")),
        jobs_dir=jobs_dir,
        host=os.getenv("SB_HOST", "127.0.0.1"),
        port=int(os.getenv("SB_PORT", "8000")),
        repo_root=repo_root,
        code_root=CODE_ROOT,
    )
