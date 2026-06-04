#!/usr/bin/env python3
"""Scribe — generate report 336's evidence/report.html and refresh the allowlist.

Composes a single-page HTML wrapper that points at curve-latest.png,
live-agent-console.html (iframe or link), and the KPI table. Idempotent so it
can be re-run after every batch.

Also extends report.yaml's `assets:` allowlist to include all evidence files
served by report 336.

Usage:
    python scripts/build_report336.py
    python scripts/build_report336.py --evidence-dir /path/to/evidence \\
                                       --report-yaml /path/to/report.yaml
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

REPORT_JOB_DIR = Path(
    "/Users/shubh-trips/Documents/OpenAlex/oxjobs/working/parseland-work-reporting"
)
EVIDENCE_DIR_DEFAULT = REPORT_JOB_DIR / "evidence"
REPORT_YAML_DEFAULT = REPORT_JOB_DIR / "report.yaml"

REQUIRED_ASSETS = [
    "evidence/kpi-by-publisher-count.csv",
    "evidence/curve-latest.png",
    "evidence/curve-latest.svg",
    "evidence/curve-latest.json",
    "evidence/live-agent-events.ndjson",
    "evidence/live-agent-console.html",
]


REPORT_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Parseland Improver — Whole-Goldie KPI Sprint</title>
<style>
  :root {{
    --bg: oklch(98% 0 0);
    --fg: oklch(20% 0 0);
    --muted: oklch(55% 0 0);
    --accent: oklch(55% 0.18 250);
    --border: oklch(90% 0 0);
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: var(--bg); color: var(--fg); line-height: 1.55;
  }}
  .container {{ max-width: 1100px; margin: 0 auto; padding: 2rem 1.5rem 4rem; }}
  header h1 {{ margin: 0 0 0.25rem; font-size: 1.75rem; }}
  header p {{ margin: 0 0 1.5rem; color: var(--muted); }}
  section {{ margin: 2rem 0; }}
  section h2 {{ font-size: 1.25rem; margin: 0 0 0.5rem; }}
  .panel {{ border: 1px solid var(--border); border-radius: 10px; background: white; padding: 1rem 1.25rem; }}
  img.curve {{ width: 100%; height: auto; border-radius: 6px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.875rem; margin-top: 0.5rem; }}
  th, td {{ text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid var(--border); }}
  th {{ background: oklch(96% 0 0); font-weight: 600; }}
  .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-top: 1rem; }}
  .metric {{ border: 1px solid var(--border); border-radius: 8px; padding: 1rem; background: white; }}
  .metric .label {{ color: var(--muted); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.04em; }}
  .metric .value {{ font-size: 1.5rem; font-weight: 600; margin-top: 0.25rem; }}
  .console-link {{ margin: 1rem 0; }}
  .console-link a {{ display: inline-block; padding: 0.5rem 1rem; background: var(--accent); color: white; text-decoration: none; border-radius: 6px; font-weight: 500; }}
  footer {{ margin-top: 3rem; padding-top: 1rem; border-top: 1px solid var(--border); color: var(--muted); font-size: 0.8rem; }}
</style>
</head>
<body>
<div class="container">
<header>
  <h1>Parseland Improver — Whole-Goldie KPI Sprint</h1>
  <p>Generated {ts} · run_id {run_id} · batches: {batches_n} · publishers ranked: {pubs_total}</p>
</header>

<section>
  <h2>Latest KPIs</h2>
  <div class="summary-grid">{metric_cards}</div>
</section>

<section>
  <h2>KPI-vs-publisher-count curve</h2>
  <div class="panel"><img class="curve" src="curve-latest.png" alt="KPI curve"></div>
  <p style="color: var(--muted); font-size: 0.85rem; margin-top: 0.5rem;">
    Curve-driven termination: continue while marginal lift remains &gt; 0.25pp / 100 publishers across two consecutive batches.
  </p>
</section>

<section>
  <h2>Live agent console</h2>
  <div class="console-link">
    <a href="live-agent-console.html">Open live agent console →</a>
  </div>
</section>

<section>
  <h2>Batch summary</h2>
  <div class="panel">{batches_table}</div>
</section>

<footer>
  Frozen source corpus: <code>merged-FINAL.csv</code> (10,000 data rows).
  Versioned derived corpora are tracked at <code>parseland-eval/eval/data/manifest.json</code>.
  Shipped fixes pass Shield's no-regression gate; commit message includes the gate artifact path.
</footer>
</div>
</body>
</html>
"""


