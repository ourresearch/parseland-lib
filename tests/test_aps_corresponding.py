"""Corresponding authors on APS's older article template from the notes under the affiliations (oxjob #2146).

Markup is cut down from stored journals.aps.org pages sampled 10 Nov 2026 (#2146 EXPLORE § 1). The byline marks the
corresponding author with a symbol (<sup>1,*</sup>) whose note in ul.contrib-notes reads "Corresponding author: x@y",
"Contact author: x@y" or, in APS's older style, only that author's e-mail ("x@y"; gold v1.3 physrevlett.108.183001).
The APS parser read the byline but never the notes, so ~21% of these pages whose work showed no corresponding author
had one on the page.
"""
from parseland_lib.parse import parse_page

OG = '<meta content="https://journals.aps.org/pre/abstract/10.1103/PhysRevE.92.033108" property="og:url" />'


def _page(byline, affs, notes):
    aff_li = "".join(f"<li><sup>{i}</sup>{a}</li>" for i, a in enumerate(affs, 1))
    note_li = "".join(f'<li id="n{i}"><sup>{s}</sup>{t}</li>' for i, (s, t) in enumerate(notes, 1))
    return (f'<html><head>{OG}</head><body><section class="article authors open"><h4 class="title">Authors</h4>'
            f'<div class="content"><p>{byline}</p><ul class="no-bullet">{aff_li}</ul>'
            f'<ul class="no-bullet contrib-notes">{note_li}</ul></div></section></body></html>')


def _a(name, sup):
    return f'<a href="/search/field/author/{name}">{name}</a><sup>{sup}</sup>'


def _parse(html):
    return parse_page(html.encode(), "doi", "https://doi.org/10.1103/PhysRevE.92.033108")["authors"]


def _corr(html):
    return [a["name"] for a in _parse(html) if a["is_corresponding"]]


def test_corresponding_author_note_wins_over_email_notes():
    html = _page(", ".join([_a("P. Palmeri", "1,*"), _a("G. Boutoux", "2,†"), _a("D. Batani", "2,‡")])
                 + ", and " + _a("P. Quinet", "1,3,§"),
                 ["Université de Mons", "Univ. de Bordeaux", "Université de Liège"],
                 [("*", "Corresponding author: patrick.palmeri@umons.ac.be"), ("†", "boutoux@celia.u-bordeaux1.fr"),
                  ("‡", "batani@celia.u-bordeaux1.fr"), ("§", "pascal.quinet@umons.ac.be")])
    authors = _parse(html)
    assert [a["name"] for a in authors if a["is_corresponding"]] == ["P. Palmeri"]
    assert [a["is_corresponding"] for a in authors] == [True, False, False, False]
    assert authors[0]["affiliations"] == [{"name": "Université de Mons"}]  # the * mark is no affiliation id


def test_email_only_note_marks_its_author():
    html = _page(", ".join([_a("J. Wu", "1,2"), _a("L. Ph. H. Schmidt", "1")]) + ", and " + _a("R. Dörner", "1,*"),
                 ["Goethe Universität", "East China Normal University"],
                 [("*", "doerner@atom.uni-frankfurt.de")])
    assert _corr(html) == ["R. Dörner"]


def test_two_email_notes_mark_two_authors_but_not_present_address():
    html = _page(", ".join([_a("E. E. Peters", "1,*"), _a("A. Chakraborty", "2,†"), _a("S. W. Yates", "1,∥")]),
                 ["University of Kentucky", "Visva-Bharati"],
                 [("*", "fe.peters@uky.edu"), ("†", "Present address: Department of Physics, Visva-Bharati."),
                  ("∥", "yates@uky.edu")])
    assert _corr(html) == ["E. E. Peters", "S. W. Yates"]


def test_contact_author_note():
    html = _page(_a("V. Zimmermann", "1,*") + " and " + _a("A. Leija", "2,†"), ["UCF", "SLU"],
                 [("*", "Contact author: vinzenz.zimmermann@ucf.edu"), ("†", "Contact author: armando.leija@slu.edu")])
    assert _corr(html) == ["V. Zimmermann", "A. Leija"]


def test_email_for_every_author_is_no_mark():
    html = _page(_a("A. One", "1,*") + " and " + _a("B. Two", "1,†"), ["Somewhere"],
                 [("*", "one@x.org"), ("†", "two@x.org")])
    assert _corr(html) == []


def test_no_notes_no_mark():
    html = _page(_a("A. One", "1") + " and " + _a("B. Two", "1"), ["Somewhere"], [])
    assert _corr(html) == []


def test_unmarked_author_does_not_take_the_next_authors_mark_and_orcid_icon_is_skipped():
    orcid = '<a href="https://orcid.org/0000-0001-8782-195X"><span class="orcid-id-icon"></span></a>'
    byline = (_a("Xuanyu Liu", "1,*") + ", " + '<a href="/search/field/author/Wange%20Song">Wange Song</a>' + orcid
              + "<sup>1,†</sup>, " + '<a href="/search/field/author/Jiacheng%20Sun">Jiacheng Sun</a>, and '
              + _a("Tao Li", "1,‡"))
    html = _page(byline, ["Nanjing University"],
                 [("*", "These authors contributed equally to this work."),
                  ("†", "Corresponding author: songwange@nju.edu.cn"), ("‡", "Corresponding author: taoli@nju.edu.cn")])
    assert _corr(html) == ["Wange Song", "Tao Li"]


def test_page_without_affiliation_list_still_gets_the_mark():
    # no affiliation <ul>: the APS parser has no affiliations, so another parser can win the dispatch
    html = (f'<html><head>{OG}<meta name="citation_author" content="Chi-Shung Yip">'
            '<meta name="citation_author_institution" content="University of Wisconsin">'
            '<meta name="citation_author" content="Noah Hershkowitz">'
            '<meta name="citation_author_institution" content="University of Wisconsin"></head><body>'
            '<section class="article authors open"><div class="content"><p>'
            '<a href="/search/field/author/ChiShung%20Yip">Chi-Shung Yip</a> and '
            '<a href="/search/field/author/Noah%20Hershkowitz">Noah Hershkowitz</a><sup>*</sup></p>'
            '<ul class="no-bullet contrib-notes"><li id="n1"><sup>*</sup>hershkowitz@engr.wisc.edu</li></ul>'
            '</div></section></body></html>')
    assert _corr(html) == ["Noah Hershkowitz"]
