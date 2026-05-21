"""Zero-dependency TUI for watching scripts/elsevier_inprocess_diff.py progress.

Tails the script's stdout log (passed on argv, or auto-discovered from the
most recent .output file under /private/tmp/claude-501/...), parses the
per-row score lines emitted by ``fmt_score_line``, and renders a live
dashboard with running counters, recent rows, and an ETA.

Usage:

    .venv/bin/python scripts/eval_progress_tui.py <path-to-log>

    # or, auto-discover the most-recent log:
    .venv/bin/python scripts/eval_progress_tui.py

Press Ctrl+C to exit. The TUI doesn't modify state.

Per-row line format (from elsevier_inprocess_diff.fmt_score_line):

    found=<✓|✗>  <DOI>  [<BOT-CHECK>]  auth F1 <X>  aff F1 <X>  abs <X> (<✓|✗>)  pdf <✓|✗>  (<elapsed>s)

Failure line format (stage = resolve_uuid | r2_read):

    FAIL  <DOI>  stage=<stage>  err=<msg>
    # or partial form from inline prints:
    FAIL  <DOI>  resolve_uuid: <msg>
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

TOTAL_ROWS = 1459  # ~1,142 score + 317 fail in iter 2 — used for the progress bar

ROW_RE = re.compile(
    r"^\s*found=(?P<found>[^\s]+)\s+(?P<doi>\S+)\s+(?P<bot>\([A-Z\- ]+\))?\s*auth F1\s+(?P<auth>[0-9.]+|\s*-\s*)\s+aff F1\s+(?P<aff>[0-9.]+|\s*-\s*)\s+abs\s+(?P<abs>[0-9.]+)\s+\((?P<absok>[^\)]+)\)\s+pdf\s+(?P<pdf>[^\s]+)\s+\((?P<elapsed>[0-9.]+)s\)"
)
FAIL_RE = re.compile(r"^\s*FAIL\s+(?P<doi>\S+)")
AGG_HEADER_RE = re.compile(r"==+ TL;DR AGGREGATE")


@dataclass
class Counters:
    rows: int = 0
    failures: int = 0
    authors_found: int = 0
    pdf_hits: int = 0
    abstract_hits: int = 0
    auth_f1_sum: float = 0.0
    auth_f1_n: int = 0
    aff_f1_sum: float = 0.0
    aff_f1_n: int = 0
    elapsed_sum: float = 0.0
    recent: list[tuple[str, str, str, str, str, str]] = field(default_factory=list)  # (doi, auth, aff, abs, pdf, elapsed)
    last_failures: list[str] = field(default_factory=list)
    started_at: Optional[float] = None
    finished: bool = False


def parse_line(line: str, c: Counters) -> None:
    if AGG_HEADER_RE.search(line):
        c.finished = True
        return
    m = ROW_RE.search(line)
    if m:
        c.rows += 1
        if c.started_at is None:
            c.started_at = time.time()
        if m.group("found") == "✓":
            c.authors_found += 1
        if m.group("pdf") == "✓":
            c.pdf_hits += 1
        if m.group("absok") == "✓":
            c.abstract_hits += 1
        auth_str = m.group("auth").strip()
        if auth_str and auth_str != "-":
            try:
                v = float(auth_str)
                c.auth_f1_sum += v
                c.auth_f1_n += 1
            except ValueError:
                pass
        aff_str = m.group("aff").strip()
        if aff_str and aff_str != "-":
            try:
                v = float(aff_str)
                c.aff_f1_sum += v
                c.aff_f1_n += 1
            except ValueError:
                pass
        try:
            c.elapsed_sum += float(m.group("elapsed"))
        except ValueError:
            pass
        c.recent.append(
            (
                m.group("doi"),
                auth_str,
                aff_str,
                m.group("abs"),
                m.group("pdf"),
                m.group("elapsed") + "s",
            )
        )
        c.recent = c.recent[-12:]
        return
    m = FAIL_RE.search(line)
    if m:
        c.failures += 1
        c.last_failures.append(m.group("doi"))
        c.last_failures = c.last_failures[-5:]


def _fmt_pct(num: int, den: int) -> str:
    return f"{num}/{den} ({100 * num / den:.1f}%)" if den else f"{num}/0"


def _fmt_mean(s: float, n: int) -> str:
    return f"{s / n:.3f}" if n else "  -  "


def _fmt_eta(c: Counters) -> str:
    """ETA from the actual elapsed-time accumulator in the log.

    The script's fmt_score_line emits a per-row (Xs) elapsed value; we sum
    those into ``elapsed_sum``. That's the wall-clock time the eval has spent
    on rows we've observed, regardless of when we started reading the log.
    For total-elapsed time we approximate with file mtime - mtime-at-row-1,
    but elapsed_sum is the source of truth for rate."""
    done = c.rows + c.failures
    if done == 0 or c.elapsed_sum <= 0:
        return "—"
    # rate from scored rows only — failures are sub-second resolve_uuid 404s
    # that don't reflect the real per-row cost.
    rate = c.rows / c.elapsed_sum if c.rows else 0.0
    remaining_scored = max(TOTAL_ROWS - done, 0)
    eta_s = remaining_scored / rate if rate else float("inf")
    if eta_s == float("inf") or eta_s > 1e8:
        return "—"
    h, rem = divmod(int(eta_s), 3600)
    m, s = divmod(rem, 60)
    rate_str = f"{rate:.2f} rows/s"
    if h:
        return f"{h}h{m:02d}m  ({rate_str})"
    return f"{m}m{s:02d}s  ({rate_str})"


def render(c: Counters) -> str:
    CLEAR = "\033[H\033[2J"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GREEN = "\033[32m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    RESET = "\033[0m"

    done = c.rows + c.failures
    bar_w = 40
    fill = int(bar_w * done / TOTAL_ROWS) if TOTAL_ROWS else 0
    bar = "█" * fill + "░" * (bar_w - fill)
    pct = 100 * done / TOTAL_ROWS if TOTAL_ROWS else 0

    lines = []
    lines.append(f"{CLEAR}{BOLD}{CYAN}Elsevier 10K in-process eval — live progress{RESET}")
    lines.append(f"{DIM}log: {LOG_PATH}{RESET}")
    lines.append("")
    lines.append(f"  Progress  [{bar}]  {done}/{TOTAL_ROWS}  ({pct:5.1f}%)")
    lines.append(f"  ETA       {_fmt_eta(c)}")
    if c.finished:
        lines.append(f"  {GREEN}{BOLD}✓ AGGREGATE BLOCK REACHED — run complete{RESET}")
    lines.append("")
    lines.append(f"{BOLD}Counters{RESET}")
    lines.append(f"  scored rows ........ {c.rows}")
    lines.append(f"  authors_found() .... {_fmt_pct(c.authors_found, c.rows)}")
    lines.append(f"  pdf  hit (parsed) .. {GREEN}{_fmt_pct(c.pdf_hits, c.rows)}{RESET}")
    lines.append(f"  abstract @ 0.74 .... {_fmt_pct(c.abstract_hits, c.rows)}")
    lines.append(f"  authors F1 mean .... {_fmt_mean(c.auth_f1_sum, c.auth_f1_n)}  (n={c.auth_f1_n})")
    lines.append(f"  affil   F1 mean .... {_fmt_mean(c.aff_f1_sum, c.aff_f1_n)}  (n={c.aff_f1_n})")
    lines.append(f"  failures ........... {RED if c.failures else ''}{c.failures}{RESET}")
    if c.last_failures:
        lines.append(f"  {DIM}last failures: {', '.join(c.last_failures)}{RESET}")
    lines.append("")
    lines.append(f"{BOLD}Recent rows{RESET}")
    lines.append(f"  {DIM}{'DOI':<48} {'auth':>5} {'aff':>5} {'abs':>5} {'pdf':>4} {'elapsed':>8}{RESET}")
    for doi, auth, aff, abs_, pdf, elapsed in c.recent:
        col = GREEN if pdf == "✓" else YELLOW
        lines.append(f"  {col}{doi[:48]:<48}{RESET} {auth:>5} {aff:>5} {abs_:>5} {col}{pdf:>4}{RESET} {elapsed:>8}")
    lines.append("")
    lines.append(f"{DIM}Ctrl+C to exit. Refreshes ~5x/s while log grows.{RESET}")
    return "\n".join(lines)


def find_latest_log() -> Path:
    candidates = sorted(
        glob.glob("/private/tmp/claude-501/*/tasks/*.output"),
        key=lambda p: os.path.getmtime(p),
        reverse=True,
    )
    if not candidates:
        sys.exit("no .output files found under /private/tmp/claude-501/.../tasks/")
    return Path(candidates[0])


LOG_PATH: Path = Path("/dev/null")


def main():
    global LOG_PATH, TOTAL_ROWS
    ap = argparse.ArgumentParser()
    ap.add_argument("log", nargs="?", help="path to tail; auto-discovered if omitted")
    ap.add_argument("--total", type=int, default=TOTAL_ROWS, help=f"total expected rows (default {TOTAL_ROWS})")
    ap.add_argument("--once", action="store_true", help="print one snapshot and exit (no live loop)")
    args = ap.parse_args()

    TOTAL_ROWS = args.total

    LOG_PATH = Path(args.log) if args.log else find_latest_log()
    if not LOG_PATH.exists():
        sys.exit(f"log not found: {LOG_PATH}")

    c = Counters()
    pos = 0
    try:
        while True:
            with LOG_PATH.open() as f:
                f.seek(pos)
                for line in f:
                    parse_line(line.rstrip("\n"), c)
                pos = f.tell()
            sys.stdout.write(render(c))
            sys.stdout.flush()
            if c.finished or args.once:
                break
            time.sleep(0.2)
    except KeyboardInterrupt:
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
