"""A De Gruyter chapter page's citation line in og:description is not its abstract (oxjob #2604).

Chapter pages with no abstract carry "<chapter title> was published in <book> on page 53." as og:description; the meta
reader took it whenever it ran over 200 characters (~67K works). These pin: (1) the line gives no abstract; (2) a page
that also shows an abstract section gets that abstract; (3) a real og:description abstract is kept.

Hand-crafted HTML: no Taxicab, no network.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from parseland_lib.publisher.parsers.de_gruyter import DeGruyter

LINE = (
    "Broken at the Nodes: Ekphrastic Crisis and Speculative Moral Receptivity in Hegel's Religious Phenomenology and "
    "Shakespeare's the Rape of Lucrece was published in L'héritage de Hegel - Hegel's Legacy on page 165."
)
REAL_ABSTRACT = (
    "This chapter reads Hegel's account of the unhappy consciousness against Shakespeare's narrative poem and argues "
    "that ekphrasis there stages a crisis of moral receptivity, which the poem resolves through speculative reading."
)


def _parse(og: str, body: str = ""):
    html = (f'<html><head><meta property="og:url" content="https://www.degruyterbrill.com/document/doi/x/html" />'
            f'<meta property="og:description" content="{og}" /></head><body>{body}</body></html>')
    return DeGruyter(BeautifulSoup(html, features="lxml")).parse()


def test_chapter_line_is_no_abstract():
    assert not _parse(LINE)["abstract"]


def test_abstract_section_wins_over_the_line():
    assert _parse(LINE, f'<div class="abstract">Abstract {REAL_ABSTRACT}</div>')["abstract"] == REAL_ABSTRACT


def test_real_meta_abstract_kept():
    assert _parse(REAL_ABSTRACT)["abstract"] == REAL_ABSTRACT
