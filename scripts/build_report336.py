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
WORKFLOW_DIR_DEFAULT = REPO_ROOT / "mismatches" / "workflows" / "20260604T163736Z-77fe45"

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
  <p>Generated {ts} · run_id {run_id} · batches: {batches_n} · publishers ranked: {pubs_total} · publisher-field cells: {queue_cells}</p>
</header>

<section>
  <h2>Latest KPIs</h2>
  <div class="summary-grid">{metric_cards}</div>
</section>

<section>
  <h2>Full 10K coverage and 98% targets</h2>
  <div class="panel">{coverage_status}</div>
  <div class="panel" style="margin-top: 1rem;">{field_target_table}</div>
</section>

<section>
  <h2>Publisher × field accounting</h2>
  <div class="panel">{publisher_field_table}</div>
</section>

<section>
  <h2>KPI-vs-publisher-count curve</h2>
  <div class="panel">{curve_svg_inline}</div>
  <p style="color: var(--muted); font-size: 0.85rem; margin-top: 0.5rem;">
    Curve-driven termination: continue while marginal lift remains &gt; 0.25pp / 100 publishers across two consecutive batches.
    <a href="curve-latest.png" style="margin-left:0.5rem;">PNG</a> ·
    <a href="curve-latest.svg">SVG</a> ·
    <a href="curve-latest.json">JSON</a>
  </p>
</section>

<section>
  <h2>Per-field opportunity table</h2>
  <div class="panel">{field_opportunity_table}</div>
</section>

<section>
  <h2>Publisher queue — ready / onboarding</h2>
  <div class="panel">{publisher_queue_table}</div>
</section>

<section>
  <h2>Goldie-backfilled candidate status</h2>
  <div class="panel">{goldie_backfilled_table}</div>
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


def _load_run_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _run_total_rows(run: dict) -> int:
    cov = run.get("coverage") or {}
    try:
        return int(cov.get("total_rows", run.get("row_count_corpus", 0)) or 0)
    except (TypeError, ValueError):
        return 0


def find_latest_whole_goldie_run() -> Path | None:
    candidates = list((REPO_ROOT / "mismatches").glob("whole-goldie*.json"))
    candidates += list((REPO_ROOT / "eval" / "runs").glob("whole-goldie*.json"))
    candidates = [p for p in candidates if p.is_file()]
    if not candidates:
        return None

    # The live report is the full-corpus control surface. Scoped gates are still
    # valuable evidence, but they must not replace the main 10K KPI/coverage view.
    full_10k = []
    for path in candidates:
        run = _load_run_json(path)
        if run and _run_total_rows(run) >= 10000:
            full_10k.append(path)
    if full_10k:
        return max(full_10k, key=lambda p: p.stat().st_mtime)
    return max(candidates, key=lambda p: p.stat().st_mtime)


def load_latest_whole_goldie() -> dict | None:
    path = find_latest_whole_goldie_run()
    if not path:
        return None
    data = _load_run_json(path)
    if data is None:
        return None
    data["_artifact_path"] = str(path)
    return data


