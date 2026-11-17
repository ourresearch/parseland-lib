"""University of Szczecin Press journals (wnus.usz.edu.pl, wnus.edu.pl; DOI prefix 10.18276), oxjob #2339.

Markup cut down from stored pages of the publisher's own journal system (17 Nov 2026). Its citation_* tags carry the
byline and affiliations and the generic parser reads them; the site parser adds the reference list the page prints in
its "Bibliografia" / "Bibliography" panel and leaves the other fields as the generic parser reads them.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.usz_edu_pl import UniversityOfSzczecinPress

URL = "https://doi.org/10.18276/sip.2017.48/3-29"
HOME = "https://wnus.usz.edu.pl/sip/pl/issue/367/article/6181/"

ENTRIES = [
    "Benassi, M., Greve, A., Harkola, J. (1999). Looking for a Network Organization: The Case of GESTO. Journal of "
    "Market Focused Management, 4 (3), 205–229.",
    "Fołtyn, H. (2007). Klasyczne i nowoczesne struktury organizacyjne. Warszawa: Wydawnictwo Key Text.",
    "Janicki, T., Popławski, W., Słupska, U. (2015). The Concept and the Level of Virtualization in Contemporary "
    "Companies. Social Sciences, 90 (4), 19–31. DOI: 10.5755/j01.ss.90.4.14248.",
]


def _head(home=HOME):
    return ('<head><meta name="author" content="Kamil Sawicki contact@sawicki.uk">'
            '<meta name="DC.Description" xml:lang="pl" content="W artykule poruszono kwestię ewolucji struktur '
            'organizacyjnych, zaczynając od opisu struktur klasycznych, przechodząc przez struktury projektowe."/>'
            '<meta name="DC.Description" xml:lang="en" content="The article deals with the evolution of organizational '
            'structures, starting from the description of classical structures, the structure of the project."/>'
            '<meta name="citation_author" content="Tomasz Janicki"/>'
            '<meta name="citation_author_institution" content="Wyższa Szkoła Bankowa w Toruniu"/>'
            '<meta name="citation_author" content="Urszula Słupska"/>'
            '<meta name="citation_author_institution" content="Kujawsko-Pomorska Szkoła Wyższa w Bydgoszczy"/>'
            '<meta name="citation_title" content="Kształtowanie struktur organizacyjnych"/>'
            '<meta name="citation_doi" content="10.18276/sip.2017.48/3-29"/>'
            f'<meta name="citation_abstract_html_url" content="{home}"/></head>')


def _references_panel(entries=ENTRIES, numbers=None, title="Bibliografia"):
    numbers = numbers or [f"{i}." for i in range(1, len(entries) + 1)]
    rows = "".join(f'<tr><td>{n}</td><td class="td-wrap">{e}</td></tr>' for n, e in zip(numbers, entries))
    return (f'<div class="panel panel-default"><div class="panel-heading"><h3 class="panel-title"><strong>{title}'
            '</strong></h3></div><div class="table-responsive"><table class="table table-bordered table-hover">'
            f'{rows}</table></div></div>')


BODY_START = ('<div class="panel panel-default"><div class="panel-heading"><h3 class="panel-title">'
              '<strong itemprop="headline">Kształtowanie struktur organizacyjnych</strong></h3></div>'
              '<table class="table table-bordered table-hover"><tr><td>Autorzy:</td><td><strong>Tomasz Janicki</strong>'
              '<br>Wyższa Szkoła Bankowa w Toruniu<br><br><strong>Urszula Słupska</strong><br>Kujawsko-Pomorska Szkoła '
              'Wyższa w Bydgoszczy</td></tr></table></div>'
              '<div class="panel panel-default"><div class="panel-heading"><h3 class="panel-title"><strong>Abstrakt'
              '</strong></h3></div><div class="panel-body">W artykule poruszono kwestię ewolucji struktur '
              'organizacyjnych, zaczynając od opisu struktur klasycznych, przechodząc przez struktury projektowe.'
              '</div></div>'
              '<div id="cited-by-crossref-text" class="panel panel-default" style="display:none;">'
              '<div class="panel-heading"><h3 class="panel-title"><strong>Cited-by (Crossref)</strong></h3></div>'
              '<div class="table-responsive"><table class="table table-bordered table-hover"><tr><td></td></tr>'
              '</table></div></div>')


def _page(panel=None, home=HOME):
    return f"<html>{_head(home)}<body>{BODY_START}{panel if panel is not None else _references_panel()}</body></html>"


def _parser(html):
    return UniversityOfSzczecinPress(BeautifulSoup(html, parser="lxml", features="lxml"))


def test_reads_the_whole_numbered_reference_list():
    parsed = _parser(_page()).parse()
    assert [r["raw"] for r in parsed["references"]] == ENTRIES
    assert [r["position"] for r in parsed["references"]] == [1, 2, 3]
    assert [r["doi"] for r in parsed["references"]] == [None, None, "10.5755/j01.ss.90.4.14248"]
    assert parsed["references_complete"] is True


def test_english_and_german_list_titles():
    for title in ("Bibliography", "Bibliographie"):
        parsed = _parser(_page(_references_panel(title=title))).parse()
        assert len(parsed["references"]) == 3 and parsed["references_complete"] is True


def test_list_with_a_gap_in_its_numbers_is_not_whole():
    parsed = _parser(_page(_references_panel(numbers=["1.", "2.", "4."]))).parse()
    assert len(parsed["references"]) == 3
    assert parsed["references_complete"] is False


def test_no_acknowledgments_or_funding_on_these_pages():
    parsed = _parser(_page()).parse()
    assert parsed["acknowledgments"] is None and parsed["funding_statement"] is None


def test_byline_and_abstract_stay_the_generic_parsers():
    html = _page()
    out = parse_page(html.encode(), "doi", URL)
    assert [a["name"] for a in out["authors"]] == ["Tomasz Janicki", "Urszula Słupska"]
    assert [[x["name"] for x in a["affiliations"]] for a in out["authors"]] == [
        ["Wyższa Szkoła Bankowa w Toruniu"], ["Kujawsko-Pomorska Szkoła Wyższa w Bydgoszczy"]]
    assert not any(a["is_corresponding"] for a in out["authors"])
    # the same page on a host the site parser doesn't take: only the generic parser reads it
    generic = parse_page(_page(home="https://journals.example.edu.pl/sip/pl/issue/367/article/6181/").encode(), "doi", URL)
    assert out["authors"] == generic["authors"] and out["abstract"] == generic["abstract"]
    assert out["abstract"] and generic["references"] is None


def test_parse_page_returns_the_reference_list():
    out = parse_page(_page().encode(), "doi", URL)
    assert [r["raw"] for r in out["references"]] == ENTRIES
    assert out["references_complete"] is True


def test_older_host_is_claimed_too():
    assert _parser(_page(home="https://wnus.edu.pl/nk/pl/issue/42/article/571/")).authors_found()


def test_page_without_a_reference_list_is_left_to_the_generic_parser():
    assert not _parser(_page(panel="")).authors_found()


def test_look_alike_page_from_another_site_is_not_claimed():
    # the same panels and citation_* tags, on another publisher's host, and an Open Journal Systems page
    other = _page(home="https://journals.example.edu.pl/sip/pl/issue/367/article/6181/")
    assert not _parser(other).is_publisher_specific_parser() and not _parser(other).authors_found()
    ojs = ('<html><head><meta name="generator" content="Open Journal Systems 3.3.0.10"/>'
           '<meta name="citation_author" content="A Name"/>'
           '<meta name="citation_abstract_html_url" content="https://czasopisma.example.pl/index.php/j/article/view/1"/>'
           f'</head><body>{_references_panel()}</body></html>')
    assert not _parser(ojs).authors_found()


def test_entry_split_over_two_numbered_rows_is_not_whole():
    entries = ["1. Dudka K. (red.). Kodeks postępowania karnego. Komentarz, wyd. III, LEX 2023,",
               "https://sip.lex.pl/#/commentary/587774957/741737/dudka-katarzyna-red-kodeks",
               "2. Golik C., Funkcja gwarancyjna instytucji przedstawienia zarzutów, WPP 2021, nr 2."]
    parsed = _parser(_page(_references_panel(entries=entries))).parse()
    assert len(parsed["references"]) == 3
    assert parsed["references_complete"] is False
