"""MedCrave Online (medcraveonline.com) article pages (oxjob #2338).

Markup is cut down from stored medcraveonline.com pages. The site's own PHP template prints the byline in
``h4.allauthornames`` (names, numbered ``<sup>`` marks, ORCID ``<sup>``s and an envelope ``<sup>`` after one author,
then the captcha pop-up), the affiliations in the next ``<p>`` one per ``<br>`` line, then a "Correspondence:" line;
the body is ``h1.atsdhdNew`` headings, each followed by a ``div.fultextNew``. Its citation_author meta tag is broken
(``content=">``), so before this parser Parseland read no byline on these pages.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.medcrave import MedCrave

URL = "https://medcraveonline.com/MOJPH/a-study.html"
PUBLISHER = '<meta name="citation_publisher" content="MedCrave Publishing">'
ABSTRACT_TEXT = ("COVID-19 has been a public health crisis for quite a long time worldwide. Providing primary health "
                 "care during this has proven to be quite difficult. Telemedicine played an imperative part in this by "
                 "minimizing virus spread and utilizing the time of healthcare experts.")
ORCID = ('<sup><a href="https://orcid.org/0009-0008-8623-3062" target="_blank">'
         '<img src="http://medcraveonline.com/images/orcid-icon.png" style="width:16px; height:16px"/></a></sup>')
ENVELOPE = ('<sup><i class="fa fa-envelope" aria-hidden="true" data-toggle="modal" data-target="#emailModal"></i></sup>'
            '<div id="emailModal" class="modal fade" role="dialog"><div class="modal-content">'
            '<h4 class="modal-title">Verify Captcha</h4><p>Please type the correct Captcha word to see email ID.</p>'
            '<form><input name="name" id="name" /></form></div></div>')
SCRIPT = '<script type="text/javascript">function clickButton(){ var name = 1; }</script>'


def _section(title, body):
    return (f'<!--Hedding content start-->\n<h1 class="atsdhdNew">{title}</h1>\n'
            f'<div class="fultextNew">{body}</div>\n<!--Hedding content End-->')


ABSTRACT = _section("Abstract", f'<p>{ABSTRACT_TEXT}</p><p><strong>Keywords: </strong>telemedicine, pandemic</p>')
ACK = _section("Acknowledgments", '<p>The authors are grateful to the Department of Pharmaceutical Technology, '
                                  'University of Dhaka for their support.</p>')
ACK_NONE = _section("Acknowledgements", "<p>None.</p>")
FUNDING = _section("Funding ", '<p>The authors received no financial support for the research, authorship, and/or '
                               'publication of this article.</p>')
REFS = _section("References", '<ol>'
                '<li class="ref" id="ref1"><a href="https://pubmed.ncbi.nlm.nih.gov/32888871/">Liu Q, Xu K, Wang X, '
                'et al. From SARS to COVID-19: What lessons have we learned? <em>J Infect Public Health</em>. '
                '2020;13(11):1611&ndash;1618.</a></li>'
                '<li class="ref" id="ref2"><a href="https://doi.org/10.1007/s10916-020-01596-5">Anthony Jnr B. Use of '
                'telemedicine and virtual care for remote treatment. <em>J Med Syst</em>. 2020;44(7):132.</a></li>'
                '<li class="ref" id="ref3">Perrone G, Zerbo S, Bilotta C, et al. Telemedicine during Covid-19 '
                'pandemic: advantage or critical issue? <em>Med Leg J</em>. 2020;88(2):76&ndash;77.</li>'
                '</ol>')

BYLINE = (f' Tasnuma Tabassum,<sup>1</sup> {ORCID}  Adeeba Jaheen Faruqui,<sup>1,2</sup> {ORCID}  '
          f'Md Elias Al-Mamun<sup>1</sup> {ORCID} {SCRIPT} {ENVELOPE}')
AFFS = ('<p><sup>1</sup>Department of Pharmaceutical Technology, University of Dhaka, Bangladesh<br />'
        '<sup>2</sup>Department of Pharmacy, University of Asia Pacific, Dhaka, Bangladesh<br /></p>')
CORRESPONDENCE = ('<p><strong>Correspondence:</strong> Md Elias Al-Mamun, Department of Pharmaceutical Technology, '
                  'University of Dhaka, Bangladesh, Tel 01710857444</p>')


def _page(byline=BYLINE, affs=AFFS, correspondence=CORRESPONDENCE, sections=ABSTRACT + ACK + FUNDING + REFS,
          metas=PUBLISHER):
    header = (f'<div class="atttlNew"><h1>A study</h1><h4 class="allauthornames">{byline}</h4>{affs}{correspondence}'
              f'<p><span class="font-weight-bold">Received:</span> January 18, 2025 | '
              f'<span class="font-weight-bold">Published:</span> March 7, 2025</p>'
              f'<p><strong>Citation: </strong>Tabassum T, Faruqui AJ, Al-Mamun ME. A study. <i>MOJ Public Health</i>.'
              f' 2025;14(1):45-50.</p></div>')
    return (f'<html><head><meta name="abstract" content="{ABSTRACT_TEXT}">{metas}'
            f'<meta name="citation_title" content="A study" /><meta name="citation_author" content=">'
            f'<meta name="citation_doi" content="10.15406/mojph.2025.14.00470"></head>'
            f'<body><div class="innercontentbox">{header}{sections}</div></body></html>')


def _parsed(html):
    return MedCrave(BeautifulSoup(html, "lxml")).parse()


def test_claims_medcrave_pages():
    parser = MedCrave(BeautifulSoup(_page(), "lxml"))
    assert parser.is_publisher_specific_parser()
    assert parser.authors_found()


def test_byline_with_numbered_affiliations_and_correspondence():
    out = parse_page(_page().encode(), "doi", URL)
    assert [a["name"] for a in out["authors"]] == ["Tasnuma Tabassum", "Adeeba Jaheen Faruqui", "Md Elias Al-Mamun"]
    assert [[x["name"] for x in a["affiliations"]] for a in out["authors"]] == [
        ["Department of Pharmaceutical Technology, University of Dhaka, Bangladesh"],
        ["Department of Pharmaceutical Technology, University of Dhaka, Bangladesh",
         "Department of Pharmacy, University of Asia Pacific, Dhaka, Bangladesh"],
        ["Department of Pharmaceutical Technology, University of Dhaka, Bangladesh"]]
    assert [a["is_corresponding"] for a in out["authors"]] == [False, False, True]


def test_captcha_popup_text_is_not_a_name():
    names = [a["name"] for a in _parsed(_page())["authors"]]
    assert not any("Captcha" in n or "clickButton" in n for n in names)


def test_unnumbered_affiliation_goes_to_every_author():
    byline = f' Kochnev VI, Kotlyarevskiy EV {ENVELOPE}'
    affs = '<p>Professor of Techno sciences, MADI, Russia<br/></p>'
    corr = '<p><strong>Correspondence:</strong> Kotlyarevskiy EV, Professor Dr Techno sciences, MADI, Russia</p>'
    out = parse_page(_page(byline, affs, corr).encode(), "doi", URL)
    assert [a["name"] for a in out["authors"]] == ["Kochnev VI", "Kotlyarevskiy EV"]
    assert all([x["name"] for x in a["affiliations"]] == ["Professor of Techno sciences, MADI, Russia"]
               for a in out["authors"])
    assert [a["is_corresponding"] for a in out["authors"]] == [False, True]


def test_correspondence_line_names_author_in_another_form():
    # "Acosta G" in the line is "Gerardo Acosta" in the byline; no envelope on this page
    byline = 'Maira Madriz Mendoza,<sup>2</sup>  Gerardo Acosta<sup>1</sup>'
    affs = ('<p><sup>1</sup>Institute of Mathematics, National Autonomous University of Mexico, Mexico<br/>'
            '<sup>2</sup>Autonomous Technological Institute of Mexico, Mexico<br/></p>')
    corr = '<p><strong>Correspondence:</strong> Acosta G, Institute of Mathematics, Mexico</p>'
    authors = _parsed(_page(byline, affs, corr))["authors"]
    assert [a["is_corresponding"] for a in authors] == [False, True]
    assert authors[0]["affiliations"] == ["Autonomous Technological Institute of Mexico, Mexico"]


def test_envelope_and_correspondence_line_on_different_authors_mark_both():
    # the envelope follows the first author while the line names the second: the page marks both (label-v1)
    byline = f' Milad  Yusefi,{ORCID} {ENVELOPE} Nasrullah  Rastegar-Pouyani,{ORCID}  Rasoul  Karamiani{ORCID}'
    affs = '<p>Department of Biology, Faculty of Science, Razi University, Iran<br/></p>'
    corr = '<p><strong>Correspondence:</strong> Nasrullah Rastegar-Pouyani, Department of Biology, Iran</p>'
    authors = _parsed(_page(byline, affs, corr))["authors"]
    assert [a["name"] for a in authors] == ["Milad Yusefi", "Nasrullah Rastegar-Pouyani", "Rasoul Karamiani"]
    assert [a["is_corresponding"] for a in authors] == [True, True, False]


def test_empty_affiliation_paragraph_gives_no_affiliations():
    corr = '<p><strong>Correspondence:</strong> Hasmah Abdullah, School of Health Science, Malaysia</p>'
    authors = _parsed(_page(' Noor Sisin, Hasmah Abdullah  ', '<p></p>', corr))["authors"]
    assert [a["affiliations"] for a in authors] == [[], []]
    assert [a["is_corresponding"] for a in authors] == [False, True]


def test_abstract_stays_the_meta_tag_reading():
    assert parse_page(_page().encode(), "doi", URL)["abstract"] == ABSTRACT_TEXT


def test_acknowledgments_and_funding():
    out = _parsed(_page())
    assert out["acknowledgments"] == ("The authors are grateful to the Department of Pharmaceutical Technology, "
                                      "University of Dhaka for their support.")
    assert out["funding_statement"].startswith("The authors received no financial support")


def test_none_section_is_not_a_statement():
    out = _parsed(_page(sections=ABSTRACT + ACK_NONE + REFS))
    assert out["acknowledgments"] is None
    assert out["funding_statement"] is None


def test_reference_list_whole():
    out = _parsed(_page())
    assert [r["position"] for r in out["references"]] == [1, 2, 3]
    assert out["references"][0]["raw"].startswith("Liu Q, Xu K, Wang X, et al. From SARS to COVID-19")
    assert out["references"][1]["doi"] == "10.1007/s10916-020-01596-5"
    assert out["references"][0]["doi"] is None
    assert out["references_complete"] is True


def test_reference_list_with_gap_is_not_whole():
    refs = REFS.replace('id="ref2"', 'id="ref5"')
    out = _parsed(_page(sections=ABSTRACT + refs))
    assert len(out["references"]) == 3
    assert out["references_complete"] is False


def test_older_template_reference_list_follows_its_heading():
    refs = ('<h1 class="atsdhd"><a name="References"></a><a id="References"></a>References</h1>'
            '<ol id="j"><li class="ref"><a href="https://www.ncbi.nlm.nih.gov/pubmed/1">Wistuba II, Gazdar AF (2004) '
            'Gallbladder cancer: lessons from a rare tumour. Nat Rev Cancer 4(9): 695-706.</a></li>'
            '<li class="ref">Lazcano Ponce EC, Miquel JF (2001) Epidemiology of gallbladder cancer. Clin Epidemiol 51: '
            '349-364.</li></ol>')
    out = _parsed(_page(sections=refs))
    assert len(out["references"]) == 2
    assert out["references_complete"] is True


def test_nested_lists_are_not_whole():
    refs = ('<h1 class="atsdhd">References</h1><ol id="j"><ol><li class="ref">Cameron KL (2011) Incidence of '
            'osteoarthritis. Arthritis Rheum 63(10): 2974-2982.</li></ol></ol>')
    out = _parsed(_page(sections=refs))
    assert len(out["references"]) == 1
    assert out["references_complete"] is False


def test_issue_page_is_not_read():
    # an issue's table of contents: no byline block, no citation_publisher tag
    html = ('<html><head><title>Volume 4 - Issue 3</title></head><body><h1>Volume 4 - Issue 3</h1>'
            '<div class="article"><a href="x.html">A study</a><p>Ann Lee, Bo Kim</p></div></body></html>')
    assert not MedCrave(BeautifulSoup(html, "lxml")).authors_found()


def test_lookalike_from_another_publisher_is_not_claimed():
    # the same byline markup under another publisher's citation_publisher tag
    html = _page(metas='<meta name="citation_publisher" content="Lupine Publishers">')
    parser = MedCrave(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
