# Fonts

`drawtext` and burned-in subtitles need a `.ttf` on disk. The package looks for
these in order:

1. `NotoSansHebrew-Regular.ttf` — best for Hebrew text overlays
2. `DejaVuSans.ttf` — fallback, covers Latin + many diacritics

Neither font is bundled here (both are freely redistributable, but this repo
stays small). Drop them in before the first run that needs text.

## Where to get them

- **Noto Sans Hebrew**:
  <https://fonts.google.com/noto/specimen/Noto+Sans+Hebrew> — pick the Regular
  weight, SIL OFL 1.1 licence.
- **DejaVu Sans**: ships with most Linux distros at
  `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf` — public-domain-ish
  licence, see <https://dejavu-fonts.github.io/License.html>.

Copy either file into this directory:

```bash
cp /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf video_agent/assets/fonts/
```

If no font is present, `drawtext` will fall back to whatever ffmpeg picks from
the system — usually fine for Latin but likely wrong for Hebrew.
