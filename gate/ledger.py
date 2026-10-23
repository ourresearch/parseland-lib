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
    return {"corpus": corpus.lock()["version"],
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


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["update", "check"])
    a = ap.parse_args()
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
