"""Demo v2: AE-style animated titles, lower third, and zoom.

What this would look like as a natural-language instruction to the agent:

  "Keep the whole 8 seconds. Slide 'Hello Alien' in from the left for the
   first 3 seconds. Show a lower third 'Alien McAlienface / Visitor' on the
   left between 3 and 6 seconds. Slow Ken-Burns zoom through the whole clip.
   Finish with a sepia filter and a half-second fade in and out."
"""

from pathlib import Path

from video_agent.probe import probe
from video_agent.renderer import render
from video_agent.timeline import Op, Timeline

SRC = Path(__file__).parent / "alien.mp4"
OUT = Path(__file__).parent / "alien_edited_v2.mp4"

clip = probe(SRC)
tl = Timeline(clip=clip)

# Smooth continuous zoom through the whole clip.
tl.add(
    Op(
        kind="zoom",
        args={
            "start": 0.0,
            "end": clip.duration,
            "direction": "in",
            "factor_start": 1.0,
            "factor_end": 1.2,
        },
    )
)

# AE-style animated title: slide in from the left, hold, slide out to the right.
tl.add(
    Op(
        kind="animated_text",
        args={
            "text": "Hello Alien",
            "start": 0.3,
            "end": 3.5,
            "enter_from": "left",
            "exit_to": "right",
            "enter_duration": 0.6,
            "exit_duration": 0.6,
            "position": "top",
            "style": {"size": 56, "color": "white", "stroke": "black", "stroke_width": 3},
        },
    )
)

# Lower third name card.
tl.add(
    Op(
        kind="lower_third",
        args={
            "primary_text": "Alien McAlienface",
            "secondary_text": "Visitor from GitHub",
            "start": 3.8,
            "end": 7.0,
            "side": "left",
            "accent_color": "#1f6feb",
        },
    )
)

# Mood: sepia preset.
tl.add(Op(kind="filter", args={"name": "sepia"}))

# Clean fade in / out.
tl.add(Op(kind="transition", args={"type": "fade", "at": 0.0, "duration": 0.5}))
tl.add(Op(kind="transition", args={"type": "fade", "at": 999.0, "duration": 0.5}))

result = render(tl, OUT)
print("Rendered:", result)
