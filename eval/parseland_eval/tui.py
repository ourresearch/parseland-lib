"""Live TUI for prompt_eval progress.

Tails a `parseland_eval.prompt_eval` log file and renders:
  - overall progress bar (rows done / total, elapsed, ETA)
  - status breakdown (ok / no_cached_html / other_errors)
  - recent rows with latency
  - rolling latency stats (min/median/p95/avg)

Usage:
    python -m parseland_eval.tui /tmp/prompt_eval.log
    python -m parseland_eval.tui /tmp/prompt_eval.log --total 50

The log is parsed with one regex per line — no shared state with the
running job, so it is safe to attach/detach while the eval is in flight.
"""
from __future__ import annotations

import argparse
import re
import statistics
import sys
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Deque

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.table import Table
from rich.text import Text


ROW_PATTERN = re.compile(r"row\s+(?P<no>\d+):\s+(?P<status>\S+)\s+\((?P<ms>[\d.]+)ms\)")
WROTE_PATTERN = re.compile(r"^wrote\s+(?P<path>.+\.json)\s*$")
TRACEBACK_PATTERN = re.compile(r"^(Traceback|\s+File\s|Error:)", re.IGNORECASE)


@dataclass
class RowEvent:
    no: int
    status: str
    ms: float


@dataclass
class State:
    total: int = 50
    events: list[RowEvent] = field(default_factory=list)
    status_counts: Counter = field(default_factory=Counter)
    recent: Deque[RowEvent] = field(default_factory=lambda: deque(maxlen=10))
    final_path: str | None = None
    traceback_lines: list[str] = field(default_factory=list)
    start: float = field(default_factory=time.time)

    def record(self, ev: RowEvent) -> None:
        self.events.append(ev)
        self.status_counts[ev.status] += 1
        self.recent.append(ev)

    def latencies(self) -> list[float]:
        return [e.ms for e in self.events if e.status == "ok"]

    def done(self) -> bool:
        return self.final_path is not None or len(self.events) >= self.total


def _follow(path: Path):
    """Yield each new line appended to `path` (like `tail -F`).

    Handles files that don't exist yet or get truncated/rotated.
    """
    while True:
        if path.exists():
            break
        time.sleep(0.5)
    with path.open("r", encoding="utf-8", errors="replace") as f:
        f.seek(0, 2)  # jump to end so existing lines aren't re-parsed twice if attaching mid-run
        # but also emit existing content so tui shows history when attaching late:
        pass
    with path.open("r", encoding="utf-8", errors="replace") as f:
        while True:
            line = f.readline()
            if line:
                yield line.rstrip("\n")
            else:
                time.sleep(0.2)


def _build_view(state: State) -> Group:
    done = len(state.events)
    pct = (done / state.total * 100) if state.total else 0
    ok = state.status_counts.get("ok", 0)
    errs = sum(c for s, c in state.status_counts.items() if s != "ok")
    error_rate = (errs / done * 100) if done else 0

    header = Panel(
        Text.from_markup(
            f"[bold]parseland prompt_eval[/] · "
            f"[cyan]{done}/{state.total}[/] rows · "
            f"[green]ok={ok}[/] · [red]err={errs}[/] · "
            f"[yellow]{error_rate:4.1f}%[/] error rate · "
            f"[dim]elapsed {int(time.time() - state.start)}s[/]"
        ),
        expand=True,
    )

    # Progress bar
    progress = Progress(
        TextColumn("[bold]progress"),
        BarColumn(bar_width=None),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        TextColumn("ETA"),
        TimeRemainingColumn(),
        expand=True,
    )
    task = progress.add_task("rows", total=state.total, completed=done)
    _ = task  # silence

    # Status breakdown table
    status_table = Table(title="Status breakdown", expand=True, show_header=True, header_style="bold")
    status_table.add_column("status", style="cyan", no_wrap=True)
    status_table.add_column("count", justify="right")
    for status, count in state.status_counts.most_common():
        color = "green" if status == "ok" else "red"
        status_table.add_row(f"[{color}]{status}[/]", str(count))

    # Latency stats
    lats = state.latencies()
    lat_table = Table(title="Latency (ok rows)", expand=True, show_header=True, header_style="bold")
    lat_table.add_column("metric")
    lat_table.add_column("ms", justify="right")
    if lats:
        lat_sorted = sorted(lats)
        p95 = lat_sorted[int(len(lat_sorted) * 0.95) - 1] if len(lat_sorted) > 1 else lat_sorted[0]
        lat_table.add_row("min", f"{min(lats):.0f}")
        lat_table.add_row("median", f"{statistics.median(lats):.0f}")
        lat_table.add_row("avg", f"{statistics.mean(lats):.0f}")
        lat_table.add_row("p95", f"{p95:.0f}")
        lat_table.add_row("max", f"{max(lats):.0f}")
    else:
        lat_table.add_row("[dim]no ok rows yet[/]", "")

    # Recent events
    recent_table = Table(title="Recent rows", expand=True, show_header=True, header_style="bold")
    recent_table.add_column("row", justify="right", style="cyan", no_wrap=True)
    recent_table.add_column("status", no_wrap=True)
    recent_table.add_column("ms", justify="right")
    for ev in list(state.recent)[::-1]:
        color = "green" if ev.status == "ok" else "red"
        recent_table.add_row(str(ev.no), f"[{color}]{ev.status}[/]", f"{ev.ms:.0f}")

    # Bottom section: wrote path or traceback
    if state.traceback_lines:
        tail = Panel(
            Text("\n".join(state.traceback_lines[-8:]), style="red"),
            title="Error", border_style="red", expand=True,
        )
    elif state.final_path:
        tail = Panel(
            Text.from_markup(f"[bold green]done[/] → [cyan]{state.final_path}[/]"),
            title="Run complete", border_style="green", expand=True,
        )
    else:
        tail = Panel(
            Text.from_markup("[dim]waiting for next row…[/]"),
            expand=True,
        )

    # Stack everything
    mid = Table.grid(expand=True)
    mid.add_column(ratio=1)
    mid.add_column(ratio=1)
    mid.add_row(status_table, lat_table)

    return Group(header, progress, mid, recent_table, tail)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("logfile", help="Path to the prompt_eval log (e.g. /tmp/prompt_eval.log)")
    ap.add_argument("--total", type=int, default=50, help="Total rows expected")
    ap.add_argument("--refresh", type=float, default=4.0, help="UI refresh Hz")
    args = ap.parse_args()

    log = Path(args.logfile)
    state = State(total=args.total)
    console = Console()

    with Live(_build_view(state), console=console, refresh_per_second=args.refresh, screen=False) as live:
        for line in _follow(log):
            m = ROW_PATTERN.search(line)
            if m:
                state.record(RowEvent(int(m["no"]), m["status"], float(m["ms"])))
            else:
                m2 = WROTE_PATTERN.search(line)
                if m2:
                    state.final_path = m2["path"].strip()
                elif TRACEBACK_PATTERN.search(line):
                    state.traceback_lines.append(line)
            live.update(_build_view(state))
            if state.done():
                live.update(_build_view(state))
                break
    return 0


if __name__ == "__main__":
    sys.exit(main())
