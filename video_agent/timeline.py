"""In-memory timeline data model.

Operations accumulate declaratively. Nothing touches disk until renderer.render()
compiles a single ffmpeg filter graph and runs it once.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from .probe import ClipInfo

OpKind = Literal[
    "trim",
    "speed",
    "text",
    "animated_text",
    "lower_third",
    "zoom",
    "subtitles",
    "music",
    "filter",
    "color",
    "transition",
]


class TimelineError(ValueError):
    pass


@dataclass
class Op:
    kind: OpKind
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class Timeline:
    clip: ClipInfo
    ops: list[Op] = field(default_factory=list)

    def add(self, op: Op) -> None:
        if op.kind == "trim":
            # Enforce single global trim in v1 for a sane time base.
            if any(o.kind == "trim" for o in self.ops):
                raise TimelineError(
                    "Only one trim operation is supported; the second one would "
                    "ambiguously reset the time base."
                )
            start = float(op.args.get("start", 0))
            end = float(op.args.get("end", self.clip.duration))
            if start < 0 or end <= start or end > self.clip.duration + 0.01:
                raise TimelineError(
                    f"Invalid trim range [{start}, {end}] for a {self.clip.duration:.2f}s clip."
                )
            op.args["start"] = start
            op.args["end"] = min(end, self.clip.duration)
            # Trim always sinks to the front so later ops operate on trimmed time.
            self.ops.insert(0, op)
            return
        self.ops.append(op)

    def effective_duration(self) -> float:
        """Approximate duration after trim and whole-clip speed ops."""
        dur = self.clip.duration
        for op in self.ops:
            if op.kind == "trim":
                dur = op.args["end"] - op.args["start"]
            elif op.kind == "speed":
                factor = float(op.args.get("factor", 1.0))
                start = op.args.get("start")
                end = op.args.get("end")
                if start is None and end is None:
                    if factor > 0:
                        dur = dur / factor
                else:
                    s = float(start or 0)
                    e = float(end or dur)
                    seg = max(0.0, e - s)
                    if factor > 0:
                        dur = dur - seg + seg / factor
        return dur

    def summary(self) -> dict[str, Any]:
        """Lightweight description for feedback to the agent."""
        return {
            "source": self.clip.source.name,
            "effective_duration_seconds": round(self.effective_duration(), 3),
            "original_resolution": f"{self.clip.width}x{self.clip.height}",
            "fps": round(self.clip.fps, 3),
            "has_audio": self.clip.has_audio,
            "ops": [
                {"kind": op.kind, "args": _redact_paths(op.args)} for op in self.ops
            ],
        }


def _redact_paths(args: dict[str, Any]) -> dict[str, Any]:
    """Return paths as basenames so the agent sees stable, short identifiers."""
    out: dict[str, Any] = {}
    for k, v in args.items():
        if isinstance(v, Path):
            out[k] = v.name
        elif isinstance(v, str) and ("/" in v or "\\" in v):
            out[k] = Path(v).name
        else:
            out[k] = v
    return out
