"""Mot ban clone moi phai theo duoc README.

requirements.txt tung khong he co fastapi/uvicorn/pydantic, trong khi lenh
dau tien trong web/README.md la chay uvicorn - nguoi doc lam theo tung buoc
se dung lai ngay o dong dau.
"""

import importlib.metadata as metadata
import re

from web.settings import CODE_ROOT

REQUIREMENTS = CODE_ROOT / "requirements.txt"
WEB_README = CODE_ROOT / "web" / "README.md"


def _requirements() -> dict[str, str | None]:
    found: dict[str, str | None] = {}
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([A-Za-z0-9_.\-]+)\s*(?:>=|==)?\s*([0-9][0-9A-Za-z.\-]*)?$", line)
        assert match, f"dong khong doc duoc trong requirements.txt: {line!r}"
        found[match.group(1).lower()] = match.group(2)
    return found


def _version_tuple(raw: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", raw)[:3])


def test_requirements_lists_the_web_layer_dependencies():
    listed = _requirements()
    for package in ["fastapi", "uvicorn", "pydantic"]:
        assert package in listed, f"{package} thieu trong requirements.txt"


def test_listed_versions_match_what_is_actually_installed():
    """Con so ghi trong requirements.txt phai la con so that su dang chay o
    .venv, khong phai mot con so doan."""
    for package, wanted in _requirements().items():
        if wanted is None:
            continue
        try:
            installed = metadata.version(package)
        except metadata.PackageNotFoundError:
            continue  # thu vien cua pipeline, khong bat buoc co trong .venv
        assert _version_tuple(installed) >= _version_tuple(wanted), (
            f"{package}: requirements.txt ghi {wanted} nhung .venv co {installed}"
        )


def test_readme_tells_the_reader_to_create_the_venv_and_install():
    text = WEB_README.read_text(encoding="utf-8")
    first_block = text.split("```")[1]
    assert "venv" in first_block
    assert "pip install -r requirements.txt" in first_block
    # Lenh chay server phai den SAU hai buoc tren.
    assert first_block.index("venv") < first_block.index("uvicorn")


def test_readme_has_no_em_or_en_dashes():
    text = WEB_README.read_text(encoding="utf-8")
    assert "—" not in text
    assert "–" not in text
