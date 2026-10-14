"""Tool definitions and dispatcher for the Claude agent.

Each tool is a JSON schema (sent to the API) plus a Python handler that
mutates the shared Timeline. The terminal `render` tool actually touches disk
and returns a result that the agent loop uses to stop.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .. import renderer
from ..timeline import Op, Timeline, TimelineError

FILTER_NAMES = list(renderer.FILTER_PRESETS.keys())
POSITIONS = [
    "top",
    "center",
    "bottom",
    "top-left",
    "top-right",
    "bottom-left",
    "bottom-right",
]


class ToolError(Exception):
    """Raised by a tool handler so the agent loop can feed it back to Claude."""


@dataclass
class ToolContext:
    timeline: Timeline
    output_default: Path
    on_render: Callable[[dict], None] | None = None
    rendered: dict | None = None


Handler = Callable[[ToolContext, dict[str, Any]], dict[str, Any]]
HANDLERS: dict[str, Handler] = {}


def _register(name: str) -> Callable[[Handler], Handler]:
    def deco(fn: Handler) -> Handler:
        HANDLERS[name] = fn
        return fn

    return deco


# ------------------------- Tool schemas ---------------------------------------

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "get_clip_info",
        "description": (
            "Return a summary of the timeline so far: effective duration, "
            "resolution, fps, and the ordered list of operations added. Call "
            "this to confirm the state before `render` or when unsure what has "
            "been queued."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "name": "trim",
        "description": (
            "Keep only the segment between `start` and `end` seconds of the "
            "source clip. May be called at most once. All later time arguments "
            "refer to the trimmed timeline."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "start": {"type": "number", "description": "Start time in seconds (>= 0)."},
                "end": {"type": "number", "description": "End time in seconds (> start)."},
            },
            "required": ["start", "end"],
            "additionalProperties": False,
        },
    },
    {
        "name": "change_speed",
        "description": (
            "Change playback speed. factor > 1 speeds up (2 = 2x), factor < 1 "
            "slows down (0.5 = half speed). If `start`/`end` are given, only "
            "that segment is affected; otherwise the whole clip."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "factor": {"type": "number", "description": "Speed multiplier, must be > 0."},
                "start": {"type": ["number", "null"], "description": "Segment start seconds."},
                "end": {"type": ["number", "null"], "description": "Segment end seconds."},
            },
            "required": ["factor", "start", "end"],
            "additionalProperties": False,
        },
    },
    {
        "name": "add_text_overlay",
        "description": (
            "Burn a text overlay onto the video between `start` and `end` "
            "seconds. Supports Hebrew via a bundled font."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "start": {"type": "number"},
                "end": {"type": "number"},
                "position": {"type": "string", "enum": POSITIONS},
                "style": {
                    "type": ["object", "null"],
                    "description": "Optional {size:int, color:str, stroke:str, stroke_width:int, background:str}",
                },
            },
            "required": ["text", "start", "end", "position", "style"],
            "additionalProperties": False,
        },
    },
    {
        "name": "add_subtitles",
        "description": (
            "Burn subtitles into the video. `source` is `\"auto\"` to run "
            "Whisper on the current audio, or a path to an existing .srt file."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "'auto' or path to an .srt file.",
                },
                "language": {
                    "type": ["string", "null"],
                    "description": "Language hint for Whisper (e.g., 'he', 'en'). Optional.",
                },
            },
            "required": ["source", "language"],
            "additionalProperties": False,
        },
    },
    {
        "name": "add_music",
        "description": (
            "Mix a music track under the existing audio. The user must supply a "
            "local audio file path - no built-in library in v1."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the music file."},
                "volume": {"type": "number", "description": "0.0 (silent) to 1.0 (full)."},
                "fade_in": {"type": "number", "description": "Seconds of fade-in."},
                "fade_out": {"type": "number", "description": "Seconds of fade-out."},
                "start": {"type": ["number", "null"]},
                "end": {"type": ["number", "null"]},
            },
            "required": ["path", "volume", "fade_in", "fade_out", "start", "end"],
            "additionalProperties": False,
        },
    },
    {
        "name": "apply_filter",
        "description": "Apply a named cinematic filter preset.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "enum": FILTER_NAMES},
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "color_grade",
        "description": (
            "Manually grade color. brightness in [-1,1], contrast and saturation "
            "around 1.0 (0..3), temperature in [-100, 100] (negative = cooler)."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "brightness": {"type": ["number", "null"]},
                "contrast": {"type": ["number", "null"]},
                "saturation": {"type": ["number", "null"]},
                "temperature": {"type": ["number", "null"]},
            },
            "required": ["brightness", "contrast", "saturation", "temperature"],
            "additionalProperties": False,
        },
    },
    {
        "name": "add_transition",
        "description": (
            "Fade in (`at` near 0) or fade out (`at` near the clip end). v1 "
            "operates on the single clip; `type` picks the fade style."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["fade", "fadeblack", "dissolve"]},
                "at": {"type": "number", "description": "Timeline time to center the transition on."},
                "duration": {"type": "number"},
            },
            "required": ["type", "at", "duration"],
            "additionalProperties": False,
        },
    },
    {
        "name": "render",
        "description": (
            "TERMINAL: compile all queued operations and render the final video. "
            "Call this exactly once when the user's request is satisfied."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "output_path": {"type": ["string", "null"], "description": "Omit to use the default."},
                "resolution": {
                    "type": ["string", "null"],
                    "enum": ["1080p", "720p", "480p", "source", None],
                },
                "fps": {"type": ["number", "null"]},
                "codec": {"type": "string", "enum": ["h264", "h265"]},
            },
            "required": ["output_path", "resolution", "fps", "codec"],
            "additionalProperties": False,
        },
    },
]


# ------------------------- Handlers -------------------------------------------


@_register("get_clip_info")
def _get_clip_info(ctx: ToolContext, args: dict) -> dict:
    return ctx.timeline.summary()


@_register("trim")
def _trim(ctx: ToolContext, args: dict) -> dict:
    try:
        ctx.timeline.add(Op(kind="trim", args={"start": args["start"], "end": args["end"]}))
    except (TimelineError, ValueError) as e:
        raise ToolError(str(e)) from e
    return ctx.timeline.summary()


@_register("change_speed")
def _change_speed(ctx: ToolContext, args: dict) -> dict:
    factor = float(args["factor"])
    if factor <= 0:
        raise ToolError("factor must be > 0")
    op_args = {"factor": factor}
    if args.get("start") is not None:
        op_args["start"] = float(args["start"])
    if args.get("end") is not None:
        op_args["end"] = float(args["end"])
    ctx.timeline.add(Op(kind="speed", args=op_args))
    return ctx.timeline.summary()


@_register("add_text_overlay")
def _add_text(ctx: ToolContext, args: dict) -> dict:
    if args["end"] <= args["start"]:
        raise ToolError("end must be > start")
    style = args.get("style") or {}
    ctx.timeline.add(
        Op(
            kind="text",
            args={
                "text": args["text"],
                "start": float(args["start"]),
                "end": float(args["end"]),
                "position": args["position"],
                "style": style,
            },
        )
    )
    return ctx.timeline.summary()


@_register("add_subtitles")
def _add_subtitles(ctx: ToolContext, args: dict) -> dict:
    from . import subtitles as sub_mod

    source = args["source"]
    language = args.get("language")
    if source == "auto":
        srt = sub_mod.transcribe_to_srt(ctx.timeline.clip.source, language=language)
    else:
        srt = Path(source)
        if not srt.exists():
            raise ToolError(f"Subtitle file not found: {srt}")
    ctx.timeline.add(Op(kind="subtitles", args={"srt_path": str(srt)}))
    return ctx.timeline.summary()


@_register("add_music")
def _add_music(ctx: ToolContext, args: dict) -> dict:
    path = Path(args["path"]).expanduser()
    if not path.exists():
        raise ToolError(f"Music file not found: {path}")
    volume = float(args.get("volume", 0.3))
    if not 0.0 <= volume <= 1.0:
        raise ToolError("volume must be between 0 and 1")
    ctx.timeline.add(
        Op(
            kind="music",
            args={
                "path": str(path),
                "volume": volume,
                "fade_in": float(args.get("fade_in") or 0.0),
                "fade_out": float(args.get("fade_out") or 0.0),
                "start": None if args.get("start") is None else float(args["start"]),
                "end": None if args.get("end") is None else float(args["end"]),
            },
        )
    )
    return ctx.timeline.summary()


@_register("apply_filter")
def _apply_filter(ctx: ToolContext, args: dict) -> dict:
    name = args["name"]
    if name not in FILTER_NAMES:
        raise ToolError(f"Unknown filter: {name}. Available: {FILTER_NAMES}")
    ctx.timeline.add(Op(kind="filter", args={"name": name}))
    return ctx.timeline.summary()


@_register("color_grade")
def _color_grade(ctx: ToolContext, args: dict) -> dict:
    op_args: dict[str, Any] = {}
    for key in ("brightness", "contrast", "saturation", "temperature"):
        v = args.get(key)
        if v is not None:
            op_args[key] = float(v)
    if not op_args:
        raise ToolError("At least one of brightness/contrast/saturation/temperature required")
    ctx.timeline.add(Op(kind="color", args=op_args))
    return ctx.timeline.summary()


@_register("add_transition")
def _add_transition(ctx: ToolContext, args: dict) -> dict:
    ttype = args["type"]
    if ttype not in ("fade", "fadeblack", "dissolve"):
        raise ToolError(f"Unsupported transition: {ttype}")
    ctx.timeline.add(
        Op(
            kind="transition",
            args={
                "type": ttype,
                "at": float(args["at"]),
                "duration": float(args["duration"]),
            },
        )
    )
    return ctx.timeline.summary()


@_register("render")
def _render(ctx: ToolContext, args: dict) -> dict:
    out = args.get("output_path") or str(ctx.output_default)
    resolution = args.get("resolution")
    if resolution in (None, "source"):
        resolution = None
    fps = args.get("fps")
    codec = args.get("codec") or "h264"
    try:
        result = renderer.render(
            ctx.timeline,
            out,
            resolution=resolution,
            fps=fps,
            codec=codec,
        )
    except TimelineError as e:
        raise ToolError(str(e)) from e
    ctx.rendered = result
    if ctx.on_render:
        ctx.on_render(result)
    return result


def dispatch(name: str, args: dict, ctx: ToolContext) -> str:
    """Run a tool by name and return a JSON string result."""
    handler = HANDLERS.get(name)
    if handler is None:
        raise ToolError(f"Unknown tool: {name}")
    out = handler(ctx, args)
    return json.dumps(out, default=str)
