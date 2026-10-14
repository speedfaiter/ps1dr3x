"""Auto-subtitles via faster-whisper.

The model loads lazily on first use. Downloaded weights are cached under
`video_agent/assets/models/` (gitignored).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from .. import config, logging_utils

_MODEL = None


def _format_ts(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds - (h * 3600) - (m * 60)
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def _get_model():
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise RuntimeError(
            "faster-whisper is required for auto-subtitles. Install with "
            "`pip install faster-whisper`."
        ) from e
    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model_name = config.WHISPER_MODEL
    logging_utils.say("whisper_download", model=model_name)
    # device/compute_type auto-detect; CPU-only is the default.
    os.environ.setdefault("HF_HOME", str(config.MODELS_DIR))
    _MODEL = WhisperModel(model_name, download_root=str(config.MODELS_DIR))
    return _MODEL


def transcribe_to_srt(source: Path, language: str | None = None) -> Path:
    """Transcribe the audio of `source` and write a .srt file next to it (temp)."""
    logging_utils.say("whisper_transcribing")
    model = _get_model()
    segments, _ = model.transcribe(str(source), language=language or None, vad_filter=True)
    srt_path = Path(tempfile.gettempdir()) / f"{source.stem}.auto.srt"
    with srt_path.open("w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, start=1):
            f.write(f"{i}\n")
            f.write(f"{_format_ts(seg.start)} --> {_format_ts(seg.end)}\n")
            f.write(f"{seg.text.strip()}\n\n")
    return srt_path
