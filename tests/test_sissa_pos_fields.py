"""Proceedings of Science (pos.sissa.it, SISSA Medialab) contribution pages (oxjob #2338, Parseland swarm).

Markup cut down from stored PoS pages (17 Nov 2026). The page's byline (div#landing-page div.authors) prints one
span.au per author, initials first ("T.W. Chiu"), and marks the corresponding author with class "corresponding" and
the title "Corresponding author" (newer pages add a "*: corresponding author" note). The citation_author tags give the
same authors in the same order, in fuller form ("Chiu, Ting-Wai"), and carry no mark: before this parser no one was
marked. Single-author pages mark no one. The page shows no affiliations and no back matter.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.sissa_pos import SissaPoS

URL = "https://pos.sissa.it/363/133"
ABSTRACT = ("Using 10-16 units of Nvidia DGX-1, we have generated the first gauge ensemble for lattice QCD with "
            "physical domain-wall quarks. The salient feature of this gauge ensemble is that the chiral symmetry is "
            "preserved to a high precision and all topological sectors are sampled ergodically.")


def _page(metas, byline, identifier="https://pos.sissa.it/363/133", abstract=ABSTRACT, landing_id="landing-page"):
    tags = "".join(f'<meta name="dcterms.creator" content="{m}"/><meta name="citation_author" content="{m}"/>'
                   for m in metas)
    ident = f'<meta name="dcterms.identifier" content="{identifier}"/>' if identifier else ""
    abs_meta = f'<meta name="citation_abstract" content="{abstract}"/>' if abstract else ""
    abs_block = (f'<div class="abstract"><span class="label">Abstract</span><div class="content">{abstract}</div></div>'
                 if abstract else "")
    return (f'<!DOCTYPE html><html><head><title>A title</title>{ident}'
            f'<meta name="citation_publisher" content="SISSA Medialab"/>'
            f'<meta name="citation_title" content="A title"/>{tags}'
            f'<meta name="citation_pdf_url" content="https://pos.sissa.it/363/133/pdf"/>{abs_meta}'
            f'<meta name="citation_doi" content="10.22323/1.363.0133"/></head><body>'
            f'<div id="{landing_id}"><div class="title">A title</div>'
            f'<div class="authors"><div class="list">{byline}</div></div>{abs_block}</div></body></html>')


def _au(name, corresponding=False):
    if corresponding:
        return f'<span class="au corresponding" title="Corresponding author">{name}</span>*'
    return f'<span class="au">{name}</span>'


def _authors(html):
    return parse_page(html.encode(), "doi", URL)["authors"]


def _corr(html):
    return [a["name"] for a in _authors(html) if a["is_corresponding"]]


def test_marked_author_is_corresponding_and_keeps_the_fuller_meta_name():
    html = _page(["Chiu, Ting-Wai", "on behalf of TWQCD Collaboration,"],
                 _au("T.W.\xa0Chiu", True) + " " + _au(" on behalf of TWQCD Collaboration"))
    authors = _authors(html)
    assert [a["name"] for a in authors] == ["Chiu, Ting-Wai", "on behalf of TWQCD Collaboration,"]
    assert [a["is_corresponding"] for a in authors] == [True, False]


def test_newer_byline_with_note_marks_a_later_author():
    metas = ["Fink, Cornelia", "Jaeger, Benjamin", "Gasparyan, Ashot", "Rusetsky, Akaki"]
    byline = ", ".join([_au("C.\xa0Fink"), _au("B.\xa0Jaeger", True), _au("A.\xa0Gasparyan"), _au("A.\xa0Rusetsky")])
    html = _page(metas, byline + '<div style="margin-top:1em;">*: corresponding author</div>')
    assert _corr(html) == ["Jaeger, Benjamin"]


def test_two_word_family_name_is_matched():
    html = _page(["Barbosa Martins, Victor", "Kerr, Matthew"],
                 _au("V.\xa0Barbosa Martins", True) + ", " + _au("M.\xa0Kerr"))
    assert _corr(html) == ["Barbosa Martins, Victor"]


def test_byline_longer_than_the_tags_marks_by_family_name():
    # a byline and tags of different lengths: the mark goes to the tag author with the marked span's family name
    html = _page(["Kerr, Matthew", "Sugiura, Takuya"],
                 ", ".join([_au("A.\xa0Other"), _au("M.\xa0Kerr"), _au("T.\xa0Sugiura", True)]))
    assert _corr(html) == ["Sugiura, Takuya"]


def test_single_author_page_marks_no_one():
    html = _page(["Davoudi, Zohreh"], _au("Z.\xa0Davoudi"), abstract=None)
    authors = _authors(html)
    assert [a["name"] for a in authors] == ["Davoudi, Zohreh"]
    assert not any(a["is_corresponding"] for a in authors)


def test_abstract_is_read_as_before():
    html = _page(["Chiu, Ting-Wai", "Lee, Ann"], _au("T.W.\xa0Chiu", True) + ", " + _au("A.\xa0Lee"))
    assert parse_page(html.encode(), "doi", URL)["abstract"] == ABSTRACT


def test_parse_returns_no_back_matter_keys():
    html = _page(["Chiu, Ting-Wai", "Lee, Ann"], _au("T.W.\xa0Chiu", True) + ", " + _au("A.\xa0Lee"))
    parsed = SissaPoS(BeautifulSoup(html, parser="lxml", features="lxml")).parse()
    assert not any(parsed.get(k) for k in ("acknowledgments", "funding_statement", "references"))


def test_journal_of_science_communication_page_is_not_claimed():
    # SISSA Medialab's JCOM (jcom.sissa.it) shares the publisher tag but is another template; and a look-alike byline
    # on any page without PoS's identifier is never claimed
    html = _page(["Chiu, Ting-Wai", "Lee, Ann"], _au("T.W.\xa0Chiu", True) + ", " + _au("A.\xa0Lee"),
                 identifier="info:doi/10.22323/2.21050202")
    parser = SissaPoS(BeautifulSoup(html, parser="lxml", features="lxml"))
    assert not parser.authors_found()
    assert not parser.is_publisher_specific_parser()


def test_identifier_in_the_body_is_not_a_claim():
    html = _page(["Chiu, Ting-Wai", "Lee, Ann"], _au("T.W.\xa0Chiu", True) + ", " + _au("A.\xa0Lee"),
                 identifier=None).replace(
        "<body>", '<body><meta name="dcterms.identifier" content="https://pos.sissa.it/1/1"/>')
    assert not SissaPoS(BeautifulSoup(html, parser="lxml", features="lxml")).authors_found()
