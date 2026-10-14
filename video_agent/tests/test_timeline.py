"""Unit tests for the Timeline data model (no ffmpeg required)."""

from __future__ import annotations

from pathlib import Path

import pytest

from video_agent.probe import ClipInfo
from video_agent.timeline import Op, Timeline, TimelineError


def _clip(duration: float = 10.0) -> ClipInfo:
    return ClipInfo(
        source=Path("/fake/clip.mp4"),
        duration=duration,
        fps=24.0,
        width=1920,
        height=1080,
        has_audio=True,
    )


def test_trim_sinks_to_front():
    tl = Timeline(clip=_clip())
    tl.add(Op(kind="filter", args={"name": "bw"}))
    tl.add(Op(kind="trim", args={"start": 1, "end": 5}))
    assert tl.ops[0].kind == "trim"
    assert tl.ops[1].kind == "filter"


def test_trim_second_rejected():
    tl = Timeline(clip=_clip())
    tl.add(Op(kind="trim", args={"start": 0, "end": 5}))
    with pytest.raises(TimelineError):
        tl.add(Op(kind="trim", args={"start": 1, "end": 2}))


def test_trim_invalid_range():
    tl = Timeline(clip=_clip())
    with pytest.raises(TimelineError):
        tl.add(Op(kind="trim", args={"start": 5, "end": 5}))
    with pytest.raises(TimelineError):
        tl.add(Op(kind="trim", args={"start": -1, "end": 2}))
    with pytest.raises(TimelineError):
        tl.add(Op(kind="trim", args={"start": 0, "end": 999}))


def test_effective_duration_trim():
    tl = Timeline(clip=_clip(duration=10))
    tl.add(Op(kind="trim", args={"start": 2, "end": 7}))
    assert tl.effective_duration() == pytest.approx(5.0)


def test_effective_duration_whole_speed():
    tl = Timeline(clip=_clip(duration=10))
    tl.add(Op(kind="speed", args={"factor": 2.0}))
    assert tl.effective_duration() == pytest.approx(5.0)


def test_effective_duration_segment_speed():
    tl = Timeline(clip=_clip(duration=10))
    # Slow down a 4s segment to half speed -> adds 4s.
    tl.add(Op(kind="speed", args={"factor": 0.5, "start": 2.0, "end": 6.0}))
    assert tl.effective_duration() == pytest.approx(14.0)


def test_summary_shape():
    tl = Timeline(clip=_clip())
    tl.add(Op(kind="trim", args={"start": 0, "end": 5}))
    tl.add(Op(kind="filter", args={"name": "warm"}))
    s = tl.summary()
    assert s["source"] == "clip.mp4"
    assert s["effective_duration_seconds"] == pytest.approx(5.0)
    assert len(s["ops"]) == 2
    assert s["ops"][0]["kind"] == "trim"
