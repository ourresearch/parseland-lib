from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.thieme import Thieme


THIEME_HEAD = """
<meta name="citation_publisher" content="Thieme Medical Publishers">
<link rel="canonical" href="https://www.thieme-connect.de/products/ejournals/abstract/10.1055/example">
"""


def _soup(body, head=THIEME_HEAD):
    return BeautifulSoup(f"<html><head>{head}</head><body>{body}</body></html>", "lxml")


def test_thieme_citation_author_fallback_shares_unlabelled_affiliation():
    head = """
    <meta name="citation_publisher" content="Thieme">
    <meta name="citation_author" content="P. Toth Daru">
    <meta name="citation_author" content="E. Huszka">
    <link rel="canonical" href="https://www.thieme-connect.de/products/ejournals/abstract/10.1055/example">
    """
    body = """
    <div class="authors">P. Toth Daru, E. Huszka</div>
    <ul class="authorsAffiliationsList">
      <li>Department of Pediatric Surgery, Example University, Budapest</li>
    </ul>
    """

    parsed = Thieme(_soup(body, head=head)).parse()

    assert [author.name for author in parsed["authors"]] == ["P. Toth Daru", "E. Huszka"]
    assert parsed["authors"][0].affiliations == [
        "Department of Pediatric Surgery, Example University, Budapest"
    ]
    assert parsed["authors"][1].affiliations == parsed["authors"][0].affiliations


def test_thieme_labelled_affiliation_ids_do_not_mutate_soup():
    body = """
    <div class="authors">
      HC Tsay <a href="#AF1"><sup><b>1</b></sup></a>
      YF Chang <a href="#AF2"><sup><b>2</b></sup></a>
    </div>
    <ul class="authorsAffiliationsList">
      <li><sup><b>1</b></sup>Department of Neurology, First Hospital</li>
      <li><sup><b>2</b></sup>Department of Surgery, Second Hospital</li>
    </ul>
    """
    parser = Thieme(_soup(body))

    first = parser.parse()
    second = parser.parse()

    assert first["authors"][0].affiliations == ["Department of Neurology, First Hospital"]
    assert first["authors"][1].affiliations == ["Department of Surgery, Second Hospital"]
    assert second["authors"][0].affiliations == first["authors"][0].affiliations
    assert second["authors"][1].affiliations == first["authors"][1].affiliations


def test_thieme_abstract_uses_visible_abstract_and_drops_boilerplate():
    body = """
    <div id="abstract">
      PDF Download Buy Article Permissions and Reprints
      Zusammenfassung Dieses Kapitel beschreibt die wichtigsten klinischen Merkmale.
      Abstract This English abstract should not replace the German abstract.
      Key words sample words
    </div>
    """

    abstract = Thieme(_soup(body)).parse_abstract()

    assert abstract == "Dieses Kapitel beschreibt die wichtigsten klinischen Merkmale."


def test_thieme_citation_abstract_cleans_html_fragment():
    head = """
    <meta name="citation_publisher" content="Thieme">
    <meta name="citation_author" content="A. Researcher">
    <meta name="citation_abstract" content="&lt;p&gt;Abstract This is a long Thieme abstract with inline markup and enough text to pass the parser threshold.&lt;/p&gt;">
    """

    parsed = Thieme(_soup("", head=head)).parse()

    assert parsed["authors"][0].name == "A. Researcher"
    assert parsed["abstract"] == (
        "This is a long Thieme abstract with inline markup and enough text "
        "to pass the parser threshold."
    )


def test_parse_page_dispatches_thieme_from_citation_publisher():
    head = """
    <meta name="description" content="Article landing page">
    <meta name="citation_publisher" content="Georg Thieme Verlag">
    <meta name="citation_author" content="A. Researcher">
    <meta name="citation_abstract" content="This citation abstract is long enough for the Thieme parser to keep from metadata.">
    """

    parsed = parse_page(str(_soup("", head=head)), "doi", "https://doi.org/10.1055/example")

    assert parsed["authors"][0]["name"] == "A. Researcher"
    assert parsed["abstract"].startswith("This citation abstract")
