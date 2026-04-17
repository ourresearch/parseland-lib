# parseland-lib

The parsing library behind [parseland](https://github.com/ourresearch/parseland), plus its evaluation harness and dashboard. Code without evals isn't really done — so they live here.

## Example

```python
from parseland_lib.parse import parse_page
from parseland_lib.s3 import get_landing_page_from_r2

url = 'https://doi.org/10.1002/andp.19033150414'
lp = get_landing_page_from_r2(url)
response = parse_page(lp)
print(response)
```

## Layout

```
parseland-lib/
├── parseland_lib/        Library source
├── tests/                Library tests
├── eval/                 Offline eval harness (Python)
│   ├── parseland_eval/       Harness package
│   ├── runs/                 Benchmark run JSON
│   └── Gold Standard For Parseland - Sheet1.{csv,json}
│                             100-row hand-annotated gold standard
└── dashboard/            Static dashboard (Vite + React + TS)
```

## Two-minute quickstart

```bash
# 1. Eval harness
cd eval
/opt/homebrew/bin/python3.11 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
pip install -r ../requirements.txt
python -m parseland_eval fetch
python -m parseland_eval run --label baseline

# 2. Dashboard
cd ../dashboard
npm install
npm run dev                     # → http://localhost:5173
```

## What gets measured

Per-field, at three strictnesses (see `eval/README.md` for the matrix):

| Field | Strict | Soft | Fuzzy |
|---|---|---|---|
| Authors | last + first-initial | — | rapidfuzz ≥ 85 |
| Affiliations | exact | normalized | token_set_ratio ≥ 85 |
| Abstract | exact | Levenshtein / normalized | Levenshtein / raw |
| PDF URL | canonicalized exact | — | — |

Aggregated per row, per publisher domain, and per failure mode (paywall, login, bot_check, broken_url, no_abstract, non_article, image_only, clean).

## Baseline (2026-04-16)

| Metric | Score |
|---|---|
| Authors F1 (soft) | 33.1% |
| Affiliations F1 (fuzzy) | 81.1% |
| Abstract Levenshtein | 26.4% |
| Abstract present rate | 27.0% |
| PDF URL accuracy | 12.0% |

Most Authors/Abstract loss comes from Elsevier `linkinghub.elsevier.com` redirects, Oxford "Thanks for visiting…" gates, and login-wall landing pages. See `dashboard/` → heatmap + failure-mode bar.

## Workflow

1. **Establish baseline** — `python -m parseland_eval run --label baseline` once.
2. **Make a parser change** in `parseland_lib/publisher/parsers/…`.
3. **Re-run** — `python -m parseland_eval run --label fix-elsevier-2026-04-16`.
4. **Compare** — dashboard renders delta vs previous run; trend chart accumulates.