def load_workflow_summary() -> dict:
    path = WORKFLOW_DIR_DEFAULT / "summary.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def render_coverage_status(run: dict | None, workflow_summary: dict | None = None) -> str:
    if not run:
        return '<p style="color: var(--muted);">No whole-Goldie coverage artifact found yet. Target corpus: <strong>10,000</strong> rows; field target: <strong>98%</strong>.</p>'
    cov = run.get("coverage") or {}
    workflow_summary = workflow_summary or {}
    artifact = run.get("_artifact_path", "")
    total = cov.get("total_rows", run.get("row_count_corpus", 0))
    full_target = 10000
    queue_cells = workflow_summary.get("total_tasks") or "—"
    ranked_publishers = workflow_summary.get("total_publishers") or "—"
    if int(total or 0) >= full_target:
        artifact_note = (
            "Report is using the latest full 10,000-row whole-Goldie artifact. "
            "Scoped publisher gates remain available through the live ledger."
        )
    else:
        artifact_note = (
            "Full 10,000-row accounting remains the active gate until this section "
            "shows 10,000 current artifact rows."
        )

    parts = [
        '<div class="summary-grid">',
        f'<div class="metric"><div class="label">Current artifact rows</div><div class="value">{html.escape(str(total))}</div></div>',
        f'<div class="metric"><div class="label">Full target rows</div><div class="value">{full_target:,}</div></div>',
        f'<div class="metric"><div class="label">HTML available</div><div class="value">{html.escape(str(cov.get("html_available", "—")))}</div></div>',
        f'<div class="metric"><div class="label">Retrieval blocked</div><div class="value">{html.escape(str(cov.get("retrieval_blocked_rows", "—")))}</div></div>',
        f'<div class="metric"><div class="label">Backfill candidates</div><div class="value">{html.escape(str(cov.get("gold_empty_parser_present_count", "—")))}</div></div>',
        f'<div class="metric"><div class="label">Per-field target</div><div class="value">98%</div></div>',
        f'<div class="metric"><div class="label">Publisher-field cells</div><div class="value">{html.escape(str(queue_cells))}</div></div>',
        f'<div class="metric"><div class="label">Publishers ranked</div><div class="value">{html.escape(str(ranked_publishers))}</div></div>',
        '</div>',
        f'<p style="color: var(--muted); font-size: 0.85rem;">Latest whole-Goldie artifact: <code>{html.escape(artifact)}</code>. {html.escape(artifact_note)}</p>',
    ]
    by_status = workflow_summary.get("by_status") or {}
    if by_status:
        parts.append("<p>Publisher-field queue status: ")
        parts.append(" · ".join(f"{html.escape(str(k))}: {html.escape(str(v))}" for k, v in by_status.items()))
        parts.append("</p>")
    reasons = cov.get("retrieval_blocked_by_reason") or {}
    if reasons:
        parts.append("<p>Retrieval blocked by reason: ")
        parts.append(" · ".join(f"{html.escape(str(k))}: {html.escape(str(v))}" for k, v in reasons.items()))
        parts.append("</p>")
    return "".join(parts)


def render_field_target_table(run: dict | None) -> str:
    if not run:
        return '<p style="color: var(--muted);">No field target data yet.</p>'
    summary = run.get("summary") or {}
    overall = summary.get("overall") or {}
    per_field = summary.get("per_field") or {}
    metrics = [
        ("authors", "authors_f1_soft"),
        ("affiliations", "affiliations_f1_fuzzy"),
        ("abstract", "abstract_ratio_fuzzy"),
        ("pdf_url", "pdf_url_accuracy"),
        ("corresponding", "corresponding_accuracy"),
    ]
    parts = ["<table><thead><tr>"]
    cols = ["Field", "Current KPI", "Distance to 98%", "Rows", "HTML", "Blocked", "Scored", "Empty-empty", "Misses", "Backfill", "Status"]
    parts += [f"<th>{c}</th>" for c in cols]
    parts += ["</tr></thead><tbody>"]
    for field, metric in metrics:
        current = float(overall.get(metric) or 0.0)
        counts = per_field.get(field) or {}
        distance = max(0.0, 0.98 - current)
        status = "above_98" if current >= 0.98 else "needs_agent_or_explanation"
        misses = int(counts.get("gold_present_parser_empty", 0))
        parts.append("<tr>")
        vals = [
            field,
            f"{current:.3f}",
            f"{distance:.3f}",
            counts.get("total_rows", "—"),
            counts.get("html_available", "—"),
            counts.get("retrieval_blocked", "—"),
            counts.get("scored_rows", "—"),
            counts.get("empty_empty_pass", "—"),
            misses,
            counts.get("gold_empty_parser_present", "—"),
            status,
        ]
        parts += [f"<td>{html.escape(str(v))}</td>" for v in vals]
        parts.append("</tr>")
    parts += ["</tbody></table>"]
    return "".join(parts)


def load_publisher_field_tasks() -> dict[tuple[str, str], dict]:
    path = REPO_ROOT / "mismatches" / "workflows" / "20260604T163736Z-77fe45" / "publisher-field-queue.v2.ndjson"
    if not path.exists():
        return {}
    tasks: dict[tuple[str, str], dict] = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            pub = str(row.get("publisher_id") or "")
            field = str(row.get("field") or "")
            if pub and field:
                tasks[(pub, field)] = row
    return tasks


