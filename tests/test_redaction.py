"""Key phai bi loc o MOI duong ra, khong chi o luong SSE.

Mot key Gemini co the lot vao log qua thong bao loi cua thu vien (google.genai
dua ca URL yeu cau, kem "?key=AIza...", vao message). Tu do no co bon duong ra
khac nhau: file log.txt tren dia, truong "error" trong job.json, REST
(GET /api/jobs/{id}), va route tai file (GET /api/jobs/{id}/file). Moi bai
test duoi day gam mot duong.
"""

import time

from fastapi.testclient import TestClient

from web import jobs
from web.schemas import CreateJobRequest, JobParams
from web.server import app

client = TestClient(app)

# Dung dinh dang that (AIza + 35 ky tu) de khop dung mau ma progress.redact()
# tim - mot chuoi ngan nhu "AIzaSyFAKE" se khong bi loc va bai test se khong
# chung minh duoc gi.
FAKE_KEY = "AIzaSyA1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7"

BODY = {"params": {"context": "Redaction topic"}, "api_key": "AIzaSyFAKE"}


def make_job(context="Redaction topic", key_source="server"):
    return jobs.create_job(
        CreateJobRequest(params=JobParams(context=context)), key_source=key_source
    )


def wait_for_terminal(job_id, timeout=20.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if jobs.read_job(job_id)["status"] in jobs.TERMINAL:
            return jobs.read_job(job_id)
        time.sleep(0.1)
    raise AssertionError(f"{job_id} khong ket thuc trong {timeout}s")


def test_log_tail_redacts_the_key():
    job = make_job()
    (jobs.job_dir(job["id"]) / "log.txt").write_text(
        f"google.genai error: POST https://x/y?key={FAKE_KEY}\n", encoding="utf-8"
    )
    tail = jobs.log_tail(job["id"])
    assert FAKE_KEY not in tail
    assert "***" in tail


def test_set_status_never_writes_a_key_into_job_json():
    job = make_job()
    jobs.set_status(job["id"], "failed", error=f"boom key={FAKE_KEY}", exit_code=1)
    raw = (jobs.job_dir(job["id"]) / "job.json").read_text(encoding="utf-8")
    assert FAKE_KEY not in raw
    assert "***" in raw


def test_read_job_redacts_a_key_already_present_on_disk():
    """Ban ghi cu (ghi boi phien ban truoc khi co bo loc) van co the con key
    trong "error". Duong doc phai loc them mot lan nua, neu khong gia tri do
    di thang ra REST."""
    job = make_job()
    on_disk = jobs.read_job(job["id"])
    on_disk["status"] = "failed"
    on_disk["error"] = f"stale record with key={FAKE_KEY}"
    (jobs.job_dir(job["id"]) / "job.json").write_text(
        __import__("json").dumps(on_disk), encoding="utf-8"
    )

    assert FAKE_KEY not in jobs.read_job(job["id"])["error"]
    detail = client.get(f"/api/jobs/{job['id']}")
    assert FAKE_KEY not in detail.text


def test_reap_orphans_error_does_not_carry_the_key():
    job = make_job()
    (jobs.job_dir(job["id"]) / "log.txt").write_text(
        f"crashed while calling ?key={FAKE_KEY}\n", encoding="utf-8"
    )
    jobs.set_status(job["id"], "running", pid=999999)

    jobs.reap_orphans()

    reaped = jobs.read_job(job["id"])
    assert reaped["status"] == "interrupted"
    assert FAKE_KEY not in reaped["error"]
    assert FAKE_KEY not in (jobs.job_dir(job["id"]) / "job.json").read_text(encoding="utf-8")


def test_file_route_redacts_the_served_log():
    job = make_job()
    (jobs.job_dir(job["id"]) / "log.txt").write_text(
        f"line one\nkey={FAKE_KEY}\nline three\n", encoding="utf-8"
    )

    resp = client.get(f"/api/jobs/{job['id']}/file", params={"path": "log.txt"})

    assert resp.status_code == 200
    assert FAKE_KEY not in resp.text
    assert "***" in resp.text
    # Van phai la noi dung that, chi bo phan key di.
    assert "line one" in resp.text
    assert "line three" in resp.text


def test_a_key_in_a_pipeline_error_reaches_no_exit_at_all():
    """Bai test xuyen suot, dung tien trinh con that.

    Dat mot module `pipeline` gia ngay trong thu muc job (cwd cua tien trinh
    con, va `python -m` dat cwd o dau sys.path) de run_real() nem mot ngoai le
    co chua key - dung nhu thong bao loi that cua google.genai. Sau do soi ca
    bon duong ra.
    """
    job = make_job()
    directory = jobs.job_dir(job["id"])
    (directory / "pipeline.py").write_text(
        "def run_pipeline(*args, **kwargs):\n"
        f"    raise RuntimeError('400 INVALID_ARGUMENT https://api/v1?key={FAKE_KEY}')\n",
        encoding="utf-8",
    )

    jobs.spawn(job["id"], api_key=FAKE_KEY)
    finished = wait_for_terminal(job["id"])
    assert finished["status"] == "failed"

    # 1. file log tren dia (bo loc o phia GHI, trong web/runner.py)
    log_text = (directory / "log.txt").read_text(encoding="utf-8")
    assert "PIPELINE ERROR" in log_text
    assert FAKE_KEY not in log_text

    # 2. job.json
    assert FAKE_KEY not in (directory / "job.json").read_text(encoding="utf-8")

    # 3. REST
    detail = client.get(f"/api/jobs/{job['id']}")
    assert detail.status_code == 200
    assert FAKE_KEY not in detail.text
    assert FAKE_KEY not in client.get("/api/jobs").text

    # 4. SSE
    with client.stream("GET", f"/api/jobs/{job['id']}/events") as resp:
        body = "".join(resp.iter_text())
    assert FAKE_KEY not in body

    # 5. route tai file
    served = client.get(f"/api/jobs/{job['id']}/file", params={"path": "log.txt"})
    assert served.status_code == 200
    assert FAKE_KEY not in served.text
