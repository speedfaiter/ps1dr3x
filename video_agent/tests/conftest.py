"""Shared test fixtures."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def sample_mp4() -> Path:
    """Generate a 5-second test clip once per session."""
    path = FIXTURES / "sample.mp4"
    if path.exists():
        return path
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not on PATH")
    FIXTURES.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=24:duration=5",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
        "-shortest", str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        pytest.skip(f"ffmpeg could not build fixture: {result.stderr[:200]}")
    return path


@pytest.fixture
def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None
