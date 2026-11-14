"""Texila Journal article pages (texilajournal.com, oxjob #2210).

The site's own PHP template prints no citation_* meta tags: the DOI, a comma-separated "Authors :" line, an "Abstract:"
heading and a "References:" heading whose entries are Word-pasted paragraphs numbered "[1].", "[2]" ... No affiliations,
corresponding author, acknowledgments or funding section. Markup is cut down from stored pages (13 Nov 2026).
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.texilajournal import TexilaJournal

URL = "https://www.texilajournal.com/public-health/article/2726-factors-contributing-to"
SCRIPT = '<script src="https://www.texilajournal.com/commonfiles/js/common.js" type=text/javascript></script>'

ABSTRACT = ("Introduction: In Ghana, the Expanded Programme on Immunization has reduced infant mortality. "
            "Methods: A descriptive cross-sectional quantitative study involved 424 participants. "
            "Conclusion: Frequency of immunization sessions significantly influenced coverage.")

REFS = ('<p><span><span>[1].<span>&nbsp;&nbsp;\n</span></span></span><span>Andaleeb, S., 2001, Service quality '
        'perceptions and patient satisfaction, <i>Social Science and Medicine,</i> Vol.52, pp. 1359- 1370.</span></p>'
        '<p><font><span><br></span></font></p>'
        '<p><span>[2]<span> </span></span><span>Nuri, N. N., Sarker, M., 2019, Experience and perceived quality of care. '
        '<i>International Journal of Mental Health Systems,</i> 13(1), 46. </span><span><a><span>'
        'https://doi.org/10.1186/s13033-019-0303-x</span></a></span></p>'
        '<p>[3] Amzat, J., (2020). Faith effect and voice on early marriage. <i>SAGE Open.</i> '
        'doi:&nbsp;10.1177/2158244020919513.&nbsp;[CrossRef]</p>'
        '<p>[4]. Lu, W., 2020, Spatial study. Environment, 257(3), 330-338. '
        'https://doi.org/10.1016/j.jenvman.2020.110013).</p>')


def _page(authors="William Fosu Amankwaa, Michael Jeroen Adjabeng", abstract=f"<p><i><span>{ABSTRACT}</span></i></p>",
          refs=REFS, script=SCRIPT):
    return (f"<html><head><title> A title | Texila Journal </title>{script}</head><body>"
            '<h3 class="section-title">A title</h3>'
            '<div class="col-md-12 col-sm-12 col-xs-12"><div><b>DOI</b>: 10.21522/TIJPH.2013.12.03.Art062 </div></div>'
            f'<div class="col-md-12 col-sm-12 col-xs-12"><br> <div><b>Authors</b> : {authors}</div><p></p></div>'
            f'<div class="col-md-12 col-sm-12 col-xs-12"><h3>Abstract:</h3>{abstract}</div>'
            '<div class="col-md-12 col-sm-12 col-xs-12"><div style="clear:both;margin-top:30px;"></div>'
            f'<h3>References:</h3><div><p></p><div>{refs}</div></div></div>'
            "</body></html>")


def _out(html):
    return parse_page(html.encode(), "doi", URL)


def _parsed(html):
    return TexilaJournal(BeautifulSoup(html, "lxml")).parse()


def test_authors_come_from_the_comma_separated_byline():
    authors = _out(_page(authors="Innocent  Chinedu Udemezue, Ebenezer Obi Daniel, Amitabye Luximon-Ramma"))["authors"]
    assert [a["name"] for a in authors] == ["Innocent Chinedu Udemezue", "Ebenezer Obi Daniel", "Amitabye Luximon-Ramma"]
    assert all(a["affiliations"] == [] and not a["is_corresponding"] for a in authors)


def test_trailing_comma_in_byline_adds_no_empty_author():
    authors = _out(_page(authors="Sunarto, Setya Haksama, Sulikah, "))["authors"]
    assert [a["name"] for a in authors] == ["Sunarto", "Setya Haksama", "Sulikah"]


def test_abstract_is_the_text_under_its_heading():
    assert _out(_page())["abstract"] == ABSTRACT


def test_abstract_stops_before_keywords():
    abstract = (f"<p><span><i>{ABSTRACT}</i></span></p>"
                "<p><span><i>Keywords: Coping Strategies, Depression, Mental Health.</i></span></p>")
    assert _out(_page(abstract=abstract))["abstract"] == ABSTRACT


def test_abstract_without_a_paragraph_tag():
    assert _out(_page(abstract=f"<i><span>{ABSTRACT}</span></i>"))["abstract"] == ABSTRACT


def test_numbered_references_run_one_to_n_and_are_complete():
    parsed = _parsed(_page())
    refs = parsed["references"]
    assert [r["position"] for r in refs] == [1, 2, 3, 4]
    assert refs[0]["raw"].startswith("Andaleeb, S., 2001, Service quality")
    assert refs[0]["doi"] is None
    assert refs[1]["doi"] == "10.1186/s13033-019-0303-x"
    assert refs[2]["doi"] == "10.1177/2158244020919513"
    assert refs[3]["doi"] == "10.1016/j.jenvman.2020.110013"  # the closing bracket and full stop are not the DOI's
    assert not refs[2]["raw"].startswith("[")
    assert parsed["references_complete"] is True


def test_reference_without_its_number_makes_the_list_incomplete():
    refs = REFS + "<p>Odimegwu, C. O., Akinyemi, J. O., 2017, HIV-Stigma in Nigeria. AIDS Research and Treatment.</p>"
    parsed = _parsed(_page(refs=refs))
    assert len(parsed["references"]) == 5
    assert parsed["references_complete"] is False


def test_reference_outside_the_paragraphs_makes_the_list_incomplete():
    refs = REFS + "<span>Ifijeh, M., (2020). COVID19: Lagos Establishes Sample Collection Centres.</span>"
    assert _parsed(_page(refs=refs))["references_complete"] is False


def test_gap_in_numbering_makes_the_list_incomplete():
    refs = REFS.replace("[3] Amzat", "[5] Amzat")
    assert _parsed(_page(refs=refs))["references_complete"] is False


def test_no_acknowledgments_or_funding_on_the_page():
    parsed = _parsed(_page())
    assert parsed["acknowledgments"] is None and parsed["funding_statement"] is None


def test_issue_listing_page_is_not_read():
    item = ('<div class="col-md-12"><h3>Abstract:</h3><p>An abstract.</p></div>'
            '<div class="col-md-12"><h3>References:</h3><p>[1] A reference.</p></div>')
    html = f"<html><head>{SCRIPT}</head><body><h3>September 2024</h3>{item}{item}</body></html>"
    assert not TexilaJournal(BeautifulSoup(html, "lxml")).authors_found()


def test_same_markup_on_another_site_is_not_claimed():
    html = _page(script='<script src="https://www.example-journal.org/commonfiles/js/common.js"></script>')
    assert not TexilaJournal(BeautifulSoup(html, "lxml")).is_publisher_specific_parser()
    # a script that only mentions the domain in its path or query does not count either
    html = _page(script='<script src="https://cdn.example.org/texilajournal.com/common.js"></script>')
    assert not TexilaJournal(BeautifulSoup(html, "lxml")).is_publisher_specific_parser()
