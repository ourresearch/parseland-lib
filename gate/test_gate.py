"""Tests for the gate's own rules and matching (no corpus needed). Run: python -m pytest gate/test_gate.py"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gate import fields as F  # noqa: E402
from gate.compare import decide  # noqa: E402


def page(pid, cell, right=None, crash=False):
    right = right or {}
    return {"page_id": pid, "cell": cell, "stratum": "host", "crash": crash,
            "right": {f: right.get(f, True) for f in F.FIELDS},
            "gold_present": {f: True for f in F.FIELDS}, "cand_present": {f: True for f in F.FIELDS}}


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
