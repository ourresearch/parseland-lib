"""Score parse_page outputs against the gold, page by page and field by field (rules in gate/fields.py).

Usage: python gate/score.py --corpus <bundle dir> --parsed parsed.ndjson --out scores.ndjson [--cells cells.json]
Each output line: {"page_id", "cell", "stratum", "right": {field: bool}, "gold_present": {...},
                   "cand_present": {...}, "crash": bool, "ms": float}
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gate import fields as F  # noqa: E402

EMPTY = {"authors": [], "abstract": None, "pdf_url": None, "license": None}


def load_ndjson(path):
    with open(path) as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def cell_of(m):
    """Gate cell: the host for random host pages, the failure class for diagnostic pages, else the stratum."""
    if m["stratum"] == "host":
        return m["cell"]
    if m["stratum"] == "failure":
        return f"failure:{m['cell']}"
    return m["stratum"]


def score_corpus(corpus, parsed_path):
    man = {m["page_id"]: m for m in load_ndjson(os.path.join(corpus, "manifest.ndjson"))}
    gold = {g["page_id"]: g for g in load_ndjson(os.path.join(corpus, "gold.ndjson"))}
    out = []
    for p in load_ndjson(parsed_path):
        pid = p["page_id"]
        if pid not in gold or pid not in man:
            continue
        g = F.from_label(gold[pid]["gold"])
        c = F.from_parseland(p["out"]) if p.get("out") else dict(EMPTY)
        out.append({
            "page_id": pid, "cell": cell_of(man[pid]), "stratum": man[pid]["stratum"],
            "right": {f: F.compare(f, g, c) for f in F.FIELDS},
            "gold_present": {f: F.present(f, g) for f in F.FIELDS},
            "cand_present": {f: F.present(f, c) for f in F.FIELDS},
            "crash": bool(p.get("error")), "ms": p.get("ms"),
        })
    return out


def cells(results):
    """(cell, field) -> {"n", "right", "gold_present", "cand_present", "true_pos"}; plus "*" pooled rows."""
    agg = collections.defaultdict(lambda: collections.Counter())
    for r in results:
        for f in F.FIELDS:
            for key in ((r["cell"], f), ("*", f)):
                a = agg[key]
                a["n"] += 1
                a["right"] += r["right"][f]
                a["gold_present"] += r["gold_present"][f]
                a["cand_present"] += r["cand_present"][f]
                a["true_pos"] += r["right"][f] and r["gold_present"][f]
    return {f"{c}|{f}": dict(v) for (c, f), v in sorted(agg.items())}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--parsed", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cells")
    a = ap.parse_args()
    res = score_corpus(a.corpus, a.parsed)
    with open(a.out, "w") as f:
        for r in res:
            f.write(json.dumps(r) + "\n")
    if a.cells:
        json.dump(cells(res), open(a.cells, "w"), indent=1)
    tot = sum(sum(r["right"].values()) for r in res)
    print(f"scored {len(res)} pages: {tot}/{len(res) * len(F.FIELDS)} page-fields right", file=sys.stderr)
