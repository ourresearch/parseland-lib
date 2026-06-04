#!/usr/bin/env python3
"""Scribe — live TUI tailing the event ledger.

Falls back to plain stdout if Rich is unavailable. Pass --run-id to filter to a
specific sprint run.

Usage:
    python scripts/agent_console.py
    python scripts/agent_console.py --run-id 20260604T081505Z-786742
    python scripts/agent_console.py --once    # snapshot, no follow
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

LEDGER_PATH_DEFAULT = Path(
    "/Users/shubh-trips/Documents/OpenAlex/oxjobs/working/parseland-work-reporting/evidence/live-agent-events.ndjson"
)

ROLES = ["Pathfinder", "Craftsman", "Referee", "Shield", "Scribe", "Courier"]


def follow_lines(path: Path):
    """Tail a file; yield new lines as they appear."""
    while not path.exists():
        time.sleep(0.5)
    with open(path, "r", encoding="utf-8") as f:
        f.seek(0, 2)  # seek to end
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.5)
                continue
            yield line


def read_all(path: Path) -> list[dict]:
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
    return events


def render_plain(events: list[dict], *, head: str = "") -> None:
    if head:
        print(head)
    role_latest: dict[str, dict] = {}
    for ev in events:
        r = ev.get("agent_role")
        if r in ROLES:
            role_latest[r] = ev
    print("─" * 80)
    for r in ROLES:
        ev = role_latest.get(r)
        if ev is None:
            print(f"  {r:11s}  idle")
        else:
            action = (ev.get("action") or "")[:50]
            pub = ev.get("publisher") or ""
            status = ev.get("status") or "ok"
            print(f"  {r:11s}  {status:8s}  {action:50s}  {pub}")
    print("─" * 80)
    # Last 10 events
    print(f"Recent events (last 10 of {len(events)}):")
    for ev in events[-10:]:
        ts = ev.get("timestamp", "")[-12:]
        role = ev.get("agent_role", "?")[:11]
        action = (ev.get("action") or "")[:40]
        pub = ev.get("publisher") or ""
        status = ev.get("status") or "ok"
        notes = (ev.get("notes") or "")[:40]
        print(f"  {ts}  {role:11s}  {status:8s}  {action:40s}  {pub:14s}  {notes}")


def render_rich(events: list[dict], live, console) -> None:
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.table import Table

    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="roles", size=10),
        Layout(name="feed"),
    )

    # Header
    n = len(events)
    last_ts = events[-1].get("timestamp", "—") if events else "—"
    run_id = events[-1].get("run_id", "—") if events else "—"
    layout["header"].update(Panel(
        f"[bold]Parseland Improver — Live Console[/bold]   run_id: {run_id}   events: {n}   latest: {last_ts}",
        border_style="blue",
    ))

    # Role table
    role_table = Table(show_header=True, header_style="bold")
    role_table.add_column("Role", width=12)
    role_table.add_column("Status", width=10)
    role_table.add_column("Last action", width=40)
    role_table.add_column("Publisher", width=20)
    role_latest: dict[str, dict] = {}
    for ev in events:
        r = ev.get("agent_role")
        if r in ROLES:
            role_latest[r] = ev
    for r in ROLES:
        ev = role_latest.get(r)
        if ev is None:
            role_table.add_row(r, "idle", "—", "—")
        else:
            status = ev.get("status") or "ok"
            color = {"ok": "green", "blocked": "red", "failed": "red",
                     "started": "yellow"}.get(status, "white")
            role_table.add_row(
                r, f"[{color}]{status}[/{color}]",
                (ev.get("action") or "")[:40],
                (ev.get("publisher") or "")[:20],
            )
    layout["roles"].update(Panel(role_table, title="Agents", border_style="green"))

    # Feed
    feed_table = Table(show_header=True, header_style="bold", expand=True)
    feed_table.add_column("Time", width=14)
    feed_table.add_column("Role", width=12)
    feed_table.add_column("Status", width=8)
    feed_table.add_column("Action", width=30)
    feed_table.add_column("Pub", width=14)
    feed_table.add_column("Notes")
    for ev in events[-30:]:
        ts = ev.get("timestamp", "")[-12:]
        status = ev.get("status") or "ok"
        color = {"ok": "green", "blocked": "red", "failed": "red",
                 "started": "yellow"}.get(status, "white")
        feed_table.add_row(
            ts, ev.get("agent_role", "?")[:12],
            f"[{color}]{status}[/{color}]",
            (ev.get("action") or "")[:30],
            (ev.get("publisher") or "")[:14],
            (ev.get("notes") or "")[:80],
        )
    layout["feed"].update(Panel(feed_table, title=f"Events (last 30 of {n})",
                                border_style="cyan"))

    live.update(layout)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ledger", type=Path, default=LEDGER_PATH_DEFAULT)
    p.add_argument("--run-id", type=str, help="Filter to a specific run_id.")
    p.add_argument("--once", action="store_true",
                   help="Snapshot once instead of following.")
    p.add_argument("--refresh", type=float, default=1.0,
                   help="Seconds between refreshes when following (default 1.0).")
    args = p.parse_args()

    def filter_evs(evs: list[dict]) -> list[dict]:
        if not args.run_id:
            return evs
        return [e for e in evs if e.get("run_id") == args.run_id]

    if args.once:
        events = filter_evs(read_all(args.ledger))
        render_plain(events, head=f"Snapshot of {args.ledger}")
        return 0

    try:
        from rich.console import Console
        from rich.live import Live

        console = Console()
        with Live(console=console, refresh_per_second=4, screen=True) as live:
            while True:
                events = filter_evs(read_all(args.ledger))
                render_rich(events, live, console)
                time.sleep(args.refresh)
    except ImportError:
        # Plain fallback: print snapshot every refresh seconds.
        while True:
            events = filter_evs(read_all(args.ledger))
            print(f"\033[2J\033[H", end="")  # clear screen
            render_plain(events, head=f"[{args.ledger.name}] run_id={args.run_id or 'ALL'}")
            time.sleep(args.refresh)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
