import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    max_concurrent: int
    jobs_dir: Path
    host: str
    port: int
    repo_root: Path


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    jobs_dir = Path(os.getenv("SB_JOBS_DIR", REPO_ROOT / "output" / "jobs"))
    return Settings(
        max_concurrent=int(os.getenv("SB_MAX_CONCURRENT", "1")),
        jobs_dir=jobs_dir,
        host=os.getenv("SB_HOST", "127.0.0.1"),
        port=int(os.getenv("SB_PORT", "8000")),
        repo_root=REPO_ROOT,
    )
