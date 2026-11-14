"""Corresponding authors on Copernicus (copernicus.org) journal pages (oxjob #2218).

Markup is cut down from stored pages sampled 13 Nov 2026 (#2218 EXPLORE § 1). The current template opens a pop-up per
byline author; the corresponding author's pop-up header reads "CORRESPONDING AUTHOR". Those pages go to the meta-tag
parser, which marked no one, or only the author its e-mail tag pairs with. The older template (byline in
``span.authors-full``) states "Correspondence: Name (e-mail)" under the affiliations; its parser marked every author
with an ORCID logo instead.
"""
from bs4 import BeautifulSoup

import parseland_lib.parse as parse_module
from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.copernicus import copernicus_corresponding_names, _statement_names

_HEAD = '<link rel="preconnect" crossorigin="" href="https://contentmanager.copernicus.org/" />'
URL = "https://acp.copernicus.org/articles/23/10533/2023/"


def _modal(key, name, corresponding, by_class):
    marker = f'class="modal fade {key}"' if by_class else f'class="modal fade" id="{key}"'
    # the real pop-up also holds the e-mail; left out so the Open Journal Systems lone-e-mail rule stays out of these
    mark = '<div class="row no-gutters"><div class="col-12">CORRESPONDING AUTHOR</div></div>' if corresponding else ""
    return (f'<div {marker} tabindex="-1"><div class="modal-dialog"><div class="modal-content"><div class="modal-header">'
            f'<div class="container-fluid p-0"><h3 class="modal-title">{name}</h3>{mark}</div></div>'
            f'<div class="modal-body"><div class="col-12 mb-3">Some University, Somewhere</div></div></div></div></div>')


def _current(authors, by_class=False, head=_HEAD, emails=()):
    """authors: [(first last, "Last, First", corresponding)]"""
    metas = "".join(f'<meta name="citation_author" content="{inv}"/>' +
                    "".join(f'<meta name="citation_author_email" content="{e}">' for e in emails if e[0] == inv[0].lower())
                    for _, inv, _ in authors)
    byline, modals = [], []
    for i, (name, _, corr) in enumerate(authors):
        key = f"author{900 + i}"
        target = f".{key}" if by_class else f"#{key}"
        byline.append(f'<nobr><span class="hover-cursor-pointer" data-toggle="modal" data-target="{target}">{name}</span>,</nobr>')
        modals.append(_modal(key, name, corr, by_class))
    return (f'<html><head>{head}<meta name="citation_title" content="A paper"/>{metas}</head><body>'
            f'<div class="mb-3 authors-with-affiliations">{" ".join(byline)}</div>{"".join(modals)}</body></html>')


THREE = [("Herizo Narivelo", "Narivelo, Herizo", False), ("Paul David Hamer", "Hamer, Paul David", True),
         ("Virginie Marécal", "Marécal, Virginie", False)]


def _marked(html, url=URL):
    return [a["name"] for a in parse_page(html.encode(), "doi", url)["authors"] if a["is_corresponding"]]


def test_pop_up_marks_the_corresponding_author():
    html = _current(THREE)
    assert copernicus_corresponding_names(BeautifulSoup(html, "lxml")) == ["Paul David Hamer"]
    authors = parse_page(html.encode(), "doi", URL)["authors"]
    assert [a["name"] for a in authors if a["is_corresponding"]] == ["Hamer, Paul David"]
    assert len(authors) == 3 and all(a["is_corresponding"] is not None for a in authors)


def test_pop_up_linked_by_class_on_newer_pages():
    assert _marked(_current(THREE, by_class=True)) == ["Hamer, Paul David"]


def test_page_marks_replace_an_e_mail_tag_guess():
    two = [("Peter Kalverla", "Kalverla, Peter", True), ("Ruud J. van der Ent", "van der Ent, Ruud J.", True),
           ("Anna Smith", "Smith, Anna", False)]
    html = _current(two, emails=["k@example.org"])
    assert _marked(html) == ["Kalverla, Peter", "van der Ent, Ruud J."]


