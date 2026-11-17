"""ClinicalTrials.gov study records, classic "Full Text View" (clinicaltrials.gov/ct2/show/NCT...) (oxjob #2338).

DOI prefix 10.31525 (trial registrations) resolves to these pages. Markup is cut down from stored pages (17 Nov 2026).
No parser claimed them and the generic one read nothing: the record's "Brief Summary" sits under a label div, not an
"Abstract" heading or a meta tag. Both blind labellers (label-v1) give the Brief Summary as the abstract (2 of 2 build
pages), never the Detailed Description; the sponsor, responsible party and principal investigator are not authors.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.clinicaltrials import ClinicalTrialsGov

URL = "https://doi.org/10.31525/ct1-nct04036864"
HEAD = ('<head><title>A Study - Full Text View - ClinicalTrials.gov</title>'
        '<link href="/ct2/show/NCT04036864" rel="canonical"/>'
        '<meta property="og:type" content="article" />'
        '<meta property="og:title" content="A Study - Full Text View - ClinicalTrials.gov">'
        '<meta property="og:url" content="https://clinicaltrials.gov/ct2/show/NCT04036864"></head>')

P1 = ("Singers are over-represented in phoniatric consultation; they present increased risk of developing voice "
      "disorders. They represent a specific population among phoniatric patients.")
P2 = ("Voice assessment of dysodic singers includes aerodynamic voice measurements. The use of aerodynamic "
      "measurements for the diagnosis of voice pathologies is now widely demonstrated.")
DETAIL = "This detailed description is longer protocol text and is not the record's summary."


def _summary(inner):
    return ('<div class="tr-indent2" style="margin-top:2ex">'
            '<div class="ct-body3">Brief Summary:</div>\r\n'
            f'  <div class="ct-body3 tr-indent2">{inner}</div><br/>'
            '<table class="ct-data_table tr-data_table"><tr><th>Condition or disease</th></tr></table></div>')


def _detail():
    return ('<div class="tr-indent2"><div class="ct-body3">Detailed Description:</div>'
            f'<div class="ct-body3 tr-indent2">{DETAIL}</div></div>')


PARTY = ('<table class="ct-layout_table tr-tableStyle tr-moreInfo"><tr><td class="ct-nowrap">Responsible Party:</td>'
         '<td>Marion Beaud, Principal Investigator, University Hospital, Montpellier</td></tr></table>'
         '<span class="ct-header3"> Publications:</span><div class="tr-indent2"><div style="margin-top:2ex">'
         '<a href="/ct2/bye/x">Watson NF. Health Care Savings. J Clin Sleep Med. 2016;12(8):1075-7. '
         'doi: 10.5664/jcsm.6034.</a></div></div>')


def _page(body, head=HEAD):
    return f'<!DOCTYPE html><html lang="en">{head}<body><div id="tab-body">{body}</div></body></html>'


def _paragraphs():
    return (f'<p style="margin-top:1ex; margin-bottom:1ex;">{P1}</p>\r\n'
            f'  <p style="margin-top:0ex; margin-bottom:1ex;">{P2}</p>')


def test_brief_summary_paragraphs_are_the_abstract():
    out = parse_page(_page(_summary(_paragraphs()) + _detail() + PARTY).encode(), "doi", URL)
    assert out["abstract"] == f"{P1}\n{P2}"


def test_brief_summary_as_plain_text():
    text = ("Epilepsy is the second commonest chronic neurological disorder in developed countries,\r\n Comorbidity "
            "refers to the co-occurrence of two conditions with a greater frequency than found in the population")
    out = parse_page(_page(_summary(text) + _detail()).encode(), "doi", URL)
    assert out["abstract"] == " ".join(text.split())


def test_responsible_party_and_investigator_are_not_authors():
    out = parse_page(_page(_summary(_paragraphs()) + PARTY).encode(), "doi", URL)
    assert out["authors"] == []


def test_publications_are_not_a_whole_reference_list():
    """The record's "Publications:" entries are unnumbered and carry no count: no positive evidence of a whole list."""
    soup = BeautifulSoup(_page(_summary(_paragraphs()) + PARTY), "lxml")
    parsed = ClinicalTrialsGov(soup).parse()
    assert not parsed.get("references_complete")
    assert not parsed.get("acknowledgments") and not parsed.get("funding_statement")


def test_look_alike_page_is_not_claimed():
    """The same label markup on a page that is not ClinicalTrials.gov's (a mirror or another registry) is not taken."""
    head = HEAD.replace("https://clinicaltrials.gov/ct2/show/", "https://registry.example.org/show/")
    soup = BeautifulSoup(_page(_summary(_paragraphs()), head=head), "lxml")
    parser = ClinicalTrialsGov(soup)
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    out = parse_page(_page(_summary(_paragraphs()), head=head).encode(), "doi", URL)
    assert out["abstract"] is None


def test_claimed_record_without_a_summary_is_left_alone():
    soup = BeautifulSoup(_page(PARTY), "lxml")
    parser = ClinicalTrialsGov(soup)
    assert parser.is_publisher_specific_parser()
    assert not parser.authors_found()
