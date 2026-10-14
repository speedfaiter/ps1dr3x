"""Bilingual status strings (English / Hebrew) rendered via rich."""

from __future__ import annotations

import os
from typing import Literal

from rich.console import Console

console = Console()

Lang = Literal["en", "he"]

_STRINGS: dict[str, dict[Lang, str]] = {
    "rendering": {"en": "Rendering...", "he": "מרנדר..."},
    "render_done": {"en": "Done: {path} ({size:.1f} MB)", "he": "הסתיים: {path} ({size:.1f} MB)"},
    "probing": {"en": "Probing {path}", "he": "בודק את {path}"},
    "whisper_download": {
        "en": "Downloading Whisper model '{model}' on first use...",
        "he": "מוריד מודל Whisper '{model}' בהרצה הראשונה...",
    },
    "whisper_transcribing": {
        "en": "Transcribing audio...",
        "he": "מתמלל אודיו...",
    },
    "agent_thinking": {
        "en": "Agent planning edits...",
        "he": "הסוכן מתכנן את העריכה...",
    },
    "tool_called": {"en": "Tool: {name}", "he": "כלי: {name}"},
    "agent_max_iters": {
        "en": "Agent reached the max iteration limit ({n}) without rendering.",
        "he": "הסוכן הגיע למגבלת האיטרציות ({n}) בלי לרנדר.",
    },
    "need_api_key": {
        "en": "ANTHROPIC_API_KEY is not set. Add it to .env or export it.",
        "he": "ANTHROPIC_API_KEY לא מוגדר. הוסף אותו ל-.env או ייצא אותו.",
    },
    "ffmpeg_missing": {
        "en": "ffmpeg not found on PATH. Install it (apt/brew/choco) and retry.",
        "he": "ffmpeg לא נמצא ב-PATH. התקן אותו ונסה שוב.",
    },
}


def resolve_lang(explicit: str | None = None) -> Lang:
    if explicit in ("en", "he"):
        return explicit  # type: ignore[return-value]
    for env in ("LC_ALL", "LC_MESSAGES", "LANG"):
        v = os.environ.get(env, "")
        if v.lower().startswith("he"):
            return "he"
    return "en"


def msg(key: str, lang: Lang | None = None, /, **kw) -> str:
    lang = lang or resolve_lang()
    template = _STRINGS.get(key, {}).get(lang) or _STRINGS.get(key, {}).get("en") or key
    try:
        return template.format(**kw)
    except (KeyError, IndexError):
        return template


def say(key: str, lang: Lang | None = None, /, **kw) -> None:
    console.print(msg(key, lang, **kw))
