"""Unit tests from the frozen gold corpus (oxjob #1791): one test per dev page, offline.

Every dev page x field is pinned to gate/known_failures.json. A page-field that turns wrong is a regression; one that
turns right must be recorded with `python gate/ledger.py update` in the same commit, so progress is explicit.
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
    assert ledger["corpus"] == corpus.lock()["version"], "ledger was built on another corpus version"


@pytest.mark.parametrize("page", PAGES, ids=[f"{p.get('cell') or p['stratum']}/{p['page_id'][:8]}" for p in PAGES])
def test_page(page, results, ledger):
    r = results.get(page["page_id"])
    assert r is not None, "page has no gold row"
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
