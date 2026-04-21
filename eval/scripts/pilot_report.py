"""Pilot P4: summary report for the 50-DOI pilot.

Aggregates:
- Per-pass extraction success (non-empty Authors/Abstract/PDF URL rates)
- Per-pass cost, wall time, error count
- Agent-browser bot-check rate per pass
- GPT reviewer verdict distribution per field per pass (if review CSV exists)
- Publisher distribution over the 50 DOIs (DOI prefix)

Prints to stdout and appends a dated entry to the oxjob LEARNING.md.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from parseland_eval.paths import EVAL_DIR


PASSIVE_CSV = EVAL_DIR / "data" / "random-50-extracted.csv"
PASSIVE_META = EVAL_DIR / "data" / "random-50-extracted.meta.json"
AGENTIC_CSV = EVAL_DIR / "data" / "random-50-agentic.csv"
AGENTIC_META = EVAL_DIR / "data" / "random-50-agentic.meta.json"
DIFF_CSV = EVAL_DIR / "data" / "random-50-diff.csv"
REVIEW_CSV = EVAL_DIR / "data" / "random-50-review.csv"
REVIEW_META = EVAL_DIR / "data" / "random-50-review.meta.json"

LEARNING_MD = Path.home() / "Documents/OpenAlex/oxjobs/working/parseland-gold-standard/LEARNING.md"


def _load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _load_meta(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _extraction_stats(rows: list[dict[str, str]]) -> dict[str, Any]:
    if not rows:
        return {}
    n = len(rows)
    authors_hit = sum(1 for r in rows if (r.get("Authors") or "").strip())
    abstract_hit = sum(1 for r in rows if (r.get("Abstract") or "").strip())
    pdf_hit = sum(1 for r in rows if (r.get("PDF URL") or "").strip())
    bot_checks = sum(1 for r in rows if (r.get("Has Bot Check") or "").upper() == "TRUE")
    status_false = sum(1 for r in rows if (r.get("Status") or "").upper() == "FALSE")
    return {
        "rows": n,
        "authors_hit_rate": f"{authors_hit}/{n} ({100*authors_hit/n:.0f}%)",
        "abstract_hit_rate": f"{abstract_hit}/{n} ({100*abstract_hit/n:.0f}%)",
        "pdf_url_hit_rate": f"{pdf_hit}/{n} ({100*pdf_hit/n:.0f}%)",
        "bot_check_rate": f"{bot_checks}/{n} ({100*bot_checks/n:.0f}%)",
        "status_false_rate": f"{status_false}/{n} ({100*status_false/n:.0f}%)",
    }


def _publisher_distribution(rows: list[dict[str, str]]) -> dict[str, int]:
    prefixes: Counter[str] = Counter()
    for r in rows:
        doi = r.get("DOI") or ""
        prefix = doi.split("/", 1)[0] if "/" in doi else doi
        prefixes[prefix] += 1
    return dict(prefixes.most_common())


def _review_summary(review_rows: list[dict[str, str]]) -> dict[str, dict[str, Counter]]:
    """{pass_name: {field: Counter(verdict -> count)}}."""
    out: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    for r in review_rows:
        out[r["pass_name"]][r["field"]][r["verdict"]] += 1
    return {p: {f: dict(c) for f, c in fields.items()} for p, fields in out.items()}


def _diff_summary(diff_rows: list[dict[str, str]]) -> dict[str, Counter]:
    out: dict[str, Counter] = defaultdict(Counter)
    for r in diff_rows:
        out[r["field"]][r["verdict"]] += 1
    return {f: dict(c) for f, c in out.items()}


def _fmt_field_table(title: str, data: dict[str, Counter] | dict[str, dict]) -> str:
    lines = [f"\n{title}"]
    if not data:
        lines.append("  (no data)")
        return "\n".join(lines)
    # collect all verdict keys
    verdicts = sorted({k for c in data.values() for k in c})
    header = ["field"] + verdicts
    widths = [max(18, len(h)) for h in header]
    lines.append("  " + " | ".join(h.rjust(w) for h, w in zip(header, widths)))
    lines.append("  " + "-+-".join("-" * w for w in widths))
    for field_name, counts in data.items():
        cells = [field_name] + [str(counts.get(v, 0)) for v in verdicts]
        lines.append("  " + " | ".join(c.rjust(w) for c, w in zip(cells, widths)))
    return "\n".join(lines)


def _build_report() -> str:
    pa_rows = _load_csv(PASSIVE_CSV)
    ag_rows = _load_csv(AGENTIC_CSV)
    diff_rows = _load_csv(DIFF_CSV)
    review_rows = _load_csv(REVIEW_CSV)
    pa_meta = _load_meta(PASSIVE_META)
    ag_meta = _load_meta(AGENTIC_META)
    review_meta = _load_meta(REVIEW_META)

    pa_totals = pa_meta.get("totals") or {}
    ag_totals = ag_meta.get("totals") or {}

    lines = []
    lines.append(f"# 50-DOI Pilot Report — {dt.datetime.now():%Y-%m-%d %H:%M}")
    lines.append("")
    lines.append("## Pass A (passive — agent-browser → Claude API)")
    for k, v in _extraction_stats(pa_rows).items():
        lines.append(f"- {k}: {v}")
    lines.append(f"- cost_usd: {pa_totals.get('cost_usd', '?')}")
    lines.append(f"- wall_seconds: {pa_totals.get('wall_seconds', '?')}")
    lines.append(f"- errors: {pa_totals.get('errors', '?')}")

    lines.append("")
    lines.append("## Pass B (agentic — Claude drives browser via tool-use)")
    for k, v in _extraction_stats(ag_rows).items():
        lines.append(f"- {k}: {v}")
    lines.append(f"- cost_usd: {ag_totals.get('cost_usd', '?')}")
    lines.append(f"- wall_seconds: {ag_totals.get('wall_seconds', '?')}")
    lines.append(f"- errors: {ag_totals.get('errors', '?')}")
    lines.append(f"- total_turns: {ag_totals.get('total_turns', '?')}")
    lines.append(f"- tool_calls_by_name: {ag_totals.get('tool_calls_by_name', '?')}")

    lines.append("")
    lines.append("## Passive vs Agentic diff")
    lines.append(_fmt_field_table("Per-field verdict counts:", _diff_summary(diff_rows)))

    lines.append("")
    lines.append("## GPT reviewer verdicts")
    review_summary = _review_summary(review_rows)
    if review_summary:
        for pass_name, fields in review_summary.items():
            lines.append(_fmt_field_table(f"Pass {pass_name}:", fields))
        lines.append(f"\n  GPT cost: ${review_meta.get('total_cost_usd', '?')} "
                     f"model={review_meta.get('model', '?')}")
    else:
        lines.append("  (no GPT review — run gpt_review.py to populate)")

    lines.append("")
    lines.append("## Publisher distribution (DOI prefixes, passive CSV)")
    for prefix, count in _publisher_distribution(pa_rows).items():
        lines.append(f"- {prefix}: {count}")

    lines.append("")
    lines.append("## Totals")
    total_cost = float(pa_totals.get("cost_usd") or 0) + \
                 float(ag_totals.get("cost_usd") or 0) + \
                 float(review_meta.get("total_cost_usd") or 0)
    lines.append(f"- Pilot total cost: ${total_cost:.4f}")
    lines.append(f"  - Passive (Anthropic): ${pa_totals.get('cost_usd', 0)}")
    lines.append(f"  - Agentic (Anthropic): ${ag_totals.get('cost_usd', 0)}")
    lines.append(f"  - GPT review (OpenAI): ${review_meta.get('total_cost_usd', 0)}")

    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-learning", action="store_true",
                    help="Skip appending to the oxjob LEARNING.md.")
    args = ap.parse_args()

    report = _build_report()
    print(report)

    if not args.no_learning and LEARNING_MD.exists():
        with LEARNING_MD.open("a", encoding="utf-8") as f:
            f.write("\n\n---\n\n")
            f.write(report)
            f.write("\n")
        print(f"\nappended to {LEARNING_MD}")
    elif not args.no_learning:
        print(f"\n(LEARNING.md not found at {LEARNING_MD}, skipped append)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
