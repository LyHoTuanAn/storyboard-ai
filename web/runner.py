"""Chay trong tien trinh con. Khong bao giờ import boi web/server.py."""

import os
import sys
import time
from pathlib import Path

from web import jobs

RESEARCH_LABEL = {
    "deep": "Performing Deep Research...",
    "web": "Performing Web-Grounded Research (Fast)...",
    "none": "Skipping Research as per request. Using provided context directly.",
}


def run_fake(job: dict) -> str:
    """In ra chuoi log giong that, tao file gia. Khong goi API nao."""
    total = 2
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
    job = jobs.read_job(job_id)
    try:
        if os.getenv("SB_FAKE_PIPELINE") == "1":
            video = run_fake(job)
        else:
            video = run_real(job)
    except Exception as error:  # noqa: BLE001 - phai bat het de ghi vao job.json
        print(f"PIPELINE ERROR: {error}")
        jobs.set_status(job_id, "failed", error=str(error), exit_code=1)
        return 1

    jobs.set_status(job_id, "done", result_video=video, exit_code=0)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