def render_publisher_field_table(run: dict | None) -> str:
    if not run:
        return '<p style="color: var(--muted);">No publisher × field accounting yet.</p>'
    summary = run.get("summary") or {}
    per_pub = summary.get("per_publisher") or {}
    per_pub_field = summary.get("per_publisher_field") or {}
    task_by_cell = load_publisher_field_tasks()
    field_metrics = {
        "authors": "authors_f1_soft",
        "affiliations": "affiliations_f1_fuzzy",
        "abstract": "abstract_ratio_fuzzy",
        "pdf_url": "pdf_url_accuracy",
        "corresponding": "corresponding_accuracy",
    }
    rows: list[tuple[int, str, str, dict, dict]] = []
    for pub, fields in per_pub_field.items():
        for field, counts in fields.items():
            blocked = int(counts.get("retrieval_blocked", 0))
            backfill = int(counts.get("gold_empty_parser_present", 0))
            misses = int(counts.get("gold_present_parser_empty", 0))
            rows.append((blocked + backfill + misses, pub, field, counts, per_pub.get(pub, {})))
    rows.sort(reverse=True)
    if not rows:
        return '<p style="color: var(--muted);">No publisher × field rows yet.</p>'
    parts = ["<table><thead><tr>"]
    cols = [
        "Publisher",
        "Field",
        "KPI",
        "Distance",
        "Rows",
        "HTML",
        "Blocked",
        "Scored",
        "Empty-empty",
        "Misses",
        "Backfill",
        "Active agent",
        "Status",
        "Next action",
        "Latest artifact",
    ]
    parts += [f"<th>{c}</th>" for c in cols]
    parts += ["</tr></thead><tbody>"]
    for _, pub, field, counts, pub_summary in rows[:100]:
        metric = field_metrics.get(field)
        current = float(pub_summary.get(metric) or 0.0) if metric else 0.0
        distance = max(0.0, 0.98 - current)
        task = task_by_cell.get((pub, field), {})
        vals = [
            pub,
            field,
            f"{current:.3f}",
            f"{distance:.3f}",
            counts.get("total_rows", "—"),
            counts.get("html_available", "—"),
            counts.get("retrieval_blocked", "—"),
            counts.get("scored_rows", "—"),
            counts.get("empty_empty_pass", "—"),
            counts.get("gold_present_parser_empty", "—"),
            counts.get("gold_empty_parser_present", "—"),
            task.get("assigned_agent") or "—",
            task.get("status") or "—",
            task.get("next_action") or "—",
            task.get("artifact_path") or "—",
        ]
        parts.append("<tr>")
        parts += [f"<td>{html.escape(str(v))}</td>" for v in vals]
        parts.append("</tr>")
    parts += ["</tbody></table>"]
    if len(rows) > 100:
        parts.append(f'<p style="color: var(--muted); font-size: 0.8rem;">Showing top 100 of {len(rows)} publisher × field rows by blocked/miss/backfill volume.</p>')
    return "".join(parts)


def update_report_yaml(yaml_path: Path) -> dict:
    """Ensure report.yaml's assets list includes all REQUIRED_ASSETS. Idempotent."""
    if not yaml_path.exists():
        return {"updated": False, "reason": "report.yaml not found"}
    text = yaml_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # Find assets: block. The yaml is simple enough we do a light-touch update
    # rather than pulling pyyaml. Robustly: leave the assets block the moment
    # a line is NOT either (a) a `  - ...` continuation or (b) blank.
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
            # Continuation of the block: a list item.
            if stripped.startswith("- "):
                asset = stripped[2:].strip()
                assets_seen.add(asset)
                out.append(ln)
                continue
            # Anything else closes the block. Flush missing assets first, then
            # let the line through unchanged. This handles the `tags: [...]`
            # case (which doesn't end with ":") that the previous logic
            # mis-handled by treating it as a continuation.
            for a in REQUIRED_ASSETS:
                if a not in assets_seen:
                    out.append(f"{assets_indent}{a}")
                    assets_seen.add(a)
            in_assets = False
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


def load_curve_svg_inline(svg_path: Path) -> str:
    """Embed the curve SVG directly. Strips any <?xml?> and outer comments
    so it nests cleanly inside <div>. Falls back to an <img src=...> tag
    if the SVG file doesn't exist (e.g. matplotlib not installed)."""
    if not svg_path.exists():
        return '<img class="curve" src="curve-latest.png" alt="KPI curve" style="width:100%;height:auto;">'
    try:
        text = svg_path.read_text(encoding="utf-8")
    except Exception:
        return '<img class="curve" src="curve-latest.png" alt="KPI curve" style="width:100%;height:auto;">'
    # Drop the XML prolog if present.
    idx = text.find("<svg")
    if idx == -1:
        return '<img class="curve" src="curve-latest.png" alt="KPI curve" style="width:100%;height:auto;">'
    svg = text[idx:]
    # Force responsive width by injecting style on the root tag if absent.
    if "width=" not in svg[:200]:
        svg = svg.replace("<svg", '<svg style="width:100%;height:auto;"', 1)
    else:
        # Strip fixed width/height for responsive sizing.
        import re as _re
        svg = _re.sub(r'\s(width|height)="[^"]+"', "", svg, count=2)
        svg = svg.replace("<svg", '<svg style="width:100%;height:auto;"', 1)
    return svg


