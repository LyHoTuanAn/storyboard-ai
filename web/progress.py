import re

_STEP = re.compile(r"^Step (\d+): (.+)$")
_SCENE = re.compile(r"^--- Processing Scene (\d+)/(\d+) ---$")
_ACTIVITY = re.compile(r"^Scene (\d+): (.+)$")
_WARNING = re.compile(r"^\s*\[X\] SKIPPING Scene (\d+): (.+)$")

# Key Gemini bat dau bang AIza; key cua gateway thu ba thuong dang sk_...
_KEY_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),
    re.compile(r"sk_[0-9A-Za-z_\-]{16,}"),
    re.compile(r"hf_[0-9A-Za-z]{20,}"),
]


def redact(text: str) -> str:
    for pattern in _KEY_PATTERNS:
        text = pattern.sub("***", text)
    return text


def parse_line(line: str) -> dict | None:
    line = line.rstrip("\r\n")

    match = _WARNING.match(line)
    if match:
        return {"event": "warning", "data": {"scene": int(match.group(1)), "message": match.group(2)}}

    match = _SCENE.match(line)
    if match:
        return {"event": "scene", "data": {"current": int(match.group(1)), "total": int(match.group(2))}}

    match = _STEP.match(line)
    if match:
        return {"event": "step", "data": {"n": int(match.group(1)), "label": match.group(2)}}

    match = _ACTIVITY.match(line)
    if match:
        return {"event": "activity", "data": {"scene": int(match.group(1)), "label": match.group(2)}}

    return None
