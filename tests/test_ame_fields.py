"""AME Publishing (amegroups.org, amegroups.com, theajo.com, annalscts.com ...): the reference list, funding statement
and acknowledgments (#2215's contract), and a claim cheap enough to run on every page (oxjob #2289, template
"ojs-like": OJS-style URLs on AME's own platform).

Markup is cut down from stored AME article pages (17 Nov 2026). Every AME journal loads its styles and scripts from
cdn.amegroups.cn and prints the back matter the same way: an "Acknowledgments" h2 whose paragraphs may include a run-in
"<em>Funding:</em>" paragraph, a "Footnote" h2 whose paragraphs may hold it instead, and a "References" h2 followed by
<ol class="ref-item"> with one <li id="B1">, <li id="B2"> ... per entry and [Crossref] [PubMed] buttons.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.ame import AMEPublishing

URL = "https://aes.amegroups.org/article/view/8145/html"
HEAD = ('<link rel="stylesheet" href="//cdn.amegroups.cn/journals/aes/styles/most.css?v=1"/>'
        '<script src="//cdn.amegroups.cn/journals/aes/js/common.js?v=1"></script>'
        '<meta name="citation_journal_title" content="Annals of Eye Science"/>'
        '<meta name="citation_publisher" content="AME Publishing Company"/>'
        '<meta name="citation_author" content="Sabrina Poonja"/><meta name="citation_author" content="John J. Chen"/>'
        '<meta name="citation_title" content="A title"/><meta name="citation_doi" content="10.21037/aes-24-38"/>')
BYLINE = ('<div class="meta"><p class="authors">Sabrina Poonja<sup>1</sup>, John J. Chen<sup>1,2</sup></p>'
          '<p class="affiliation"><aff id="aff1"><sup>1</sup><institution>Department of Ophthalmology</institution>, '
          '<institution>Mayo Clinic</institution>, <country>USA</country>;</aff><aff id="aff2"><sup>2</sup>'
          '<institution>Department of Neurology</institution>, <institution>Mayo Clinic</institution>, '
          '<country>USA</country></aff></p>'
          '<div class="correspond-author"><corresp id="cor1"><em>Correspondence to:</em> John J. Chen, MD, PhD. '
          'Department of Ophthalmology, Mayo Clinic. Email: <email>chen.john@mayo.edu</email>.</corresp></div></div>')
REF1 = ('<li id="B1">Berry S, Lin WV, Sadaka A, <em>et al</em>. Nonarteritic anterior ischemic optic neuropathy: cause, '
        'effect, and management. Eye Brain 2017;9:23-8. [<a href="http://dx.doi.org/10.2147/EB.S125311" '
        'target="_blank">Crossref</a>] [<a href="http://www.ncbi.nlm.nih.gov/pubmed/29033621" '
        'target="_blank">PubMed</a>]</li>')
REF2 = '<li id="B2">NICE. Menopause: diagnosis and management. NG23. 2015.</li>'
REF3 = ('<li id="B3">Foster RC, Bhatti MT, Crum OM, <em>et al</em>. Reexamining the Incidence of Nonarteritic Anterior '
        'Ischemic Optic Neuropathy. J Neuroophthalmol 2024;44:337-41. [<a href="http://www.ncbi.nlm.nih.gov/pubmed/'
        '38358828" target="_blank">PubMed</a>]</li>')
FUNDING_TEXT = "This study was supported by the Guangdong Basic and Applied Basic Research Foundation (No. 2023A1515)."
ACK_TEXT = "The authors would like to acknowledge Dr. A for preparing the histopathology slides."


def _page(ack="<p>None.</p>", footnote="<p><em>Funding:</em> None.</p>", refs=REF1 + REF2 + REF3, head=HEAD,
          ol='<ol class="ref-item">'):
    body = (f'<section>{BYLINE}<h2 id="introduction" class="section-title color-bg">Introduction</h2><p>Text.</p>'
            f'<hr/><h2 id="acknowledgments" class="section-title color-bg">Acknowledgments</h2>{ack}'
            f'<hr/><h2 id="Footnote" class="section-title color-bg">Footnote</h2>'
            f'<p><em>Conflicts of Interest:</em> The authors have no conflicts of interest to declare.</p>{footnote}'
            f'<hr/><h2 id="references" class="section-title color-bg">References</h2>{ol}{refs}</ol>'
            f'<div><p>Cite this article as: Poonja S, Chen JJ. A title. Ann Eye Sci 2025;10:5.</p></div></section>')
    return f"<html><head>{head}</head><body>{body}</body></html>"


def _parse(html):
    return AMEPublishing(BeautifulSoup(html, "lxml")).parse()


def test_byline_fields_unchanged():
    out = parse_page(_page().encode(), "doi", URL)
    assert [a["name"] for a in out["authors"]] == ["Sabrina Poonja", "John J. Chen"]
    assert out["authors"][0]["affiliations"] == [{"name": "Department of Ophthalmology, Mayo Clinic, USA;"}]
    assert [a["is_corresponding"] for a in out["authors"]] == [None, True]


def test_reference_list_in_page_order_without_buttons():
    refs = _parse(_page())["references"]
    assert [r["position"] for r in refs] == [1, 2, 3]
    assert refs[0]["raw"] == ("Berry S, Lin WV, Sadaka A, et al. Nonarteritic anterior ischemic optic neuropathy: "
                              "cause, effect, and management. Eye Brain 2017;9:23-8.")
    assert refs[0]["doi"] == "10.2147/EB.S125311"  # the entry's own Crossref button
    assert refs[1] == {"position": 2, "raw": "NICE. Menopause: diagnosis and management. NG23. 2015.", "doi": None}
    assert refs[2]["doi"] is None and refs[2]["raw"].endswith("2024;44:337-41.")  # a PubMed button is no DOI


def test_ids_running_one_to_n_make_the_list_whole():
    assert _parse(_page())["references_complete"] is True
    out = parse_page(_page().encode(), "doi", URL)
    assert len(out["references"]) == 3 and out["references_complete"] is True


def test_a_gap_in_the_entry_ids_is_not_whole():
    assert _parse(_page(refs=REF1 + REF3))["references_complete"] is False


def test_a_list_that_starts_later_is_not_whole():
    assert _parse(_page(ol='<ol class="ref-item" start="4">'))["references_complete"] is False


def test_funding_in_the_footnote_and_real_acknowledgments():
    out = _parse(_page(ack=f"<p>{ACK_TEXT}</p>", footnote=f"<p><em>Funding:</em> {FUNDING_TEXT}</p>"))
    assert out["funding_statement"] == FUNDING_TEXT
    assert out["acknowledgments"] == ACK_TEXT


def test_funding_paragraph_under_the_acknowledgments_heading_is_the_funding_statement():
    out = _parse(_page(ack=f"<p><em>Funding</em>: {FUNDING_TEXT}</p>", footnote=""))
    assert out["funding_statement"] == FUNDING_TEXT
    assert out["acknowledgments"] is None  # the section holds nothing but the funding paragraph


def test_none_is_no_statement():
    out = _parse(_page(ack="<p><em>Funding:</em> None.</p>", footnote=""))
    assert out["funding_statement"] is None and out["acknowledgments"] is None
    out = _parse(_page())
    assert out["funding_statement"] is None and out["acknowledgments"] is None


def test_a_page_without_the_platform_marks_is_not_read():
    """SciEngine and elpub pages print a <p class="authors"> byline too: never AME's to read."""
    look_alike = _page(head='<link rel="stylesheet" href="https://www.sciengine.com/static/css/article.css"/>'
                            '<meta name="citation_publisher" content="Science China Press"/>'
                            '<meta name="citation_author" content="Sabrina Poonja"/>')
    parser = AMEPublishing(BeautifulSoup(look_alike, "lxml"))
    assert not parser.authors_found()
    assert not parser.is_publisher_specific_parser()


