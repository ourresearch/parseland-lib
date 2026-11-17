"""Acknowledgments and reference lists on jci.org pages: The Journal of Clinical Investigation and JCI Insight
(oxjob #2338).

Markup is cut down from stored jci.org pages (17 Nov 2026, #2338 site jci-org: JCI14080, JCI180570,
jci.insight.153868). Every full-text article prints an "Acknowledgments" accordion (div#acknowledgments, whose last
paragraph is often the "Address correspondence to" note) and a numbered reference list (div#references > ol >
li.reference value="N", each entry followed by its "View this article via: CrossRef PubMed" links). No reader took
them: the JCI parser claimed only JCI Insight, and the generic reader won The Journal of Clinical Investigation's pages.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.jci import JCI

URL = "https://doi.org/10.1172/JCI180570"
ASCI = "American Society for Clinical Investigation"


def _head(journal="The Journal of Clinical Investigation", publisher=ASCI, html_url="http://www.jci.org/articles/view/180570",
          names=("Dong-Hee Shin", "Young-Ho Ahn")):
    metas = "".join(f'<meta name="citation_author" content="{n}" />' for n in names)
    return (f'<head><meta charset="utf-8"><meta name="citation_title" content="A title" />{metas}'
            f'<meta name="citation_journal_title" content="{journal}" />'
            f'<meta name="citation_publisher" content="{publisher}" />'
            f'<meta name="citation_doi" content="10.1172/JCI180570" />'
            f'<meta name="citation_html_url" content="{html_url}" /></head>')


def _byline(names=("Dong-Hee Shin", "Young-Ho Ahn")):
    links = "".join(f'<a class="author-affiliation show-more" href="javascript:void(0);" '
                    f'data-dropdown="author-affiliation-{i}"> {n}<sup>1</sup> </a>' for i, n in enumerate(names))
    boxes = "".join(f'<div class="f-dropdown content large" data-dropdown-content id="author-affiliation-{i}"><p>'
                    f'<p class="affiliations"><sup>1</sup>Department of Molecular Medicine, Ewha Womans University, '
                    f'Seoul, South Korea.</p></p></div>' for i, _ in enumerate(names))
    return f'<h4 class="author-list">{links}</h4>{boxes}'


ACK = ('<a href="#acknowledgments"><span class="section-title">Acknowledgments</span></a>'
       '<div id="acknowledgments" class="content active">'
       '<p>This work was supported by National Research Foundation of Korea (NRF) grants '
       '(NRF-2020R1A5A2019210 to YHA).</p>'
       '<p>We thank the UroGyn Efficacy Evaluation Center for technical assistance.</p>'
       '<p>Address correspondence to: Young-Ho Ahn, Department of Molecular Medicine, Ewha Womans University, Seoul '
       '07804, South Korea. Email: <a href="mailto:yahn@example.ac.kr">yahn@example.ac.kr</a>.</p>'
       '<p></p></div>')


def _ref(n, text, doi=None):
    crossref = f'<a target="_blank" href="https://doi.org/{doi}"> CrossRef </a>' if doi else ""
    return (f'<a class="in-page" name="B{n}"></a><li class="reference" value="{n}">{text} '
            f'<div class="reference_linkouts">View this article via: {crossref}'
            f'<a target="_blank" href="http://www.ncbi.nlm.nih.gov/pubmed/3303719{n}"> PubMed </a>'
            f'<a href="/references/scholar/46069/B{n}">Google Scholar</a></div></li>')


REFS = [(1, "Winkler J, et al. Concepts of extracellular matrix remodelling in tumour progression and metastasis. "
            "<i>Nat Commun</i>. 2020;11(1):5120.", "10.1038/s41467-020-18794-x"),
        (2, "Karousou E, et al. Hyaluronan in the cancer cells microenvironment. <i>Cancers (Basel)</i>. "
            "2023;15(3):798.", "10.3390/cancers15030798"),
        (3, "Wahba HA, El-Hadaad HA. Current approaches in treatment of triple-negative breast cancer. "
            "<i>Cancer Biol Med</i>. 2015;12(2):106–116.", None)]


def _refs(refs=REFS):
    return ('<a href="#references"><span class="section-title">References</span></a>'
            '<div id="references" class="content active"><ol compact>'
            + "".join(_ref(*r) for r in refs) + "</ol></div>")


def _page(head=None, body=None):
    body = body if body is not None else (_byline() + '<div id="section-abstract" class="content active"><p>'
                                          + "An abstract. " * 30 + "</p></div>" + ACK + _refs())
    return f"<!DOCTYPE html><html lang='en'>{head or _head()}<body>{body}</body></html>"


def _parse(html):
    return JCI(BeautifulSoup(html, "lxml")).parse()


def test_acknowledgments_without_the_correspondence_note():
    parsed = _parse(_page())
    assert parsed["acknowledgments"] == (
        "This work was supported by National Research Foundation of Korea (NRF) grants (NRF-2020R1A5A2019210 to "
        "YHA).\nWe thank the UroGyn Efficacy Evaluation Center for technical assistance.")
    # jci.org prints its funding sentences in the acknowledgments, under no label of their own
    assert parsed["funding_statement"] is None


def test_correspondence_note_alone_is_no_acknowledgments():
    ack = ('<div id="acknowledgments" class="content active"><p>Address correspondence to: Young-Ho Ahn, Seoul, '
           'South Korea.</p></div>')
    assert _parse(_page(body=_byline() + ack + _refs()))["acknowledgments"] is None


def test_reference_list_in_order_with_crossref_dois():
    parsed = _parse(_page())
    assert parsed["references"] == [
        {"position": 1, "raw": "Winkler J, et al. Concepts of extracellular matrix remodelling in tumour progression "
                               "and metastasis. Nat Commun. 2020;11(1):5120.", "doi": "10.1038/s41467-020-18794-x"},
        {"position": 2, "raw": "Karousou E, et al. Hyaluronan in the cancer cells microenvironment. Cancers (Basel). "
                               "2023;15(3):798.", "doi": "10.3390/cancers15030798"},
        {"position": 3, "raw": "Wahba HA, El-Hadaad HA. Current approaches in treatment of triple-negative breast "
                               "cancer. Cancer Biol Med. 2015;12(2):106–116.", "doi": None},
    ]
    assert parsed["references_complete"] is True


def test_numbering_with_a_gap_is_not_the_whole_list():
    parsed = _parse(_page(body=_byline() + _refs([REFS[0], REFS[1], (4, "Kim PK, et al. A title. Elife. 2021.", None)])))
    assert len(parsed["references"]) == 3
    assert parsed["references_complete"] is False


def test_jci_page_keeps_the_six_fields_and_gains_back_matter():
    out = parse_page(_page().encode(), "doi", URL)
    assert [a["name"] for a in out["authors"]] == ["Dong-Hee Shin", "Young-Ho Ahn"]
    # the byline pop-ups still give the affiliations (#2252) and the note still marks the corresponding author
    assert out["authors"][0]["affiliations"] == [
        {"name": "Department of Molecular Medicine, Ewha Womans University, Seoul, South Korea."}]
    assert out["acknowledgments"].startswith("This work was supported by National Research Foundation of Korea")
    assert [r["position"] for r in out["references"]] == [1, 2, 3]
    assert out["references_complete"] is True


def test_jci_insight_page_keeps_its_byline_parse_and_gains_back_matter():
    head = _head(journal="JCI Insight", html_url="http://insight.jci.org/articles/view/153868")
    parsed = _parse(_page(head=head))
    assert [a["name"] for a in parsed["authors"]] == ["Dong-Hee Shin", "Young-Ho Ahn"]
    assert parsed["authors"][1]["affiliations"] == [
        "Department of Molecular Medicine, Ewha Womans University, Seoul, South Korea."]
    assert parsed["acknowledgments"].endswith("for technical assistance.")
    assert parsed["references_complete"] is True


def test_look_alike_page_from_another_site_is_not_claimed():
    # same accordion markup and byline classes, another publisher's head
    other = _head(journal="Journal of Other Studies", publisher="Other Society Press",
                  html_url="https://www.example.org/articles/view/1")
    parser = JCI(BeautifulSoup(_page(head=other), "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_jci_article_mirrored_elsewhere_is_not_claimed():
    # a JCI article's copy on another host (PubMed Central keeps the publisher tag): not jci.org's page
    mirror = _head(html_url="https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1/")
    parser = JCI(BeautifulSoup(_page(head=mirror), "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
