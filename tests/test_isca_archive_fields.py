"""ISCA Archive pages (www.isca-archive.org, DOI prefix 10.21437: Interspeech and other speech-communication
proceedings), oxjob #2338.

Markup is cut down from stored pages. Each paper's page is a static W3.CSS card: the title in <h3>, the byline in <h5>
(names only), then the abstract. The current template (titled "ISCA Archive - <paper title>", with citation_* tags)
prints the abstract in <div id="abstract">, as bare text or <p> paragraphs; the older one (titled "ISCA Archive",
mostly no meta tags) prints it as <p> paragraphs right after the byline, before the PDF link and the "Cite as" line.
No page shows affiliations, a corresponding mark, acknowledgments, funding or references. Neither template has an
"Abstract" heading or an abstract meta tag, so the generic readers find no abstract on either.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.isca_archive import ISCAArchive

URL = "https://doi.org/10.21437/interspeech.2021-1633"
ABSTRACT = ("We present two multimodal fusion-based deep learning models that consume ASR transcribed speech and "
            "acoustic data simultaneously to classify whether a speaker in a structured diagnostic task has "
            "Alzheimer&#8217;s Disease and to what degree, evaluating the ADReSSo challenge 2021 data.")
ABSTRACT_TEXT = ABSTRACT.replace("&#8217;", "’")
SECOND = "The data were collected and organised in conformity with the standards of the Esprit Project 2589 SAM."
CITE = ("<p class='w3-text'>Cite as: Rohanian, M., Hough, J., Purver, M. (2021) Alzheimer&#8217;s Dementia "
        "Recognition. Proc. Interspeech 2021, 3820-3824, doi: 10.21437/Interspeech.2021-1633</p>")
BIBTEX = ('<pre class="w3-text w3-small">@inproceedings{rohanian21_interspeech,\n  author={Morteza Rohanian and '
          'Julian Hough},\n  doi={10.21437/Interspeech.2021-1633}\n}</pre>')


def _old_page(paragraphs, title="ISCA Archive", metas=""):
    """The older template (most stored pages): no <head>, abstract paragraphs after the <h5> byline."""
    body = "".join(f"<p>{p}\n</p>" for p in paragraphs)
    return (f'<!DOCTYPE html><html>{metas}<meta charset="UTF-8"><title>{title}</title>'
            '<link rel="stylesheet" href="../resources/w3.css">'
            '<div class="w3-top w3-hide-small"><div class="w3-bar w3-theme-d4 w3-center">'
            '<a href="../../index.html" class="w3-bar-item w3-button">ISCA</a>'
            '<a href="index.html" class="w3-bar-item w3-button">Interspeech 2021</a></div></div>'
            '<div class="w3-grayscale w3-theme-l5"><div class="w3-container"><div class="w3-content">'
            '<div class="w3-container w3-card w3-padding-large w3-white">'
            '<h3 class="w3-center">Alzheimer&#8217;s Dementia Recognition Using Acoustic Features</h3>'
            '<h5 class="w3-center w3-margin w3-padding">Morteza Rohanian, Julian Hough, Matthew Purver</h5>'
            f'{body}<p></p><br>'
            '<a href="../pdfs/interspeech_2021/rohanian21_interspeech.pdf"><i class="fa fa-file-pdf-o"></i></a>'
            f' doi: 10.21437/Interspeech.2021-1633 {CITE}{BIBTEX}</div></div></div></div></body></html>')


def _new_page(abstract_html, title="ISCA Archive - Tonal density characterises the scope of mais"):
    """The current template: citation_* tags, the abstract in <div id="abstract">."""
    return ('<!DOCTYPE html><html><head>'
            '<meta name="citation_title" content="Tonal density characterises the scope of mais">'
            '<meta name="citation_conference_title" content="Proc. SpeechProsody 2024">'
            '<meta name="citation_author" content="Portes, Cristel">'
            '<meta name="citation_author" content="Rauzy, Stéphane">'
            '<meta name="citation_pdf_url" content="">'
            '<meta name="citation_doi" content="10.21437/SpeechProsody.2024-156">'
            f'<meta charset="UTF-8"><title>{title}</title>'
            '<link rel="stylesheet" href="../resources/w3.css"><link rel="stylesheet" href="../resources/is.css">'
            '</head><body><div class="w3-theme-l5"><div class="w3-container"><div class="w3-content">'
            '<div class="w3-container w3-card w3-padding-large w3-white" style="border-radius:20px">'
            '<div id="global-info" class="w3-margin w3-padding">'
            '<h3 class="w3-center">Tonal density characterises the scope of mais</h3>'
            '<h5 class="w3-center">Cristel Portes, Stéphane Rauzy</h5></div>'
            f'<div id="abstract">{abstract_html}</div>'
            '<div id="content" class="w3-center"><div class="icon-row">'
            '<a href="portes24_speechprosody.pdf"><i class="icon-file-pdf-o"></i></a></div>'
            '<div id="popup-box" style="display:none;"><div id=bibtex><pre class="language-bib"><code>'
            '@inproceedings{portes24_speechprosody, author = {Cristel Portes and Stéphane Rauzy}}'
            '</code></pre></div></div></div></div></div></div></div></body></html>')


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def test_old_template_abstract_after_byline():
    out = _parse(_old_page([ABSTRACT]))
    assert out["abstract"] == ABSTRACT_TEXT


def test_old_template_paragraphs_join_and_index_terms_left_out():
    out = _parse(_old_page([ABSTRACT, SECOND, "Index Terms: Duration modification, epochs, zero frequency filtering"]))
    assert out["abstract"] == ABSTRACT_TEXT + " " + SECOND


def test_old_template_inline_keyword_line_left_out():
    out = _parse(_old_page([ABSTRACT + " Keywords: Speech recognition; Spectrogram reading knowledge"]))
    assert out["abstract"] == ABSTRACT_TEXT


def test_old_template_byline_is_not_read():
    # the works these pages stand for already have their authors (#2338 sizing: 0 works would gain), so the
    # parser keeps the generic parser's reading: the citation_author tags, none on this page
    assert _parse(_old_page([ABSTRACT]))["authors"] == []


def test_old_template_with_meta_tags_keeps_tag_authors():
    metas = '<meta name="citation_author" content="Chao, Chih-yu"><meta name="citation_author" content="Wang, Chao">'
    out = _parse(_old_page([ABSTRACT], metas=metas))
    assert [a["name"] for a in out["authors"]] == ["Chao, Chih-yu", "Wang, Chao"]
    assert out["abstract"] == ABSTRACT_TEXT


def test_new_template_bare_text_abstract():
    out = _parse(_new_page(f"\n    {ABSTRACT}\n    "))
    assert out["abstract"] == ABSTRACT_TEXT


def test_new_template_paragraph_abstract_without_index_terms():
    out = _parse(_new_page(f"<p>{ABSTRACT}\n</p><p>Index Terms: Duration modification, epochs\n</p><p></p>"))
    assert out["abstract"] == ABSTRACT_TEXT


def test_new_template_authors_from_tags_as_before():
    out = _parse(_new_page(f"<p>{ABSTRACT}</p>"))
    assert [(a["name"], a["affiliations"], a["is_corresponding"]) for a in out["authors"]] == [
        ("Portes, Cristel", [], None), ("Rauzy, Stéphane", [], None)]


def test_new_fields_absent():
    parsed = ISCAArchive(BeautifulSoup(_new_page(f"<p>{ABSTRACT}</p>"), "lxml")).parse()
    assert parsed["acknowledgments"] is None
    assert parsed["funding_statement"] is None
    assert parsed["references"] is None
    assert parsed["references_complete"] is False


def test_page_without_abstract_is_left_to_the_generic_parser():
    parser = ISCAArchive(BeautifulSoup(_old_page([]), "lxml"))
    assert parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_archive_index_page_is_not_read():
    html = ('<html><head><title>ISCA Archive</title></head><body><div class="w3-card"><h3>Interspeech 2019</h3>'
            '<p>Graz, Austria, 15-19 September 2019</p></div></body></html>')
    assert not ISCAArchive(BeautifulSoup(html, "lxml")).authors_found()


def test_other_w3css_site_with_same_card_is_not_claimed():
    html = _old_page([ABSTRACT], title="ACM Archive")
    parser = ISCAArchive(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    assert _parse(html)["abstract"] is None
