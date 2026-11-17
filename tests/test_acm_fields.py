"""ACM Digital Library's older item template (dl.acm.org, Atypon Literatum UX3; oxjob #2289).

Markup is cut down from #2289's stored ACM pages (17 Nov 2026). What the parser must do there: no empty affiliation
for an author whose institution span is empty (Zendesk ticket 2685), every paragraph of the abstract, and the
reference list with each entry's DOI; and it must not claim another Literatum site's page with the same author cards.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.acm import AssociationForComputingMachinery

URL = "https://dl.acm.org/doi/10.1145/800256.810708"


def _card(name, inst=""):
    return ('<span class="loa__author-info"> <div class="author-data"><span class="loa__author-name"><span>'
            f'<img alt="" aria-hidden="true" class="author-picture" src="/pb-assets/icons/default.svg"/>{name}'
            f'</span></span></div><span class="loa_author_inst">{inst}</span></span>')


def _ref(i, text, label="", suffix="", pub_id="", prefix="ref-"):
    lab = f'<span class="label">{label}</span>' if label else ""
    pid = f'<span class="references__pub-id doi {pub_id}"></span>' if pub_id else ""
    return (f'<li id="{prefix}{i:05d}" class="references__item"><span class="references__note">{lab}{text} {pid}'
            f'<span class="references__suffix"><a class="google-scholar" href="http://scholar.google.com/scholar?q=x">'
            f'<span class="visibility-hidden">Google Scholar</span></a></span>{suffix}</span></li>')


def _refs(items, extra=""):
    return ('<div class="article__section article__references show-more-items" data-sectionname="References">'
            '<h2 class="section__title">References</h2><ol class="rlist references__list references__numeric">'
            + "".join(items) + "</ol></div>" + extra)


def _page(cards, abstract="<p>One paragraph.</p>", refs="", og_url="https://dl.acm.org/doi/10.1145/800256.810708"):
    return (f'<html><head><meta property="og:url" content="{og_url}"/>'
            '<meta property="og:site_name" content="ACM Conferences"/><title>A title</title></head><body>'
            f'<div class="loa"><div class="loa-wrapper">{"".join(cards)}</div></div>'
            f'<div class="article__section article__abstract hlFld-Abstract"><div class="abstractSection abstractInFull">'
            f'{abstract}</div></div>{refs}</body></html>')


def _parse(html):
    return AssociationForComputingMachinery(BeautifulSoup(html, "lxml")).parse()


def test_empty_institution_span_gives_no_affiliation():
    html = _page([_card("D. R. Winner"), _card("L. L. Marsh")])
    authors = parse_page(html.encode(), "doi", URL)["authors"]
    assert [a["name"] for a in authors] == ["D. R. Winner", "L. L. Marsh"]
    assert [a["affiliations"] for a in authors] == [[], []]


def test_affiliation_is_kept():
    html = _page([_card("Claudia P. C. Maciel", "<p>Federal Technological University of Paraná, Brazil</p>")])
    authors = parse_page(html.encode(), "doi", URL)["authors"]
    assert [x["name"].strip() for x in authors[0]["affiliations"]] == ["Federal Technological University of Paraná, Brazil"]


def test_every_abstract_paragraph():
    first = "We first consider an MIMD multiprocessor configuration with n processors and a parallel program."
    second = "We then consider a distributed MIMD supercomputer with k clusters, containing u processors each."
    html = _page([_card("E. Lerner")], abstract=f"<p>{first}</p><p>{second}</p>")
    abstract = parse_page(html.encode(), "doi", URL)["abstract"]
    assert first in abstract and second in abstract


def test_references_with_dois_and_whole_list():
    items = [
        _ref(1, "A. Aurum and J. Ward. 2008. Knowledge Management practices. Information and Software Technology 50.",
             pub_id="10.1016/j.infsof.2007.05.005"),
        _ref(2, "S. Ghobadi and L. Mathiassen. 2018. Risks to Effective Knowledge Sharing. Information Systems Journal.",
             suffix='<span class="references__suffix"><a href="/servlet/linkout?suffix=e_1&amp;dbid=16&amp;'
                    'doi=10.1145%2F3275245.3275260&amp;key=10.1111%2Fisj.12117">Cross Ref</a></span>'),
        _ref(3, "A. Aho, R. Sethi and J. Ullman. 1986. Compilers: Principles, Techniques, and Tools. Addison-Wesley.",
             label="3.", pub_id="10.5555/6448"),
    ]
    out = _parse(_page([_card("A. Author")], refs=_refs(items)))
    assert [r["doi"] for r in out["references"]] == ["10.1016/j.infsof.2007.05.005", "10.1111/isj.12117", None]
    assert out["references"][2]["raw"].startswith("A. Aho, R. Sethi")  # the list number is not the entry's text
    assert not any("Google Scholar" in r["raw"] or "Cross Ref" in r["raw"] for r in out["references"])
    assert out["references_complete"] is True


def test_a_gap_in_the_numbering_is_not_a_whole_list():
    items = [_ref(1, "First reference, 2001."), _ref(3, "Third reference, 2003.")]
    out = _parse(_page([_card("A. Author")], refs=_refs(items)))
    assert len(out["references"]) == 2 and out["references_complete"] is False


def test_author_year_label_stays_in_the_entry():
    items = [_ref(1, "ALGOL colloquium - closing word, ALGOL Bulletin AB29.3.2, Nov. 1968.", label="Wirth 1968 ")]
    out = _parse(_page([_card("A. Author")], refs=_refs(items)))
    assert out["references"][0]["raw"].startswith("Wirth 1968 ALGOL colloquium")


def test_footnotes_and_cited_by_are_not_references():
    footnotes = ('<ol class="rlist references__list"><li class="references__item" id="fn1"><span class="references__note">'
                 '1 The ontology is available online. Footnote</span></li></ol>')
    cited_by = ('<div class="article__cited article__section show-more-items"><div class="header-container">'
                '<ol class="rlist citedBy-main references__list"><li class="references__item">'
                '<span class="references__note">A citing work, 2024.</span></li></ol></div></div>')
    html = _page([_card("A. Author")], refs=footnotes + _refs([_ref(1, "Bib one, 2013.", prefix="Bib")], cited_by))
    out = _parse(html)
    assert [r["raw"] for r in out["references"]] == ["Bib one, 2013."] and out["references_complete"] is True


def test_another_literatum_site_with_the_same_author_cards_is_not_claimed():
    html = _page([_card("A. Author", "<p>University of Somewhere</p>")],
                 og_url="https://epubs.siam.org/doi/10.1137/080734029")
    parser = AssociationForComputingMachinery(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_core_template_page_is_left_to_the_shared_readers():
    core = ('<html><head><meta property="og:url" content="https://dl.acm.org/doi/10.1145/3651671.3651674"/></head>'
            '<body><section class="core-authors"><div property="author"><span property="givenName">Ana</span> '
            '<span property="familyName">Lima</span></div></section></body></html>')
    assert not AssociationForComputingMachinery(BeautifulSoup(core, "lxml")).authors_found()
