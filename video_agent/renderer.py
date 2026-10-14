"""Compile a Timeline into a single ffmpeg command and run it.

Design:
  - One pass. The whole timeline becomes one `-filter_complex` graph that
    produces [vout] and [aout] labels, then ffmpeg encodes once.
  - Trim is a global `-ss`/`-to` on input 0 for performance.
  - Segment speed uses trim+setpts+concat inside the filter graph.
  - Music is a second input, mixed via amix.
"""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import Any

from . import config
from .probe import ensure_ffmpeg_available
from .timeline import Op, Timeline, TimelineError

RESOLUTION_PRESETS = {
    "1080p": (1920, 1080),
    "720p": (1280, 720),
    "480p": (854, 480),
}


FILTER_PRESETS = {
    "vintage": "curves=vintage,vignette=PI/5",
    "bw": "hue=s=0",
    "warm": "colortemperature=temperature=5500",
    "cold": "colortemperature=temperature=7500",
    "cinematic": "eq=contrast=1.1:saturation=0.9,curves=preset=increase_contrast",
    "sepia": "colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131",
    "vibrant": "eq=saturation=1.4:contrast=1.08",
}


def compile_command(
    timeline: Timeline,
    output_path: Path,
    resolution: str | None = None,
    fps: float | None = None,
    codec: str = "h264",
) -> list[str]:
    """Build the ffmpeg argv for this timeline."""
    ensure_ffmpeg_available()

    ops = list(timeline.ops)
    trim_op = next((o for o in ops if o.kind == "trim"), None)
    other_ops = [o for o in ops if o.kind != "trim"]

    inputs: list[str] = []
    extra_input_flags: list[list[str]] = []

    # Input 0: the source clip, with global trim applied at the input layer.
    input0_flags: list[str] = []
    if trim_op is not None:
        input0_flags += ["-ss", f"{trim_op.args['start']}", "-to", f"{trim_op.args['end']}"]
    input0_flags += ["-i", str(timeline.clip.source)]
    extra_input_flags.append(input0_flags)

    # Collect music inputs.
    music_ops = [o for o in other_ops if o.kind == "music"]
    for mop in music_ops:
        mpath = str(mop.args["path"])
        extra_input_flags.append(["-stream_loop", "-1", "-i", mpath])

    # Build the video + audio filter graph.
    video_label = "0:v"
    audio_label = "0:a" if timeline.clip.has_audio else None

    filter_parts: list[str] = []
    counter = {"n": 0}

    def new_label(prefix: str) -> str:
        counter["n"] += 1
        return f"{prefix}{counter['n']}"

    # Apply segment / whole-clip speed changes (if any), then rest.
    speed_ops = [o for o in other_ops if o.kind == "speed"]
    for sop in speed_ops:
        video_label, audio_label = _apply_speed(
            sop, video_label, audio_label, timeline, filter_parts, new_label
        )

    # Color/filter/text/subtitles/transition: layer onto video chain in order given.
    for op in other_ops:
        if op.kind == "speed" or op.kind == "music":
            continue
        if op.kind in ("color", "filter"):
            vf = _video_filter_for(op)
            new = new_label("v")
            filter_parts.append(f"[{video_label}]{vf}[{new}]")
            video_label = new
        elif op.kind == "text":
            vf = _drawtext_for(op)
            new = new_label("v")
            filter_parts.append(f"[{video_label}]{vf}[{new}]")
            video_label = new
        elif op.kind == "subtitles":
            srt = op.args["srt_path"]
            escaped = _ffmpeg_escape(str(srt))
            font_arg = ""
            fonts_dir = config.FONTS_DIR
            if fonts_dir.exists():
                font_arg = f":fontsdir='{_ffmpeg_escape(str(fonts_dir))}'"
            new = new_label("v")
            filter_parts.append(f"[{video_label}]subtitles='{escaped}'{font_arg}[{new}]")
            video_label = new
        elif op.kind == "transition":
            vf, af = _transition_filters(op, timeline, audio_label is not None)
            if vf:
                new = new_label("v")
                filter_parts.append(f"[{video_label}]{vf}[{new}]")
                video_label = new
            if af and audio_label is not None:
                new = new_label("a")
                filter_parts.append(f"[{audio_label}]{af}[{new}]")
                audio_label = new

    # Scale/fps normalization at the end.
    final_v_filters: list[str] = []
    if resolution and resolution != "source":
        if resolution not in RESOLUTION_PRESETS:
            raise TimelineError(f"Unknown resolution preset: {resolution}")
        w, h = RESOLUTION_PRESETS[resolution]
        final_v_filters.append(
            f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"
        )
    if fps:
        final_v_filters.append(f"fps={fps}")
    if final_v_filters:
        new = new_label("v")
        filter_parts.append(f"[{video_label}]{','.join(final_v_filters)}[{new}]")
        video_label = new

    # Mix music onto audio (last, so earlier audio speed/fade already applied).
    if music_ops and audio_label is not None:
        processed_music_labels: list[str] = []
        for idx, mop in enumerate(music_ops, start=1):
            vol = float(mop.args.get("volume") or 0.3)
            fade_in = float(mop.args.get("fade_in") or 0.0)
            fade_out = float(mop.args.get("fade_out") or 0.0)
            start = float(mop.args.get("start") or 0.0)
            effective_dur = timeline.effective_duration()
            end_val = mop.args.get("end")
            end = float(end_val if end_val is not None else effective_dur)
            seg_dur = max(0.0, end - start)
            chain = [f"atrim=0:{seg_dur}", "asetpts=PTS-STARTPTS", f"volume={vol}"]
            if fade_in > 0:
                chain.append(f"afade=t=in:st=0:d={fade_in}")
            if fade_out > 0:
                chain.append(f"afade=t=out:st={max(0.0, seg_dur - fade_out)}:d={fade_out}")
            if start > 0:
                chain.append(f"adelay={int(start * 1000)}|{int(start * 1000)}")
            lbl = new_label("m")
            filter_parts.append(f"[{idx}:a]{','.join(chain)}[{lbl}]")
            processed_music_labels.append(lbl)
        mix_inputs = [audio_label] + processed_music_labels
        mixed = new_label("a")
        labels_str = "".join(f"[{m}]" for m in mix_inputs)
        filter_parts.append(
            f"{labels_str}amix=inputs={len(mix_inputs)}:duration=first:dropout_transition=0[{mixed}]"
        )
        audio_label = mixed
    elif music_ops and audio_label is None:
        # Original had no audio; use first music track as the audio.
        mop = music_ops[0]
        vol = float(mop.args.get("volume") or 0.5)
        fade_in = float(mop.args.get("fade_in") or 0.0)
        fade_out = float(mop.args.get("fade_out") or 0.0)
        effective_dur = timeline.effective_duration()
        chain = [f"atrim=0:{effective_dur}", "asetpts=PTS-STARTPTS", f"volume={vol}"]
        if fade_in > 0:
            chain.append(f"afade=t=in:st=0:d={fade_in}")
        if fade_out > 0:
            chain.append(f"afade=t=out:st={max(0.0, effective_dur - fade_out)}:d={fade_out}")
        lbl = new_label("a")
        filter_parts.append(f"[1:a]{','.join(chain)}[{lbl}]")
        audio_label = lbl

    def _map_arg(label: str) -> str:
        # Raw input stream specifiers (`0:v`, `1:a`) go without brackets.
        # Filter-graph labels go wrapped in brackets.
        if ":" in label and not any(f"[{label}]" in p for p in filter_parts):
            return label
        return f"[{label}]"

    cmd: list[str] = ["ffmpeg", "-y"]
    for group in extra_input_flags:
        cmd += group
    if filter_parts:
        cmd += ["-filter_complex", ";".join(filter_parts)]
        cmd += ["-map", _map_arg(video_label)]
        if audio_label:
            cmd += ["-map", _map_arg(audio_label)]
    else:
        cmd += ["-c", "copy"]

    # Codec settings.
    codec_map = {
        "h264": ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p"],
        "h265": ["-c:v", "libx265", "-preset", "medium", "-crf", "24", "-pix_fmt", "yuv420p"],
    }
    if codec not in codec_map:
        raise TimelineError(f"Unsupported codec: {codec}")
    if filter_parts:
        cmd += codec_map[codec]
        if audio_label:
            cmd += ["-c:a", "aac", "-b:a", "192k"]

    if config.FFMPEG_EXTRA:
        cmd += config.FFMPEG_EXTRA

    cmd.append(str(output_path))
    return cmd


