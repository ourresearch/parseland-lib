"""Corresponding authors on Atypon Literatum pages (oxjob #2220).

Markup is cut down from stored pages of Literatum society sites (13 Nov 2026, #2220 EXPLORE § 1): AHA, APA Psychiatry
Online, APS Physiology, ATS (older template: JATS ``<corresp>`` rendered as ``.NLM_corresp``), ASCE and ASM (2022 "core"
template). No publisher parser claims these sites; the parser that wins reads authors and affiliations and marks no
one. Rubric label-v1: an explicit correspondence label naming the author is a mark; "Address reprint requests to" alone,
or an e-mail alone, is not.
"""
from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.literatum import literatum_corresponding_marks, pick_literatum_corresponding

URL = "https://www.ahajournals.org/doi/10.1161/01.atv.20.1.111"
LITERATUM = '<link rel="stylesheet" href="/pb-assets/css/build-1700000000000.css"/>'


def _page(names, body, head=LITERATUM):
    metas = "".join(f'<meta name="citation_author" content="{n}"/>' for n in names)
    return (f"<html><head>{head}{metas}<meta name=\"citation_title\" content=\"A title\"/>"
            f"<meta name=\"citation_doi\" content=\"10.1161/x.1\"/></head><body>{body}</body></html>")


def _core_page(people, notes=""):
    """2022 core template: one div[property=author] per author in section.core-authors."""
    blocks = "".join(
        f'<div id="con{i}" property="author" typeof="Person"><div class="heading"><span property="givenName">{g}</span> '
        f'<span property="familyName">{f}</span></div><div class="content"><div class="affiliations">'
        f'<div property="affiliation" typeof="Organization"><span property="name">{aff}</span></div></div></div></div>'
        for i, (g, f, aff) in enumerate(people, 1))
    body = (f'<section id="tab-contributors" role="tabpanel"><section class="core-authors"><h4>Affiliations</h4>{blocks}'
            f'</section>{notes}</section>')
    return _page([f"{g} {f}" for g, f, _ in people], body)


def _corr(html):
    return [a["name"] for a in parse_page(html.encode(), "doi", URL)["authors"] if a["is_corresponding"]]


def _notes(text):
    return f'<h3>Footnotes</h3><div class="NLM_author-notes"><div class="NLM_corresp">{text}</div></div>'


PSY = ["Véronique Thomas-Ollivier", "Thibault Deschamps", "Samuel Bulteau"]


def test_send_correspondence_to_surname_only():
    html = _page(PSY, _notes("Send correspondence to Dr. Thomas-Ollivier; e-mail: vto@example.fr"))
    assert _corr(html) == ["Véronique Thomas-Ollivier"]


def test_address_for_reprint_requests_and_other_correspondence_with_initials():
    names = ["Mark C. Bellingham", "Jane Q. Smith"]
    html = _page(names, '<ul class="author-notes"><li id="cor1">Address for reprint requests and other correspondence: '
                        'M. C. Bellingham, School of Biomedical Sciences, Univ. of Queensland, Brisbane.</li></ul>')
    assert _corr(html) == ["Mark C. Bellingham"]


def test_correspondence_and_requests_for_reprints_should_be_addressed_to():
    names = ["Ognjen Gajic", "Alice Brown"]
    html = _page(names, _notes("Correspondence and requests for reprints should be addressed to Ognjen Gajic, M.D., "
                               "Mayo Clinic, 200 First Street SW, Rochester, MN 55905."))
    assert _corr(html) == ["Ognjen Gajic"]


def test_reprint_requests_alone_mark_no_one():
    html = _page(PSY, _notes("Address reprint requests to Dr. Thomas-Ollivier, University Hospital, Nantes."))
    assert _corr(html) == []


def test_core_template_label_in_the_authors_own_block():
    people = [("Xiang", "Qiu", "School of Civil Engineering, Changsha Univ. of Science and Technology. Email: x@x.cn"),
              ("Zhuo", "Jia", "School of Civil Engineering, Changsha Univ. of Science and Technology "
                              "(corresponding author). Email: z@x.cn")]
    assert _corr(_core_page(people)) == ["Zhuo Jia"]


def test_core_template_authors_notes_footnote():
    people = [("Atsushi", "Iguchi", "Miyazaki University"), ("Keiko", "Seto", "Osaka Institute of Public Health")]
    notes = ('<section class="core-authors-notes"><div role="doc-footnote" id="cor1">'
             'Address correspondence to Atsushi Iguchi, iguchi@example.jp.</div></section>')
    assert _corr(_core_page(people, notes)) == ["Atsushi Iguchi"]


def test_note_without_a_name_marks_no_one():
    people = [("Ann", "Lee", "University A"), ("Bo", "Kim", "University B")]
    notes = ('<section class="core-authors-notes"><div role="doc-footnote" id="cor1">'
             'To whom correspondence may be addressed. Email: lee@example.org.</div></section>')
    assert _corr(_core_page(people, notes)) == []


def test_label_on_every_author_marks_no_one():
    people = [("Ann", "Lee", "University A (corresponding author)"), ("Bo", "Kim", "University B (corresponding author)")]
    assert _corr(_core_page(people)) == []


def test_page_not_built_on_literatum_is_not_read():
    html = _page(PSY, _notes("Send correspondence to Dr. Thomas-Ollivier; e-mail: vto@example.fr"),
                 head='<meta name="generator" content="Open Journal Systems 3.3.0.10"/>')
    assert _corr(html) == []


def test_marks_and_pick_directly():
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(_notes("Correspondence to Dr Joseph C. Obunike, Division of Preventive Medicine, BB 906, "
                                "Columbia University, New York, NY 10032."), "lxml")
    marks = literatum_corresponding_marks(soup)
    assert marks["names"] == []
    assert pick_literatum_corresponding(["Joseph C. Obunike", "Latha Paka"], marks) == ["Joseph C. Obunike"]
    assert literatum_corresponding_marks(BeautifulSoup("<div class='NLM_corresp'>Received 3 May.</div>", "lxml")) is None
