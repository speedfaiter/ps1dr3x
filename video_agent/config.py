"""Defaults and environment resolution."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PACKAGE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = PACKAGE_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
MODELS_DIR = ASSETS_DIR / "models"
PROMPTS_DIR = PACKAGE_DIR / "prompts"

DEFAULT_MODEL = os.environ.get("VIDEO_AGENT_MODEL", "claude-opus-5-5")
WHISPER_MODEL = os.environ.get("VIDEO_AGENT_WHISPER_MODEL", "small")
FFMPEG_EXTRA = os.environ.get("VIDEO_AGENT_FFMPEG_EXTRA", "").split()

MAX_AGENT_ITERATIONS = 15
DEFAULT_MAX_TOKENS = 16000


def hebrew_capable_font() -> Path:
    """Path to a bundled font that renders Hebrew for drawtext/subtitles."""
    candidates = [
        FONTS_DIR / "NotoSansHebrew-Regular.ttf",
        FONTS_DIR / "DejaVuSans.ttf",
    ]
    for p in candidates:
        if p.exists():
            return p
    return FONTS_DIR / "DejaVuSans.ttf"
