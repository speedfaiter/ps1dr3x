"""Renderer command-compilation tests (no ffmpeg execution)."""

from __future__ import annotations

from pathlib import Path

import pytest

from video_agent.probe import ClipInfo
from video_agent.renderer import compile_command
from video_agent.timeline import Op, Timeline, TimelineError


def _clip() -> ClipInfo:
    return ClipInfo(
        source=Path("/fake/clip.mp4"),
        duration=10.0,
        fps=24.0,
        width=1920,
        height=1080,
        has_audio=True,
    )


@pytest.fixture(autouse=True)
def _skip_if_no_ffmpeg():
    import shutil
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("ffmpeg not available")


def test_bare_timeline_compiles():
    tl = Timeline(clip=_clip())
    cmd = compile_command(tl, Path("out.mp4"))
    assert cmd[0] == "ffmpeg"
    assert "-i" in cmd
    assert "out.mp4" in cmd[-1]


def test_trim_uses_ss_to():
    tl = Timeline(clip=_clip())
    tl.add(Op(kind="trim", args={"start": 1.0, "end": 3.0}))
    cmd = compile_command(tl, Path("out.mp4"))
    joined = " ".join(cmd)
    assert "-ss 1.0" in joined
    assert "-to 3.0" in joined


def test_filter_preset_appears_in_graph():
    tl = Timeline(clip=_clip())
    tl.add(Op(kind="filter", args={"name": "bw"}))
    cmd = compile_command(tl, Path("out.mp4"))
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "hue=s=0" in graph


def test_drawtext_in_graph():
    tl = Timeline(clip=_clip())
    tl.add(
        Op(
            kind="text",
            args={
                "text": "Hello",
                "start": 0.0,
                "end": 2.0,
                "position": "top",
                "style": {"size": 48},
            },
        )
    )
    cmd = compile_command(tl, Path("out.mp4"))
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "drawtext" in graph
    assert "Hello" in graph


def test_unknown_filter_raises():
    tl = Timeline(clip=_clip())
    tl.add(Op(kind="filter", args={"name": "no-such-filter"}))
    with pytest.raises(TimelineError):
        compile_command(tl, Path("out.mp4"))


def test_animated_text_in_graph():
    tl = Timeline(clip=_clip())
    tl.add(
        Op(
            kind="animated_text",
            args={
                "text": "Hello",
                "start": 0.0,
                "end": 3.0,
                "enter_from": "left",
                "exit_to": "right",
                "enter_duration": 0.5,
                "exit_duration": 0.5,
                "position": "center",
                "style": {},
            },
        )
    )
    cmd = compile_command(tl, Path("out.mp4"))
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "drawtext" in graph
    assert "-text_w" in graph  # off-screen left anchor


def test_lower_third_two_drawtexts():
    tl = Timeline(clip=_clip())
    tl.add(
        Op(
            kind="lower_third",
            args={
                "primary_text": "Jane Doe",
                "secondary_text": "Engineer",
                "start": 1.0,
                "end": 5.0,
                "side": "left",
                "accent_color": "#1f6feb",
            },
        )
    )
    cmd = compile_command(tl, Path("out.mp4"))
    graph = cmd[cmd.index("-filter_complex") + 1]
    # Two drawtext filters produced (one per line).
    assert graph.count("drawtext") == 2


def test_zoom_in_graph():
    tl = Timeline(clip=_clip())
    tl.add(
        Op(
            kind="zoom",
            args={
                "start": 0.0,
                "end": 3.0,
                "direction": "in",
                "factor_start": 1.0,
                "factor_end": 1.3,
            },
        )
    )
    cmd = compile_command(tl, Path("out.mp4"))
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "scale=" in graph
    assert "crop=" in graph


def test_word_captions_in_graph():
    tl = Timeline(clip=_clip())
    tl.add(
        Op(
            kind="word_captions",
            args={
                "words": [
                    {"text": "Hello", "start": 0.0, "end": 0.4},
                    {"text": "world", "start": 0.5, "end": 1.0},
                ],
                "style": {},
            },
        )
    )
    cmd = compile_command(tl, Path("out.mp4"))
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert graph.count("drawtext") == 2
    assert "Hello" in graph and "world" in graph


def test_flash_compiles():
    tl = Timeline(clip=_clip())
    tl.add(Op(kind="flash", args={"at": 2.0, "duration": 0.25, "color": "white"}))
    cmd = compile_command(tl, Path("out.mp4"))
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "fade=t=out" in graph
    assert "fade=t=in" in graph


def test_glitch_compiles():
    tl = Timeline(clip=_clip())
    tl.add(Op(kind="glitch", args={"start": 1.0, "end": 1.5, "intensity": 0.6}))
    cmd = compile_command(tl, Path("out.mp4"))
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "rgbashift" in graph
    assert "noise=" in graph


def test_zoom_punch_compiles():
    tl = Timeline(clip=_clip())
    tl.add(Op(kind="zoom_punch", args={"at": 3.0, "duration": 0.4, "peak_zoom": 1.3}))
    cmd = compile_command(tl, Path("out.mp4"))
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "scale=" in graph


def test_sfx_text_compiles():
    tl = Timeline(clip=_clip())
    tl.add(
        Op(
            kind="sfx_text",
            args={
                "text": "BOOM!",
                "at": 2.0,
                "duration": 0.6,
                "size": 120,
                "color": "yellow",
                "background": "red",
            },
        )
    )
    cmd = compile_command(tl, Path("out.mp4"))
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "BOOM!" in graph
    assert "box=1" in graph


def test_blurred_bg_compiles():
    tl = Timeline(clip=_clip())
    tl.add(Op(kind="blurred_bg", args={"width": 1080, "height": 1920, "blur": 30}))
    cmd = compile_command(tl, Path("out.mp4"))
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "gblur" in graph
    assert "overlay" in graph


def test_music_adds_second_input(tmp_path):
    tl = Timeline(clip=_clip())
    music = tmp_path / "bgm.mp3"
    music.write_bytes(b"\x00")
    tl.add(
        Op(
            kind="music",
            args={
                "path": str(music),
                "volume": 0.3,
                "fade_in": 0.5,
                "fade_out": 0.5,
                "start": None,
                "end": None,
            },
        )
    )
    cmd = compile_command(tl, Path("out.mp4"))
    i_indices = [i for i, a in enumerate(cmd) if a == "-i"]
    assert len(i_indices) == 2  # main + music
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "amix" in graph
