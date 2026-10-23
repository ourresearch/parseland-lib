"""The holdout gate: compare the candidate's scores with the commit in production (and the published baseline)
and decide whether the deploy may go ahead. Rules (oxjob #1791 EXPLORE § 5; charter plans/landing-pages.md § 6):

  per cell     refuse if, in any cell x field, losses >= 2 and losses > wins   (vs the commit in production)
  pooled       refuse if, for any field over all cells, losses - wins >= 3     (vs the commit in production)
  cumulative   refuse if any cell x field has >= 2 fewer right pages than the published baseline
  crashes      refuse if any page crashes that didn't crash in production

A "loss" is a page that was right and is now wrong; a "win" the reverse. Parseland is deterministic, so a flip is a
real output change; one lone loss passes (it can be a gold error or a one-off page) and is reported.
Output is counts per cell only, never page ids, URLs or values: this runs in a public repo's CI.

Usage: python gate/compare.py --base base_scores.ndjson --head head_scores.ndjson [--baseline gate/baseline.json]
                              [--summary summary.md] [--json result.json] [--override "reason"]
Exit 0 = deploy may proceed, 1 = refused, 2 = the two runs don't cover the same pages.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gate import fields as F  # noqa: E402
from gate.score import cells, load_ndjson  # noqa: E402

CELL_MIN_LOSSES = 2
POOLED_MAX_NET_LOSS = 3
BASELINE_MAX_DROP = 2


def decide(base, head, baseline=None):
    b = {r["page_id"]: r for r in base}
    h = {r["page_id"]: r for r in head}
    if set(b) != set(h):
        return {"verdict": "error", "reasons": [f"runs differ: {len(set(b) ^ set(h))} pages not in both"]}
    flips = collections.defaultdict(lambda: {"wins": 0, "losses": 0})
    pooled = collections.defaultdict(lambda: {"wins": 0, "losses": 0})
    new_crashes = 0
    for pid, hr in h.items():
        br = b[pid]
        new_crashes += hr["crash"] and not br["crash"]
        for f in F.FIELDS:
            if hr["right"][f] == br["right"][f]:
                continue
            k = "wins" if hr["right"][f] else "losses"
            flips[(hr["cell"], f)][k] += 1
            pooled[f][k] += 1
    hc, bc = cells(head), cells(base)
    reasons, rows = [], []
    for (cell, f), v in sorted(flips.items()):
        key = f"{cell}|{f}"
        rows.append({"cell": cell, "field": f, "n": hc[key]["n"], "right_before": bc[key]["right"],
                     "right_after": hc[key]["right"], **v})
        if v["losses"] >= CELL_MIN_LOSSES and v["losses"] > v["wins"]:
            reasons.append(f"{cell} {f}: {v['losses']} pages worse, {v['wins']} better")
    for f, v in sorted(pooled.items()):
        if v["losses"] - v["wins"] >= POOLED_MAX_NET_LOSS:
            reasons.append(f"all publishers {f}: {v['losses']} pages worse, {v['wins']} better")
    drops = []
    if baseline:
        for key, v in hc.items():
            base_v = baseline.get("cells", {}).get(key)
            if base_v and base_v["n"] == v["n"] and base_v["right"] - v["right"] >= BASELINE_MAX_DROP:
                cell, f = key.split("|")
                drops.append(key)
                reasons.append(f"{cell} {f}: {base_v['right'] - v['right']} pages below the published baseline")
    if new_crashes:
        reasons.append(f"{new_crashes} pages now crash the parser")
    return {"verdict": "refuse" if reasons else "pass", "reasons": reasons, "changed_cells": rows,
            "pooled": {f: dict(v) for f, v in pooled.items()}, "new_crashes": new_crashes,
            "pages": len(h), "baseline_drops": drops,
            "right_total": {"before": sum(sum(r["right"].values()) for r in base),
                            "after": sum(sum(r["right"].values()) for r in head)}}


def markdown(res, override=None):
    v = res["verdict"]
    head = {"pass": "PASS: no field worse on any publisher beyond noise",
            "refuse": "REFUSED: a field got worse beyond noise", "error": "ERROR"}[v]
    if override and v == "refuse":
        head = f"OVERRIDDEN ({override}); the gate would have refused"
    lines = [f"### Parseland holdout gate: {head}", "",
             f"{res.get('pages', 0)} sealed holdout pages; page-fields right: "
             f"{res.get('right_total', {}).get('before')} in production -> {res.get('right_total', {}).get('after')} "
             f"with this commit."]
    if res.get("reasons"):
        lines += ["", "**Why:**"] + [f"- {r}" for r in res["reasons"]]
    if res.get("changed_cells"):
        lines += ["", "| Cell | Field | Pages | Right before | Right after | Better | Worse |", "|---|---|---|---|---|---|---|"]
        lines += [f"| {r['cell']} | {r['field']} | {r['n']} | {r['right_before']} | {r['right_after']} | "
                  f"{r['wins']} | {r['losses']} |" for r in res["changed_cells"]]
    else:
        lines += ["", "No page changed on any field."]
    lines += ["", "Counts only: the holdout is sealed. Rules: gate/README.md."]
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--head", required=True)
    ap.add_argument("--baseline")
    ap.add_argument("--summary")
    ap.add_argument("--json")
    ap.add_argument("--override", default=os.environ.get("GATE_OVERRIDE") or None)
    a = ap.parse_args()
    baseline = json.load(open(a.baseline)) if a.baseline and os.path.exists(a.baseline) else None
    res = decide(list(load_ndjson(a.base)), list(load_ndjson(a.head)), baseline)
    md = markdown(res, a.override)
    print(md)
    if a.summary:
        open(a.summary, "a").write(md + "\n")
    if a.json:
        json.dump(res, open(a.json, "w"), indent=1)
    if res["verdict"] == "error":
        sys.exit(2)
    if res["verdict"] == "refuse" and (not a.override or res.get("new_crashes")):
        sys.exit(1)  # an override never waves through new crashes
