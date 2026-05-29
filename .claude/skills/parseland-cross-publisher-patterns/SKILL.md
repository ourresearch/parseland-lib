---
name: parseland-cross-publisher-patterns
description: Cross-sprint knowledge base of transferable patterns discovered while improving parseland-lib publisher parsers. Read at the start of every sprint so field-orchestrators can inject prior findings into worker prompts and avoid re-discovering known infra noise, methodology pitfalls, and reusable parser idioms. Patterns are grouped by category (infra, methodology, parser-logic) and backed by an append-only NDJSON log at `mismatches/patterns.ndjson`.
---

# Parseland Cross-Publisher Patterns

Append-only, multi-sprint knowledge base. Source of truth: `mismatches/patterns.ndjson`. This document is the human-readable index.

## How to use this knowledge base

**Field-orchestrators** at sprint start: scan the categories below for patterns that touch the field you are improving (e.g. `corresponding`, `affiliations`, `authors`) or the publisher you are working on. For each relevant pattern:

1. Inject the `description` (not the exemplar) into your worker's system prompt as a "prior finding" so the worker does not re-derive it.
2. If a pattern is in the `infra` category, also inject it into the measurement harness instructions so the worker interprets metric movements correctly.
3. If a pattern is in the `methodology` category, weight your worker's confidence claims accordingly (e.g. require a larger gold slice before declaring a winner).

**Pattern-archivists** at sprint end: append new patterns only when a winning patch generalizes across publishers. Never delete; mark superseded via `superseded_by` on the older row.

**Workers** do not read this file directly. Orchestrators select and inject.

---

## Sprint log

| Sprint | Date | Patterns added | Notes |
|---|---|---|---|
| smoke-pilot-elsevier-corresponding | 2026-05-29 | 3 (0 parser-logic, 2 infra, 1 methodology) | Baseline saturated (F1=0.947 on 13 rows); no winning patch. Worker surfaced harness and methodology insights only. |

---

## Category: infra

Patterns about the measurement harness, dispatch, or repo-level architecture — not about parser logic.

### `infra-gold-cross-publisher-routing-artifact`

**Added**: 2026-05-29 (smoke-pilot-elsevier-corresponding)

When a publisher's gold NDJSON contains a DOI whose `10.<prefix>` matches that publisher but whose actual landing-page HTML is hosted on another publisher's portal (e.g. an Elsevier DOI republished on Oxford Academic's Atypon platform), an in-process diff harness that force-runs the prefix-matched parser reports a false failure. Production routing via `is_publisher_specific_parser()` correctly dispatches to the host-publisher's parser; only the measurement harness is fooled. Workers should treat such rows as harness noise, not parser bugs.

**Exemplar**: gold row `10.1016/s0378-1097(99)00346-8` → landing page `academic.oup.com/femsle/article/177/2/289/447451`. ElsevierBV parser scored corresp F1 = 0.00 on this row; production routes to the Oxford parser.

### `infra-diff-harness-needs-dispatch-aware-filter`

**Added**: 2026-05-29 (smoke-pilot-elsevier-corresponding)

`scripts/field_inprocess_diff.py` scores every gold row against the requested parser regardless of whether that parser's own `is_publisher_specific_parser()` returns True on the HTML. This produces systematic false-negative noise that affects workers across all publishers. Mitigation: skip rows where the parser self-rejects, OR mark them as `dispatch-rejected` and exclude from the aggregate micro-F1. A single guard at the row-iteration boundary cleans the signal for every future sprint.

**Suggested guard**:
```python
if not Parser(html).is_publisher_specific_parser():
    row["status"] = "dispatch-rejected"
    continue  # exclude from aggregate
```

---

## Category: methodology

Patterns about how to interpret metrics, design experiments, or weight evidence.

### `methodology-small-gold-ca-high-variance`

**Added**: 2026-05-29 (smoke-pilot-elsevier-corresponding)

**Field**: `corresponding`

When a per-publisher gold slice has only ~10–15 rows and a substantial fraction (e.g. 4/13) have `gold_total_ca == 0`, the effective denominator for corresponding-author micro-F1 collapses to 8–9 rows. Any single mismatch then dominates the metric. Workers and orchestrators should weight smoke-pilot or small-slice conclusions accordingly: a small absolute lift on a small gold can be statistical noise rather than a real signal. Prefer rerunning on a larger slice (≥50 rows with non-zero CA) before declaring a winning patch.

**Exemplar**: Smoke pilot — elsevier corresp slice = 13 rows, 4 with `gold_total_ca == 0` → effective denominator 8–9. Baseline F1 = 0.947 already near-saturated; any single-row delta swings the metric by ~6pp.

---

## Category: parser-logic

Patterns that capture transferable parser idioms (e.g. "corresponding-author detection via email-domain signal", "NBSP normalization before name comparison", "JSON-LD as fallback when meta tags are missing").

_No parser-logic patterns recorded yet — the smoke pilot produced no winning patch. Future sprints with successful patches will populate this section._
