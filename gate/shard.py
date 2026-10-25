"""Parse and score one slice of a frozen corpus, and merge the slices back (CI's parallel parse jobs, oxjob #1791).

Nearly all of the gate's time is parse_page over ~2,000 pages per corpus, ~7 min each on a 4-vCPU runner. CI parses
each corpus as GATE_SHARDS slices on separate runners at once, then the "Test gate" job merges the scores and judges
them exactly as before. Pages are parsed one by one and Parseland is deterministic, so merged slices score the same
as one unsliced run (proved 25 Oct 2026 against main 14423e2's saved scores); parse_and_score() is the one path both
take (ledger.current() calls it unsliced).

  python gate/shard.py parse --split dev|holdout --lib <checkout> --shard 0/3 --out dev-0.ndjson
  python gate/shard.py merge --split dev|holdout --out dev_scores.ndjson dev-0.ndjson dev-1.ndjson dev-2.ndjson

Score rows hold booleans per page x field and no page text, like the scores CI already keeps in the private bucket.
A run that scored fewer pages than it parsed, or a merge that doesn't add up to the corpus, stops.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from gate import corpus  # noqa: E402
from gate.run_parser import WORKERS, run  # noqa: E402
from gate.score import load_ndjson, score_corpus, write_ndjson  # noqa: E402


def parse_and_score(split, lib, shard=None, workers=None):
    """Score lib's parse_page on a corpus split, or on slice shard=(i, n) of it."""
    d = corpus.fetch(split)
    with tempfile.TemporaryDirectory() as tmp:
        parsed = os.path.join(tmp, "parsed.ndjson")
        n = run(lib, d, parsed, workers or WORKERS, shard)
        res = score_corpus(d, parsed)
    if len(res) != n:
        raise SystemExit(f"{split} {shard or ''}: scored {len(res)} of {n} parsed pages")
    return res


def merge(split, out, paths):
    rows, seen = [], set()
    for p in paths:
        for r in load_ndjson(p):
            if r["page_id"] in seen:
                raise SystemExit(f"{split}: page {r['page_id'][:8]} is in two shards")
            seen.add(r["page_id"])
            rows.append(r)
    want = corpus.lock()[split]["pages"]
    if len(rows) != want:
        raise SystemExit(f"{split}: the shards hold {len(rows)} pages, the corpus {want}: a shard is missing")
    write_ndjson(rows, out)
    print(f"{split}: merged {len(paths)} shards, {len(rows)} pages", file=sys.stderr)


def parse_shard(text):
    i, n = (int(x) for x in text.split("/"))
    return i, n


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("parse")
    p.add_argument("--split", required=True, choices=["dev", "holdout"])
    p.add_argument("--lib", required=True, help="checkout whose parseland_lib parses (this one, or production's)")
    p.add_argument("--shard", required=True, type=parse_shard, help="i/n: manifest rows i, i+n, ...")
    p.add_argument("--out", required=True)
    m = sub.add_parser("merge")
    m.add_argument("--split", required=True, choices=["dev", "holdout"])
    m.add_argument("--out", required=True)
    m.add_argument("paths", nargs="+")
    a = ap.parse_args()
    if a.cmd == "parse":
        write_ndjson(parse_and_score(a.split, a.lib, a.shard), a.out)
    else:
        merge(a.split, a.out, a.paths)
