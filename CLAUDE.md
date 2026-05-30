# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

This is a **GitHub special/profile repository**: the repo name (`ps1dr3x`) matches the
owner's GitHub username, so `README.md` is rendered as the profile page at
`https://github.com/ps1dr3x`.

There is no application code, build system, package manager, test suite, or linter. The
entire deliverable is the rendered `README.md`. "Development" here means editing Markdown
and managing the image assets in `resources/`.

## Structure

- `README.md` — the profile content GitHub renders. Mixes Markdown with raw HTML (`<img>`,
  `<a target="_blank">`) for layout control GitHub-flavored Markdown can't express.
- `resources/` — assets referenced by the README: `alien.gif` (header), and the
  `telegram.svg` / `linkedin.svg` / `github.svg` social icons.

## Conventions that matter

- **Asset references use absolute `raw.githubusercontent.com` URLs pinned to the `master`
  branch**, e.g. `https://raw.githubusercontent.com/ps1dr3x/ps1dr3x/master/resources/alien.gif`,
  not relative paths. GitHub serves profile READMEs in a context where relative asset paths
  don't reliably resolve, so any new image in `resources/` must be linked the same way. The
  branch segment is `master` — keep that consistent when adding references.
- **Dynamic stat cards** come from external services (`github-readme-stats.vercel.app`) with
  the `theme=radical` styling. Preserve the theme/params when editing so the cards stay visually consistent.
- Attribution lines (e.g. the alien gif credit at the bottom) are intentional — keep
  third-party asset credits when modifying related content.

## Workflow

- The default/published branch is `master`; the profile renders from it. Because asset URLs
  are pinned to `master`, images only appear once changes land there.
- Commit history is almost entirely "Update README.md" — this repo evolves through small
  content edits, not feature work.
- There is nothing to build, run, or test. Verify changes by previewing the Markdown/HTML
  rendering rather than running tooling.
