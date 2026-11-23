"""Tests for the gate's own rules and matching (no corpus needed). Run: python -m pytest gate/test_gate.py"""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gate import corpus, shard  # noqa: E402
from gate import fields as F  # noqa: E402
from gate.compare import decide  # noqa: E402
from gate.run_parser import shard_rows  # noqa: E402
from gate.score import cells, other_paper  # noqa: E402


def page(pid, cell, right=None, crash=False, dont_care=False, emits=True, fields=F.FIELDS):
    right = right or {}
    return {"page_id": pid, "cell": cell, "stratum": "host", "crash": crash, "dont_care": dont_care,
            "right": {f: right.get(f, True) for f in fields},
            "gold_present": {f: True for f in fields}, "cand_present": {f: emits for f in fields}}


def run(base, head, baseline=None):
    return decide(base, head, baseline)


def test_no_change_passes():
    base = [page(f"p{i}", "wiley.com") for i in range(20)]
    assert run(base, base)["verdict"] == "pass"


def test_one_loss_passes_two_refuse():
    base = [page(f"p{i}", "wiley.com") for i in range(20)]
    one = base[:19] + [page("p19", "wiley.com", {"affiliations": False})]
    assert run(base, one)["verdict"] == "pass"
    two = base[:18] + [page(f"p{i}", "wiley.com", {"affiliations": False}) for i in (18, 19)]
    res = run(base, two)
    assert res["verdict"] == "refuse" and "wiley.com affiliations" in res["reasons"][0]


def test_losses_offset_by_wins_pass():
    base = [page(f"p{i}", "wiley.com", {"abstract": i >= 2}) for i in range(20)]
    head = [page(f"p{i}", "wiley.com", {"abstract": i not in (2, 3)}) for i in range(20)]  # 2 wins, 2 losses
    assert run(base, head)["verdict"] == "pass"


def test_pooled_small_losses_across_publishers_refuse():
    hosts = ["a.com", "b.com", "c.com"]
    base = [page(f"{h}{i}", h) for h in hosts for i in range(10)]
    head = [page(f"{h}{i}", h, {"pdf_url": i != 0}) for h in hosts for i in range(10)]  # one loss per host
    res = run(base, head)
    assert res["verdict"] == "refuse" and any(r.startswith("all publishers pdf_url") for r in res["reasons"])


def test_new_crash_refuses():
    base = [page(f"p{i}", "x.com") for i in range(5)]
    head = base[:4] + [page("p4", "x.com", crash=True)]
    assert run(base, head)["verdict"] == "refuse"


def test_baseline_ratchet_refuses():
    base = [page(f"p{i}", "x.com", {"license": i >= 1}) for i in range(10)]   # production: 9 right
    head = [page(f"p{i}", "x.com", {"license": i >= 2}) for i in range(10)]   # one more loss: 8 right
    baseline = {"cells": {"x.com|license": {"n": 10, "right": 10}}}            # published baseline: 10 right
    res = run(base, head, baseline)
    assert res["verdict"] == "refuse" and "below the published baseline" in res["reasons"][-1]


def test_different_paper_pages_are_dont_care():
    """A stored page showing another paper can't make the gate refuse, and is reported apart (charter § 6, 24 Oct)."""
    base = [page(f"p{i}", "karger.com") for i in range(10)] + [
        page(f"d{i}", "karger.com", dont_care=True, emits=False) for i in range(3)]
    head = [page(f"p{i}", "karger.com") for i in range(10)] + [
        page(f"d{i}", "karger.com", {"abstract": False, "authors": False}, dont_care=True) for i in range(3)]
    baseline = {"cells": cells(base)}
    res = run(base, head, baseline)
    assert res["verdict"] == "pass" and not res["changed_cells"] and not res["pooled"]
    assert res["pages"] == 10 and res["right_total"]["before"] == res["right_total"]["after"] == 60
    assert res["other_paper"]["before"]["pages"] == 3 and res["other_paper"]["before"]["emits"]["abstract"] == 0
    assert res["other_paper"]["after"]["emits"]["abstract"] == 3
    assert cells(head)["karger.com|abstract"]["n"] == 10


def test_dont_care_flag_on_either_run_counts():
    """Production's saved scores can predate the flag: a page flagged on either run is left out."""
    base = [page(f"p{i}", "x.com") for i in range(5)] + [page(f"d{i}", "x.com") for i in range(2)]
    head = [page(f"p{i}", "x.com") for i in range(5)] + [
        page(f"d{i}", "x.com", {"license": False}, dont_care=True) for i in range(2)]
    res = run(base, head)
    assert res["verdict"] == "pass" and res["pages"] == 5 and not res["changed_cells"]