def _apply_speed(
    op: Op,
    video_label: str,
    audio_label: str | None,
    timeline: Timeline,
    parts: list[str],
    new_label,
) -> tuple[str, str | None]:
    factor = float(op.args["factor"])
    if factor <= 0:
        raise TimelineError("Speed factor must be > 0")
    start = op.args.get("start")
    end = op.args.get("end")
    duration = timeline.effective_duration()

    if start is None and end is None:
        # Whole clip.
        v_new = new_label("v")
        parts.append(f"[{video_label}]setpts=PTS/{factor}[{v_new}]")
        a_new = None
        if audio_label is not None:
            a_new = new_label("a")
            parts.append(f"[{audio_label}]{_atempo_chain(factor)}[{a_new}]")
        return v_new, a_new

    s = max(0.0, float(start or 0))
    e = min(duration, float(end or duration))
    if e <= s:
        raise TimelineError("Segment speed requires end > start")

    # Split into pre / mid / post, change speed on mid, concat.
    pre_v = new_label("v")
    mid_v = new_label("v")
    post_v = new_label("v")
    mid_v_fast = new_label("v")
    parts.append(f"[{video_label}]trim=start=0:end={s},setpts=PTS-STARTPTS[{pre_v}]")
    parts.append(f"[{video_label}]trim=start={s}:end={e},setpts=PTS-STARTPTS[{mid_v}]")
    parts.append(f"[{video_label}]trim=start={e},setpts=PTS-STARTPTS[{post_v}]")
    parts.append(f"[{mid_v}]setpts=PTS/{factor}[{mid_v_fast}]")
    v_concat = new_label("v")
    parts.append(f"[{pre_v}][{mid_v_fast}][{post_v}]concat=n=3:v=1:a=0[{v_concat}]")

    a_concat: str | None = None
    if audio_label is not None:
        pre_a = new_label("a")
        mid_a = new_label("a")
        post_a = new_label("a")
        mid_a_fast = new_label("a")
        parts.append(
            f"[{audio_label}]atrim=start=0:end={s},asetpts=PTS-STARTPTS[{pre_a}]"
        )
        parts.append(
            f"[{audio_label}]atrim=start={s}:end={e},asetpts=PTS-STARTPTS[{mid_a}]"
        )
        parts.append(
            f"[{audio_label}]atrim=start={e},asetpts=PTS-STARTPTS[{post_a}]"
        )
        parts.append(f"[{mid_a}]{_atempo_chain(factor)}[{mid_a_fast}]")
        a_concat = new_label("a")
        parts.append(
            f"[{pre_a}][{mid_a_fast}][{post_a}]concat=n=3:v=0:a=1[{a_concat}]"
        )

    return v_concat, a_concat


