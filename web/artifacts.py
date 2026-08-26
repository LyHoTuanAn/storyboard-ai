import re
from pathlib import Path

from web import jobs

SCENE_DIR = re.compile(r"^scene_(\d+)$")
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
AUDIO_SUFFIXES = {".wav", ".mp3"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".webm"}


class Forbidden(Exception):
    pass


def _is_contained(root: Path, candidate: Path) -> bool:
    """True neu `candidate` nam trong `root`, ke ca khi candidate == root.

    So sanh theo tung thanh phan Path (candidate.parents), khong phai
    string-prefix - "jobs/j_x_extra" khong duoc coi la nam trong
    "jobs/j_x" chi vi ten bat dau giong nhau.
    """
    return candidate == root or root in candidate.parents


def safe_path(job_id: str, relative: str) -> Path:
    """Phan giai `relative` thanh duong dan tuyet doi trong thu muc job.

    Day la bien gioi bao mat: `relative` co the den tu URL param nguoi
    dung goi tuy y (query string cua GET /api/jobs/{id}/file). Moi truong
    hop khong the xac nhan chac chan nam trong thu muc job phai bi tu choi
    bang Forbidden - khong bao gio tra ve mot Path nam ngoai `root`.
    """
    if not relative or relative.strip() == "":
        raise Forbidden(relative)

    root = jobs.job_dir(job_id).resolve()

    # Path.resolve() thu gon moi doan ".." VA theo (follow) symlink, nen
    # candidate la vi tri THUC SU tren dia sau khi giai quyet moi symlink -
    # mot symlink nam trong job dir nhung tro ra ngoai se resolve thanh
    # duong dan ben ngoai, va bi containment check ben duoi tu choi.
    #
    # `relative` la du lieu tu URL param, co the chua byte NUL (%00) hoac
    # mot thanh phan qua dai - ca hai deu khien resolve()/exists() nem
    # ValueError hoac OSError (vi du ENAMETOOLONG) thay vi tra ve gia tri.
    # Bien gioi bao mat nay phai tu no bao boc nhung loi do va quy ve
    # Forbidden, chu khong de chung lot ra ngoai thanh 500 - moi noi goi
    # safe_path() (khong chi route hien tai) deu duoc bao dam cung mot hop
    # dong: hoac tra ve Path hop le, hoac Forbidden, khong bao gio loi khac.
    try:
        candidate = (root / relative).resolve()
        contained = _is_contained(root, candidate)
        exists = candidate.exists() if contained else False
    except (ValueError, OSError) as exc:
        raise Forbidden(relative) from exc

    if not contained:
        raise Forbidden(relative)
    # candidate == root nghia la relative la "." hoac tuong duong - do la
    # chinh thu muc job, khong phai mot file cu the, nen cung bi tu choi.
    if candidate == root:
        raise Forbidden(relative)
    if not exists:
        raise Forbidden(relative)
    return candidate


def _first(directory: Path, suffixes: set[str], root: Path) -> str | None:
    try:
        entries = sorted(directory.iterdir())
    except OSError:
        return None
    for item in entries:
        if item.is_file() and item.suffix.lower() in suffixes:
            return str(item.relative_to(root))
    return None


def collect(job_id: str) -> dict:
    root = jobs.job_dir(job_id).resolve()
    scenes: list[dict] = []
    final_video = None

    output_dir = root / "output"
    for run_dir in sorted(output_dir.glob("run_*")) if output_dir.exists() else []:
        # glob("run_*") khop theo TEN, khong theo kieu: mot file thuong (hay
        # mot symlink hong) ten "run_gi_do" cung khop, va iterdir() tren no
        # nem NotADirectoryError - du de bien ca route artifacts thanh loi
        # 500. Chi doc nhung gi that su la thu muc; thu khac thi bo qua.
        try:
            entries = sorted(run_dir.iterdir()) if run_dir.is_dir() else []
        except OSError:
            continue

        for candidate in entries:
            if candidate.is_file() and candidate.name == "storyboard_final_video.mp4":
                final_video = str(candidate.relative_to(root))

        for scene_dir in entries:
            match = SCENE_DIR.match(scene_dir.name) if scene_dir.is_dir() else None
            if not match:
                continue
            scenes.append(
                {
                    "scene": int(match.group(1)),
                    "image": _first(scene_dir, IMAGE_SUFFIXES, root),
                    "audio": _first(scene_dir, AUDIO_SUFFIXES, root),
                    "video": _first(scene_dir, VIDEO_SUFFIXES, root),
                }
            )

    scenes.sort(key=lambda item: item["scene"])
    return {"scenes": scenes, "final_video": final_video}
