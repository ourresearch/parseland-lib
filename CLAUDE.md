# CLAUDE.md — parseland-lib

Guidance for Claude Code instances working in this repo. Loaded automatically.

## What this repo is

Parseland-lib is a Python library that extracts structured metadata (authors, affiliations, abstract, PDF URL) from scholarly article landing-page HTML across ~89 publisher-specific parsers. The live Flask service at `app.py` wraps it. Work on parseland quality happens here.

This repo is also a monorepo for:
- `eval/` — offline evaluation harness scoring parseland-lib against a hand-annotated gold standard
- `dashboard/` — Vite + React + TS static site rendering eval runs; deployed to Heroku (`openalex-parseland-dashboard`), auto-deploys on push to `main`

## Active job

All parseland-quality work lives under oxjob **#122 `parseland-gold-standard`** at `~/Documents/OpenAlex/oxjobs/working/parseland-gold-standard/`. Before making changes:

- Read `OBJECTIVE.md` — the single north-star
- Read `CONTEXT.md` — parseland architecture, stakeholders, data sources
- Read `LEARNING.md` — running experiment log, what worked, what didn't
- Read `PLAN.md` for phases, `ACCEPTANCE.md` for pass/fail tests

## Conventions

- **Python 3.11** required (`/opt/homebrew/bin/python3.11` on this Mac). System default 3.10 is too old for the eval harness.
- **No parseland-lib mutations without an upstream PR** — this repo IS the upstream. Changes land via GitHub.
- **Eval harness never modifies gold data in-place** — all quirks handled in adapters (`gold.py` `_normalize_authors_field`).
- **Dashboard reads `public/runs` via symlink** to `../eval/runs/`. Don't copy JSON; re-run eval and reload.
- **Tests**: `cd eval && .venv/bin/pytest` — 25/25 must pass before committing scorer changes.
- **Commits**: conventional commits (`feat(eval):`, `fix(dashboard):`). Sign off before force-pushing to `main` for obvious reasons.

## Quickstart

```bash
# Eval harness (first time)
cd eval
/opt/homebrew/bin/python3.11 -m venv .venv
.venv/bin/pip install -e '.[dev]'

# Fetch HTML for all 100 gold DOIs
.venv/bin/python -m parseland_eval fetch

# Score parseland-lib against gold
.venv/bin/python -m parseland_eval run --label baseline

# Score a Claude prompt against the 50-row holdout (requires ANTHROPIC_API_KEY in eval/.env)
.venv/bin/python -m parseland_eval.prompt_eval --model claude-sonnet-4-6 --label sonnet-v1

# Live TUI while a run is in flight (tails the log)
.venv/bin/python -m parseland_eval.tui /tmp/prompt_eval.log
```

## Key files by concern

| Concern | File |
|---|---|
| Path constants | `eval/parseland_eval/paths.py` |
| Gold-standard loader (tolerant) | `eval/parseland_eval/gold.py` |
| CSV → JSON rebuilder | `eval/parseland_eval/build_gold.py` |
| 50/50 seed/holdout split | `eval/parseland_eval/split.py` |
| Parseland-lib runner | `eval/parseland_eval/runner.py` |
| Per-field scorers | `eval/parseland_eval/score/*.py` |
| Report writer | `eval/parseland_eval/report.py` |
| Anthropic extraction scaffold | `eval/parseland_eval/expand.py` |
| Anthropic holdout eval | `eval/parseland_eval/prompt_eval.py` |
| Prompt templates (versioned) | `eval/parseland_eval/prompts/` |
| Live TUI | `eval/parseland_eval/tui.py` |
| Dashboard source | `dashboard/src/` |
| Heroku deploy config | root `package.json`, `Procfile`, `.github/workflows/deploy-dashboard.yml` |

## Pitfalls

- **Sonnet 4.6 and Opus 4.7 have 1M context at standard pricing** (confirmed April 2026). No `context-1m-*` beta header needed.
- **Few-shot + full HTML blows context** — 50 few-shot × 40K chars = 500K tokens per call. Use `_pick_diverse_seed()` (one per DOI-prefix / publisher registrant, up to 10) + ≤12K excerpts for few-shot, ≤30K for target. Enable prompt caching on the last few-shot assistant turn — the whole seed becomes ~90%-off after the first request.
- **html-cache/ is gitignored** — lose the cache and every fetch re-runs. Don't rm -rf casually.
- **`.env` lives at `eval/.env`** — covered by root `.gitignore` (line 2). `chmod 600`. Never commit.
- **Heroku nodejs buildpack skips devDependencies by default** — `heroku-postbuild` must use `npm ci --include=dev` or `tsc` is missing.
- **Dashboard auto-deploys only when GHA workflow paths trigger it** — currently on all main pushes. Be intentional about what's committed; adding a new eval run file triggers a rebuild.

## Git / branch hygiene

- Default branch: `main`. Pushes auto-deploy dashboard via `.github/workflows/deploy-dashboard.yml`.
- Direct pushes to `main` are allowed by convention in this repo (small team). PRs are optional.
- Heroku `HEROKU_API_KEY` secret lives in the GitHub repo settings — rotate via `heroku authorizations:rotate`.

## External dependencies

- **Anthropic API** — Claude Sonnet 4.6 default for gold expansion. Key in `eval/.env` as `ANTHROPIC_API_KEY`.
- **OpenAI API** — GPT reviewer for pilot + gold-expansion validation. Key in `eval/.env` as `OPENAI_API_KEY` (chmod 600).
- **Anthropic SDK 0.42**, **python-dotenv 1.0**, **rich** — pinned in `eval/pyproject.toml`.
- **Vercel `agent-browser`** — global CLI (`npm install -g agent-browser && agent-browser install`). Headless Chrome binary installs to `~/.agent-browser/browsers/`. Used for JS-rendered landing pages. Known limitation: UA string advertises `HeadlessChrome` so bot-checked publishers (ScienceDirect, Wiley) block it — Zyte cloud mode is the mitigation for Phase 4.

## Where to put new work

| New work | Location |
|---|---|
| Parser fix in parseland-lib | `parseland_lib/publisher/parsers/…` + landing-page parser test |
| New scorer / new metric | `eval/parseland_eval/score/…` + unit test under `eval/tests/` |
| Dashboard feature | `dashboard/src/…` — keep bundle under 150 KB JS gzipped |
| New prompt version | `eval/parseland_eval/prompts/extraction_v2.md` (never overwrite v1 after a run has used it — runs reference the version by filename) |
| Experiment log entry | `~/Documents/OpenAlex/oxjobs/working/parseland-gold-standard/LEARNING.md` |
