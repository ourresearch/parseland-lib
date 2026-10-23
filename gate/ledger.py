"""Known-failure ledger for the dev corpus: which page x field the current code gets wrong.

The unit tests (tests/test_gold_corpus.py) pin every dev page x field to this ledger:
  right but listed here   -> the test fails until you record the improvement:  python gate/ledger.py update
  wrong and not listed    -> a regression; fix the code (or, if the gold is wrong, file a dispute: gate/README.md)
So every change in what Parseland gets right shows up in the diff of gate/known_failures.json.

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
from gate.score import score_corpus  # noqa: E402

LEDGER = os.path.join(ROOT, "gate", "known_failures.json")


def current(workers=None):
    dev = corpus.fetch("dev")
    with tempfile.TemporaryDirectory() as tmp:
        parsed = os.path.join(tmp, "parsed.ndjson")
        run(ROOT, dev, parsed, workers or max(1, min(4, os.cpu_count() or 2)))
        return score_corpus(dev, parsed)


def as_ledger(results):
    return {"corpus": corpus.version(),
            "pages": {r["page_id"]: sorted(f for f, ok in r["right"].items() if not ok)
                      for r in sorted(results, key=lambda r: r["page_id"]) if not all(r["right"].values())}}


def load():
    return json.load(open(LEDGER)) if os.path.exists(LEDGER) else {"corpus": None, "pages": {}}


def diff(old, new):
    better, worse = [], []
    for pid in set(old["pages"]) | set(new["pages"]):
        o, n = set(old["pages"].get(pid, [])), set(new["pages"].get(pid, []))
        better += [(pid, f) for f in o - n]
        worse += [(pid, f) for f in n - o]
    return sorted(better), sorted(worse)


def guard(base_path):
    """CI: refuse a ledger that records new failures relative to production's (a regression written down
    with `ledger.py update` is still a regression). Corpus version changes reset the comparison."""
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
    a = ap.parse_args()
    if a.cmd == "guard":
        sys.exit(guard(a.base))
    new = as_ledger(current())
    better, worse = diff(load(), new)
    print(f"{len(better)} page-fields now right, {len(worse)} now wrong")
    for pid, f in worse[:50]:
        print(f"  worse: {pid} {f}")
    if a.cmd == "update":
        json.dump(new, open(LEDGER, "w"), indent=0, sort_keys=True)
        open(LEDGER, "a").write("\n")
        print(f"wrote {LEDGER}")
    elif better or worse:
        sys.exit(1)
