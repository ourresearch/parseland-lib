"""Unit tests from the frozen gold corpus (oxjob #1791): one test per dev page, offline.

Every dev page x field is pinned to gate/known_failures.json. A page-field that turns wrong is a regression; one that
turns right must be recorded with `python gate/ledger.py update` in the same commit, so progress is explicit.
Pages of a different paper (gold page_kind "different_item") are don't-care and skip (charter § 6, 24 Oct 2026).
Needs the dev bundle (`python gate/corpus.py fetch dev`); without it these tests skip, except in CI
(GATE_REQUIRE_CORPUS=1), where a missing corpus fails the run.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from gate import corpus  # noqa: E402

DEV = corpus.bundle_dir("dev")
HAVE = os.path.exists(os.path.join(DEV, "manifest.ndjson"))
REQUIRE = os.environ.get("GATE_REQUIRE_CORPUS") == "1"


def _manifest():
    if not HAVE:
        return []
    return [json.loads(l) for l in open(os.path.join(DEV, "manifest.ndjson"))]


PAGES = _manifest()


@pytest.fixture(scope="session")
def results():
    from gate.ledger import current
    return {r["page_id"]: r for r in current()}


@pytest.fixture(scope="session")
def ledger():
    from gate.ledger import load
    return load()


def test_corpus_present():
    if not HAVE:
        msg = f"dev corpus not at {DEV}: run `python gate/corpus.py fetch dev`"
        if REQUIRE:
            pytest.fail(msg)
        pytest.skip(msg)


def test_ledger_matches_corpus_version(ledger):
    if not HAVE:
        pytest.skip("no dev corpus")
    assert ledger["corpus"] == corpus.version(), "ledger was built on another corpus version"


def test_ledger_lists_no_dont_care_page(results, ledger):
    if not HAVE:
        pytest.skip("no dev corpus")
    listed = sorted(p[:8] for p in ledger["pages"] if results.get(p, {}).get("dont_care"))
    assert not listed, (f"the ledger lists pages of a different paper, which are don't-care: {listed}; "
                        "rebuild it with `python gate/ledger.py update`")


@pytest.mark.parametrize("page", PAGES, ids=[f"{p.get('cell') or p['stratum']}/{p['page_id'][:8]}" for p in PAGES])
def test_page(page, results, ledger):
    r = results.get(page["page_id"])
    assert r is not None, "page has no gold row"
    if r.get("dont_care"):
        pytest.skip(f"stored page shows a different paper (gold page_kind {r.get('page_kind')}): don't-care")
    expected_wrong = set(ledger["pages"].get(page["page_id"], []))
    now_wrong = {f for f, ok in r["right"].items() if not ok}
    worse = sorted(now_wrong - expected_wrong)
    better = sorted(expected_wrong - now_wrong)
    msgs = []
    if worse:
        msgs.append(f"REGRESSION on {worse} ({page.get('cell')} {page.get('template')})")
    if better:
        msgs.append(f"now right on {better}: record it with `python gate/ledger.py update`")
    assert not msgs, "; ".join(msgs)
