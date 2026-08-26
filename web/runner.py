"""Chay trong tien trinh con. Khong bao giờ import boi web/server.py."""

import io
import os
import sys
import time
from pathlib import Path

from web import jobs
from web.progress import redact

RESEARCH_LABEL = {
    "deep": "Performing Deep Research...",
    "web": "Performing Web-Grounded Research (Fast)...",
    "none": "Skipping Research as per request. Using provided context directly.",
}


class _RedactingStream(io.TextIOBase):
    """Boc stdout/stderr cua tien trinh con, loc key truoc khi ghi.

    Day la cho GAN NHAT voi luc ghi ma ta con kiem soat duoc: spawn() noi
    thang stdout cua tien trinh nay vao log.txt, nen bat cu thu gi qua duoc
    day la da nam tren dia. Mot thong bao loi cua google.genai co the chua ca
    URL yeu cau kem "?key=AIza..."; loc o day nghia la key khong bao gio duoc
    ghi vao log.txt ngay tu dau, thay vi trong cho tung noi doc log nho loc.

    Ghi theo tung lan write() chu khong gom dong: cac mau key deu nam gon
    trong mot dong va print() thuong ghi ca dong mot lan, con viec gom dong o
    day se lam tre dau ra (SSE dang doc log.txt theo thoi gian thuc).
    """

    def __init__(self, stream):
        self._stream = stream

    def write(self, text: str) -> int:
        self._stream.write(redact(text))
        return len(text)

    def flush(self) -> None:
        self._stream.flush()

    def isatty(self) -> bool:
        return False

    @property
    def encoding(self) -> str:
        return getattr(self._stream, "encoding", "utf-8")


def install_redacting_output() -> None:
    sys.stdout = _RedactingStream(sys.stdout)
    sys.stderr = _RedactingStream(sys.stderr)


def run_fake(job: dict) -> str:
    """In ra chuoi log giong that, tao file gia. Khong goi API nao."""
    total = 2
    sleep_for = float(os.getenv("SB_FAKE_SLEEP", "0"))
    if sleep_for:
        print("Step 0: fake mode dang ngu de test huy...")
        time.sleep(sleep_for)
    skip = os.getenv("SB_FAKE_SKIP_SCENE")
    out_dir = Path.cwd() / "output" / f"run_fake_{int(time.time())}"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"--- Starting Storyboard Pipeline for context: {job['params']['context']} ---")
    print(f"Artifacts will be saved to: {out_dir}")
    print(f"\nStep 1: {RESEARCH_LABEL[job['params']['research_mode']]}")
    print("\nStep 2: Director Planning & Scene Writing...")
    print(f"Director planned {total} scenes. Tone: calm, Arc: explanatory")

    for scene in range(1, total + 1):
        print(f"--- Processing Scene {scene}/{total} ---")
        scene_dir = out_dir / f"scene_{scene}"
        scene_dir.mkdir(exist_ok=True)

        print(f"Scene {scene}: Generating image prompt...")
        time.sleep(0.05)
        print(f"Scene {scene}: Generating image...")
        if skip and int(skip) == scene:
            print(f"  [X] SKIPPING Scene {scene}: Image generation failed - fake mode.")
            continue
        (scene_dir / f"generated_image_{scene}.png").write_bytes(b"\x89PNG\r\n\x1a\n fake")
        print(f"Scene {scene}: Generating narration audio...")
        (scene_dir / f"generated_audio_{scene}.wav").write_bytes(b"RIFF fake")
        print(f"Scene {scene}: Merging audio and video...")
        (scene_dir / f"scene_{scene}.mp4").write_bytes(b"fake mp4")

    final = out_dir / "storyboard_final_video.mp4"
    final.write_bytes(b"fake final mp4")
    print(f"\nFinal video: {final}")
    return str(final.relative_to(Path.cwd()))


def run_real(job: dict) -> str:
    from pipeline import run_pipeline

    params = job["params"]
    mode = params["research_mode"]
    result = run_pipeline(
        params["context"],
        do_research=(mode == "deep"),
        do_web_search=(mode == "web"),
        use_internet_image_search=params["use_internet_image_search"],
        fast_mode=params["fast_mode"],
        language=params["language"],
        enable_veo=params["enable_veo"],
        veo_direction_by_director=params["veo_direction_by_director"],
    )
    if not result:
        raise RuntimeError("pipeline khong tra ve video")
    return str(Path(result).resolve().relative_to(Path.cwd().resolve()))


def main(job_id: str) -> int:
    install_redacting_output()
    job = jobs.read_job(job_id)
    try:
        if os.getenv("SB_FAKE_PIPELINE") == "1":
            video = run_fake(job)
        else:
            video = run_real(job)
    except Exception as error:  # noqa: BLE001 - phai bat het de ghi vao job.json
        # redact() ca o day chu khong chi dua vao stdout da boc: chuoi nay di
        # vao job.json (roi ra REST va man hinh), mot duong ra khac han
        # duong log. jobs.set_status() cung loc lan nua - ba lop, vi mot
        # thong bao loi cua google.genai la noi de lo key nhat.
        message = redact(str(error))
        print(f"PIPELINE ERROR: {message}")
        try:
            jobs.set_status(job_id, "failed", error=message, exit_code=1)
        except jobs.InvalidTransition:
            print(f"Job {job_id} was already finalized elsewhere (e.g. cancelled).")
        return 1

    try:
        jobs.set_status(job_id, "done", result_video=video, exit_code=0)
    except jobs.InvalidTransition:
        print(f"Job {job_id} was already finalized elsewhere (e.g. cancelled).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
