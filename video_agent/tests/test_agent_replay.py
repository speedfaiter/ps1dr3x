"""Agent loop test with a replay LLM client (deterministic, offline)."""

from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest


# ------- replay client ----------

@dataclass
class _Block:
    type: str
    text: str | None = None
    id: str | None = None
    name: str | None = None
    input: dict | None = None


@dataclass
class _Response:
    content: list[_Block]
    stop_reason: str


class ReplayClient:
    """Returns pre-scripted assistant turns, ignoring the request body."""

    def __init__(self, turns: list[_Response]):
        self._turns = list(turns)
        self.calls = 0

    def messages_create(self, **kwargs) -> _Response:
        if not self._turns:
            raise AssertionError("Replay client ran out of turns")
        self.calls += 1
        return self._turns.pop(0)


def _tool_use(name: str, input_: dict) -> _Block:
    return _Block(type="tool_use", id=f"tu_{uuid.uuid4().hex[:8]}", name=name, input=input_)


def _text(text: str) -> _Block:
    return _Block(type="text", text=text)


@pytest.fixture
def sample_mp4(sample_mp4):  # re-expose from conftest
    return sample_mp4


def test_agent_trim_then_render(sample_mp4, tmp_path):
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not available")

    from video_agent.agent import run

    output = tmp_path / "out.mp4"
    turns = [
        _Response(
            content=[_tool_use("trim", {"start": 1.0, "end": 3.0})],
            stop_reason="tool_use",
        ),
        _Response(
            content=[
                _tool_use(
                    "render",
                    {
                        "output_path": str(output),
                        "resolution": None,
                        "fps": None,
                        "codec": "h264",
                    },
                )
            ],
            stop_reason="tool_use",
        ),
        _Response(
            content=[_text("Done.")],
            stop_reason="end_turn",
        ),
    ]
    result = run(
        "trim to seconds 1 through 3",
        source=sample_mp4,
        output_path=output,
        client=ReplayClient(turns),
    )
    assert Path(result.rendered["output_path"]).exists()

    from video_agent.probe import probe

    out_info = probe(result.rendered["output_path"])
    assert abs(out_info.duration - 2.0) < 0.3


def test_agent_handles_tool_error(sample_mp4, tmp_path):
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not available")

    from video_agent.agent import run

    output = tmp_path / "out.mp4"
    turns = [
        # First call: bad filter name -> tool_error, agent corrects.
        _Response(
            content=[_tool_use("apply_filter", {"name": "not-a-real-filter"})],
            stop_reason="tool_use",
        ),
        _Response(
            content=[_tool_use("apply_filter", {"name": "bw"})],
            stop_reason="tool_use",
        ),
        _Response(
            content=[
                _tool_use(
                    "render",
                    {
                        "output_path": str(output),
                        "resolution": None,
                        "fps": None,
                        "codec": "h264",
                    },
                )
            ],
            stop_reason="tool_use",
        ),
        _Response(content=[_text("Done.")], stop_reason="end_turn"),
    ]
    result = run(
        "make it black and white",
        source=sample_mp4,
        output_path=output,
        client=ReplayClient(turns),
    )
    assert Path(result.rendered["output_path"]).exists()
