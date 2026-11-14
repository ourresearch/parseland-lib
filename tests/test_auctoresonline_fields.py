"""Auctores (auctoresonline.com) article pages (oxjob #2210).

Markup is cut down from stored Auctores pages (13 Nov 2026). The site's own PHP template prints no citation_* meta
tags, so before this parser Parseland read nothing from it: the byline is a ``div.u-list`` list with superscript
affiliation numbers and a ``*`` explained by the ``*Corresponding Author:`` note, the abstract sits in
``div.parent-cls[data-for="abstract"]``, and the references are one ``<ol>`` under ``h4#references``.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.auctoresonline import Auctores

URL = "https://auctoresonline.com/article/a-title"
HEAD = ('<meta property="og:site_name" content="Auctores" />'
        '<meta property="og:url" content="https://auctoresonline.com/article/a-title" />'
        '<meta name="description" content="Short cut description">')


def _li(name, sup):
    sup_html = f'<sup><a href="#author1">{sup}</a></sup>' if sup is not None else ''
    return f'<li>\n   {name}   {sup_html}\n</li>'


def _page(byline, affs, corr="*Corresponding Author:</b> Ann Lee, Department of Botany, Cairo University, Egypt.",
          desc="", refs="", head=HEAD):
    corr_html = f'<p><b>{corr}</p>' if corr else ''
    return (f'<html><head><title>A title | Auctores</title>{head}</head><body>'
            '<div class="article-details row"><div>'
            '<p class="article-type">Research Article | <span>DOI: <a href="https://doi.org/10.31579/2693-7247/208">'
            'https://doi.org/10.31579/2693-7247/208</a></span></p><h2>A title</h2>'
            f'<div class="u-list"><ul>{"".join(byline)}</ul>{affs}</div>'
            f'<div class="copyrights">{corr_html}<p><b>Citation:</b> Ann Lee, (2024), A title, J. Pharm, 7(9)</p>'
            '<p><b>Copyright:</b> &copy; 2024, Ann Lee. This is an open access article.</p></div>'
            '<div class="article-desc ck-content">'
            '<h4 class="article-det-header" id="abstract">Abstract</h4>'
            '<div class="parent-cls" data-for="abstract"><p><strong>Background:</strong> Ozone gas was tested as a '
            'terminal disinfectant against six reference strains for up to forty minutes.</p>'
            '<p><strong>Results:</strong> Viability fell by more than 98% after thirty minutes for most strains.</p></div>'
            '<h4 class="article-det-header" id="introduction">Introduction</h4>'
            '<div class="parent-cls" data-for="introduction"><p>Sanitation is a challenge.</p></div>'
            f'{desc}'
            f'<h4 id="references">References</h4><div class="ref-links"><ol>{refs}</ol></div>'
            '</div></div></div></body></html>')


def _ref(i, text):
    return (f'<li id="R{i}">{text}<br/> <span class="reflinks"> <a href="https://scholar.google.com/x">View at Publisher'
            '</a> | <a href="https://scholar.google.com/y">View at Google Scholar</a> </span> </li>')


NUMBERED = ['<p>1 Department of Botany, Cairo University, Egypt.</p>',
            '<p>2Department of Food Chemistry, National Nutrition Institute, Cairo, Egypt.</p>']
BYLINE = [_li("Ann Lee", "1*"), _li("Bo Chen", "1,2"), _li("Cy Diaz", "2")]


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _affs(author):
    return [a["name"] if isinstance(a, dict) else a for a in author["affiliations"]]


def _raw(html):
    return Auctores(BeautifulSoup(html, "lxml")).parse()


def test_authors_and_numbered_affiliations():
    authors = _parse(_page(BYLINE, "".join(NUMBERED)))["authors"]
    assert [a["name"] for a in authors] == ["Ann Lee", "Bo Chen", "Cy Diaz"]
    assert _affs(authors[0]) == ["Department of Botany, Cairo University, Egypt."]
    assert _affs(authors[1]) == ["Department of Botany, Cairo University, Egypt.",
                                          "Department of Food Chemistry, National Nutrition Institute, Cairo, Egypt."]
    assert _affs(authors[2]) == ["Department of Food Chemistry, National Nutrition Institute, Cairo, Egypt."]


def test_star_marks_the_corresponding_author():
    authors = _parse(_page(BYLINE, "".join(NUMBERED)))["authors"]
    assert [a["is_corresponding"] for a in authors] == [True, False, False]


def test_star_without_the_note_is_no_mark():
    authors = _parse(_page(BYLINE, "".join(NUMBERED), corr=None))["authors"]
    assert not any(a["is_corresponding"] for a in authors)


def test_note_names_the_corresponding_author_when_no_star():
    byline = [_li("Hakan Ercan", None), _li("Ilija Golubović,", None)]
    html = _page(byline, "<p>Hatay Mustafa Kemal University, Turkey.</p>",
                 corr="*Corresponding Author:</b> Ilija Golubovic., Clinic for Digestive Surgery, Nis, Serbia.")
    authors = _parse(html)["authors"]
    assert [a["name"] for a in authors] == ["Hakan Ercan", "Ilija Golubović"]  # trailing comma dropped
    assert [a["is_corresponding"] for a in authors] == [False, True]


def test_unnumbered_affiliation_goes_to_every_author():
    byline = [_li("Bon E*", None), _li("Maksimovich N.Ye", None)]  # star typed into the name itself
    html = _page(byline, "<p>Grodno State Medical University, Grodno, Belarus.&nbsp;</p>",
                 corr="*Corresponding Author:</b> Elizaveta I Bon, Grodno State Medical University.")
    authors = _parse(html)["authors"]
    assert [a["name"] for a in authors] == ["Bon E", "Maksimovich N.Ye"]
    assert all(_affs(a) == ["Grodno State Medical University, Grodno, Belarus."] for a in authors)
    assert [a["is_corresponding"] for a in authors] == [True, False]


def test_affiliations_in_one_paragraph_split_on_line_breaks():
    affs = ('<p>1 Center for Biological and Health Sciences, Brazil &nbsp;<br/>2 Medical Student, Pontifical Catholic '
            'University of Minas Gerais, Betim</p>')
    authors = _parse(_page([_li("Ann Lee", "1*"), _li("Bo Chen", "2")], affs))["authors"]
    assert _affs(authors[0]) == ["Center for Biological and Health Sciences, Brazil"]
    assert _affs(authors[1]) == ["Medical Student, Pontifical Catholic University of Minas Gerais, Betim"]


def test_one_affiliation_line_for_several_numbers():
    affs = '<p>1 Center for Health Sciences, Brazil<br/>2,3 Educational Foundation of Penapolis, Brazil<br/> </p>'
    authors = _parse(_page([_li("Ann Lee", "1*"), _li("Bo Chen", "2"), _li("Cy Diaz", "3")], affs))["authors"]
    assert _affs(authors[1]) == _affs(authors[2]) == ["Educational Foundation of Penapolis, Brazil"]


def test_orcid_link_text_is_not_part_of_the_name():
    li = ('<li> Luis F. Pereira <a href="https://orcid.org/0000-0002-7574-6611"><img src="orcid.png"/>ID</a> '
          '<sup><a href="#author1">1</a></sup></li>')
    authors = _parse(_page([li, _li("Ann Lee", "1*")], NUMBERED[0]))["authors"]
    assert [a["name"] for a in authors] == ["Luis F. Pereira", "Ann Lee"]


def test_abstract_is_read_in_full():
    abstract = _parse(_page(BYLINE, "".join(NUMBERED)))["abstract"]
    assert abstract.startswith("Background: Ozone gas was tested")
    assert abstract.endswith("after thirty minutes for most strains.")


def test_references_whole_list():
    refs = _ref(0, "Alvaro, J. E. (2009). Effects of peracetic acid. Journal of Food Engineering, 95(1), 11-15.") + \
        _ref(1, "Teh, C. H. (2013). Invitro antibacterial activity. Med Vet Entomol. doi: 10.1111/mve.12012")
    out = _raw(_page(BYLINE, "".join(NUMBERED), refs=refs))
    assert out["references"] == [
        {"position": 1, "raw": "Alvaro, J. E. (2009). Effects of peracetic acid. Journal of Food Engineering, 95(1), 11-15.",
         "doi": None},
        {"position": 2, "raw": "Teh, C. H. (2013). Invitro antibacterial activity. Med Vet Entomol. doi: 10.1111/mve.12012",
         "doi": "10.1111/mve.12012"}]
    assert out["references_complete"] is True


def test_empty_reference_placeholder_is_no_list():
    out = _raw(_page(BYLINE, "".join(NUMBERED), refs=_ref(0, ".")))
    assert out["references"] is None
    assert out["references_complete"] is False


def test_reference_list_with_a_gap_is_not_complete():
    refs = _ref(0, "First reference, Journal A, 2001, 1-2.") + _ref(2, "Third reference, Journal C, 2003, 5-6.")
    out = _raw(_page(BYLINE, "".join(NUMBERED), refs=refs))
    assert len(out["references"]) == 2
    assert out["references_complete"] is False


def test_acknowledgments_section_and_funding_label():
    desc = ('<h4 class="article-det-header" id="acknowledgment">Acknowledgment</h4>'
            '<div class="parent-cls" data-for="acknowledgment"><p>We thank the laboratory staff.</p>'
            '<p>We thank the hospital.</p></div>'
            '<h4 class="article-det-header" id="conclusion">Conclusion</h4>'
            '<div class="parent-cls" data-for="conclusion"><p>It works.</p>'
            '<p><strong>Conflict of interest:</strong> None declared.</p>'
            '<p><strong>Funding:</strong> No funds were received for this manuscript.</p></div>')
    out = _raw(_page(BYLINE, "".join(NUMBERED), desc=desc))
    assert out["acknowledgments"] == "We thank the laboratory staff.\nWe thank the hospital."
    assert out["funding_statement"] == "No funds were received for this manuscript."


def test_bold_label_paragraph_heads_the_next_paragraph():
    desc = ('<h4 class="article-det-header" id="conclusion">Conclusion</h4>'
            '<div class="parent-cls" data-for="conclusion"><p>It works.</p>'
            '<p><strong>Acknowledgement</strong></p><p>Dedicated to the memory of two scientists.</p>'
            '<p><strong>Funding Statement </strong></p><p>This study was not supported by any funder.</p>'
            '<p><strong>Author Contributions</strong></p><p>All authors wrote the paper.</p></div>')
    out = _raw(_page(BYLINE, "".join(NUMBERED), desc=desc))
    assert out["acknowledgments"] == "Dedicated to the memory of two scientists."
    assert out["funding_statement"] == "This study was not supported by any funder."


def test_combined_acknowledgments_and_funding_heading_goes_to_acknowledgments():
    desc = ('<h4 class="article-det-header" id="acknowledgments-and-funding">Acknowledgments and Funding</h4>'
            '<div class="parent-cls" data-for="acknowledgments-and-funding"><p>Supported by grant 1400120310169.</p></div>')
    out = _raw(_page(BYLINE, "".join(NUMBERED), desc=desc))
    assert out["acknowledgments"] == "Supported by grant 1400120310169."
    assert out["funding_statement"] is None


def test_declarations_under_an_acknowledgements_heading():
    # the heading says Acknowledgements but the section holds only labelled declarations
    desc = ('<h4 class="article-det-header" id="acknowledgements-">Acknowledgements </h4>'
            '<div class="parent-cls" data-for="acknowledgements-"><p><strong>Funding: </strong>None.<strong> </strong></p>'
            '<p><strong>Conflicts of Interest:</strong> The authors have no conflicts of interest to declare.</p></div>')
    out = _raw(_page(BYLINE, "".join(NUMBERED), desc=desc))
    assert out["acknowledgments"] is None
    assert out["funding_statement"] == "None."


def test_no_new_fields_when_the_page_shows_none():
    out = _raw(_page(BYLINE, "".join(NUMBERED)))
    assert out["acknowledgments"] is None and out["funding_statement"] is None
    assert out["references"] is None and out["references_complete"] is False


def test_same_markup_on_another_site_is_not_claimed():
    head = ('<meta property="og:site_name" content="Other Press" />'
            '<meta property="og:url" content="https://otherpress.example.org/article/a-title" />')
    html = _page(BYLINE, "".join(NUMBERED), head=head)
    assert not Auctores(BeautifulSoup(html, "lxml")).is_publisher_specific_parser()
    assert not Auctores(BeautifulSoup(html, "lxml")).authors_found()
    assert parse_page(html.encode(), "doi", "https://otherpress.example.org/article/a-title")["authors"] == []
