# parseland-eval

Offline evaluation harness for `parseland-lib` against a 100-row hand-annotated gold standard.

## Quickstart

```bash
cd eval
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
pip install -r ../parseland-lib/requirements.txt    # so parseland-lib's deps resolve
```

Then:

```bash
# 1. Cache raw HTML for every DOI (one-off, ~5 minutes).
python -m parseland_eval fetch

# 2. Run parseland-lib against cached HTML + score.
python -m parseland_eval run --label baseline
```

Output lands in `eval/runs/<label>-<timestamp>.json`. The `eval/runs/index.json` index file is regenerated after every run.

## What it measures

Per field, at three strictnesses (see `parseland_eval/score/`):

| Field          | Strict                    | Soft                                | Fuzzy                           |
|----------------|---------------------------|-------------------------------------|---------------------------------|
| Authors        | last-name + first-initial | (same; no softer variant)           | rapidfuzz token_set_ratio ≥ 85 |
| Affiliations   | exact string              | normalized string                   | token_set_ratio ≥ 85           |
| Abstract       | exact string              | Levenshtein on normalized text      | Levenshtein on raw text        |
| PDF URL        | canonicalized exact match | —                                    | —                               |

Aggregated per row, per publisher domain, per failure mode (derived from gold `Notes`).

## Known gold-standard quirks handled in adapter

Source JSON is never mutated. Adapter in `parseland_eval/gold.py` handles:

- `"N/A"` / `"N/A\`"` in Authors → `authors=[]` (expected-empty).
- Row 5 journal title in Authors → `gold_quality="journal-title-leaked"`, skip Authors scoring.
- Row 51 unparsed JSON string → retry; else `gold_quality="broken-json"`, skip Authors scoring.
- `rasses` key accepted as alias for `affiliations`.

## Tests

```bash
pytest
```
