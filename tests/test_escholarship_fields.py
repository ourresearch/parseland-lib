"""eScholarship item pages (escholarship.org/uc/item/..., University of California), oxjob #2338.

Markup is cut down from stored item pages. The page's citation_author tags carry the byline, and the generic parser
read them, but no tag carries an affiliation: each author's institution is only in the page state the site embeds for
its React app (<script>window.jscholApp_initialPageData = {...}</script>, "authors": [{"name", "institution"}]).
label-v1 takes the affiliation from there. The state's e-mail is the depositor's contact, not a corresponding-author
mark, and its "abstract" holds placeholders ("[No abstract]", "Poem") the meta tags leave out, so authors, marks and
abstract stay as the generic parser reads them. The sidebar's related items carry other works' authors.
"""
import json

from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.escholarship import EScholarship

URL = "https://escholarship.org/uc/item/463199zs"
CANONICAL = '<link rel="canonical" href="https://escholarship.org/uc/item/463199zs"/>'
ABSTRACT = ("Sinonasal carcinoma is a rare malignancy that often presents with nonspecific symptoms, making early "
            "diagnosis challenging. Delayed recognition can lead to disease progression and worse outcomes. This case "
            "report emphasizes the importance of early identification, prompt imaging, and management.")


def _state(authors, abstract="", sidebar=None):
    return {"attrs": {"doi": "10.5070/M5.52257", "abstract": abstract}, "authors": authors,
            "sidebar": sidebar or [], "id": "463199zs", "pdf_url": "/content/qt463199zs/qt463199zs.pdf"}


def _page(names, state, canonical=CANONICAL, abstract=ABSTRACT):
    metas = "".join(f'<meta name="citation_author" content="{n}"/>' for n in names)
    abs_tag = f'<meta id="meta-abstract" name="citation_abstract" content="{abstract}"/>' if abstract else ""
    # the site prints its head tags inside <div class="react-head-temp"> in <head>; lxml moves them into <body>
    return ('<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/><div class="react-head-temp">'
            f'<title>A title</title><meta property="citation_title" content="A title"/>{metas}{abs_tag}'
            f'<meta name="citation_doi" content="10.5070/M5.52257"/>{canonical}</div></head>'
            '<body><div id="main"><main id="maincontent"><h2 class="c-tabcontent__main-heading">Main Content</h2>'
            '</main></div><script>window.jscholApp_initialPageData = ' + json.dumps(state) + ';</script></body></html>')


def _authors(html):
    out = parse_page(html.encode(), "doi", URL)
    return [(a["name"], [x["name"] for x in a["affiliations"]], a["is_corresponding"]) for a in out["authors"]]


NAMES = ["Usuga, Daniela", "Osunjima, Ayomide", "Danko, Colin"]
UTSW = "University of Texas Southwestern Medical Center"


def test_institutions_from_page_state_become_affiliations():
    state = _state([{"name": NAMES[0], "email": "d.u@example.edu", "institution": UTSW},
                    {"name": NAMES[1], "institution": UTSW}, {"name": NAMES[2]}])
    got = _authors(_page(NAMES, state))
    assert [(n, a) for n, a, _ in got] == [(NAMES[0], [UTSW]), (NAMES[1], [UTSW]), (NAMES[2], [])]


def test_email_in_page_state_marks_no_one():
    state = _state([{"name": NAMES[0], "email": "d.u@example.edu", "institution": UTSW}])
    assert not any(c for _, _, c in _authors(_page(NAMES[:1], state)))


def test_several_institutions_split_and_address_lines_kept():
    inst = ("California Poison Control System, Valley Children's Hospital, Madera, California\n"
            "University of California San Francisco, Fresno Medical Education Program, Fresno, California")
    inst2 = ("Delta Stewardship Council, Delta Science Program\nSacramento, CA 95814 USA\n\n"
             "California State Water Resources Control Board\nSacramento, CA 95814 USA")
    inst3 = "Loyola University Medical Center, Maywood, Illinois; Stritch School of Medicine, Maywood, Illinois"
    state = _state([{"name": "A, B", "institution": inst}, {"name": "C, D", "institution": inst2},
                    {"name": "E, F", "institution": inst3}])
    got = {n: a for n, a, _ in _authors(_page(["A, B", "C, D", "E, F"], state))}
    assert got["A, B"] == ["California Poison Control System, Valley Children's Hospital, Madera, California",
                           "University of California San Francisco, Fresno Medical Education Program, Fresno, California"]
    assert got["C, D"] == ["Delta Stewardship Council, Delta Science Program, Sacramento, CA 95814 USA",
                           "California State Water Resources Control Board, Sacramento, CA 95814 USA"]
    assert got["E, F"] == ["Loyola University Medical Center, Maywood, Illinois",
                           "Stritch School of Medicine, Maywood, Illinois"]


def test_abstract_stays_the_meta_tags_and_a_placeholder_is_never_one():
    state = _state([{"name": NAMES[0], "institution": UTSW}], abstract="<p>" + ABSTRACT + "</p>")
    assert parse_page(_page(NAMES[:1], state).encode(), "doi", URL)["abstract"] == ABSTRACT
    state = _state([{"name": NAMES[0], "institution": UTSW}], abstract="[No abstract]")
    assert parse_page(_page(NAMES[:1], state, abstract="").encode(), "doi", URL)["abstract"] is None


def test_sidebar_authors_are_never_the_pages():
    sidebar = [{"id": 1, "kind": "RecentArticles", "attrs": {"items": [
        {"id": "qt08t3x488", "authors": [{"name": NAMES[0], "institution": "Medical College of Wisconsin"}]}]}}]
    state = _state([{"name": NAMES[0]}], sidebar=sidebar)
    assert _authors(_page(NAMES[:1], state)) == [(NAMES[0], [], None)]


def test_names_that_do_not_line_up_are_matched_by_name():
    state = _state([{"name": NAMES[1], "institution": "Rice University"}, {"name": "Someone, Else", "institution": "X U"}])
    got = _authors(_page(NAMES[:2], state))
    assert [(n, a) for n, a, _ in got] == [(NAMES[0], []), (NAMES[1], ["Rice University"])]


def test_parse_returns_no_back_matter_keys():
    state = _state([{"name": NAMES[0], "institution": UTSW}])
    parsed = EScholarship(BeautifulSoup(_page(NAMES[:1], state), "lxml")).parse()
    assert set(parsed) == {"authors", "abstract"}


def test_look_alike_page_from_another_site_is_not_claimed():
    other = '<link rel="canonical" href="https://journals.example.org/article/view/12"/>'
    state = _state([{"name": NAMES[0], "institution": UTSW}])
    html = _page(NAMES[:1], state, canonical=other)
    parser = EScholarship(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser() and not parser.authors_found()
    assert _authors(html) == [(NAMES[0], [], None)]


def test_canonical_link_in_head_is_claimed_too():
    state = _state([{"name": NAMES[0], "institution": UTSW}])
    html = _page(NAMES[:1], state).replace('<div class="react-head-temp">', "").replace("</div></head>", "</head>")
    assert EScholarship(BeautifulSoup(html, "lxml")).is_publisher_specific_parser()
    assert _authors(html) == [(NAMES[0], [UTSW], None)]


def test_item_page_without_page_state_is_left_to_the_generic_parser():
    html = (f'<html><head><meta name="citation_author" content="{NAMES[0]}"/>{CANONICAL}</head>'
            '<body><main id="maincontent"></main></body></html>')
    assert not EScholarship(BeautifulSoup(html, "lxml")).authors_found()
