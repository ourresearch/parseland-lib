"""TEMPORARY, gate-proof branch only (oxjob #1791, 24 Oct 2026): prove on the sealed holdout that the don't-care rule
for pages of a different paper moves only those rows. Counts only (public repo).

  python gate/_proof_dont_care.py <holdout dir> <old prod scores> <new prod scores> <old baseline scores>
                                  <old baseline.json> <new baseline.json> <out.json>

old prod scores      production's own saved holdout scores (scorer before the rule)
new prod scores      the same production commit re-scored in this run (scorer with the rule)
old baseline scores  the baseline commit's saved holdout scores (first gated run, scorer before the rule)
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gate.score import DONT_CARE_KINDS, cells, load_ndjson, other_paper  # noqa: E402

KEYS = ["cell", "stratum", "right", "gold_present", "cand_present", "crash"]

if __name__ == "__main__":
    hold, old_p, new_p, old_b, old_bj, new_bj, out = sys.argv[1:8]
    dc = {g["page_id"] for g in load_ndjson(os.path.join(hold, "gold.ndjson"))
          if g["gold"].get("page_kind") in DONT_CARE_KINDS}
    old = {r["page_id"]: r for r in load_ndjson(old_p)}
    new = {r["page_id"]: r for r in load_ndjson(new_p)}
    flagged = {p for p, r in new.items() if r.get("dont_care")}
    res = {
        "holdout_pages": len(new),
        "same_pages": set(old) == set(new),
        "different_item_pages": len(dc),
        "flagged_equals_different_item": flagged == dc,
        "raw_rows_changed": sum(any(old[p][k] != new[p][k] for k in KEYS) for p in new if p in old),
        "prod_cells_equal_old_minus_different_item":
            cells(list(new.values())) == cells([r for r in old.values() if r["page_id"] not in dc]),
        "prod_right_before": sum(sum(r["right"].values()) for r in old.values()),
        "prod_right_after": sum(sum(r["right"].values()) for r in new.values() if not r.get("dont_care")),
        "prod_other_paper": other_paper(list(new.values())),
    }
    ob = [r for r in load_ndjson(old_b)]
    obj, nbj = json.load(open(old_bj)), json.load(open(new_bj))
    res["old_baseline_matches_its_scores"] = cells(ob) == obj["cells"]
    res["new_baseline_equals_old_minus_different_item"] = \
        cells([r for r in ob if r["page_id"] not in dc]) == nbj["cells"]
    res["baseline_cells_moved"] = sum(obj["cells"][k] != nbj["cells"].get(k) for k in obj["cells"])
    res["baseline_cells_dropped"] = sorted(set(obj["cells"]) - set(nbj["cells"]))
    res["baseline_pages"] = {"before": obj["pages"], "after": nbj["pages"]}
    res["baseline_other_paper"] = nbj.get("other_paper")
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))
