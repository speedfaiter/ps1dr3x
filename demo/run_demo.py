"""Demonstrate the agent's rendering engine end-to-end without the API.

Simulates what Claude would plan for the instruction:
  "Keep seconds 1-7, slow down the opening 2 seconds, add a 'Hello Alien'
   title at the top for 3 seconds, apply the sepia filter, and fade in / out."
"""

from pathlib import Path

from video_agent.probe import probe
from video_agent.renderer import render
from video_agent.timeline import Op, Timeline

SRC = Path(__file__).parent / "alien.mp4"
OUT = Path(__file__).parent / "alien_edited.mp4"

clip = probe(SRC)
tl = Timeline(clip=clip)

# What the agent would call:
tl.add(Op(kind="trim", args={"start": 1.0, "end": 7.0}))
tl.add(Op(kind="speed", args={"factor": 0.5, "start": 0.0, "end": 2.0}))
tl.add(
    Op(
        kind="text",
        args={
            "text": "Hello Alien",
            "start": 0.0,
            "end": 3.0,
            "position": "top",
            "style": {"size": 42, "color": "white", "stroke": "black", "stroke_width": 3},
        },
    )
)
tl.add(Op(kind="filter", args={"name": "sepia"}))
tl.add(Op(kind="transition", args={"type": "fade", "at": 0.0, "duration": 0.5}))
tl.add(Op(kind="transition", args={"type": "fade", "at": 999.0, "duration": 0.5}))

result = render(tl, OUT)
print("Timeline:", tl.summary())
print("Rendered:", result)
