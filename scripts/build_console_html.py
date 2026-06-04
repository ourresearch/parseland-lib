#!/usr/bin/env python3
"""Scribe — render live-agent-console.html from the event ledger.

Plain HTML + small inlined JS (no build step). Reads:
- evidence/live-agent-events.ndjson  (live event ledger)
- evidence/curve-latest.json         (KPI series, optional)
- evidence/kpi-by-publisher-count.csv (KPI table, optional)

Writes evidence/live-agent-console.html. Designed for a JS bundle < 80 KB and
deterministic rendering — no remote calls.

Usage:
    python scripts/build_console_html.py
    python scripts/build_console_html.py --evidence-dir /path/to/evidence
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

EVIDENCE_DIR_DEFAULT = Path(
    "/Users/shubh-trips/Documents/OpenAlex/oxjobs/working/parseland-work-reporting/evidence"
)


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Parseland Improver — Live Console</title>
<style>
  :root {{
    --bg: oklch(98% 0 0);
    --fg: oklch(20% 0 0);
    --muted: oklch(55% 0 0);
    --accent: oklch(55% 0.18 250);
    --ok: oklch(60% 0.16 145);
    --blocked: oklch(60% 0.20 30);
    --border: oklch(90% 0 0);
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: var(--bg);
    color: var(--fg);
    line-height: 1.5;
  }}
  header {{
    padding: 1.25rem 1.5rem;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: baseline;
    gap: 1rem;
  }}
  header h1 {{ margin: 0; font-size: 1.25rem; }}
  header .meta {{ color: var(--muted); font-size: 0.875rem; }}
  main {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.5rem;
    padding: 1.5rem;
  }}
  section {{
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1rem;
    background: white;
  }}
  section h2 {{ margin: 0 0 0.75rem 0; font-size: 1rem; }}
  .role-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.5rem;
  }}
  .role {{
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.6rem;
    font-size: 0.875rem;
    background: oklch(99% 0 0);
  }}
  .role.active {{
    border-color: var(--accent);
    box-shadow: 0 0 0 1px var(--accent);
  }}
  .role .name {{ font-weight: 600; }}
  .role .task {{ color: var(--muted); font-size: 0.8rem; margin-top: 0.2rem; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
  th, td {{ text-align: left; padding: 0.35rem 0.6rem; border-bottom: 1px solid var(--border); }}
  th {{ background: oklch(96% 0 0); font-weight: 600; }}
  .feed {{ max-height: 24rem; overflow-y: auto; font-family: ui-monospace, SFMono-Regular, monospace; font-size: 0.78rem; }}
  .feed .row {{ padding: 0.2rem 0; border-bottom: 1px solid oklch(95% 0 0); }}
  .ok {{ color: var(--ok); }}
  .blocked {{ color: var(--blocked); font-weight: 600; }}
  .failed {{ color: var(--blocked); font-weight: 600; }}
  .ts {{ color: var(--muted); }}
  img.curve {{ width: 100%; height: auto; }}
  footer {{ padding: 1rem 1.5rem; color: var(--muted); font-size: 0.75rem; border-top: 1px solid var(--border); }}
</style>
</head>
<body>
<header>
  <h1>Parseland Improver — Live Console</h1>
  <span class="meta">report 336 · generated {ts}</span>
  <span class="meta" style="margin-left:auto;">run_id: {run_id} · events: {events_n} · batches: {batches_n}</span>
</header>
<main>
  <section style="grid-column: 1 / -1;">
    <h2>KPI vs Publishers processed</h2>
    <img class="curve" src="curve-latest.png" alt="KPI curve">
  </section>

  <section>
    <h2>Active agents</h2>
    <div class="role-grid">{role_cards}</div>
  </section>

  <section>
    <h2>Batch progress</h2>
    {batches_table}
  </section>

  <section style="grid-column: 1 / -1;">
    <h2>Recent events ({events_shown}/{events_n})</h2>
    <div class="feed">{events_html}</div>
  </section>
</main>
<footer>
  Data sources: <code>live-agent-events.ndjson</code>, <code>kpi-by-publisher-count.csv</code>, <code>curve-latest.png</code>.
  Refresh page to pull latest.
</footer>
</body>
</html>
"""


