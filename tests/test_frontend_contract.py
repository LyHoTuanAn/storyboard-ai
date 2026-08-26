"""Nhung giao uoc giua backend va frontend ma khong ben nao tu kiem duoc.

Frontend chua co bo chay test rieng (them mot bo la them phu thuoc npm moi,
nam ngoai pham vi), nhung vai giao uoc quan trong nhat lai chi la "hai danh
sach o hai ngon ngu phai khop nhau". Doc thang ma nguon TypeScript va doi
chieu voi Python o day re hon nhieu so voi mot lan nua bi loi cua khe ho do.
"""

import re

from web import events
from web.settings import CODE_ROOT

SRC = CODE_ROOT / "web" / "frontend" / "src"


def test_client_and_server_agree_on_which_statuses_end_the_stream():
    """web/events.py ket thuc luong SSE ngay lap tuc cho moi trang thai trong
    END_STATUSES. Neu client khong coi mot trong so do la ket thuc, no se tu
    ket noi lai sau moi lan server dong - vai giay mot lan, mai mai. Do dung
    la chuyen da xay ra voi "corrupt": co trong END_STATUSES, thieu trong
    TERMINAL_STATUSES."""
    source = (SRC / "hooks" / "useJobEvents.ts").read_text(encoding="utf-8")
    match = re.search(
        r"const TERMINAL_STATUSES: readonly JobStatus\[\] = \[(.*?)\];", source, re.S
    )
    assert match, "khong tim thay TERMINAL_STATUSES trong useJobEvents.ts"
    client_statuses = set(re.findall(r'"([a-z]+)"', match.group(1)))

    assert client_statuses == events.END_STATUSES


def test_job_detail_does_not_open_a_stream_for_a_corrupt_job():
    """Server dong luong ngay voi job corrupt va JobDetail cung an luon khung
    nhat ky - mo ket noi chi de no bi dong ngay la thua."""
    source = (SRC / "components" / "JobDetail.tsx").read_text(encoding="utf-8")
    assert 'job.status !== "corrupt"' in source
    assert re.search(r"useJobEvents\(jobId,\s*\w+\)", source)


def test_log_view_scrolls_its_own_container_not_the_page():
    """scrollIntoView cuon moi phan tu to hon dang chua no, ke ca ca trang -
    nen moi dong log moi lai giat trang. Phai dat scrollTop cua chinh khung
    nhat ky."""
    source = (SRC / "components" / "LogView.tsx").read_text(encoding="utf-8")
    # Bo cac dong chu thich: chinh chu thich giai thich VI SAO khong dung
    # scrollIntoView cung chua tu do.
    code = "\n".join(
        line for line in source.splitlines() if not line.strip().startswith("//")
    )
    assert "scrollIntoView" not in code
    assert "scrollTop" in code and "scrollHeight" in code
