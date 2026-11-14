"""American Scientific Publishing Group (americaspg.com) article pages (oxjob #2210).

Markup is cut down from stored americaspg.com pages (13 Nov 2026). The byline is a run of
<span class="font-16"> names whose <sup> carries the affiliation number (and sometimes a bare "*" the page never
explains); the numbered affiliations follow as <li class="font-14"> items ending in " - (e-mail)". The abstract and
the reference list sit in their own "box2" panels; references are Word-pasted paragraphs numbered "[n]".
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.americaspg import AmericasPG

URL = "https://www.americaspg.com/articleinfo/2/show/4038"
PUBLISHER = '<meta name="citation_publisher" content="American Scientific Publishing Group (ASPG)" />'


def _byline(authors):
    spans = "".join(f'<span class="font-16" style="font-weight:bold">{n}<sup>{s}</sup>,</span>' for n, s in authors)
    return f'<p class="font-16">{spans}</p>'


def _affs(affs):
    return "".join(f'<li class="font-14"><span class="left">{i}</span> {a}</li>' for i, a in enumerate(affs, 1))


def _box(heading, body, cls="box2 shadow"):
    return f'<div class="{cls}"><h5 class="green"><b>{heading}</b></h5>{body}</div>'


def _page(authors=(("Ahmad Salim", "1"), ("Omar Muthanna Khudhur", "2 *")),
          affs=("Middle Technical University, Iraq - (ahmad@example.edu.iq)",
                "Department of Computer Engineering Techniques, University of Al Maarif, Al Anbar, Iraq - (omar@example.edu.iq)"),
          abstract="<p><p><span>Intrusion detection has garnered significant attention.</span></p></p>",
          refs="", publisher=PUBLISHER):
    metas = "".join(f'<meta name="citation_author" content="{n}">' for n, _ in authors)
    head = f'<head>{publisher}{metas}<meta name="citation_title" content="A title"></head>'
    art = (f'<div class="r-art col-md-6"><div class="box2 shadow notch"><h3 class="green"><b>A title</b></h3>'
           f'{_byline(authors)}{_affs(affs)}<p class="green font-16"><b>Doi: 10.54216/JCIM.170208</b></p></div>'
           f'{_box("Abstract", abstract)}{_box("Keywords :", "<p>Network security</p>")}'
           f'{_box("References ", refs, "box2 Refer shadow") if refs else ""}</div>')
    return f"<html>{head}<body>{art}</body></html>"


def _refs(*entries):
    return "<p></p>" + "<p>&nbsp;</p>".join(f'<p class="ds-markdown-paragraph"><span>{e}</span></p>' for e in entries)


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _affs_of(html):
    return [[x["name"] for x in a["affiliations"]] for a in _parse(html)["authors"]]


def _raw(html):
    return AmericasPG(BeautifulSoup(html, "lxml")).parse()


def test_authors_come_from_the_byline_in_order():
    assert [a["name"] for a in _parse(_page())["authors"]] == ["Ahmad Salim", "Omar Muthanna Khudhur"]


def test_affiliations_follow_the_superscript_number_without_the_email():
    assert _affs_of(_page()) == [["Middle Technical University, Iraq"],
                                 ["Department of Computer Engineering Techniques, University of Al Maarif, Al Anbar, Iraq"]]


def test_shared_affiliation_number_goes_to_each_author():
    page = _page(authors=(("A. Madhuri", "1"), ("T. Umadevi", "1")), affs=("GITAM University, India - (a@example.in)",))
    assert _affs_of(page) == [["GITAM University, India"]] * 2


def test_an_unexplained_asterisk_is_not_a_corresponding_mark():
    assert not any(a["is_corresponding"] for a in _parse(_page())["authors"])


def test_abstract_is_the_abstract_panel_without_word_comments():
    abstract = ("<p><!-- [if gte mso 9]><xml><w:WordDocument><w:View>Normal</w:View></w:WordDocument></xml>"
                "<![endif]--><span>Intrusion detection has garnered significant attention.</span></p>")
    assert _parse(_page(abstract=abstract))["abstract"] == "Intrusion detection has garnered significant attention."


def test_numbered_references_are_read_whole_and_complete():
    out = _raw(_page(refs=_refs("<span>[1]&nbsp;&nbsp; </span>M. Du, Int. J. Commun. Syst., 2022.",
                                "<span>[2]&nbsp;&nbsp; </span>X. Ma, GLOBECOM, 2019, doi: 10.1109/GLOBECOM38437.2019.9013999.")))
    assert [(r["position"], r["raw"]) for r in out["references"]] == [
        (1, "M. Du, Int. J. Commun. Syst., 2022."),
        (2, "X. Ma, GLOBECOM, 2019, doi: 10.1109/GLOBECOM38437.2019.9013999.")]
    assert [r["doi"] for r in out["references"]] == [None, "10.1109/GLOBECOM38437.2019.9013999"]
    assert out["references_complete"] is True


def test_a_wrapped_line_joins_its_reference():
    out = _raw(_page(refs=_refs("[1] F. Smarandache, (1988). Neutrosophy. American Research", "Press, Gallup.",
                                "[2] A. A. Salama, (2012). Neutrosophic Set.", "22.")))
    assert [r["raw"] for r in out["references"]] == ["F. Smarandache, (1988). Neutrosophy. American Research Press, Gallup.",
                                                     "A. A. Salama, (2012). Neutrosophic Set. 22."]
    assert out["references_complete"] is True


def test_dot_numbered_references_count_too():
    out = _raw(_page(refs=_refs("1. C. Johnson, Journal of Decision Science.", "2. D. Smith, Algebra.")))
    assert [r["raw"] for r in out["references"]] == ["C. Johnson, Journal of Decision Science.", "D. Smith, Algebra."]
    assert out["references_complete"] is True


def test_unnumbered_references_are_not_called_complete():
    out = _raw(_page(refs=_refs("Cooper, C. (2018). Tourism.", "Pond, K. (1993). The professional guide.")))
    assert len(out["references"]) == 2 and out["references_complete"] is False


def test_a_gap_in_the_numbers_is_not_complete():
    out = _raw(_page(refs=_refs("[1] One.", "[2] Two.", "[4] Four.")))
    assert out["references_complete"] is False


def test_no_reference_panel_means_no_references():
    out = _raw(_page())
    assert out["references"] == [] and out["references_complete"] is False
    assert out["acknowledgments"] is None and out["funding_statement"] is None


def test_registration_wall_is_not_read():
    html = f'<html><head>{PUBLISHER}</head><body><h3>Create an account</h3><form></form></body></html>'
    assert not AmericasPG(BeautifulSoup(html, "lxml")).authors_found()


def test_same_markup_from_another_publisher_is_not_claimed():
    other = '<meta name="citation_publisher" content="American Scientific Publishers" />'
    page = _page(publisher=other)
    parser = AmericasPG(BeautifulSoup(page, "lxml"))
    assert not parser.is_publisher_specific_parser() and not parser.authors_found()
    assert _affs_of(page) == [[], []]
