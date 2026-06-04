"""Regression tests for Wiley abstract recovery on cached HTML samples.

These DOIs appeared as `parsed_len=0` in the
`whole-goldie-after-elsevier-canonical-dispatch.json` eval run but recover with
the current Wiley parser. Pins that recovery to prevent regression.

If/when the eval is re-run against the current parser these rows should match
gold; this test lets us catch any future change that breaks fallback paths
(section[class*=abstract] paragraph extraction, editorial article__body
fallback).
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from parseland_lib.publisher.parsers.wiley import Wiley


CACHE_DIR = Path(__file__).parent.parent / "mismatches" / "whole-goldie-cache"


def _load(doi: str) -> BeautifulSoup | None:
    sha = hashlib.sha1(doi.lower().encode()).hexdigest()
    path = CACHE_DIR / f"{sha}.html"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return BeautifulSoup(f.read(), "lxml")


# (doi, min_length, must_contain_substring)
RECOVERY_CASES: list[tuple[str, int, str]] = [
    # Modern section[class*=abstract] / p-extraction fallback
    ("10.1002/9781444351071.wbeghm234", 1000, "Film festivals"),
    ("10.1002/9781119756927.ch2", 800, ""),
    ("10.1002/9781119750482.ch5", 800, ""),
    ("10.1002/hast.935", 1000, ""),
    ("10.1111/1467-9752.12083", 800, ""),
    # Short legacy abstracts that should pass the relaxed length gate (>=15)
    ("10.1002/chin.197917304", 100, ""),
    ("10.1002/chin.198645132", 100, ""),
    ("10.1002/chin.198523283", 100, ""),
    ("10.1002/chin.197650269", 100, ""),
    ("10.1002/9780470774311.ch2", 100, ""),
    # Older Wiley/Blackwell editorials picked up by div.article__body fallback
    ("10.1111/j.1467-923x.2008.00922.x", 600, "Books reviewed"),
]


@pytest.mark.parametrize("doi,min_len,must_contain", RECOVERY_CASES)
def test_wiley_abstract_recovers(doi: str, min_len: int, must_contain: str) -> None:
    soup = _load(doi)
    if soup is None:
        pytest.skip(f"cached HTML for {doi} not present")
    parser = Wiley(soup)
    if not parser.is_publisher_specific_parser():
        pytest.skip(f"{doi}: HTML no longer identifies as Wiley (canonical/og:url drift)")
    abstract = parser.get_abstract()
    assert abstract, f"{doi}: expected non-empty abstract"
    assert len(abstract) >= min_len, (
        f"{doi}: abstract length {len(abstract)} below floor {min_len}"
    )
    if must_contain:
        assert must_contain.lower() in abstract.lower(), (
            f"{doi}: expected substring '{must_contain}' missing"
        )


def test_wiley_abstract_skips_cookie_walls() -> None:
    """Cookie-wall pages (canonical points at /action/cookieAbsent) should
    return None rather than producing garbage. Pin behavior so we know if a
    future change starts hallucinating content from such pages.
    """
    soup = _load("10.1002/suco.201700200")
    if soup is None:
        pytest.skip("cached HTML for cookie-wall case not present")
    parser = Wiley(soup)
    abstract = parser.get_abstract()
    assert abstract is None or len(abstract) < 100, (
        "cookie-wall page should produce no abstract"
    )
