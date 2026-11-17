"""EMH Swiss Medical Publishers' TYPO3 journal pages (saez.ch, bullmed.ch, smw.ch, primary-hospital-care.ch, ...;
oxjob #2338).

Markup is cut down from stored pages of the journals' full-text layout (17 Nov 2026): a byline `p.authors` in
`#section-authors` whose names carry affiliation markers (bare <sup> letters, or <a class="xref aff"> links to the
affiliation's id), `p.affiliation` entries, a "Correspondence" / "Korrespondenzadresse" section naming the
corresponding author, and `p.ref-list` references numbered 1..n. Medical Forum's layout prints its "Literatur" list
in accordion boxes. The parser used to claim bullmed.ch pages only and read none of the correspondence or references.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.emh_swiss_medical import EMHSwissMedical

URL = "https://doi.org/10.4414/smw.2021.20464"
HEAD = ('<meta property="og:url" content="https://smw.ch/article/doi/smw.2021.20464"/>'
        '<meta name="citation_doi" content="10.4414/smw.2021.20464"/>'
        '<meta name="citation_publisher" content="EMH Media"/>'
        '<meta name="citation_author" content=", "/>'
        '<meta name="generator" content="TYPO3 CMS"/>')


def _page(body, head=HEAD):
    return f'<html><head>{head}</head><body><div id="maincolumn"><article>{body}</article></div></body></html>'


SMW_BYLINE = (
    '<section class="paragraph" id="section-authors"><p class="authors" id="b1">'
    'Sandro T. Stoffel<a class="xref aff" href="#affa"><sup>a</sup></a><a class="xref aff" href="#affb"><sup>b</sup>'
    '</a><a class="xref fn" href="#fn1"><sup>*</sup></a>, Roger von Moos<a class="xref aff" href="#affc"><sup>c</sup></a>'
    '<a class="xref fn" href="#fn1"><sup>*</sup></a>, Michael Mark<a class="xref aff" href="#affc"><sup>c</sup></a>'
    '</p></section>'
    '<section class="paragraph accordion-group" id="section-affiliation"><div class="accordion-body collapse">'
    '<p class="affiliation" id="affa"><sup>a</sup> Institute of Pharmaceutical Medicine, University of Basel</p>'
    '<p class="affiliation" id="affb"><sup>b</sup> SAKK Coordinating Centre, Bern, Switzerland</p>'
    '<p class="affiliation" id="affc"><sup>c</sup> Kantonsspital Graubünden, Chur, Switzerland</p>'
    '</div></section>')
SMW_CORRESPONDENCE = (
    '<section class="paragraph" id="section-correspondence"><h3 class="correspondence">Correspondence</h3>'
    '<p class="correspondence"><em>Michael Mark, MD</em>, <em>Kantonsspital Graubünden</em>, '
    '<em>michael.mark[at]ksgr.ch</em></p></section>')
SMW_REFERENCES = (
    '<section class="paragraph" id="section-references"><h3 class="ref-list-title">References</h3>'
    '<p class="ref-list"><span class="ref-list-num">1</span> <span class="ref-list-text">So A, Chin J. Management of '
    'skeletal-related events. Can Urol Assoc J. 2012;6(6):465–70. <a class="pubid" '
    'href="http://dx.doi.org/10.5489/cuaj.117">http://dx.doi.org/10.5489/cuaj.117</a> <a class="pubid" '
    'href="http://www.ncbi.nlm.nih.gov/entrez/query.fcgi?list_uids=23282666">PubMed</a></span></p>'
    '<p class="ref-list"><span class="ref-list-num">2</span> <span class="ref-list-text">Weinfurt KP, Li Y. The '
    'significance of skeletal-related events. Ann Oncol. 2005;16(4):579–84.</span></p>'
    '</section>')
SMW_BACK = (
    '<section class="paragraph" id="section-acknowledgements"><h3 class="acknowledgements">Acknowledgments</h3>'
    '<p class="acknowledgements">We thank NACR for the data on the total number of patients.</p></section>'
    '<section class="paragraph" id="section-disclosures"><h3 class="disclosures">Financial disclosure</h3>'
    '<p class="disclosures">This study was sponsored by Amgen.</p></section>'
    '<section class="paragraph" id="section-interests"><h3 class="interests">Potential competing interests</h3>'
    '<p class="interests">Roger von Moos has participated in advisory boards.</p></section>')
SMW = _page(SMW_BYLINE + SMW_BACK + SMW_CORRESPONDENCE + SMW_REFERENCES)


def _authors(html):
    return parse_page(html.encode(), "doi", URL)["authors"]


def _parse(html):
    return EMHSwissMedical(BeautifulSoup(html, "lxml")).parse()


def test_byline_names_and_linked_affiliations():
    authors = _authors(SMW)
    assert [a["name"] for a in authors] == ["Sandro T. Stoffel", "Roger von Moos", "Michael Mark"]
    assert [x["name"] for x in authors[0]["affiliations"]] == [
        "Institute of Pharmaceutical Medicine, University of Basel", "SAKK Coordinating Centre, Bern, Switzerland"]
    assert [x["name"] for x in authors[2]["affiliations"]] == ["Kantonsspital Graubünden, Chur, Switzerland"]


def test_markers_whose_link_goes_nowhere_link_by_letter():
    body = ('<section id="section-authors"><p class="authors">Maciej Albiński<a class="xref" href="#da39"><sup>a</sup>'
            '</a><a class="xref" href="#da39"><sup>b</sup></a>, Christian Balmer<a class="xref" href="#da39"><sup>a</sup>'
            '</a></p></section><section id="section-affiliation"><div class="accordion-body">'
            '<p class="affiliation" id="x1"><sup>a</sup> University Children\'s Hospital Zurich, Switzerland</p>'
            '<p class="affiliation" id="x2"><sup>b</sup> Lausanne University Hospital, Switzerland</p></div></section>')
    authors = _authors(_page(body))
    assert [[x["name"] for x in a["affiliations"]] for a in authors] == [
        ["University Children's Hospital Zurich, Switzerland", "Lausanne University Hospital, Switzerland"],
        ["University Children's Hospital Zurich, Switzerland"]]


def test_correspondence_section_marks_the_author_it_names():
    assert [a["name"] for a in _authors(SMW) if a["is_corresponding"]] == ["Michael Mark"]


def test_correspondence_naming_someone_else_marks_no_one():
    body = ('<section id="section-authors"><p class="authors">Bernadette Häfliger Berger</p></section>'
            '<section id="section-correspondence"><h3 class="correspondence">Korrespondenzadresse</h3>'
            '<p class="correspondence">Bruno Schmucki<br/>Kommunikation, SGAIM<br/>CH-3001 Bern<br/>'
            'bruno.schmucki[at]sgaim.ch</p></section>')
    authors = _authors(_page(body))
    assert [a["name"] for a in authors] == ["Bernadette Häfliger Berger"]
    assert not any(a["is_corresponding"] for a in authors)


def test_correspondence_by_email_only():
    body = ('<section id="section-authors"><p class="authors">Jean Martin</p></section>'
            '<section id="section-correspondence"><h3 class="correspondence">Adresse de correspondance</h3>'
            '<p class="correspondence">jean.martin[at]saez.ch</p></section>')
    assert [a["is_corresponding"] for a in _authors(_page(body))] == [True]


def test_bare_sup_markers_and_one_affiliation_paragraph():
    body = ('<section id="section-authors"><p class="authors">Wolfgang Ummenhofer<sup>a</sup>, Patrick Siebenpfund'
            '<sup>b</sup></p></section><section id="section-affiliation"><div class="accordion-body">'
            '<p class="affiliation"><sup>a</sup> Prof. Dr. med., Plattform Rettungswesen FMH, Präsident; '
            '<sup>b</sup> Dr. med., SGI-Vertreter Plattform Rettungswesen FMH</p></div></section>'
            '<section id="section-correspondence"><h3 class="correspondence">Korrespondenzadresse</h3>'
            '<p class="correspondence">Prof. Dr. med. <br/>Wolfgang Ummenhofer<br/>Postfach 300<br/>'
            'w.ummenhofer[at]unibas.ch</p></section>')
    authors = _authors(_page(body))
    assert [a["name"] for a in authors] == ["Wolfgang Ummenhofer", "Patrick Siebenpfund"]
    assert [x["name"] for x in authors[0]["affiliations"]] == ["Prof. Dr. med., Plattform Rettungswesen FMH, Präsident"]
    assert [x["name"] for x in authors[1]["affiliations"]] == ["Dr. med., SGI-Vertreter Plattform Rettungswesen FMH"]
    assert [a["is_corresponding"] for a in authors] == [True, False]


def test_email_glued_to_a_name_and_a_town_after_a_letter_writer():
    body = '<section id="section-authors"><p class="authors">Wetter Eeva.wetter@suva.ch, Bleuer JP, Welz R</p></section>'
    authors = _authors(_page(body))
    assert [a["name"] for a in authors] == ["Wetter E", "Bleuer JP", "Welz R"]
    assert [a["is_corresponding"] for a in authors] == [True, False, False]  # the one e-mail in the byline
    head = HEAD.replace('content=", "', 'content="Ryser-Düblin, Peter"')
    body = '<section id="section-authors"><p class="authors">Dr. med. Peter Ryser-Düblin, Seftigen</p></section>'
    assert [a["name"] for a in _authors(_page(body, head))] == ["Peter Ryser-Düblin"]



def test_a_reply_signed_at_the_letters_end_is_an_author():
    # bullmed.ch letter "avec réplique": the byline names the letter writer only; the reply's author signs at its end
    # and is the second citation_author
    head = HEAD.replace('content=", "', 'content="Grillet, Jean-Pierre"') + \
        '<meta name="citation_author" content="Gilli, Yvonne"/>'
    body = ('<section id="section-authors"><p class="authors">Dr Jean-Pierre Grillet, Genève</p></section>'
            '<section id="section-main"><p class="paragraph-normal">Un tout grand MERCI ...</p>'
            '<p class="paragraph-normal"><em>Yvonne Gilli, présidente de la FMH</em></p></section>')
    authors = _authors(_page(body, head))
    assert [a["name"] for a in authors] == ["Jean-Pierre Grillet", "Yvonne Gilli"]
    # an editorial-office meta entry is no person, and a meta list missing a byline author is not used
    head = HEAD.replace('content=", "', 'content="Redaktion SÄZ / Rédaction BMS, "') + \
        '<meta name="citation_author" content="Schneider, Martina"/>'
    body = '<section id="section-authors"><p class="authors">Martina Schneider</p></section>'
    assert [a["name"] for a in _authors(_page(body, head))] == ["Martina Schneider"]
    head = HEAD.replace('content=", "', 'content="Muster, Margit"') + '<meta name="citation_author" content="Roth, Anna"/>'
    body = '<section id="section-authors"><p class="authors">Dr. med. Adolf Jens Koemeda</p></section>'
    assert [a["name"] for a in _authors(_page(body, head))] == ["Adolf Jens Koemeda"]

def test_references_numbered_one_to_n_are_whole():
    parsed = _parse(SMW)
    refs = parsed["references"]
    assert [r["position"] for r in refs] == [1, 2]
    assert refs[0]["raw"].startswith("So A, Chin J. Management")
    assert "PubMed" not in refs[0]["raw"]
    assert refs[0]["doi"] == "10.5489/cuaj.117"
    assert parsed["references_complete"] is True


def test_references_numbered_in_text():
    body = ('<section id="section-authors"><p class="authors">Jean Martin</p></section>'
            '<section id="section-references"><h3 class="ref-list-title">Référence</h3>'
            '<p class="ref-list">1\tMartin J. La mort et nous. Bull méd. suisses 2015;96(35):1251.</p></section>')
    parsed = _parse(_page(body))
    assert [(r["position"], r["raw"]) for r in parsed["references"]] == [
        (1, "Martin J. La mort et nous. Bull méd. suisses 2015;96(35):1251.")]
    assert parsed["references_complete"] is True


def test_a_gap_in_the_numbers_is_not_whole():
    body = ('<section id="section-authors"><p class="authors">Jean Martin</p></section>'
            '<section id="section-references"><p class="ref-list">1\tA ref. 2001.</p>'
            '<p class="ref-list">3\tAnother ref. 2002.</p></section>')
    assert _parse(_page(body))["references_complete"] is False


def test_acknowledgments_and_funding_sections():
    parsed = _parse(SMW)
    assert parsed["acknowledgments"] == "We thank NACR for the data on the total number of patients."
    assert parsed["funding_statement"] == "This study was sponsored by Amgen."


def test_medical_forum_literature_boxes():
    head = HEAD.replace("smw.ch/article", "medicalforum.ch/fr/detail").replace('content=", "', 'content="Heinzer, Raphael"')
    box = ('<div class="collapse emh-content-accordion__textbox"><article class="article-detail-recommendations__item">'
           '<span class="article-detail-recommendations__item-title"> {} </span></article></div>')
    body = ('<div class="article-detail-author"><span class="article-detail-author__contributors">PD Dr méd. Raphael '
            'Heinzer</span></div><div class="emh-content-accordion"><div class="emh-content-accordion__wrap">'
            '<a class="collapsed emh-content-accordion__title">Littérature <span></span></a>'
            + box.format("1 Mendes A, Perivier S. Troubles du sommeil chroniques. Forum Méd Suisse. 2017;17(32):712–8.")
            + box.format("2 Luca G, Haba Rubio J. Age and gender variations. 2015. doi:10.1111/jsr.12266")
            + '</div></div>')
    html = _page(body, head)
    parsed = _parse(html)
    assert [r["position"] for r in parsed["references"]] == [1, 2]
    assert parsed["references"][1]["doi"] == "10.1111/jsr.12266"
    assert parsed["references_complete"] is True
    assert [a["name"] for a in _authors(html)] == ["Heinzer, Raphael"]


def test_a_look_alike_page_from_another_publisher_is_not_claimed():
    head = ('<meta property="og:url" content="https://journal.example.org/article/1"/>'
            '<meta name="citation_publisher" content="Example Press"/>'
            '<meta name="citation_author" content="Smith, Ann"/><meta name="generator" content="TYPO3 CMS"/>')
    parser = EMHSwissMedical(BeautifulSoup(_page(SMW_BYLINE + SMW_CORRESPONDENCE, head), "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