def test_platform_assets_alone_are_enough():
    """An AME page with no citation_publisher tag (actr.amegroups.org) is still read: its <head> loads AME's assets."""
    head = HEAD.replace('<meta name="citation_publisher" content="AME Publishing Company"/>', "")
    assert AMEPublishing(BeautifulSoup(_page(head=head), "lxml")).authors_found()


SINGLE_AFF_BYLINE = ('<div class="meta"><p class="authors">Taiyuan Liu<sup>^</sup>, Yonghao Liang, Sunil Kumar Lalwani, '
                     'Yingchao Zhang<sup>^</sup></p><p class="affiliation"><aff id="aff1"><institution>Department of '
                     'Breast Surgery</institution>, <institution>Second Hospital of Jilin University</institution>, '
                     '<country>China</country></aff></p><div class="correspond-author"><corresp id="cor1">'
                     '<em>Correspondence to:</em> Yingchao Zhang, MD. Department of Breast Surgery. Email: '
                     '<email>zyc@example.edu</email>.</corresp></div></div>')


def test_a_byline_with_one_unlabelled_affiliation():
    """One affiliation, no numbers: the names share one text node and the affiliation is everyone's (the parser used
    to crash here, so another parser's reading won and the back matter was lost)."""
    html = _page().replace(BYLINE, SINGLE_AFF_BYLINE)
    out = parse_page(html.encode(), "doi", URL)
    assert [a["name"] for a in out["authors"]] == ["Taiyuan Liu", "Yonghao Liang", "Sunil Kumar Lalwani",
                                                  "Yingchao Zhang"]
    assert all(a["affiliations"] == [{"name": "Department of Breast Surgery, Second Hospital of Jilin University, China"}]
               for a in out["authors"])
    assert [a["is_corresponding"] for a in out["authors"]] == [None, None, None, True]
    assert len(out["references"]) == 3


def test_an_unlabelled_affiliation_after_a_labelled_one_continues_it():
    byline = ('<div class="meta"><p class="authors">Marco Chiarelli<sup>1</sup>, Angelo Guttadauro<sup>2</sup></p>'
              '<p class="affiliation"><aff id="aff1"><sup>1</sup>Department of General Surgery, Ospedale Manzoni, '
              '<country>Italy</country>;</aff><aff id="aff2"><sup>2</sup>Department of Surgery,</aff><aff id="aff3">'
              'University of Milan-Bicocca, Monza, <country>Italy</country></aff></p></div>')
    authors = _parse(_page().replace(BYLINE, byline))["authors"]
    assert authors[1].affiliations == ["Department of Surgery, University of Milan-Bicocca, Monza, Italy"]
    assert authors[0].affiliations == ["Department of General Surgery, Ospedale Manzoni, Italy;"]


def test_abstract_label_is_not_abstract_text():
    html = _page().replace(BYLINE, BYLINE + '<div id="abstract"><p><strong>Abstract:</strong> Advanced Practice '
                                            'Providers are fundamental to oncology care.</p></div>')
    assert _parse(html)["abstract"] == "Advanced Practice Providers are fundamental to oncology care."
