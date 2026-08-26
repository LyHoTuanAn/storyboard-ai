import shutil
from pathlib import Path

from fastapi import FastAPI

from web.settings import get_settings

app = FastAPI(title="Storyboard AI")


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def server_key_present() -> bool:
    env_file = get_settings().repo_root / "genai-pipeline" / ".env"
    if not env_file.exists():
        return False
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("GEMINI_API_KEY="):
            value = line.split("=", 1)[1].strip().strip('"').strip("'")
            return bool(value)
    return False


@app.get("/api/health")
def health() -> dict:
    return {
        "ffmpeg": ffmpeg_available(),
        "server_key": server_key_present(),
        "running": 0,
    }