def test_no_pop_up_mark_no_one_marked():
    html = _current([(n, inv, False) for n, inv, _ in THREE])
    assert copernicus_corresponding_names(BeautifulSoup(html, "lxml")) == []
    assert _marked(html) == []


def _reader_must_not_run(*_):
    raise AssertionError("the Copernicus reader ran")


def test_comment_doi_page_takes_no_marks(monkeypatch):
    # a referee or author comment's DOI resolves to the discussed preprint's page: the pop-up is the preprint's
    monkeypatch.setattr(parse_module, "copernicus_corresponding_names", _reader_must_not_run)
    url = "https://egusphere.copernicus.org/preprints/2025/egusphere-2025-3710/#AC1"
    assert "Hamer, Paul David" not in _marked(_current(THREE), url)


def test_look_alike_page_from_another_site_is_not_claimed(monkeypatch):
    html = _current(THREE, head='<link rel="preconnect" href="https://cdn.example.org/" />')
    assert copernicus_corresponding_names(BeautifulSoup(html, "lxml")) == []
    monkeypatch.setattr(parse_module, "copernicus_corresponding_names", _reader_must_not_run)
    parse_page(html.encode(), "doi", URL)


ORCID = ('<a class="orcid-authors-logo" target="_blank" href="https://orcid.org/0000-0002-5957-2201">'
         '<svg><image xlink:href="orcid_icon.svg"></image></svg></a>')


def _old(statement):
    byline = (f'<nobr>Liji M. David{ORCID}<sup>1</sup>,</nobr> <nobr>Mary Barth<sup>2</sup>,</nobr> '
              f'<nobr>Lena Höglund-Isaksson{ORCID}<sup>1</sup>,</nobr> <nobr>and A. R. Ravishankara<sup>2</sup></nobr>')
    # real pages print the statement twice (under the affiliations, and again for desktop)
    note = "".join(f'<p class="correspondence-statement{cls}"><strong>Correspondence</strong>: {statement}</p>'
                   for cls in ("", " hide-on-mobile")) if statement else ""
    return (f'<html><head>{_HEAD}<meta name="citation_title" content="A paper"/></head><body>'
            f'<span class="authors-full" style="display: none">{byline}</span>'
            f'<ul class="affiliation-list"><li><sup>1</sup><span>Utah State University, Logan, UT, USA</span></li>'
            f'<li><sup>2</sup><span>NCAR, Boulder, CO, USA</span></li></ul>{note}</body></html>')


def test_old_template_reads_the_statement_not_orcid_logos():
    html = _old("Liji M. David (liji.david@usu.edu), Mary Barth (barthm@ucar.edu), and "
                "A. R. Ravishankara (a.r.ravishankara@colostate.edu)")
    authors = parse_page(html.encode(), "doi", URL)["authors"]
    assert [a["name"] for a in authors] == ["Liji M. David", "Mary Barth", "Lena Höglund-Isaksson", "A. R. Ravishankara"]
    assert [a["name"] for a in authors if a["is_corresponding"]] == ["Liji M. David", "Mary Barth", "A. R. Ravishankara"]
    assert authors[2]["is_corresponding"] is False
    assert authors[0]["affiliations"] == [{"name": "Utah State University, Logan, UT, USA"}]


def test_old_template_orcid_logo_alone_is_not_a_mark():
    authors = parse_page(_old(None).encode(), "doi", URL)["authors"]
    assert len(authors) == 4 and not any(a["is_corresponding"] for a in authors)


def test_statement_names():
    assert _statement_names("Correspondence : Xingqi Liu (xqliu@cnu.edu.cn)") == ["Xingqi Liu"]
    assert _statement_names("Correspondence: A. Laeng (alexandra.laeng@kit.edu) and J. Doe (j@x.org)") == \
        ["A. Laeng", "J. Doe"]
    assert _statement_names("Correspondence: Maria Sand") == ["Maria Sand"]