def load_kpi(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows


def render_metric_cards(latest: dict | None) -> str:
    if latest is None:
        return '<div class="metric"><div class="label">status</div><div class="value">no batches yet</div></div>'
    fields = [
        ("overall_authors_f1_soft", "Authors F1 (soft)"),
        ("overall_affiliations_f1_fuzzy", "Affs F1 (fuzzy)"),
        ("overall_abstract_ratio_fuzzy", "Abstract ratio"),
        ("overall_pdf_url_accuracy", "PDF URL"),
        ("overall_corresponding_accuracy", "Corresponding"),
        ("marginal_lift_per_100", "Lift / 100 pubs"),
    ]
    parts: list[str] = []
    for k, label in fields:
        try:
            v = float(latest.get(k, 0.0))
            parts.append(
                f'<div class="metric"><div class="label">{html.escape(label)}</div>'
                f'<div class="value">{v:.3f}</div></div>'
            )
        except (TypeError, ValueError):
            continue
    return "".join(parts)


def render_batches_table(rows: list[dict]) -> str:
    if not rows:
        return '<p style="color: var(--muted);">no batches yet</p>'
    cols = [
        ("batch_id", "Batch"),
        ("publishers_processed", "Publishers"),
        ("cumulative_rows", "Rows"),
        ("overall_authors_f1_soft", "Authors"),
        ("overall_affiliations_f1_fuzzy", "Affs"),
        ("overall_pdf_url_accuracy", "PDF"),
        ("marginal_lift_per_100", "Lift/100"),
        ("shipped_count", "Shipped"),
        ("blocked_count", "Blocked"),
        ("timestamp_utc", "Timestamp"),
    ]
    parts = ["<table>", "<thead><tr>"]
    parts += [f"<th>{html.escape(label)}</th>" for _, label in cols]
    parts += ["</tr></thead>", "<tbody>"]
    for r in rows[-15:]:
        parts.append("<tr>")
        for k, _ in cols:
            v = r.get(k, "")
            if k.startswith("overall_") or k == "marginal_lift_per_100":
                try:
                    v = f"{float(v):.3f}"
                except (ValueError, TypeError):
                    pass
            parts.append(f"<td>{html.escape(str(v))}</td>")
        parts.append("</tr>")
    parts += ["</tbody>", "</table>"]
    return "".join(parts)


def update_report_yaml(yaml_path: Path) -> dict:
    """Ensure report.yaml's assets list includes all REQUIRED_ASSETS. Idempotent."""
    if not yaml_path.exists():
        return {"updated": False, "reason": "report.yaml not found"}
    text = yaml_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # Find assets: block. The yaml is simple enough we do a light-touch update
    # rather than pulling pyyaml.
    out: list[str] = []
    in_assets = False
    assets_seen: set[str] = set()
    assets_indent = "  - "
    for ln in lines:
        if ln.strip() == "assets:":
            in_assets = True
            out.append(ln)
            continue
        if in_assets:
            stripped = ln.strip()
            if stripped.startswith("- "):
                asset = stripped[2:].strip()
                assets_seen.add(asset)
                out.append(ln)
                continue
            # Empty line or new key: insert any missing assets before leaving.
            if stripped == "" or stripped.endswith(":"):
                for a in REQUIRED_ASSETS:
                    if a not in assets_seen:
                        out.append(f"{assets_indent}{a}")
                        assets_seen.add(a)
                in_assets = False
                out.append(ln)
                continue
        out.append(ln)
    if in_assets:
        for a in REQUIRED_ASSETS:
            if a not in assets_seen:
                out.append(f"{assets_indent}{a}")
                assets_seen.add(a)
    new_text = "\n".join(out) + ("\n" if not out[-1].endswith("\n") else "")
    if new_text != text:
        yaml_path.write_text(new_text, encoding="utf-8")
        return {"updated": True, "assets": sorted(assets_seen)}
    return {"updated": False, "assets": sorted(assets_seen)}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--evidence-dir", type=Path, default=EVIDENCE_DIR_DEFAULT)
    p.add_argument("--report-yaml", type=Path, default=REPORT_YAML_DEFAULT)
    p.add_argument("--queue-summary", type=Path,
                   default=REPO_ROOT / "mismatches" / "publisher-queue.ndjson.summary.json")
    args = p.parse_args()

    args.evidence_dir.mkdir(parents=True, exist_ok=True)

    kpi_rows = load_kpi(args.evidence_dir / "kpi-by-publisher-count.csv")
    latest = kpi_rows[-1] if kpi_rows else None
    pubs_total = 0
    if args.queue_summary.exists():
        try:
            pubs_total = int(json.loads(args.queue_summary.read_text()).get("publisher_count") or 0)
        except Exception:
            pass

    run_id = "—"
    ledger = args.evidence_dir / "live-agent-events.ndjson"
    if ledger.exists():
        last_line = ""
        with open(ledger, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    last_line = line
        if last_line:
            try:
                run_id = json.loads(last_line).get("run_id", "—")
            except Exception:
                pass

    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out_html = REPORT_HTML.format(
        ts=html.escape(ts),
        run_id=html.escape(str(run_id)),
        batches_n=len(kpi_rows),
        pubs_total=pubs_total,
        metric_cards=render_metric_cards(latest),
        batches_table=render_batches_table(kpi_rows),
    )
    out_path = args.evidence_dir / "report.html"
    out_path.write_text(out_html, encoding="utf-8")

    yaml_result = update_report_yaml(args.report_yaml)

    print(json.dumps({
        "report_html": str(out_path),
        "report_yaml_updated": yaml_result.get("updated"),
        "assets_in_allowlist": yaml_result.get("assets"),
        "batches": len(kpi_rows),
        "pubs_total": pubs_total,
        "run_id": run_id,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