def render_field_opportunity_table(path: Path) -> str:
    if not path.exists():
        return '<p style="color: var(--muted);">no field-opportunity ranking yet — run scripts/rank_field_opportunity.py</p>'
    try:
        data = json.loads(path.read_text())
    except Exception:
        return '<p style="color: var(--muted);">field-opportunity.json unreadable</p>'
    rows = data.get("rows", [])
    if not rows:
        return '<p style="color: var(--muted);">no rows</p>'
    cols = [
        ("field", "Field"),
        ("current_kpi", "Current KPI"),
        ("scored_rows", "Scored rows"),
        ("headroom_pp", "Headroom (pp)"),
        ("top_publisher", "Top publisher"),
        ("active_agent", "Active agent"),
        ("status", "Status"),
        ("recommendation", "Recommendation"),
    ]
    parts = ["<table>", "<thead><tr>"]
    parts += [f"<th>{html.escape(label)}</th>" for _, label in cols]
    parts += ["</tr></thead>", "<tbody>"]
    for r in rows:
        parts.append("<tr>")
        for k, _ in cols:
            v = r.get(k, "")
            if k == "current_kpi" and isinstance(v, (int, float)):
                v = f"{float(v):.3f}"
            parts.append(f"<td>{html.escape(str(v))}</td>")
        parts.append("</tr>")
    parts += ["</tbody>", "</table>"]
    return "".join(parts)


def render_publisher_queue_table(path: Path) -> str:
    if not path.exists():
        return '<p style="color: var(--muted);">no queue yet — run scripts/rank_publishers.py</p>'
    rows: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                rows.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
    if not rows:
        return '<p style="color: var(--muted);">empty queue</p>'
    cols = [
        ("publisher_id", "Publisher"),
        ("parser_status", "Parser status"),
        ("row_count", "Rows"),
        ("gold_fixture_path", "Gold fixture"),
        ("priority", "Priority"),
        ("confidence_tier", "Confidence"),
    ]
    parts = ["<table>", "<thead><tr>"]
    parts += [f"<th>{html.escape(label)}</th>" for _, label in cols]
    parts += ["</tr></thead>", "<tbody>"]
    for r in rows[:20]:
        parts.append("<tr>")
        for k, _ in cols:
            v = r.get(k, "")
            if k == "priority" and isinstance(v, (int, float)):
                v = f"{float(v):.2f}"
            if k == "gold_fixture_path":
                v = "YES" if v else "no"
            parts.append(f"<td>{html.escape(str(v))}</td>")
        parts.append("</tr>")
    parts += ["</tbody>", "</table>"]
    if len(rows) > 20:
        parts.append(f'<p style="color: var(--muted); margin-top: 0.4rem; font-size: 0.8rem;">+ {len(rows) - 20} more rows in mismatches/publisher-queue.ndjson</p>')
    return "".join(parts)


def render_goldie_backfilled_table(path: Path) -> str:
    if not path.exists():
        return '<p style="color: var(--muted);">no Goldie-backfilled candidates yet</p>'
    rows: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                rows.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
    if not rows:
        return '<p style="color: var(--muted);">no Goldie-backfilled candidates yet</p>'
    # Summarize per-status + per-field
    by_status = {}
    by_field = {}
    for r in rows:
        s = r.get("status", "pending")
        by_status[s] = by_status.get(s, 0) + 1
        f = r.get("field", "?")
        by_field[f] = by_field.get(f, 0) + 1
    parts = [
        f'<p>Candidates total: <strong>{len(rows)}</strong>. ',
        " · ".join(f"<strong>{html.escape(s)}</strong>: {n}" for s, n in by_status.items()),
        "</p>",
        f'<p>By field: ',
        " · ".join(f"{html.escape(k)}: {v}" for k, v in by_field.items()),
        "</p>",
    ]
    # Show first 10 candidate rows
    cols = [
        ("doi", "DOI"),
        ("publisher", "Publisher"),
        ("field", "Field"),
        ("status", "Status"),
        ("approving_agent", "Reviewer"),
    ]
    parts += ["<table>", "<thead><tr>"]
    parts += [f"<th>{html.escape(label)}</th>" for _, label in cols]
    parts += ["</tr></thead>", "<tbody>"]
    for r in rows[:10]:
        parts.append("<tr>")
        for k, _ in cols:
            v = r.get(k, "")
            parts.append(f"<td>{html.escape(str(v))}</td>")
        parts.append("</tr>")
    parts += ["</tbody>", "</table>"]
    parts.append(render_goldie_grounding_checkpoints())
    return "".join(parts)