def test_crash_on_dont_care_page_still_refuses():
    base = [page("p0", "x.com"), page("d0", "x.com", dont_care=True)]
    head = [page("p0", "x.com"), page("d0", "x.com", dont_care=True, crash=True)]
    assert run(base, head)["verdict"] == "refuse"


def test_other_paper_counts():
    rows = [page("a", "x.com", dont_care=True), page("b", "x.com", dont_care=True, emits=False), page("c", "x.com")]
    o = other_paper(rows)
    assert o["pages"] == 2 and o["emits"]["authors"] == 1 and o["crash"] == 0


def test_mismatched_runs_error():
    assert run([page("a", "x.com")], [page("b", "x.com")])["verdict"] == "error"


def test_name_and_url_matching():
    assert F.name_match("Gooch, Jan W.", "Jan W. Gooch")
    assert not F.name_match("Wei Zhang", "Wei Chen")
    assert F.name_match("V. Peréz‐Tello", "V. Peréz-Tello")  # Unicode hyphen
    assert F.name_match("O’Brien, Pat", "Pat O'Brien")
    assert F.aff_match("Daito Bunka University - Department of Economics",
                       "Daito Bunka University - Department of Economics Takashimadaira 1-9-1, Tokyo 175-857 Japan")
    assert F.canon_url("https://onlinelibrary.wiley.com/doi/epdf/10.1/x") == F.canon_url(
        "https://onlinelibrary.wiley.com/doi/pdfdirect/10.1/x?download=true")
    assert not F.aff_match("Department of Physics", "Department of Physics, MIT, Cambridge, MA, USA")


def test_extra_value_is_wrong():
    gold = {"authors": [], "abstract": None, "pdf_url": None, "license": "none"}
    cand = {"authors": [{"name": "A B", "affiliations": [], "is_corresponding": False}], "abstract": "x" * 50,
            "pdf_url": "https://x/login.html", "license": "cc-by"}
    assert not any(F.compare(f, gold, cand) for f in ("authors", "abstract", "pdf_url", "license"))


def entry(i):
    return f"{i}. Author{i} A, Writer B. A study of item number {i} in practice. J Things. 20{i:02d};{i}:1-9."


def refs(n, complete=True, dois=None, raw=entry):
    dois = dois or [None] * n
    return {"references": [{"raw": raw(i), "doi": dois[i]} for i in range(n)], "references_complete": complete}


def both(field, gold, cand):
    return F.compare(field, gold, cand), F.compare(f"{field}_safe" if field == "references" else field, gold, cand)


def test_reference_list_rules():
    """Downstream takes a list only when it is whole: a partial list called whole is wrong (#2215)."""
    whole, partial, none = refs(5), refs(3, complete=False), {"references": None, "references_complete": False}
    assert both("references", whole, refs(5)) == (True, True)
    assert both("references", whole, refs(4)) == (False, False)                    # an entry lost or merged
    assert both("references", partial, refs(3)) == (False, False)                  # a partial list called whole
    assert both("references", whole, refs(5, complete=False)) == (False, True)     # a miss, not unsafe
    assert both("references", partial, refs(2, complete=False)) == (True, True)    # two partial lists: neither used
    assert F.compare("references", none, partial) and F.compare("references", none, none)
    assert both("references", none, refs(2)) == (False, False)
    assert F.present("references", whole) and not F.present("references", partial)


def test_reference_entries_and_dois():
    """Same-count corruption is wrong: blank, cut or key=value entries, and lost or conflicting DOIs (#2215 Test 3)."""
    dois = [f"10.1/x{i}" for i in range(10)]
    gold = refs(10, dois=dois)
    assert both("references", gold, refs(10, dois=[f"https://doi.org/10.1%2FX{i}" for i in range(10)])) == (True, True)
    assert both("references", gold, refs(10)) == (False, True)                     # every DOI dropped: poorer, safe
    assert both("references", gold, refs(10, dois=["10.1/x0"] * 10)) == (False, False)  # conflicting DOIs
    assert both("references", gold, refs(10, dois=dois, raw=lambda i: "")) == (False, False)  # blank entries
    cut = refs(10, dois=dois, raw=lambda i: entry(i)[:40])
    assert both("references", gold, cut) == (False, False)                         # entries cut short
    kv = refs(10, dois=dois, raw=lambda i: f"citation_author=Author{i}; citation_year=20{i:02d}")
    assert both("references", gold, kv) == (False, False)
    one_odd = refs(10, dois=dois, raw=lambda i: entry(i) if i else "x")
    assert both("references", gold, one_odd) == (True, True)                       # >= 90% of entries hold
    linked = refs(10, dois=dois, raw=lambda i: entry(i) + f" DOI: https://doi.org/10.1/x{i}")
    assert both("references", gold, linked) == (True, True)                        # link text in the entry is fine