def load_events(path: Path, *, tail: int = 200) -> list[dict]:
    if not path.exists():
        return []
    events: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if tail and len(events) > tail:
        events = events[-tail:]
    return events


def load_kpi(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows


def render_role_cards(events: list[dict]) -> str:
    roles = ["Pathfinder", "Craftsman", "Referee", "Shield", "Scribe", "Courier"]
    last_event_by_role: dict[str, dict] = {}
    for ev in events:
        r = ev.get("agent_role")
        if r in roles:
            last_event_by_role[r] = ev
    parts: list[str] = []
    for r in roles:
        last = last_event_by_role.get(r)
        if last is None:
            parts.append(f'<div class="role"><div class="name">{r}</div><div class="task">idle</div></div>')
        else:
            cls = " active" if last.get("status") == "started" else ""
            task = html.escape(str(last.get("action") or last.get("notes") or "—"))
            parts.append(
                f'<div class="role{cls}"><div class="name">{r}</div><div class="task">{task}</div></div>'
            )
    return "".join(parts)


def render_batches_table(kpi_rows: list[dict]) -> str:
    if not kpi_rows:
        return '<p style="color: var(--muted);">no batches yet</p>'
    cols = [
        ("batch_id", "Batch"),
        ("publishers_processed", "Publishers"),
        ("cumulative_rows", "Rows"),
        ("overall_authors_f1_soft", "Authors"),
        ("overall_affiliations_f1_fuzzy", "Affs"),
        ("overall_abstract_ratio_fuzzy", "Abstract"),
        ("overall_pdf_url_accuracy", "PDF"),
        ("overall_corresponding_accuracy", "Corresp"),
        ("marginal_lift_per_100", "Lift/100"),
        ("shipped_count", "Shipped"),
        ("blocked_count", "Blocked"),
    ]
    parts = ["<table>", "<thead><tr>"]
    parts += [f"<th>{html.escape(label)}</th>" for _, label in cols]
    parts += ["</tr></thead>", "<tbody>"]
    for r in kpi_rows[-10:]:  # last 10 batches
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


def render_events(events: list[dict], *, n: int = 80) -> str:
    if not events:
        return '<p style="color: var(--muted);">no events yet</p>'
    parts: list[str] = []
    for ev in reversed(events[-n:]):  # newest first
        ts = html.escape(ev.get("timestamp", ""))
        role = html.escape(ev.get("agent_role", "?"))
        action = html.escape(str(ev.get("action") or ""))
        pub = html.escape(ev.get("publisher") or "")
        field = html.escape(ev.get("field") or "")
        status = ev.get("status") or "ok"
        status_cls = status if status in ("ok", "blocked", "failed") else "ok"
        notes = html.escape(str(ev.get("notes") or "")[:140])
        parts.append(
            f'<div class="row">'
            f'<span class="ts">{ts}</span> '
            f'<span class="{status_cls}">{status}</span> '
            f'<strong>{role}</strong> {action}'
            f'{(" · " + pub) if pub else ""}'
            f'{("/" + field) if field else ""}'
            f'{(" — " + notes) if notes else ""}'
            f'</div>'
        )
    return "".join(parts)


def build_html(evidence_dir: Path) -> str:
    events = load_events(evidence_dir / "live-agent-events.ndjson")
    kpi_rows = load_kpi(evidence_dir / "kpi-by-publisher-count.csv")
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    run_id = events[-1].get("run_id", "—") if events else "—"
    return HTML_TEMPLATE.format(
        ts=html.escape(ts),
        run_id=html.escape(run_id),
        events_n=len(events),
        events_shown=min(len(events), 80),
        batches_n=len(kpi_rows),
        role_cards=render_role_cards(events),
        batches_table=render_batches_table(kpi_rows),
        events_html=render_events(events),
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--evidence-dir", type=Path, default=EVIDENCE_DIR_DEFAULT)
    args = p.parse_args()
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    out = args.evidence_dir / "live-agent-console.html"
    out.write_text(build_html(args.evidence_dir), encoding="utf-8")
    print(json.dumps({
        "out": str(out),
        "size_bytes": out.stat().st_size,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