def _atempo_chain(factor: float) -> str:
    """atempo accepts [0.5, 100.0]; chain for anything outside."""
    remaining = factor
    stages: list[str] = []
    while remaining < 0.5:
        stages.append("atempo=0.5")
        remaining /= 0.5
    while remaining > 100.0:
        stages.append("atempo=100.0")
        remaining /= 100.0
    stages.append(f"atempo={remaining}")
    return ",".join(stages)


def _video_filter_for(op: Op) -> str:
    if op.kind == "filter":
        name = op.args["name"]
        preset = FILTER_PRESETS.get(name)
        if preset is None:
            raise TimelineError(f"Unknown filter preset: {name}")
        return preset
    if op.kind == "color":
        parts: list[str] = []
        eq_parts: list[str] = []
        br = op.args.get("brightness")
        co = op.args.get("contrast")
        sa = op.args.get("saturation")
        temp = op.args.get("temperature")
        if br is not None:
            eq_parts.append(f"brightness={float(br)}")
        if co is not None:
            eq_parts.append(f"contrast={float(co)}")
        if sa is not None:
            eq_parts.append(f"saturation={float(sa)}")
        if eq_parts:
            parts.append("eq=" + ":".join(eq_parts))
        if temp is not None:
            # Map -100..100 -> 3200..9000 K
            t = float(temp)
            kelvin = 6500 + (t / 100.0) * 2500
            parts.append(f"colortemperature=temperature={kelvin}")
        return ",".join(parts) or "null"
    raise TimelineError(f"Unsupported filter op: {op.kind}")


