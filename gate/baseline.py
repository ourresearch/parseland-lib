"""Publish the holdout baseline: one commit's counts per cell x field (oxjob #1791; rerun only when the holdout is
refreshed). Writes gate/baseline.json (counts only) and a markdown table per publisher x field for the charter.

Usage: python gate/baseline.py --lib <checkout of the baseline commit> --commit <sha> [--md baseline.md]
Needs the holdout bundle (CI, or #1791 while sealing it).
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from gate import corpus  # noqa: E402
from gate import fields as F  # noqa: E402
from gate.run_parser import run  # noqa: E402
from gate.score import cells, score_corpus  # noqa: E402

SHORT = {"authors": "authors", "affiliations": "affil.", "corresponding": "corresp.", "abstract": "abstract",
         "pdf_url": "PDF", "license": "licence"}


def table(c, results):
    hosts = sorted({r["cell"] for r in results if r["stratum"] == "host"},
                   key=lambda h: -c[f"{h}|authors"]["n"])
    pooled = ["tail", "repository", "unresolved", "wall"]
    fail = sorted({r["cell"] for r in results if r["stratum"] == "failure"})
    head = "| Publisher (holdout pages) | Pages | " + " | ".join(SHORT[f] for f in F.FIELDS) + " |"
    lines = [head, "|---|" + "---:|" * (len(F.FIELDS) + 1)]
    for h in hosts + [p for p in pooled if f"{p}|authors" in c] + fail + ["*"]:
        n = c[f"{h}|authors"]["n"]
        name = {"*": "**all holdout pages**", "tail": "long tail (pooled)", "repository": "repository pages",
                "unresolved": "unresolved older pages", "wall": "walls and shells"}.get(h, h)
        lines.append(f"| {name} | {n} | " + " | ".join(
            f"{round(100 * c[f'{h}|{f}']['right'] / n)}" for f in F.FIELDS) + " |")
    lines.append("")
    lines.append("% of pages where Parseland's value matches the gold (absent-and-absent counts as right; an extra "
                 "value counts as wrong).")
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--lib", required=True)
    ap.add_argument("--commit", required=True)
    ap.add_argument("--md")
    a = ap.parse_args()
    h = corpus.fetch("holdout")
    with tempfile.TemporaryDirectory() as tmp:
        parsed = os.path.join(tmp, "parsed.ndjson")
        run(a.lib, h, parsed)
        res = score_corpus(h, parsed)
    c = cells(res)
    out = {"commit": a.commit, "corpus": corpus.version(), "pages": len(res),
           "computed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "cells": c}
    json.dump(out, open(os.path.join(ROOT, "gate", "baseline.json"), "w"), indent=0, sort_keys=True)
    md = table(c, res)
    if a.md:
        open(a.md, "w").write(md + "\n")
    print(md)
