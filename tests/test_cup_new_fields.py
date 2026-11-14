"""Cambridge Core acknowledgments, funding statement and reference list (oxjob #2222; contract: oxjob #2215 README).

Cambridge Core renders JATS back matter: div.ack, a funding section headed "Funding" / "Financial support" /
"Funding statement", and #references-list with one .circle-list__item per entry. On many humanities journals the
same list holds footnotes (item ids fn1, en1; older pages "page 381 note 1"): those are never references. A list is
complete only when its entries run 1..n with no gap and no footnote among them. Hand-cut markup; no network.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.cup import CUP

CAMBRIDGE_URL = "https://www.cambridge.org/core/journals/x/article/y"
CAMBRIDGE_OG = f'<meta property="og:url" content="{CAMBRIDGE_URL}" />'
OTHER_OG = '<meta property="og:url" content="https://journals.example.org/article/y" />'
AUTHOR = ('<div class="author"><dl><dt>Ada Author*</dt><dd><div class="d-sm-flex">'
          '<span>Example University</span></div></dd></dl></div>'
          '<meta name="citation_abstract" content="' + "A real abstract that states what the study did. " * 4 + '">')


def _page(body: str, og: str = CAMBRIDGE_OG) -> str:
    return f"<html><head>{og}</head><body>{AUTHOR}{body}</body></html>"


def _parse(body: str, og: str = CAMBRIDGE_OG) -> dict:
    return CUP(BeautifulSoup(_page(body, og), "lxml")).parse()


def _ref(item_id: str, number: str, inner: str) -> str:
    return (f'<div class="circle-list__item" id="{item_id}"><div class="circle-list__item__indicator"></div>'
            f'<div aria-hidden="true" class="circle-list__item__number">\n{number}\n</div>'
            f'<div class="circle-list__item__grouped"><div class="circle-list__item__grouped__content">{inner}</div>'
            f'</div></div>')


def _refs(*items: str) -> str:
    return '<div id="references-list">' + "".join(items) + "</div>"


NUMBERED = _refs(
    _ref("ref001", "1", '<span class="label">1.</span><span class="name"><span class="surname">Bhimani</span>, '
         '<span class="given-names">M</span></span>. <span class="article-title">Training demographics</span>. '
         '<span class="source">CJEM</span> <span class="year">2007</span>;9:449.'
         '<a class="ref-link" href="https://dx.doi.org/10.1017/S1481803500015487">CrossRef</a>'
         '<a class="ref-link" href="https://scholar.google.com/scholar_lookup?title=x">Google Scholar</a>'
         '<a class="ref-link" href="http://www.ncbi.nlm.nih.gov/pubmed/18072991">PubMed</a>'),
    _ref("ref002", "2", '<span class="label">2.</span>Alcock, C.: 1977, Ph.D. Thesis, California.'
         '<a class="ref-link" href="https://scholar.google.com/scholar?q=Alcock">Google Scholar</a>'),
)


def test_numbered_list_is_complete_with_dois_and_no_buttons():
    out = _parse(NUMBERED)
    assert out["references_complete"] is True
    assert out["references"] == [
        {"position": 1, "raw": "Bhimani, M. Training demographics. CJEM 2007;9:449.", "doi": "10.1017/S1481803500015487"},
        {"position": 2, "raw": "Alcock, C.: 1977, Ph.D. Thesis, California.", "doi": None},
    ]


def test_bracketed_numbers_count_as_numbered():
    out = _parse(_refs(_ref("r1", "[1]", "Smith, A. 2001. One."), _ref("r2", "[2]", "Jones, B. 2002. Two.")))
    assert out["references_complete"] is True and len(out["references"]) == 2


def test_author_year_list_is_kept_but_not_complete():
    out = _parse(_refs(_ref("ref1", "", "Clarke, R. R. 1954. Treasure."), _ref("ref2", "", "Hawkes, C. 1955. Hoard.")))
    assert [r["raw"] for r in out["references"]] == ["Clarke, R. R. 1954. Treasure.", "Hawkes, C. 1955. Hoard."]
    assert out["references_complete"] is False


def test_a_gap_in_the_numbers_is_not_complete():
    out = _parse(_refs(_ref("ref2", "2", "Two."), _ref("ref3", "3", "Three.")))
    assert out["references_complete"] is False


def test_footnotes_are_not_references():
    notes = _refs(_ref("fn1", "1", "<p>Gilmore, S., Schools of Activity, 1988.</p>"),
                  _ref("fn2", "2", "<p>Varese was active in the downtown scene.</p>"))
    out = _parse(notes)
    assert out["references"] is None and out["references_complete"] is False
    old_notes = _refs(_ref("ref1", "page 381 note 1", "Cf. Hdt. 2.4."))
    assert _parse(old_notes)["references"] is None


def test_a_footnote_among_references_makes_the_list_incomplete():
    out = _parse(_refs(_ref("ref1", "1", "One."), _ref("fn1", "2", "<p>A note.</p>"), _ref("ref2", "3", "Three.")))
    assert [r["raw"] for r in out["references"]] == ["One.", "Three."]
    assert out["references_complete"] is False


def test_show_more_marker_makes_the_list_incomplete():
    out = _parse(_refs(_ref("ref1", "1", "One."), _ref("ref2", "2", "Two."), "<button>Show all references</button>"))
    assert len(out["references"]) == 2 and out["references_complete"] is False


def test_acknowledgments_and_funding_sections():
    body = ('<div class="ack"><h2 class="A">Acknowledgements</h2><p class="p">We thank the participants.</p>'
            '<p class="p">And the reviewers.</p></div>'
            '<div class="sec funding-statement" id="sec29"><h2 class="A">Financial support</h2>'
            '<p class="p">This work was supported by the Medical Research Council (grant MR/T000902/1).</p></div>'
            '<div class="notes coi-statement"><h2 class="A">Conflict of interest</h2><p class="p">None.</p></div>')
    out = _parse(body)
    assert out["acknowledgments"] == "We thank the participants.\nAnd the reviewers."
    assert out["funding_statement"] == "This work was supported by the Medical Research Council (grant MR/T000902/1)."


def test_funding_heading_inside_div_ack_is_funding():
    out = _parse('<div class="ack"><h2 class="A">Financial support</h2><p class="p">Norwegian Research Council.</p></div>'
                 '<div class="notes other"><h2 class="A">Funding</h2><p class="p">Grant 301045.</p></div>')
    assert out["acknowledgments"] is None
    assert out["funding_statement"] == "Norwegian Research Council.\nGrant 301045."


def test_combined_section_goes_to_acknowledgments():
    out = _parse('<div class="ack"><h2 class="A">Acknowledgements and funding</h2><p class="p">Thanks; NSF 123.</p></div>')
    assert out["acknowledgments"] == "Thanks; NSF 123." and out["funding_statement"] is None


def test_page_without_back_matter_says_none():
    out = _parse("<p>No back matter here.</p>")
    assert out["acknowledgments"] is None and out["funding_statement"] is None
    assert out["references"] is None and out["references_complete"] is False


def test_look_alike_page_from_another_site_gets_no_new_fields():
    body = NUMBERED + '<div class="ack"><h2>Acknowledgements</h2><p>Thanks.</p></div>'
    out = _parse(body, og=OTHER_OG)
    for key in ("acknowledgments", "funding_statement", "references", "references_complete"):
        assert key not in out


def test_six_fields_unchanged_by_back_matter():
    back = NUMBERED + '<div class="ack"><h2 class="A">Acknowledgements</h2><p class="p">Thanks.</p></div>'
    with_back = parse_page(_page(back).encode(), "doi", CAMBRIDGE_URL)
    without = parse_page(_page("").encode(), "doi", CAMBRIDGE_URL)
    for key in ("authors", "abstract", "urls", "license"):
        assert with_back.get(key) == without.get(key)
    assert with_back["authors"] and with_back["authors"][0]["affiliations"]