def _drawtext_for(op: Op) -> str:
    text = _ffmpeg_text_escape(op.args["text"])
    start = float(op.args["start"])
    end = float(op.args["end"])
    position = op.args.get("position", "center")
    style = op.args.get("style") or {}
    font_size = int(style.get("size", 48))
    color = style.get("color", "white")
    stroke = style.get("stroke", "black")
    stroke_w = int(style.get("stroke_width", 2))
    box = style.get("background")

    pos_map = {
        "top": "x=(w-text_w)/2:y=h*0.08",
        "center": "x=(w-text_w)/2:y=(h-text_h)/2",
        "bottom": "x=(w-text_w)/2:y=h*0.85-text_h",
        "top-left": "x=w*0.05:y=h*0.08",
        "top-right": "x=w*0.95-text_w:y=h*0.08",
        "bottom-left": "x=w*0.05:y=h*0.85-text_h",
        "bottom-right": "x=w*0.95-text_w:y=h*0.85-text_h",
    }
    pos = pos_map.get(position, pos_map["center"])

    font_path = config.hebrew_capable_font()
    font_arg = ""
    if font_path.exists():
        font_arg = f":fontfile='{_ffmpeg_escape(str(font_path))}'"

    enable = f":enable='between(t,{start},{end})'"
    bg = f":box=1:boxcolor={box}@0.5:boxborderw=10" if box else ""
    return (
        f"drawtext=text='{text}'{font_arg}:fontsize={font_size}:fontcolor={color}:"
        f"bordercolor={stroke}:borderw={stroke_w}:{pos}{bg}{enable}"
    )


def _transition_filters(op: Op, timeline: Timeline, has_audio: bool) -> tuple[str, str]:
    kind = op.args.get("type", "fade")
    at = float(op.args.get("at", 0.0))
    duration = float(op.args.get("duration", 1.0))
    effective = timeline.effective_duration()

    # v1: fade-in/out on the single clip.
    if at < 0.5:
        direction = "in"
        start = 0.0
    else:
        direction = "out"
        start = max(0.0, effective - duration)

    if kind in ("fade", "fadeblack", "dissolve"):
        color = "black" if kind == "fadeblack" else "black"
        vf = f"fade=t={direction}:st={start}:d={duration}:color={color}"
        af = f"afade=t={direction}:st={start}:d={duration}" if has_audio else ""
        return vf, af
    raise TimelineError(f"Unsupported transition type: {kind}")


def _ffmpeg_escape(s: str) -> str:
    """Escape single quotes and backslashes for filter graph strings."""
    return s.replace("\\", "\\\\").replace("'", r"\'").replace(":", r"\:")


def _ffmpeg_text_escape(s: str) -> str:
    """Escape text content for drawtext."""
    return (
        s.replace("\\", "\\\\")
        .replace("'", r"\'")
        .replace(":", r"\:")
        .replace("%", r"\%")
    )


def render(
    timeline: Timeline,
    output_path: str | Path,
    resolution: str | None = None,
    fps: float | None = None,
    codec: str = "h264",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Compile and execute the ffmpeg command. Returns a summary dict."""
    out = Path(output_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = compile_command(timeline, out, resolution=resolution, fps=fps, codec=codec)
    if dry_run:
        return {"command": " ".join(shlex.quote(c) for c in cmd), "output_path": str(out)}

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise TimelineError(f"ffmpeg failed: {result.stderr[-2000:]}")

    size_mb = out.stat().st_size / (1024 * 1024)
    return {
        "output_path": str(out),
        "size_mb": round(size_mb, 2),
        "effective_duration_seconds": round(timeline.effective_duration(), 3),
    }
