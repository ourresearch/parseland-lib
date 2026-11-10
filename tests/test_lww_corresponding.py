"""Corresponding authors on LWW (journals.lww.com) pages from the author-info notes (oxjob #2128).

Markup is cut down from stored pages sampled 9 Nov 2026 (#2128 EXPLORE § 1). LWW names the corresponding author in a
note under the byline ("Reprints:", "Address for reprints:", "Corresponding Author:", or only an e-mail with a mark
on that author in the byline); the Lippincott parser looked only for "correspondence", so ~11% of LWW pages whose
work showed no corresponding author had one on the page.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.lippincott import lww_corresponding_names

OG = '<meta property="og:url" content="https://journals.lww.com/jspinaldisorders/fulltext/2023/11000/x.10.aspx">'


def _page(byline, notes):
    paras = "".join(f'<p id="">{n}</p>' for n in notes)
    return (f'<html><head>{OG}</head><body><section id="ejp-article-authors"><p id="P7">{byline}</p>'
            f'<section><a href="#" id="ejp-article-authors-link"> Author Information </a></section></section>'
            f'<div class="ejp-article-authors-info-holder">{paras}</div></body></html>')


def _corr(html):
    return [a["name"] for a in parse_page(html.encode(), "doi", "https://journals.lww.com/x") ["authors"]
            if a["is_corresponding"]]


def test_reprints_note_names_the_corresponding_author():
    html = _page("Lee, Nathan J. MD<sup>1</sup>; Lehman, Ronald A. MD<sup>1</sup>",
                 ["Department of Orthopaedics, Columbia University Medical Center, New York, NY",
                  "The authors declare no conflict of interest.",
                  "Reprints: Nathan J. Lee, MD, Columbia University Medical Center, 161 Fort Washington Avenue, "
                  "New York, NY 10032 (e-mail: [email protected])."])
    assert lww_corresponding_names(BeautifulSoup(html, "lxml")) == ["Lee, Nathan J. MD"]
    assert _corr(html) == ["Lee, Nathan J. MD"]


def test_surname_only_and_titles():
    html = _page("Steinmann, Scott P. MD; Moran, Elizabeth A. MD",
                 ["<em>Dr. Steinmann is Assistant Professor, Mayo Clinic. Dr. Moran is Chief Resident.</em>",
                  "<em>Reprint requests: Dr. Steinmann, Mayo Clinic, 200 First Street SW, Rochester MN 55905.</em>"])
    assert _corr(html) == ["Steinmann, Scott P. MD"]


def test_corresponding_author_label_mid_paragraph_and_spelling_variants():
    html = _page("Besson, Caroline<sup>a</sup>; Lancar, Remi<sup>b</sup>",
                 ["<sup>a</sup>Department of Hematology, Versailles. Correspondance to Dr Caroline Besson, MD, PhD, "
                  "Department of Hematology, Centre Hospitalier de Versailles"])
    assert _corr(html) == ["Besson, Caroline"]
    html = _page("Li, Xiao-Na; Peng, Bin; Geng, Song-Mei",
                 ["All of the authors approved the manuscript.",
                  "* Corresponding author: Prof. Songmei Geng, Department of Dermatology, Xi'an"])
    assert _corr(html) == ["Geng, Song-Mei"]


def test_email_only_note_uses_the_byline_mark():
    html = _page("Habas, C.<sup>1 2 CA</sup>; Axelrad, H.<sup>1</sup>; Cabanis, E.-A.<sup>2</sup>",
                 ["<sup>1</sup>Laboratoire de Neurobiologie du Cervelet, Paris",
                  "<sup>CA</sup>Corresponding Author: <span><a href='/cdn-cgi/l/email-protection'>"
                  "<span class='__cf_email__'>[email protected]</span></a></span>"])
    assert _corr(html) == ["Habas, C."]
    html = _page("Wier, Julian MD<sup>1</sup>; Heckmann, Nathanael D. MD<sup>1,a</sup>",
                 ["<sup>1</sup>Department of Orthopaedic Surgery, Los Angeles, California",
                  "<sup>a</sup>Email for corresponding author: <span>[email protected]</span>"])
    assert _corr(html) == ["Heckmann, Nathanael D. MD"]


def test_name_in_the_next_paragraph():
    html = _page("KLEIN, VICTOR R. MD; HARRIS, ANDREW P. MD",
                 ["<em>From the Department of Gynecology and Obstetrics, Baltimore, Maryland.</em>",
                  "Address reprint requests to:",
                  "<em>Victor R. Klein, MD Department of Obstetrics and Gynecology The Johns Hopkins Hospital</em>"])
    assert _corr(html) == ["KLEIN, VICTOR R. MD"]


def test_no_mark_when_the_note_names_nobody_on_the_byline_or_two_people():
    html = _page("Lee, Nathan J. MD; Lehman, Ronald A. MD",
                 ["Reprints: not available from the authors."])
    assert _corr(html) == []
    html = _page("Chan, P.K.; Chan, T.C.W.", ["Reprints: Dr. Chan, Queen Mary Hospital, Hong Kong"])
    assert _corr(html) == []  # two authors named Chan: no guess
    html = _page("Lee, Nathan J. MD; Lehman, Ronald A. MD",
                 ["Discriminant correspondence analysis was performed with the ade4 R package."])
    assert _corr(html) == []


def test_an_existing_mark_is_kept():
    html = _page("Lee, Nathan J. MD<sup>*</sup>; Lehman, Ronald A. MD",
                 ["Reprints: Ronald A. Lehman, MD, New York, NY"])
    assert _corr(html) == ["Lee, Nathan J. MD"]
