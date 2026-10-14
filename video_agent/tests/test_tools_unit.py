"""Unit tests for the tool handlers (no API, no ffmpeg)."""

from __future__ import annotations

from pathlib import Path

import pytest

from video_agent.probe import ClipInfo
from video_agent.timeline import Timeline
from video_agent.tools import FILTER_NAMES, POSITIONS, TOOL_SCHEMAS, ToolContext, ToolError, dispatch


def _ctx(duration: float = 10.0, has_audio: bool = True) -> ToolContext:
    info = ClipInfo(
        source=Path("/fake/clip.mp4"),
        duration=duration,
        fps=24.0,
        width=1280,
        height=720,
        has_audio=has_audio,
    )
    return ToolContext(timeline=Timeline(clip=info), output_default=Path("out.mp4"))


def test_schemas_well_formed():
    required_keys = {"name", "description", "input_schema"}
    for schema in TOOL_SCHEMAS:
        assert required_keys <= schema.keys()
        s = schema["input_schema"]
        assert s["type"] == "object"
        # strict mode contract: additionalProperties:false, required covers all keys
        if schema.get("strict"):
            assert s["additionalProperties"] is False
            assert set(s["required"]) == set(s["properties"].keys())


def test_filter_names_cover_all_presets():
    import video_agent.renderer as r

    assert set(FILTER_NAMES) == set(r.FILTER_PRESETS.keys())


def test_positions_cover_all_known():
    expected = {
        "top", "center", "bottom",
        "top-left", "top-right", "bottom-left", "bottom-right",
    }
    assert set(POSITIONS) == expected


def test_trim_dispatch():
    ctx = _ctx()
    out = dispatch("trim", {"start": 1.0, "end": 4.0}, ctx)
    assert "effective_duration_seconds" in out
    assert ctx.timeline.ops[0].kind == "trim"


def test_change_speed_segment():
    ctx = _ctx()
    dispatch("change_speed", {"factor": 2.0, "start": 1.0, "end": 3.0}, ctx)
    assert ctx.timeline.ops[-1].kind == "speed"
    assert ctx.timeline.ops[-1].args["factor"] == 2.0


def test_change_speed_rejects_zero():
    ctx = _ctx()
    with pytest.raises(ToolError):
        dispatch("change_speed", {"factor": 0, "start": None, "end": None}, ctx)


def test_add_text_overlay_validates_range():
    ctx = _ctx()
    with pytest.raises(ToolError):
        dispatch(
            "add_text_overlay",
            {"text": "x", "start": 2.0, "end": 2.0, "position": "center", "style": None},
            ctx,
        )


def test_apply_filter_unknown():
    ctx = _ctx()
    with pytest.raises(ToolError):
        dispatch("apply_filter", {"name": "not-a-thing"}, ctx)


def test_color_grade_requires_some_arg():
    ctx = _ctx()
    with pytest.raises(ToolError):
        dispatch(
            "color_grade",
            {"brightness": None, "contrast": None, "saturation": None, "temperature": None},
            ctx,
        )


def test_add_music_rejects_missing_file(tmp_path):
    ctx = _ctx()
    missing = tmp_path / "nope.mp3"
    with pytest.raises(ToolError):
        dispatch(
            "add_music",
            {
                "path": str(missing),
                "volume": 0.3,
                "fade_in": 0.0,
                "fade_out": 0.0,
                "start": None,
                "end": None,
            },
            ctx,
        )


def test_add_music_rejects_bad_volume(tmp_path):
    ctx = _ctx()
    f = tmp_path / "song.mp3"
    f.write_bytes(b"\x00")
    with pytest.raises(ToolError):
        dispatch(
            "add_music",
            {
                "path": str(f),
                "volume": 2.0,
                "fade_in": 0.0,
                "fade_out": 0.0,
                "start": None,
                "end": None,
            },
            ctx,
        )