def test_statement_rules():
    g = {"acknowledgments": "Acknowledgments: We thank the staff of the archive for their help with the records.",
         "funding_statement": "Funding: This work was funded by the National Science Foundation (grant 1234567)."}
    assert F.compare("acknowledgments", g, {"acknowledgments": "We thank the staff of the archive for their help "
                                                               "with the records."})
    assert not F.compare("acknowledgments", g, {"acknowledgments": "We thank the staff."})
    assert not F.compare("acknowledgments", g, {"acknowledgments": None})
    assert not F.compare("acknowledgments", g, {"acknowledgments": "Acknowledgments"})  # a heading alone is nothing
    assert F.norm_statement("Funding:") is None and F.norm_statement("Funding") is None
    assert F.compare("funding_statement", g, {"funding_statement": "This work was funded by the National Science "
                                                                   "Foundation (grant 1234567)."})
    assert not F.compare("funding_statement", g, {"funding_statement": "This work was funded by the National Science "
                                                                       "Foundation (grant 1234568)."})
    assert F.compare("funding_statement", {"funding_statement": None}, {"funding_statement": "  "})


def test_doi_forms():
    assert F.norm_doi("doi:https://doi.org/10.1/A") == F.norm_doi("//dx.doi.org/10.1%2Fa") == "10.1/a"
    assert F.norm_doi(None) is None and F.norm_doi("") is None


def test_lock_pins_both_splits():
    lk = corpus.lock()
    assert {"dev", "holdout"} <= set(lk) and lk["holdout"]["encrypted"] and not lk["dev"]["encrypted"]


def test_pages_are_judged_on_their_own_fields():
    """Back matter is scored only where the gold labelled it; cells and rules run over each page's own fields."""
    base = [page(f"p{i}", "springer.com", fields=F.ALL_FIELDS) for i in range(6)] + [
        page(f"q{i}", "x.com") for i in range(6)]
    head = [page(f"p{i}", "springer.com", {"references": i >= 2}, fields=F.ALL_FIELDS) for i in range(6)] + base[6:]
    c = cells(head)
    assert c["springer.com|references"] == {"n": 6, "right": 4, "gold_present": 6, "cand_present": 6, "true_pos": 4}
    assert "x.com|references" not in c and c["*|references"]["n"] == 6 and c["*|authors"]["n"] == 12
    res = run(base, head)
    assert res["verdict"] == "refuse" and res["reasons"][0].startswith("springer.com references: 2 pages worse")
    assert res["fields"]["references"] == {"n": 6, "gold_present": 6, "before": 6, "after": 4}


def test_runs_scoring_different_fields_error():
    base = [page("p0", "x.com")]
    head = [page("p0", "x.com", fields=F.ALL_FIELDS)]
    assert run(base, head)["verdict"] == "error"


def test_shards_cover_every_page_once_and_balance_by_size():
    rows = [{"page_id": f"p{i}", "size": s} for i, s in enumerate([90, 10, 10, 10, 30, 30, 20, 20, 5, 5])]
    parts = [shard_rows(rows, (i, 3), lambda r: r["size"]) for i in range(3)]
    assert sorted(r["page_id"] for p in parts for r in p) == sorted(r["page_id"] for r in rows)
    assert [sum(r["size"] for r in p) for p in parts] == [90, 70, 70]
    assert shard_rows(rows, None) == rows
    with pytest.raises(ValueError):
        shard_rows(rows, (3, 3))


def test_merge_refuses_a_missing_or_doubled_shard(tmp_path, monkeypatch):
    monkeypatch.setattr(corpus, "lock", lambda: {"dev": {"pages": 3}})
    a, b = tmp_path / "a.ndjson", tmp_path / "b.ndjson"
    a.write_text("".join(json.dumps(page(p, "x.com")) + "\n" for p in ("p0", "p1")))
    b.write_text(json.dumps(page("p2", "x.com")) + "\n")
    out = tmp_path / "out.ndjson"
    shard.merge("dev", str(out), [str(a), str(b)])
    assert len(out.read_text().splitlines()) == 3
    with pytest.raises(SystemExit, match="a shard is missing"):
        shard.merge("dev", str(out), [str(a)])
    with pytest.raises(SystemExit, match="in two shards"):
        shard.merge("dev", str(out), [str(a), str(a), str(b)])
