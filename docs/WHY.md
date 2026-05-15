---
last_updated: 2026-05-15
---

# Why

## Purpose

A personal collection of single-file browser tools, plus a few CLI
utilities. Modeled after [`tools.simonwillison.net`](https://tools.simonwillison.net/) —
each tool is one self-contained HTML file that runs entirely in the
browser, with no build step per tool. The site is auto-generated and
deployed to GitHub Pages on every push.

I cloned the *shape* of Simon's repo (the build pipeline, the
git-history-as-database insight, the auto-doc generation) and put my own
tools inside it. The original Simon repo investigation lives in
`~/Tinker/research/` for reference.

## "Git history is the database"

This is the key insight stolen from the original. Each tool's metadata —
when it was created, what's been changed about it, the auto-generated
docs — all derive from the git log of that file. There's no separate
database of tools or a CMS:

- `gather_links.py` reads the git log to produce `gathered_links.json`
  and `tools.json`.
- `build_index.py`, `build_colophon.py`, `build_by_month.py`,
  `build_dates.py` consume those JSON files to generate the static
  site.
- `write_docs.py` calls Claude Haiku to write a `.docs.md` per tool,
  triggered when a tool's source changes.

Adding a new tool is just dropping an HTML file in the root and pushing.
The pipeline picks it up automatically.

## Why footer.js is injected at build time

The footer (Home / About / View source / Changes / last-updated date) is
injected into every tool by `build.sh`, not authored per-tool. Two
reasons:

- Each tool stays *truly* self-contained as a file — you can open it
  directly from disk and it works. The footer is metadata, not
  functionality.
- Updates to the footer don't require touching every tool's HTML.

## `extract_why` — a later addition

This repo also hosts `extract_why.py`, a CLI for mining Claude + Codex
transcripts and git history to draft `WHY.md` files in other repos. It
emerged from a conversation in this very repo (recursive, somewhat).
Why it lives here rather than in its own repo:

- The repo already had `pyproject.toml` and was set up for CLI tooling.
- It's a one-file utility; a separate repo would have been more
  infrastructure than the script needs.
- Installing via `uv tool install ~/Tinker/tools` puts the `extract_why`
  command on PATH, paired with the rest of the build scripts.

The build pipeline (the HTML tools side) and `extract_why` don't depend
on each other — they're co-located, not coupled.

## Deployment is fully automatic

GitHub Pages workflow (`pages.yml`) runs on every push:
1. Gathers git history → JSON.
2. Calls Claude Haiku to write any missing per-tool docs (requires the
   `ANTHROPIC_API_KEY` repo secret).
3. Generates index pages.
4. Injects footers.
5. Deploys to Pages.

The `test.yml` workflow runs pytest + Playwright in CI so the per-tool
HTML tools don't silently break.

Adding a tool is "git push" — nothing else.
