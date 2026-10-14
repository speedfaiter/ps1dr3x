"""Thin ffprobe wrapper."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class ProbeError(RuntimeError):
    pass


@dataclass
class ClipInfo:
    source: Path
    duration: float
    fps: float
    width: int
    height: int
    has_audio: bool


def ensure_ffmpeg_available() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise ProbeError(f"{tool} not found on PATH; install ffmpeg.")


def probe(path: str | Path) -> ClipInfo:
    """Return basic info about a media file via ffprobe."""
    ensure_ffmpeg_available()
    p = Path(path)
    if not p.exists():
        raise ProbeError(f"File not found: {p}")

    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(p),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise ProbeError(f"ffprobe failed: {result.stderr.strip()}")

    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if not video:
        raise ProbeError(f"No video stream found in {p}")

    def _parse_rate(value: str) -> float:
        if "/" in value:
            num, _, den = value.partition("/")
            try:
                return float(num) / float(den) if float(den) else 0.0
            except ValueError:
                return 0.0
        try:
            return float(value)
        except ValueError:
            return 0.0

    fps = _parse_rate(video.get("r_frame_rate") or video.get("avg_frame_rate") or "0/1")
    duration = float(data.get("format", {}).get("duration") or video.get("duration") or 0)
    width = int(video.get("width") or 0)
    height = int(video.get("height") or 0)

    return ClipInfo(
        source=p,
        duration=duration,
        fps=fps,
        width=width,
        height=height,
        has_audio=audio is not None,
    )
