"""RCNi (Royal College of Nursing journals, journals.rcni.com) article pages (oxjob #2330).

Markup is cut down from stored rcni.com pages (17 Nov 2026, #2330 sample). One template serves every year from 1987
to 2026: a byline block right after the <h1> (absent on news items, which credit no one), then one or two <abstract>
elements. Of two, the first is a standfirst ("Simon Rippon and Malcolm Rae outline ..."), the second the opening
paragraph; the page shows both as its abstract, so both are read. Research articles add <strong>-headed back-matter
notes (Correspondence, Acknowledgements).
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.rcn import RoyalCollegeOfNursing

URL = "https://journals.rcni.com/doi/abs/10.7748/ns.30.25.34.s45"
HEAD = ('<meta name="dcterms.title" content="A title" /><meta name="dcterms.creator" content="{creator}" />'
        '<meta name="dcterms.identifier" content="https://journals.rcni.com/doi/abs/10.7748/ns.30.25.34.s45"/>'
        '<meta name="abstract" content="" /><meta name="twitter:site" content="@rcni" />{extra}')
CITE = '<p class="mar-bot-15"><strong>Nursing Standard</strong>. 30, 25, 34-34. <strong> doi:</strong> 10.7748/ns.30.25.34.s45</p>'


def _byline(*authors):
    rows = "".join(f'<h6 class="mar-bot-15"><strong><a class="blackLink" href="/search/author/ns/x"> {name} </a>  </strong>'
                   f' {aff}<br></h6>' for name, aff in authors)
    return f'<div class="node-content mar-bot-15">{rows}</div>'


def _page(byline="", abstracts=(), back="", creator="", extra_head="", head=None):
    head = HEAD.format(creator=creator, extra=extra_head) if head is None else head
    blocks = "".join(f"<abstract>{a}</abstract>" for a in abstracts)
    return (f'<html><head>{head}</head><body><div class="articleLeftBlock"><h1 class="mar-t5 mar-b25"> A title </h1>'
            f'{byline}<div class="custom_images"></div><div class="borderBtmBlack">{blocks}{CITE}{back}</div></div>'
            f'<h2 class="font1">Want to read more?</h2></body></html>')


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def test_news_item_without_byline_gets_its_abstract():
    out = _parse(_page(abstracts=["<p>A mental health nurse defended his membership of a party last week.</p>"]))
    assert out["authors"] == []
    assert out["abstract"] == "A mental health nurse defended his membership of a party last week."


def test_standfirst_and_opening_paragraph_are_both_read():
    # cut down from a stored Nursing Older People news page (10.7748/nop.23.2.5.s5), #2330 fresh set
    p = '<p xmlns:mml="http://www.w3.org/1998/Math/MathML">{}</p>'
    html = _page(byline=_byline(("Sophie Blakemore", "")), creator="Sophie Blakemore ",
                 abstracts=["<p>Ombudsman investigations into complaints show that the health service is failing to "
                            "meet basic standards of care for older people in hospital</p>",
                            p.format("THE NHS is failing to treat older people with care, compassion, dignity and "
                                     "respect, a report from the health service ombudsman concludes.")])
    out = _parse(html)
    assert [a["name"] for a in out["authors"]] == ["Sophie Blakemore"]
    assert out["abstract"] == ("Ombudsman investigations into complaints show that the health service is failing to "
                               "meet basic standards of care for older people in hospital\n"
                               "THE NHS is failing to treat older people with care, compassion, dignity and respect, "
                               "a report from the health service ombudsman concludes.")


def test_repeated_block_is_read_once():
    text = "<p>A mental health nurse defended his membership of a party last week.</p>"
    assert _parse(_page(abstracts=[text, text]))["abstract"] == (
        "A mental health nurse defended his membership of a party last week.")


def test_structured_abstract_keeps_its_paragraphs():
    html = _page(byline=_byline(("Anne Tyldesley", "Lecturer, University of Somewhere, UK")),
                 abstracts=["<p><strong>Background</strong> Many older people experience chronic pain.</p>"
                            "<p><strong>Aim</strong> To assess differences in comfort and pain.</p>"])
    assert _parse(html)["abstract"] == ("Background Many older people experience chronic pain.\n"
                                        "Aim To assess differences in comfort and pain.")


def test_byline_names_and_affiliations():
    html = _page(byline=_byline(("Michele Shropshire", "Assistant professor, Illinois State University, US"),
                                ("Thelma Agnew         ", "")),
                 abstracts=["<p>Simulation can enhance nursing students' education.</p>"])
    authors = _parse(html)["authors"]
    assert [a["name"] for a in authors] == ["Michele Shropshire", "Thelma Agnew"]
    assert authors[0]["affiliations"] == [{"name": "Assistant professor, Illinois State University, US"}]
    assert authors[1]["affiliations"] == []  # no text beside the name: no affiliation, not an empty one


def test_lone_comma_is_no_affiliation():
    html = _page(byline=_byline(("Alison Twycross", ",")), abstracts=["<p>In response to an article on a good death.</p>"])
    assert _parse(html)["authors"][0]["affiliations"] == []


def test_correspondence_email_marks_its_author():
    html = _page(byline=_byline(("Julie Caroline Vuolo", "Senior lecturer, University of Hertfordshire"),
                                ("Peter Dunn", "Nurse, London")),
                 abstracts=["<p>Successful nursing care of surgical wounds depends on the nurse's knowledge.</p>"],
                 extra_head='<meta name="correspondence" content="j.c.vuolo@herts.ac.uk" />')
    assert [a["is_corresponding"] for a in _parse(html)["authors"]] == [True, False]


def test_listing_with_empty_abstract_reads_nothing():
    out = _parse(_page(abstracts=[""]))
    assert out["authors"] == []
    assert not out["abstract"]


def test_acknowledgements_note():
    back = ('<strong>Correspondence</strong><p class="mar-bot-15"> <a href="mailto:x@y.ac.uk">x@y.ac.uk</a> </p>'
            '<strong>Acknowledgements</strong><p class="mar-bot-15">The authors would like to thank the school staff '
            'and children involved in the simulation session</p> <p>Published online: 06 July 2026</p>')
    html = _page(byline=_byline(("Helen Reddy", "Lecturer, University of Nottingham")),
                 abstracts=["<p>Simulation can enhance nursing students' education.</p>"], back=back)
    parsed = RoyalCollegeOfNursing(BeautifulSoup(html, "lxml")).parse()
    assert parsed["acknowledgments"] == ("The authors would like to thank the school staff and children involved in "
                                         "the simulation session")
    assert parsed["funding_statement"] is None
    plain = RoyalCollegeOfNursing(BeautifulSoup(_page(abstracts=["<p>A news lead of some length here.</p>"]), "lxml"))
    assert plain.parse()["acknowledgments"] is None


def test_look_alike_page_of_another_site_is_not_claimed():
    other_head = ('<meta name="dcterms.identifier" content="https://journals.example.org/doi/abs/10.1234/x.1" />'
                  '<meta name="twitter:site" content="@example" />')
    html = _page(byline=_byline(("Jane Doe", "Nurse, Somewhere")), abstracts=["<p>An abstract of some length.</p>"],
                 head=other_head)
    parser = RoyalCollegeOfNursing(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
