"""Corresponding authors on EDP Sciences' Vision4Press pages (oxjob #2330).

Markup is cut down from stored pages of E3S, MATEC, ITM, EPJ, BIO and SHS Web of Conferences, EPJ Applied Physics,
A&A and médecine/sciences (17 Nov 2026). The byline puts each author in a span.author followed by superscripts: the
affiliation number and then the note's mark ("1", "*", "a"); p.corresp explains each mark on its own line. label-v1
counts a mark the note calls a corresponding author or ties to that author's e-mail; an e-mail for every author, a
"Corresponding author: <e-mail>" note no byline mark points to, and a mark explained as something else are not marks.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.edp_sciences import EDPSciences

URL = "https://doi.org/10.1051/e3sconf/202300000001"


def _page(names, byline, corresp="", aff="", publisher="EDP Sciences"):
    metas = "".join(f'<meta name="citation_author" content="{n}"/>'
                    f'<meta name="citation_author_institution" content="Some University, City, Country"/>' for n in names)
    return (f'<html><head><meta name="citation_publisher" content="{publisher}"/>{metas}'
            f'<meta name="citation_title" content="A title"/><meta name="citation_doi" content="10.1051/e3sconf/202300000001"/>'
            f'</head><body><div id="head"><h2 class="title">A title</h2>'
            f'<div class="article-authors"><p class="bold">{byline}</p></div>'
            f'<p class="aff">{aff or "Some University, City, Country"}</p>'
            f'<p class="corresp">{corresp}</p>'
            f'<p class="bold"><a name="abs"></a>Abstract</p><p>The abstract of this paper, one paragraph long.</p>'
            f'</div></body></html>')


def _span(name, n=1):
    return f'<span id="x-author-{n}" class="author" data-url="/component/author/?n={n}">{name}</span>'


def _corr(html):
    return [a["name"] for a in parse_page(html.encode(), "doi", URL)["authors"] if a["is_corresponding"]]


TWO = ["Viktor Zheltukhin", "Violetta Chebakova"]


def test_star_after_the_affiliation_number_is_marked():
    byline = f"{_span(TWO[0], 1)}<sup>1</sup> and {_span(TWO[1], 2)}<sup>2</sup><sup>*</sup>"
    corresp = '<sup>*</sup>  Corresponding author: <a href="mailto:v@example.ru">v@example.ru</a><br/>'
    assert _corr(_page(TWO, byline, corresp, aff="<sup>1</sup> Univ A<br/><sup>2</sup> Univ B<br/>")) == [TWO[1]]


def test_star_right_after_the_name_is_marked():
    byline = f"{_span(TWO[0], 1)}<sup>*</sup> and {_span(TWO[1], 2)}"
    corresp = '<sup>*</sup> Corresponding author: <a href="mailto:v@example.ru">v@example.ru</a><br/>'
    assert _corr(_page(TWO, byline, corresp)) == [TWO[0]]


def test_two_letter_marks_mark_both_authors():
    names = ["Steven Wells", "Alice Robson", "Robert J. Moore"]
    byline = f"{_span(names[0], 1)}<sup>a</sup>, {_span(names[1], 2)}, {_span(names[2], 3)}<sup>b</sup>"
    corresp = ('<sup>a</sup> Corresponding author: <a href="mailto:s@example.uk">s@example.uk</a><br/>'
               '<sup>b</sup> Corresponding author: <a href="mailto:r@example.uk">r@example.uk</a><br/>')
    assert _corr(_page(names, byline, corresp)) == [names[0], names[2]]


def test_note_naming_the_author_without_a_mark():
    names = ["P. Reig", "I. Papadakis", "N. D. Kylafis"]
    byline = f"{_span(names[0], 1)}<sup>1</sup><sup>,2</sup>, {_span(names[1], 2)}<sup>1</sup> and {_span(names[2], 3)}<sup>1</sup>"
    corresp = 'Corresponding author: P. Reig, <a href="mailto:p@example.gr">p@example.gr</a> '
    assert _corr(_page(names, byline, corresp, aff="<sup>1</sup> Univ A<br/><sup>2</sup> Univ B<br/>")) == ["P. Reig"]


def test_e_mail_tied_to_one_author_is_marked():
    names = ["Jean Rosenbaum", "Nicolas Bourdel", "Saadi Khochbin"]
    byline = f"{_span(names[0], 1)}<sup>1</sup><sup>*</sup>, {_span(names[1], 2)}<sup>2</sup> et {_span(names[2], 3)}<sup>3</sup>"
    corresp = ' <sup>*</sup> <a href="mailto:j@example.fr">j@example.fr</a> <br/>'
    assert _corr(_page(names, byline, corresp, aff="<sup>1</sup> A<br/><sup>2</sup> B<br/><sup>3</sup> C<br/>")) == [names[0]]


def test_an_e_mail_for_every_author_marks_no_one():
    byline = f"{_span(TWO[0], 1)}<sup>1</sup><sup>*</sup> and {_span(TWO[1], 2)}<sup>2</sup><sup>**</sup>"
    corresp = ('<sup>*</sup> E-mail: <a href="mailto:a@example.nl">a@example.nl</a><br/>'
               '<sup>**</sup> E-mail: <a href="mailto:b@example.nl">b@example.nl</a> <br/>')
    assert _corr(_page(TWO, byline, corresp, aff="<sup>1</sup> A<br/><sup>2</sup> B<br/>")) == []


def test_a_star_explained_as_something_else_is_not_a_mark():
    names = ["W. Burkart"]
    byline = f"{_span(names[0], 1)}<sup>*</sup><sup>,†</sup>"
    corresp = ('<sup>*</sup> IAEA former Deputy Director General.<br/>'
               '<sup>†</sup> E-mail: <a href="mailto:w@example.at">w@example.at</a><br/>')
    assert _corr(_page(names, byline, corresp)) == []


def test_a_note_no_byline_mark_points_to_marks_no_one():
    names = ["Maxim Sergievskiy", "Ksenia Kirpichnikova"]
    byline = f"{_span(names[0], 1)} and {_span(names[1], 2)}"
    corresp = ' <sup>*</sup> Corresponding author: <a href="mailto:s@example.ru">s@example.ru</a> <br/>'
    assert _corr(_page(names, byline, corresp)) == []


def test_a_bare_star_with_no_note_is_not_a_mark():
    byline = f"{_span(TWO[0], 1)}<sup>*</sup> and {_span(TWO[1], 2)}"
    assert _corr(_page(TWO, byline)) == []


def test_a_mark_that_also_numbers_an_affiliation_is_not_read():
    byline = f"{_span(TWO[0], 1)}<sup>1</sup> and {_span(TWO[1], 2)}<sup>2</sup>"
    corresp = '<sup>1</sup> Corresponding author: <a href="mailto:v@example.ru">v@example.ru</a><br/>'
    assert _corr(_page(TWO, byline, corresp, aff="<sup>1</sup> Univ A<br/><sup>2</sup> Univ B<br/>")) == []


def test_a_number_mark_with_no_numbered_affiliations_is_read():
    names = ["Oleg Muratovich Epkhiev", "Anatolii Sergeevich Kislyakov"]
    byline = f"{_span(names[0], 1)}<sup>1</sup> and {_span(names[1], 2)}"
    corresp = '<sup>1</sup> Corresponding author: <a href="mailto:o@example.ru">o@example.ru</a><br/>'
    assert _corr(_page(names, byline, corresp)) == [names[0]]


def test_authors_affiliations_and_abstract_still_read():
    byline = f"{_span(TWO[0], 1)}<sup>1</sup> and {_span(TWO[1], 2)}<sup>2</sup><sup>*</sup>"
    out = parse_page(_page(TWO, byline, '<sup>*</sup> Corresponding author: v@example.ru').encode(), "doi", URL)
    assert [a["name"] for a in out["authors"]] == TWO
    assert all(a["affiliations"] for a in out["authors"])
    assert out["abstract"] == "The abstract of this paper, one paragraph long."


def test_a_sister_imprint_is_claimed():
    html = _page(TWO, f"{_span(TWO[0], 1)} and {_span(TWO[1], 2)}", publisher="Éditions EDK, Groupe EDP Sciences")
    assert EDPSciences(BeautifulSoup(html, "lxml")).is_publisher_specific_parser()


def test_a_look_alike_page_from_another_publisher_is_not_claimed():
    byline = f"{_span(TWO[0], 1)}<sup>1</sup> and {_span(TWO[1], 2)}<sup>2</sup><sup>*</sup>"
    html = _page(TWO, byline, '<sup>*</sup> Corresponding author: v@example.ru', publisher="Other Science Press")
    parser = EDPSciences(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
