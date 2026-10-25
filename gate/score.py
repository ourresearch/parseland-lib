"""Score parse_page outputs against the gold, page by page and field by field (rules in gate/fields.py).

Usage: python gate/score.py --corpus <bundle dir> --parsed parsed.ndjson --out scores.ndjson [--cells cells.json]
Each output line: {"page_id", "cell", "stratum", "page_kind", "dont_care": bool, "right": {field: bool},
                   "gold_present": {...}, "cand_present": {...}, "crash": bool, "ms": float}

Don't-care pages (charter plans/landing-pages.md § 6, 24 Oct 12:58 CT): a stored page the gold marks as showing a
different paper (page_kind "different_item", e.g. a DOI one digit off) is a fetch error the parser can't see. Its row
keeps the raw right/wrong, but "dont_care" is set and no count the gate or the ledger judges on includes it (cells(),
compare.py, ledger.py). other_paper() reports them on their own line: how many, and on how many Parseland emits a
value per field (today it emits the other paper's metadata), so a future DOI-mismatch check is measured by itself.
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
DONT_CARE_KINDS = {"different_item"}


def load_ndjson(path):
    with open(path) as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def cell_of(m):
    """Gate cell: the host for random host pages; the failure class or the current template for the purposive strata
    (e.g. "failure:cairn_no_aff", "template:mdpi.com (Nuxt)"); else the stratum."""
    if m["stratum"] == "host":
        return m["cell"]
    if m["stratum"] in ("failure", "template"):
        return f"{m['stratum']}:{m['cell']}"
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
        kind = gold[pid]["gold"].get("page_kind")
        out.append({
            "page_id": pid, "cell": cell_of(man[pid]), "stratum": man[pid]["stratum"],
            "page_kind": kind, "dont_care": kind in DONT_CARE_KINDS,
            "right": {f: F.compare(f, g, c) for f in F.FIELDS},
            "gold_present": {f: F.present(f, g) for f in F.FIELDS},
            "cand_present": {f: F.present(f, c) for f in F.FIELDS},
            "crash": bool(p.get("error")), "ms": p.get("ms"),
        })
    return out


def scored(results):
    """The rows the gate and the ledger judge on: every page except the don't-care ones."""
    return [r for r in results if not r.get("dont_care")]


def other_paper(results):
    """Don't-care pages, reported apart: {"pages", "emits": {field: pages where Parseland emits a value}, "crash"}."""
    dc = [r for r in results if r.get("dont_care")]
    return {"pages": len(dc), "emits": {f: sum(bool(r["cand_present"][f]) for r in dc) for f in F.FIELDS},
            "crash": sum(bool(r["crash"]) for r in dc)}


def other_paper_line(o, label="Pages of a different paper (gold page_kind different_item; don't-care, not scored)"):
    emits = ", ".join(f"{f} {o['emits'][f]}" for f in F.FIELDS)
    return f"{label}: {o['pages']} pages; Parseland emits a value on: {emits}" + (
        f"; {o['crash']} crash" if o.get("crash") else "")


def cells(results):
    """(cell, field) -> {"n", "right", "gold_present", "cand_present", "true_pos"}; plus "*" pooled rows.
    Don't-care pages are left out."""
    agg = collections.defaultdict(lambda: collections.Counter())
    for r in scored(results):
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
    sc = scored(res)
    tot = sum(sum(r["right"].values()) for r in sc)
    print(f"scored {len(sc)} pages: {tot}/{len(sc) * len(F.FIELDS)} page-fields right", file=sys.stderr)
    print(other_paper_line(other_paper(res)), file=sys.stderr)
