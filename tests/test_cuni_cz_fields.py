"""Charles University's medical-faculty journals on cuni.cz (oxjob #2339): Acta Medica (actamedica.lfhk.cuni.cz),
Folia Biologica (foliabiologica.lf1.cuni.cz) and Prague Medical Report (pmr.lf1.cuni.cz) share one template. Markup is
cut down from stored pages (17 Nov 2026). Its meta tags give the byline and affiliations; the page links one author's
name to an e-mail address (mailto) in <div id="authors" class="abstract-authors">, and label-v1's labellers read that
as the corresponding-author mark. Only that mark is new; everything else stays as the meta-tag reader has it.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.cuni_cz import CuniMedicalJournals

URL = "https://actamedica.lfhk.cuni.cz/54/3/131/"
PUBLISHER = '<meta name="citation_publisher" content="Charles University in Prague, Karolinum Press" />'
AFF = "Department of Anatomy, Example Medical College, New Delhi, India"
NAMES = [("Alpha", "Anna"), ("Beta", "Boris"), ("Gamma", "Greta")]


def _page(byline, publisher=PUBLISHER, names=NAMES):
    metas = "".join(f'<meta name="citation_author" content="{last}, {first}" />'
                    f'<meta name="citation_author_institution" content="{AFF}" />' for last, first in names)
    return (f'<html><head><meta name="citation_title" content="A title" />{publisher}'
            f'<meta name="citation_doi" content="10.14712/18059694.2016.36" />{metas}</head>'
            f'<body><div id="page" class="page-abstract"><div id="content">'
            f'<h2 id="title">A title</h2>'
            f'<div id="authors" class="abstract-authors">{byline}<p>{AFF}<br /></p>'
            f'<p><em>Received March 14, 2011<br />Accepted August 2, 2011</em></p></div>'
            f'<div id="abstract"><p>Some abstract text.</p></div></div></div></body></html>')


def _authors(html):
    return parse_page(html.encode(), "doi", URL)["authors"]


def _corr(html):
    return [a["name"] for a in _authors(html) if a["is_corresponding"]]


ONE_MAIL = 'Anna Alpha, <a href="mailto:boris@example.com">Boris Beta</a>, Greta Gamma'


def test_mailto_linked_author_is_corresponding():
    authors = _authors(_page(ONE_MAIL))
    assert [a["is_corresponding"] for a in authors] == [False, True, False]


def test_affiliations_kept_from_meta_tags():
    authors = _authors(_page(ONE_MAIL))
    assert [len(a["affiliations"]) for a in authors] == [1, 1, 1]
    assert authors[0]["affiliations"][0]["name"] == AFF


def test_numbered_byline_with_superscripts():
    byline = ('Anna Alpha <sup>1</sup>, Boris Beta <sup>1,2</sup>, '
              '<a href="mailto:greta@example.com">Greta Gamma</a> <sup>1</sup>')
    assert _corr(_page(byline)) == ["Gamma, Greta"]


def test_no_mailto_marks_no_one():
    assert _corr(_page("Anna Alpha, Boris Beta, Greta Gamma")) == []


def test_every_author_with_a_mailto_marks_no_one():
    byline = ", ".join(f'<a href="mailto:{f.lower()}@example.com">{f} {l}</a>' for l, f in NAMES)
    assert _corr(_page(byline)) == []


def test_mailto_name_matching_no_author_marks_no_one():
    byline = 'Anna Alpha, Boris Beta, Greta Gamma, <a href="mailto:x@example.com">Editorial Office</a>'
    assert _corr(_page(byline)) == []


def test_same_markup_from_another_publisher_is_not_claimed():
    other = '<meta name="citation_publisher" content="Institute of Physiology, Czech Academy of Sciences" />'
    html = _page(ONE_MAIL, publisher=other)
    assert not CuniMedicalJournals(BeautifulSoup(html, "lxml")).is_publisher_specific_parser()
    assert _corr(html) == []


def test_karolinum_press_journal_page_is_not_claimed():
    # karolinum.cz's own journal pages (the AUC series) carry no citation_publisher tag and no abstract-authors block
    html = ('<html><head><meta name="citation_title" content="A title" />'
            '<meta name="citation_author" content="Alpha, Anna" /></head><body><main><article class="detail">'
            '<div class="casopis__clanek"><h1>A title</h1><p>Anna Alpha</p></div></article></main></body></html>')
    parser = CuniMedicalJournals(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_two_mailto_names_of_three_are_both_marked():
    byline = ('<a href="mailto:anna@example.com">Anna Alpha</a>, Boris Beta, '
              '<a href="mailto:greta@example.com">Greta Gamma</a>')
    assert _corr(_page(byline)) == ["Alpha, Anna", "Gamma, Greta"]


def test_single_author_with_a_mailto_is_not_marked():
    byline = '<a href="mailto:anna@example.com">Anna Alpha</a>'
    assert _corr(_page(byline, names=NAMES[:1])) == []
