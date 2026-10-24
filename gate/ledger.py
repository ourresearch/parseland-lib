"""Known-failure ledger for the dev corpus: which page x field the current code gets wrong.

The unit tests (tests/test_gold_corpus.py) pin every dev page x field to this ledger:
  right but listed here   -> the test fails until you record the improvement:  python gate/ledger.py update
  wrong and not listed    -> a regression; fix the code (or, if the gold is wrong, file a dispute: gate/README.md)
So every change in what Parseland gets right shows up in the diff of gate/known_failures.json.
Pages of a different paper (gold page_kind "different_item") are don't-care: never in the ledger, never a test
failure; update/check/guard report them on a separate line (charter § 6, 24 Oct 2026).

  python gate/ledger.py update      # re-run the dev corpus with this checkout and rewrite the ledger
  python gate/ledger.py check       # same run, print what changed, exit 1 if anything did
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from gate import corpus  # noqa: E402
from gate.run_parser import run  # noqa: E402
from gate.score import load_ndjson, other_paper, other_paper_line, score_corpus, scored  # noqa: E402

LEDGER = os.path.join(ROOT, "gate", "known_failures.json")


def current(workers=None):
    dev = corpus.fetch("dev")
    with tempfile.TemporaryDirectory() as tmp:
        parsed = os.path.join(tmp, "parsed.ndjson")
        run(ROOT, dev, parsed, workers or max(1, min(4, os.cpu_count() or 2)))
        res = score_corpus(dev, parsed)
    out = os.environ.get("GATE_DEV_SCORES_OUT")  # CI keeps its own dev scores (rebuild the ledger from them if needed)
    if out:
        with open(out, "w") as f:
            for r in res:
                f.write(json.dumps(r) + "\n")
    return res


def as_ledger(results):
    return {"corpus": corpus.version(),
            "pages": {r["page_id"]: sorted(f for f, ok in r["right"].items() if not ok)
                      for r in sorted(scored(results), key=lambda r: r["page_id"]) if not all(r["right"].values())}}


def load():
    return json.load(open(LEDGER)) if os.path.exists(LEDGER) else {"corpus": None, "pages": {}}


def diff(old, new):
    better, worse = [], []
    for pid in set(old["pages"]) | set(new["pages"]):
        o, n = set(old["pages"].get(pid, [])), set(new["pages"].get(pid, []))
        better += [(pid, f) for f in o - n]
        worse += [(pid, f) for f in n - o]
    return sorted(better), sorted(worse)


def report_other_paper(results, summary=None):
    line = other_paper_line(other_paper(results), "Dev pages of a different paper (don't-care, not in the ledger)")
    print(line)
    if summary:
        with open(summary, "a") as f:
            f.write(line + "\n\n")


def guard(base_path, dev_scores=None, summary=None):
    """CI: refuse a ledger that records new failures relative to production's (a regression written down
    with `ledger.py update` is still a regression). Corpus version changes reset the comparison.
    A production ledger from before the don't-care rule lists those pages; they only show as "better" here.
    A branch ledger that still lists them fails tests/test_gold_corpus.py first."""
    if dev_scores and os.path.exists(dev_scores):
        report_other_paper(list(load_ndjson(dev_scores)), summary)
    if not base_path or not os.path.exists(base_path) or os.path.getsize(base_path) == 0:
        print("no production ledger to compare with (first gated deploy)")
        return 0
    base, head = json.load(open(base_path)), load()
    if base.get("corpus") != head.get("corpus"):
        print(f"corpus changed {base.get('corpus')} -> {head.get('corpus')}: ledger guard skipped")
        return 0
    _, worse = diff(base, head)
    if worse:
        print(f"REFUSED: the ledger records {len(worse)} page-fields as newly wrong; fix the regression instead")
        for pid, f in worse[:20]:
            print(f"  {pid[:8]} {f}")
        return 1
    print("ledger guard ok")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["update", "check", "guard"])
    ap.add_argument("--base", help="guard: production's known_failures.json")
    ap.add_argument("--dev-scores", help="guard: this commit's dev scores (for the different-paper line)")
    ap.add_argument("--summary", help="guard: append the different-paper line here (CI step summary)")
    a = ap.parse_args()
    if a.cmd == "guard":
        sys.exit(guard(a.base, a.dev_scores, a.summary))
    res = current()
    new = as_ledger(res)
    better, worse = diff(load(), new)
    print(f"{len(better)} page-fields now right, {len(worse)} now wrong")
    report_other_paper(res)
    for pid, f in worse[:50]:
        print(f"  worse: {pid} {f}")
    if a.cmd == "update":
        json.dump(new, open(LEDGER, "w"), indent=0, sort_keys=True)
        open(LEDGER, "a").write("\n")
        print(f"wrote {LEDGER}")
    elif better or worse:
        sys.exit(1)
