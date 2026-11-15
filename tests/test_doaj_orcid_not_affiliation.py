"""DOAJ record pages put each author's ORCID link in the affiliation slots; it is not an affiliation (oxjob #2239)."""
from bs4 import BeautifulSoup

from parseland_lib.repository.parsers.doaj import DOAJ

HTML = """<html><head><meta property="og:url" content="https://doaj.org/article/ab883b73a39e44a39cd68fdc62439b"/></head>
<body><dl id="authors-affiliations">
<dt>Alberto CONSOLARO</dt>
<dd><a href="https://orcid.org/0000-0002-5902-5646">ORCiD</a></dd>
<dt>Jaime Pajuelo</dt>
<dd>Universidad Nacional Mayor de San Marcos</dd>
<dd><a href="https://orcid.org/0000-0001-8841-6913">ORCiD</a></dd>
</dl></body></html>"""


def test_orcid_link_is_not_an_affiliation():
    authors = DOAJ(BeautifulSoup(HTML, "lxml")).parse()
    assert [a["affiliations"] for a in authors] == [[], ["Universidad Nacional Mayor de San Marcos"]]