def render_goldie_grounding_checkpoints() -> str:
    result_paths = sorted(
        (REPO_ROOT / "mismatches" / "workflows").glob("*/results/goldie_backfill*.ndjson"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not result_paths:
        return ""
    rows: list[dict] = []
    for path in result_paths[:5]:
        total = 0
        by_status: dict[str, int] = {}
        by_conf: dict[str, int] = {}
        bad_ui_text = 0
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            total += 1
            status = str(row.get("status") or "unknown")
            conf = str(row.get("grounding_confidence") or "unknown")
            by_status[status] = by_status.get(status, 0) + 1
            by_conf[conf] = by_conf.get(conf, 0) + 1
            if "Click to increase image size" in json.dumps(row.get("parseland_candidate"), ensure_ascii=False):
                bad_ui_text += 1
        rows.append({
            "path": str(path.relative_to(REPO_ROOT)),
            "total": total,
            "status": " · ".join(f"{k}: {v}" for k, v in sorted(by_status.items())),
            "confidence": " · ".join(f"{k}: {v}" for k, v in sorted(by_conf.items())),
            "bad_ui_text": bad_ui_text,
        })
    if not rows:
        return ""
    cols = ["Artifact", "Rows", "Status", "Grounding confidence", "UI-text candidates"]
    parts = [
        '<h3 style="font-size:1rem; margin:1rem 0 0.25rem;">Browserbase grounding checkpoints</h3>',
        "<table><thead><tr>",
    ]
    parts += [f"<th>{html.escape(c)}</th>" for c in cols]
    parts += ["</tr></thead><tbody>"]
    for row in rows:
        parts.append("<tr>")
        parts.append(f"<td><code>{html.escape(row['path'])}</code></td>")
        parts.append(f"<td>{html.escape(str(row['total']))}</td>")
        parts.append(f"<td>{html.escape(row['status'])}</td>")
        parts.append(f"<td>{html.escape(row['confidence'])}</td>")
        parts.append(f"<td>{html.escape(str(row['bad_ui_text']))}</td>")
        parts.append("</tr>")
    parts += ["</tbody></table>"]
    return "".join(parts)


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
    workflow_summary = load_workflow_summary()
    if workflow_summary:
        pubs_total = int(workflow_summary.get("total_publishers") or 0)
    elif args.queue_summary.exists():
        try:
            pubs_total = int(json.loads(args.queue_summary.read_text()).get("publisher_count") or 0)
        except Exception:
            pass
    queue_cells = int(workflow_summary.get("total_tasks") or 0) if workflow_summary else 0

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
    whole_goldie = load_latest_whole_goldie()
    curve_svg_inline = load_curve_svg_inline(args.evidence_dir / "curve-latest.svg")
    field_opp_table = render_field_opportunity_table(REPO_ROOT / "mismatches" / "field-opportunity.json")
    pub_queue_table = render_publisher_queue_table(REPO_ROOT / "mismatches" / "publisher-queue.ndjson")
    backfill_table = render_goldie_backfilled_table(REPO_ROOT / "mismatches" / "goldie-backfilled-candidates.ndjson")
    out_html = REPORT_HTML.format(
        ts=html.escape(ts),
        run_id=html.escape(str(run_id)),
        batches_n=len(kpi_rows),
        pubs_total=pubs_total,
        queue_cells=queue_cells,
        metric_cards=render_metric_cards(latest),
        coverage_status=render_coverage_status(whole_goldie, workflow_summary),
        field_target_table=render_field_target_table(whole_goldie),
        publisher_field_table=render_publisher_field_table(whole_goldie),
        batches_table=render_batches_table(kpi_rows),
        curve_svg_inline=curve_svg_inline,
        field_opportunity_table=field_opp_table,
        publisher_queue_table=pub_queue_table,
        goldie_backfilled_table=backfill_table,
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
