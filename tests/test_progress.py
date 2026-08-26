import pytest

from web.progress import parse_line, redact


@pytest.mark.parametrize(
    "line,expected",
    [
        (
            "Step 1: Performing Web-Grounded Research (Fast)...",
            {"event": "step", "data": {"n": 1, "label": "Performing Web-Grounded Research (Fast)..."}},
        ),
        (
            "Step 2: Director Planning & Scene Writing...",
            {"event": "step", "data": {"n": 2, "label": "Director Planning & Scene Writing..."}},
        ),
        (
            "--- Processing Scene 2/4 ---",
            {"event": "scene", "data": {"current": 2, "total": 4}},
        ),
        (
            "Scene 3: Generating image...",
            {"event": "activity", "data": {"scene": 3, "label": "Generating image..."}},
        ),
        (
            "  [X] SKIPPING Scene 2: Image generation failed.",
            {"event": "warning", "data": {"scene": 2, "message": "Image generation failed."}},
        ),
    ],
)
def test_parse_line_recognises_known_markers(line, expected):
    assert parse_line(line) == expected


@pytest.mark.parametrize(
    "line",
    [
        "",
        "Artifacts will be saved to: /tmp/x",
        "Director planned 4 scenes. Tone: inspiring",
        "Stepping over a puddle",
        "Scene: no number here",
    ],
)
def test_parse_line_ignores_noise(line):
    assert parse_line(line) is None


def test_redact_hides_api_keys():
    text = 'using GEMINI_API_KEY=AIzaSyA1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7 now'
    out = redact(text)
    assert "AIzaSyA1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7" not in out
    assert "***" in out


def test_redact_leaves_ordinary_text_alone():
    assert redact("Scene 2: Generating image...") == "Scene 2: Generating image..."
