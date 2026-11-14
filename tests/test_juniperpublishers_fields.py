"""Juniper Publishers (juniperpublishers.com) article pages (oxjob #2210).

Markup is cut down from stored juniperpublishers.com pages. The site's own PHP template prints the byline in
``h3.authors`` with numbered ``<sup>`` affiliation marks and a ``*`` explained by a "*Corresponding author:" note, then
``h2.heading`` sections (Abstract, ..., Acknowledgment, Funding, References with one ``<ol>``). No publisher parser
claimed the pages, so the generic parser read the citation_author meta tags, whose order and institutions are scrambled,
and no abstract at all.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.juniperpublishers import JuniperPublishers

URL = "https://juniperpublishers.com/argh/ARGH.MS.ID.556048.php"
HEAD = '<link rel="shortcut icon" href="../images/Juniper-icon.ico">'
PUBLISHER = '<meta name="citation_publisher" content="Juniper Publishers">'
DROPDOWN = '<p><div class="dropdown"><button>Go to</button><ul class="dropdown-menu"><li><a href="#Abstract">Abstract</a></li></ul></div>'


def _heading(name):
    return f'{DROPDOWN}<h2 class="heading"><a data-toggle="tab" name="{name}" href="#{name}"><strong>{name}</strong></a></h2>'


def _page(byline, affs, note, sections, metas=PUBLISHER, head=HEAD):
    body = (f'<article class="post"><div><div class="post_meta">'
            f'<p><strong><a name="atype">Case Report</a></strong></p><h2 class="title"><b>A title</b></h2>'
            f'<h3 class="authors">{byline}</h3>{affs}'
            f'<p><b>Submission:</b> August 15, 2024; <b>Published:</b> August 30, 2024</p>{note}'
            f'<p align="justify"><strong>How to cite this article:</strong> A citation. DOI: '
            f'<a href="http://dx.doi.org/10.19080/argh.2024.20.556048">10.19080/ARGH.2024.20.556048.</a></p>'
            f'{sections}</div></div></article>')
    return (f'<html><head>{head}<meta name="description" content="The first sentence of the introduction.">'
            f'<meta name="citation_author" content="Ann Lee"><meta name="citation_author" content="Carl Diaz">'
            f'<meta name="citation_author_institution" content="Clinic B, Nis, Serbia"/>'
            f'<meta name="citation_author" content="Bo Kim">{metas}'
            f'<meta name="citation_doi" content="10.19080/ARGH.2024.20.556048"></head><body>{body}</body></html>')


AFFS = ('<p><i><sup>1</sup>Clinic A, University Clinical Center, Nis, Serbia</i></p>'
        '<p><i><sup>2</sup>Clinic B, University Clinical Center, Nis, Serbia</i></p>')
NOTE = ('<p align="justify"><strong style="color:#086A05;">*Corresponding author:</strong> Carl Diaz, Clinic B, '
        'University Clinical Center, Nis, Serbia</p>')
BYLINE = 'Ann Lee<sup>1</sup>, Bo Kim<sup>2</sup> and Carl Diaz<sup>2</sup>*'
ABSTRACT = (_heading("Abstract") +
            '<p align="justify"><strong>Background:</strong> Hydatid liver disease can perforate into the bile ducts.</p>'
            '<p align="justify"><strong>Conclusions:</strong> Surgery is the gold standard.</p>'
            '<p align="justify"><strong>Keywords:</strong> Liver; Hydatidosis</p>'
            '<p align="justify"><strong>Abbreviations:</strong> CBC: Cystobiliary Communication</p>'
            '<!--Abstract ends Here -->')
INTRO = _heading("Introduction") + '<p align="justify">Hydatid disease is an endemic zoonosis.</p>'
ACK = _heading("Acknowledgment") + '<p align="justify">This work was supported by the Shanghai Pujiang Program (23PJ1411400).</p>'
FUNDING = _heading("Funding") + '<p>This research was funded by the Nanjing Soft Science Project under Grant No 202403026.</p>'
REFS = (_heading("References") + '<ol>'
        '<li><a href="https://pubmed.ncbi.nlm.nih.gov/30317310/">Ahmad BS (2018) Hydatid cyst of liver. J Pak Med Assoc 68(7): 1097-1099.</a></li>'
        '<li><a href="https://doi.org/10.1007/s13244-019-0805-0">Greco S (2019) Complications of hepatic echinococcosis. Insights Imaging 10(1): 113.</a></li>'
        '<li>Stojanovic M (2009) Hydatide liver disease. Medical faculty University of Nis 15: 144-145.</li>'
        '</ol>')


def _parsed(html):
    return parse_page(html.encode(), "doi", URL)


def _raw(html):
    return JuniperPublishers(BeautifulSoup(html, "lxml")).parse()


def test_byline_order_and_numbered_affiliations():
    out = _parsed(_page(BYLINE, AFFS, NOTE, ABSTRACT + INTRO))
    assert [a["name"] for a in out["authors"]] == ["Ann Lee", "Bo Kim", "Carl Diaz"]
    assert [[x["name"] for x in a["affiliations"]] for a in out["authors"]] == [
        ["Clinic A, University Clinical Center, Nis, Serbia"],
        ["Clinic B, University Clinical Center, Nis, Serbia"],
        ["Clinic B, University Clinical Center, Nis, Serbia"]]


def test_star_explained_by_note_marks_corresponding():
    out = _parsed(_page(BYLINE, AFFS, NOTE, INTRO))
    assert [a["is_corresponding"] for a in out["authors"]] == [False, False, True]


def test_star_without_note_marks_no_one():
    out = _parsed(_page(BYLINE, AFFS, "", INTRO))
    assert not any(a["is_corresponding"] for a in out["authors"])


def test_note_names_author_when_byline_has_no_star():
    byline = 'Ann Lee<sup>1</sup>, Bo Kim<sup>2</sup> and Carl Diaz<sup>2</sup>'
    note = '<p><strong>*Corresponding author:</strong> Bo Kim, Clinic B, University Clinical Center, Nis, Serbia</p>'
    out = _parsed(_page(byline, AFFS, note, INTRO))
    assert [a["is_corresponding"] for a in out["authors"]] == [False, True, False]


def test_star_after_mark_and_missing_comma_split_authors():
    byline = ('<strong>Stanley HO<sup>1</sup>* Okhuahesogie E<sup>1</sup> and Ugboma C J<sup>2</sup><sup>3</sup></strong>')
    affs = AFFS + '<p><i><sup>3</sup>3Romanian Academy, Chemical Sciences Section, Romania</i></p>'
    out = _parsed(_page(byline, affs, NOTE, INTRO))
    assert [a["name"] for a in out["authors"]] == ["Stanley HO", "Okhuahesogie E", "Ugboma C J"]
    assert [a["is_corresponding"] for a in out["authors"]] == [True, False, False]
    assert [x["name"] for x in out["authors"][2]["affiliations"]] == [
        "Clinic B, University Clinical Center, Nis, Serbia", "Romanian Academy, Chemical Sciences Section, Romania"]


def test_unnumbered_affiliation_is_shared_and_star_in_text():
    byline = '<strong>Niloufar Mahmoudi*, Yousef Naserzadeh and Albert Engeribo</strong>'
    affs = '<p><i>Department of Agro Biotechnology, RUDN University, Russia</i></p>'
    out = _parsed(_page(byline, affs, NOTE, INTRO))
    assert [a["name"] for a in out["authors"]] == ["Niloufar Mahmoudi", "Yousef Naserzadeh", "Albert Engeribo"]
    assert all([x["name"] for x in a["affiliations"]] == ["Department of Agro Biotechnology, RUDN University, Russia"]
               for a in out["authors"])
    assert [a["is_corresponding"] for a in out["authors"]] == [True, False, False]


def test_shared_mark_and_star_inside_sup():
    byline = 'Sapna Rawat<sup>1</sup>, Vinci<sup>2</sup> and S Lakshmi Kandhan<sup>3*</sup>'
    affs = ('<p><i><sup>1,2</sup>Morarji Desai National Institute of Yoga, New Delhi, India</i></p>'
            '<p><i><sup>3</sup>Department of Yoga Therapy, New Delhi, India</i></p>')
    out = _parsed(_page(byline, affs, NOTE, INTRO))
    assert [x["name"] for x in out["authors"][1]["affiliations"]] == ["Morarji Desai National Institute of Yoga, New Delhi, India"]
    assert [a["is_corresponding"] for a in out["authors"]] == [False, False, True]


def test_abstract_paragraphs_without_keywords():
    out = _parsed(_page(BYLINE, AFFS, NOTE, ABSTRACT + INTRO))
    assert out["abstract"] == ("Background: Hydatid liver disease can perforate into the bile ducts.\n"
                               "Conclusions: Surgery is the gold standard.")


def test_no_abstract_heading_means_no_abstract():
    out = _parsed(_page(BYLINE, AFFS, NOTE, INTRO + _heading("Summary") + "<p>" + "A closing summary. " * 20 + "</p>"))
    assert out["abstract"] is None


def test_summary_heading_first_is_the_abstract():
    text = "Pheochromocytoma associated with renal artery stenosis is rare and its surgery is a challenge."
    out = _parsed(_page(BYLINE, AFFS, NOTE, _heading("Summary") + f"<p>{text}</p>" + INTRO))
    assert out["abstract"] == text


def test_acknowledgments_funding_and_whole_reference_list():
    raw = _raw(_page(BYLINE, AFFS, NOTE, ABSTRACT + INTRO + ACK + FUNDING + REFS))
    assert raw["acknowledgments"] == "This work was supported by the Shanghai Pujiang Program (23PJ1411400)."
    assert raw["funding_statement"] == ("This research was funded by the Nanjing Soft Science Project under Grant No "
                                        "202403026.")
    assert [r["position"] for r in raw["references"]] == [1, 2, 3]
    assert raw["references"][0]["raw"] == "Ahmad BS (2018) Hydatid cyst of liver. J Pak Med Assoc 68(7): 1097-1099."
    assert [r["doi"] for r in raw["references"]] == [None, "10.1007/s13244-019-0805-0", None]
    assert raw["references_complete"] is True


def test_no_sections_give_none():
    raw = _raw(_page(BYLINE, AFFS, NOTE, INTRO))
    assert raw["acknowledgments"] is None and raw["funding_statement"] is None
    assert raw["references"] is None and raw["references_complete"] is False


def test_list_split_in_two_with_start_is_whole():
    refs = (_heading("References") + '<ol><li>Ref one (2020) J 1: 1.</li><li>Ref two (2020) J 1: 2.</li></ol>'
            '<p>&nbsp;</p><ol start="3"><li>Ref three (2021) J 2: 3.</li></ol>')
    raw = _raw(_page(BYLINE, AFFS, NOTE, INTRO + refs))
    assert [r["position"] for r in raw["references"]] == [1, 2, 3]
    assert raw["references_complete"] is True


def test_gap_or_nested_list_is_not_whole():
    gap = (_heading("References") + '<ol><li>Ref one (2020) J 1: 1.</li></ol><ol start="5"><li>Ref five.</li></ol>')
    assert _raw(_page(BYLINE, AFFS, NOTE, INTRO + gap))["references_complete"] is False
    nested = (_heading("References") + '<ol><li>Ref one (2020) J 1: 1.</li><li>Ref two.<ol><li>Ref one (2020) J 1: 1.'
              '</li><li>Ref two.</li></ol></li></ol>')
    assert _raw(_page(BYLINE, AFFS, NOTE, INTRO + nested))["references_complete"] is False
    loose = (_heading("References") + '<ol><li>Ref one (2020) J 1: 1.</li></ol><p>Ref two (2021) J 2: 2.</p>')
    assert _raw(_page(BYLINE, AFFS, NOTE, INTRO + loose))["references_complete"] is False


def test_old_page_without_citation_meta_is_claimed_by_its_icon():
    html = _page(BYLINE, AFFS, NOTE, ABSTRACT + INTRO, metas="")
    assert JuniperPublishers(BeautifulSoup(html, "lxml")).is_publisher_specific_parser()
    assert [a["name"] for a in _parsed(html)["authors"]] == ["Ann Lee", "Bo Kim", "Carl Diaz"]


def test_similar_template_from_another_publisher_is_not_claimed():
    html = _page(BYLINE, AFFS, NOTE, ABSTRACT + INTRO,
                 metas='<meta name="citation_publisher" content="Lupine Publishers">',
                 head='<link rel="shortcut icon" href="../images/lupine-icon.ico">')
    parser = JuniperPublishers(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    # the meta-tag order, not the byline order: this parser did not read the page
    assert [a["name"] for a in _parsed(html)["authors"]] == ["Ann Lee", "Carl Diaz", "Bo Kim"]
