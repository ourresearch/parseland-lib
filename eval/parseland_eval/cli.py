"""CLI: `python -m parseland_eval [fetch|run|score]`."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from parseland_eval.fetch import fetch_many
from parseland_eval.gold import load_gold
from parseland_eval.paths import GOLD_JSON, HTML_CACHE, RUNS_DIR
from parseland_eval.report import write_run
from parseland_eval.runner import run_all
from parseland_eval.score.aggregate import score_row, summarize


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def cmd_fetch(args: argparse.Namespace) -> int:
    rows = load_gold()
    logging.info("loaded %d gold rows from %s", len(rows), GOLD_JSON)
    results = fetch_many((r.doi for r in rows), force=args.force)
    cached = sum(1 for r in results if r.error is None)
    errors = sum(1 for r in results if r.error)
    bot = sum(1 for r in results if r.bot_check_suspected)
    logging.info("fetch done: cached=%d errors=%d bot_suspected=%d → %s", cached, errors, bot, HTML_CACHE)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    rows = load_gold()
    logging.info("loaded %d gold rows", len(rows))

    missing = [r for r in rows if not (HTML_CACHE / f"{__import__('hashlib').sha1(r.doi.lower().encode()).hexdigest()}.html").exists()]
    if missing and not args.skip_missing:
        logging.error(
            "%d DOIs have no cached HTML. Run `python -m parseland_eval fetch` first, "
            "or pass --skip-missing to score only cached rows.",
            len(missing),
        )
        return 2

    runs = run_all(rows)
    scores = [score_row(g, r) for g, r in zip(rows, runs)]
    summary = summarize(scores)
    out = write_run(rows, runs, scores, summary, label=args.label)
    logging.info("wrote run to %s", out)

    o = summary["overall"]
    print(
        f"\n─── Parseland Eval — {len(rows)} rows ───\n"
        f"  Authors      F1 soft  : {o['authors_f1_soft']:.3f}   strict: {o['authors_f1_strict']:.3f}\n"
        f"  Affiliations F1 fuzzy : {o['affiliations_f1_fuzzy']:.3f}   strict: {o['affiliations_f1_strict']:.3f}\n"
        f"  Abstract     ratio    : {o['abstract_ratio_fuzzy']:.3f}   present_rate: {o['abstract_present_rate']:.3f}\n"
        f"  PDF URL      accuracy : {o['pdf_url_accuracy']:.3f}   divergent: {o['pdf_url_divergence_rate']:.3f}\n"
        f"  Errors              : {o['errors']}\n"
        f"  Mean duration (ms)  : {o['duration_ms_mean']:.1f}\n"
        f"\n  run file: {out}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="parseland-eval", description="Parseland offline eval")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="Cache HTML for every gold DOI")
    f.add_argument("--force", action="store_true", help="Re-fetch even if cached")
    f.set_defaults(func=cmd_fetch)

    r = sub.add_parser("run", help="Run parseland-lib against cached HTML + score")
    r.add_argument("--label", help="Optional label for the run file (e.g. 'baseline')")
    r.add_argument("--skip-missing", action="store_true", help="Proceed even if some HTML not cached")
    r.set_defaults(func=cmd_run)

    args = parser.parse_args(argv)
    _configure_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
