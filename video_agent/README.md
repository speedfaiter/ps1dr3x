# video-agent

AI-powered video editing agent driven by Claude. Describe an edit in plain
English or Hebrew; Claude plans the edits and `ffmpeg` renders them.

## עברית

סוכן AI לעריכת וידאו. תאר מה אתה רוצה בשפה טבעית (אנגלית או עברית), והסוכן
בונה את העריכה (חיתוך, האטה/האצה, טקסט, כתוביות אוטומטיות, מוזיקה, פילטרים,
צבעים, מעברים) ומרנדר קובץ פלט אחד.

דוגמה:

```
video-agent edit input.mp4 "חתוך לעשר שניות הראשונות, האט את ההתחלה ב-50%, הוסף כותרת 'ברוכים הבאים' למעלה" -o out.mp4
```

## Features

- **Trim** — keep a segment of the source
- **Speed** — whole-clip or segment speed up / slow down
- **Text overlays** — burned-in titles, Hebrew supported
- **Auto-subtitles** — via `faster-whisper` (first run downloads ~150 MB model)
- **Music** — mix a background track under the original audio with fades
- **Filter presets** — `vintage`, `bw`, `warm`, `cold`, `cinematic`, `sepia`, `vibrant`
- **Color grading** — brightness, contrast, saturation, temperature
- **Transitions** — fade in / fade out on the clip
- **One-pass render** — the whole plan compiles to a single `ffmpeg` filter graph
  (no generational quality loss between operations)

## Install

```bash
# System: ffmpeg >= 5.0 with libx264, libass, drawtext
sudo apt install ffmpeg          # Debian/Ubuntu
brew install ffmpeg              # macOS

# Python package
pip install -e .
cp .env.example .env             # then edit, add your ANTHROPIC_API_KEY

# Smoke test (needs ffmpeg, does NOT touch the API)
video-agent selftest
```

Get an API key at <https://console.anthropic.com/>.

## Usage

Single-shot:

```bash
video-agent edit INPUT.mp4 "your instruction here" -o OUTPUT.mp4
video-agent edit clip.mp4 "slow down the first 5 seconds and add dramatic music at ~/music/bgm.mp3" -o out.mp4
```

Interactive mode (accumulate instructions, then `render`):

```bash
video-agent interactive clip.mp4 -o out.mp4
> trim to the first 10 seconds
> slow down the first 3 seconds by half
> add a title "Welcome" at the top for 2 seconds
> make it cinematic
> render
```

Utilities:

```bash
video-agent probe INPUT.mp4      # duration / resolution / fps / audio
video-agent list-filters         # available filter presets
video-agent selftest             # end-to-end check with a synthetic clip
```

Options:

- `--model claude-sonnet-5-5` — pick a cheaper model
- `--resolution 1080p|720p|480p|source`
- `--dry-run` — print the compiled `ffmpeg` command without running it
- `--lang he|en` — force UI language (defaults to `$LANG`)

## How it works

1. `ffprobe` summarizes the clip (duration, fps, resolution, audio presence).
2. Claude is called with the user's instruction plus a tool palette (`trim`,
   `change_speed`, `add_text_overlay`, `add_subtitles`, `add_music`,
   `apply_filter`, `color_grade`, `add_transition`, `get_clip_info`, `render`).
3. Each tool call appends a declarative `Op` to an in-memory `Timeline`.
   Nothing touches disk until Claude calls `render`.
4. `render` compiles the timeline into one `ffmpeg -filter_complex` command and
   runs it once.
5. Tool-use errors are returned to Claude with `is_error: true` so it can
   correct and retry.

System prompt and the tool list are cached via Anthropic prompt caching for
cheaper repeat runs.

## Scope — v1

Supported: one input clip, mp4 (h264/aac) output, CPU rendering, Hebrew + Latin
text overlays, auto-subtitles via Whisper.

Out of scope for v1 (documented so expectations are set):

- Green-screen / chroma key
- Object tracking, motion-tracked overlays
- Multi-clip splicing (one input only; `add_transition` only fades the single
  clip; the schema is forward-compatible with multi-clip)
- Multi-track audio beyond `original + one music bed + burned-in subs`
- GPU encoders (NVENC / VAAPI); set `VIDEO_AGENT_FFMPEG_EXTRA` for manual flags
- TTS / voice cloning / lip-sync
- Export formats other than `.mp4` (webm/prores/gif deferred)
- Bundled royalty-free music library (user supplies a path)
- Cloud upload

## Development

```bash
python -m pytest video_agent/tests/ -q
```

Tests cover timeline invariants, tool handler validation, ffmpeg command
compilation (needs `ffmpeg` on PATH), and an end-to-end agent run against a
scripted replay client — no API calls, deterministic, offline.

## Troubleshooting

- **`ANTHROPIC_API_KEY is not set`** — put it in `.env` next to `pyproject.toml`
  or export it before running.
- **`ffmpeg not found on PATH`** — install it with your package manager (see
  Install section).
- **`faster-whisper` download hangs** — first subtitle run downloads a Whisper
  model (~150 MB for the default `small`). Pin a smaller one with
  `VIDEO_AGENT_WHISPER_MODEL=base` in `.env`.
- **Hebrew text looks like boxes** — add a Hebrew-capable `.ttf` to
  `video_agent/assets/fonts/` (DejaVu or Noto Sans Hebrew). See
  `assets/fonts/README.md`.

## License

MIT.
