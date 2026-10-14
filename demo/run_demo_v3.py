"""Demo v3: TikTok/Reels-style effect suite.

Showcases: word captions (fake word timings, since alien.mp4 is silent),
zoom_punch, flash, glitch, sfx_text, blurred background (reframed to vertical).
"""

from pathlib import Path

from video_agent.probe import probe
from video_agent.renderer import render
from video_agent.timeline import Op, Timeline

SRC = Path(__file__).parent / "alien.mp4"
OUT = Path(__file__).parent / "alien_tiktok.mp4"

clip = probe(SRC)
tl = Timeline(clip=clip)

# TikTok-style word captions (fake timings since the clip is silent).
tl.add(
    Op(
        kind="word_captions",
        args={
            "words": [
                {"text": "HELLO", "start": 0.3, "end": 1.0},
                {"text": "ALIEN", "start": 1.1, "end": 1.8},
                {"text": "FROM", "start": 2.0, "end": 2.5},
                {"text": "GITHUB", "start": 2.6, "end": 3.3},
                {"text": "LAND", "start": 5.0, "end": 5.7},
            ],
            "style": {
                "size": 72,
                "color": "yellow",
                "stroke_width": 5,
                "position": "bottom",
            },
        },
    )
)

# Zoom punch for emphasis at 1.5s and 3.0s.
tl.add(Op(kind="zoom_punch", args={"at": 1.5, "duration": 0.3, "peak_zoom": 1.2}))
tl.add(Op(kind="zoom_punch", args={"at": 3.0, "duration": 0.4, "peak_zoom": 1.3}))

# Glitch burst around 4s.
tl.add(Op(kind="glitch", args={"start": 4.0, "end": 4.5, "intensity": 0.7}))

# SFX text "BOOM!" at the glitch moment.
tl.add(
    Op(
        kind="sfx_text",
        args={
            "text": "BOOM!",
            "at": 4.1,
            "duration": 0.6,
            "size": 140,
            "color": "yellow",
            "background": "red",
        },
    )
)

# Flash transition before the final beat.
tl.add(Op(kind="flash", args={"at": 5.5, "duration": 0.3, "color": "white"}))

# Reframe for vertical (Reels/TikTok 9:16).
tl.add(Op(kind="blurred_bg", args={"width": 720, "height": 1280, "blur": 25}))

# Clean fades.
tl.add(Op(kind="transition", args={"type": "fade", "at": 0.0, "duration": 0.3}))
tl.add(Op(kind="transition", args={"type": "fade", "at": 999.0, "duration": 0.4}))

result = render(tl, OUT)
print("Rendered:", result)
