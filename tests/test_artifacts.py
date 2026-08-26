import time

import pytest
from fastapi.testclient import TestClient

from web import artifacts, jobs
from web.server import app

client = TestClient(app)

BODY = {"params": {"context": "Artifact topic"}, "api_key": "AIzaSyFAKE"}


def finished_job(monkeypatch, **env):
    monkeypatch.setenv("SB_FAKE_PIPELINE", "1")
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    job_id = client.post("/api/jobs", json=BODY).json()["id"]
    for _ in range(100):
        if jobs.read_job(job_id)["status"] in jobs.TERMINAL:
            return job_id
        time.sleep(0.1)
    raise AssertionError("job khong ket thuc")


@pytest.mark.parametrize(
    "evil",
    ["../../../etc/passwd", "/etc/passwd", "output/../../../etc/passwd", "..%2f..%2fetc"],
)
def test_safe_path_rejects_traversal(evil):
    created = client.post("/api/jobs", json=BODY).json()["id"]
    with pytest.raises(artifacts.Forbidden):
        artifacts.safe_path(created, evil)


def test_safe_path_accepts_file_inside_job(monkeypatch):
    job_id = finished_job(monkeypatch)
    target = jobs.job_dir(job_id) / "log.txt"
    resolved = artifacts.safe_path(job_id, "log.txt")
    assert resolved == target.resolve()


def test_collect_groups_by_scene(monkeypatch):
    job_id = finished_job(monkeypatch)
    tree = artifacts.collect(job_id)
    assert tree["final_video"] is not None
    assert len(tree["scenes"]) == 2
    assert tree["scenes"][0]["scene"] == 1
    assert tree["scenes"][0]["image"] is not None
    assert tree["scenes"][0]["audio"] is not None


def test_collect_marks_missing_image_for_skipped_scene(monkeypatch):
    job_id = finished_job(monkeypatch, SB_FAKE_SKIP_SCENE="2")
    tree = artifacts.collect(job_id)
    scene_two = [item for item in tree["scenes"] if item["scene"] == 2][0]
    assert scene_two["image"] is None


def test_file_route_serves_artifact(monkeypatch):
    job_id = finished_job(monkeypatch)
    tree = artifacts.collect(job_id)
    resp = client.get(f"/api/jobs/{job_id}/file", params={"path": tree["scenes"][0]["image"]})
    assert resp.status_code == 200


def test_file_route_blocks_traversal(monkeypatch):
    job_id = finished_job(monkeypatch)
    resp = client.get(f"/api/jobs/{job_id}/file", params={"path": "../../../etc/passwd"})
    assert resp.status_code == 403


def test_safe_path_rejects_empty_and_dot():
    created = client.post("/api/jobs", json=BODY).json()["id"]
    with pytest.raises(artifacts.Forbidden):
        artifacts.safe_path(created, "")
    with pytest.raises(artifacts.Forbidden):
        artifacts.safe_path(created, ".")


def test_safe_path_rejects_symlink_escape(tmp_path, monkeypatch):
    created = client.post("/api/jobs", json=BODY).json()["id"]
    job_root = jobs.job_dir(created)
    job_root.mkdir(parents=True, exist_ok=True)

    outside = tmp_path / "outside_secret.txt"
    outside.write_text("top secret")

    link = job_root / "escape_link"
    link.symlink_to(outside)

    with pytest.raises(artifacts.Forbidden):
        artifacts.safe_path(created, "escape_link")


def test_safe_path_rejects_sibling_prefix_directory():
    created = client.post("/api/jobs", json=BODY).json()["id"]
    job_root = jobs.job_dir(created)
    job_root.mkdir(parents=True, exist_ok=True)

    sibling = job_root.parent / (job_root.name + "_extra")
    sibling.mkdir(parents=True, exist_ok=True)
    (sibling / "secret.txt").write_text("nope")

    # Attempt to reach the sibling directory via a relative path that starts
    # with the job dir's own name as a substring prefix - a string-prefix
    # containment check would wrongly accept this.
    with pytest.raises(artifacts.Forbidden):
        artifacts.safe_path(created, f"../{job_root.name}_extra/secret.txt")


def test_safe_path_rejects_embedded_nul_byte():
    created = client.post("/api/jobs", json=BODY).json()["id"]
    # A NUL byte makes the underlying resolve()/stat() calls raise
    # ValueError - safe_path() must convert that into Forbidden rather
    # than let it propagate as a 500.
    with pytest.raises(artifacts.Forbidden):
        artifacts.safe_path(created, "\x00real.txt")


def test_safe_path_rejects_overlong_path_component():
    created = client.post("/api/jobs", json=BODY).json()["id"]
    overlong = "a" * 5000
    # On most filesystems a single path component this long raises
    # OSError (ENAMETOOLONG) from resolve()/stat(). safe_path() must
    # convert that into Forbidden too. If the filesystem tolerates it
    # without error, the containment/existence checks still refuse it
    # since no such file exists inside the job dir - either way the
    # observable result is Forbidden.
    with pytest.raises(artifacts.Forbidden):
        artifacts.safe_path(created, overlong)


def test_file_route_blocks_embedded_nul_byte(monkeypatch):
    job_id = finished_job(monkeypatch)
    # Passing a raw NUL byte as the query param value makes the HTTP
    # client percent-encode it to %00 in the request line; Starlette then
    # decodes it back to an actual "\x00" for the `path` parameter - this
    # exercises the real route (encode -> decode -> safe_path), not just
    # a Python string constructed in-process.
    resp = client.get(f"/api/jobs/{job_id}/file", params={"path": "log.txt\x00"})
    assert resp.status_code == 403
