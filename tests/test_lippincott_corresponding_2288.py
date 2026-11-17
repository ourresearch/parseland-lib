"""LWW (journals.lww.com): a star in the byline is a footnote key, not a corresponding mark (oxjob #2288).

Ovid's LWW template keys affiliations with *, †, ‡ ("From the *Department of Surgery ...; †..."), so a star sits on
many or all authors; the Lippincott parser took every star as a corresponding mark, and its fallback flagged every
author whose surname appeared anywhere in the first paragraph mentioning "correspondence" (the affiliation text before
the note, a shared surname, "Li" inside "Little Rock"). ~160 stored LWW pages flagged every author that way. #1791's
gold (label-v1): a note naming one author marks that author; a note naming every author marks everyone. Markup is cut
down from stored pages (families/lippincott.ndjson, 17 Nov 2026).
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.lippincott import Lippincott

OG = '<meta property="og:url" content="https://journals.lww.com/annalsofsurgery/fulltext/2022/x.aspx">'
SUP = '<sup xmlns:mrws="http://webservices.ovid.com/mrws/1.0">{}</sup>'


def _page(byline, notes):
    paras = "".join(f'<p id="BT_ID_1">{n}</p>' for n in notes)
    return (f'<html><head>{OG}</head><body><section id="ejp-article-authors"><p id="P7">{byline}</p>'
            f'<section><a href="#" id="ejp-article-authors-link"> Author Information </a></section></section>'
            f'<div class="ejp-article-authors-info-holder">{paras}</div></body></html>')


def _byline(*pairs):
    return "; ".join(name + (SUP.format(mark) if mark else "") for name, mark in pairs)


def _corr(html):
    return [a["name"] for a in parse_page(html.encode(), "doi", "https://journals.lww.com/x")["authors"]
            if a["is_corresponding"]]


def _parser_corr(html):
    return [a.name for a in Lippincott(BeautifulSoup(html, "lxml")).get_authors() if a.is_corresponding]


def test_star_keying_an_affiliation_marks_no_one():
    # 10.1097/sla.0000000000005453: every author starred, the star is the first affiliation, no note
    html = _page(_byline(("Letica-Kriegel, Allison S. MD, MSc", "*"), ("Kaplan, Amy BA", "*"),
                         ("Orlas, Claudia MD", "*,†"), ("Masiakos, Peter T. MD, MS", "*,†")),
                 [SUP.format("*") + "Department of Surgery, Massachusetts General Hospital, Boston, MA",
                  SUP.format("†") + "Pediatric Surgery Trials and Outcomes Research, Boston, MA",
                  "The authors report no conflicts of interest."])
    assert _parser_corr(html) == []
    assert _corr(html) == []


def test_star_keying_an_affiliation_with_a_reprints_note_marks_the_named_author():
    # 10.1097/jcp.0000000000001344
    html = _page(_byline(("Bo, Qijing MD, PhD", "∗,†"), ("Xing, Xiaomeng MD", "∗,†"), ("Li, Tian MD", "∗,†")),
                 ["From the " + SUP.format("∗") + "Beijing Anding Hospital " + SUP.format("†")
                  + "Capital Medical University, Beijing, China.",
                  "Reprints: Qijing Bo, MD, PhD, Beijing Anding Hospital, Beijing 100088, China (e-mail: x)."])
    assert _corr(html) == ["Bo, Qijing MD, PhD"]


def test_inline_star_key_and_a_correspondence_note():
    # 10.1097/olq.0b013e318238b846: the star is written inline in the affiliation paragraph
    html = _page(_byline(("McCann, Pol Dominic PhD", "*"), ("Gray, Richard T. PhD", "*"),
                         ("Prestage, Garrett PhD", "*†")),
                 ["From the *Kirby Institute, University of New South Wales, Sydney; and †La Trobe University",
                  "Correspondence: Garrett Prestage, PhD, The Kirby Institute, Kensington, NSW, 2052, Australia."])
    assert _corr(html) == ["Prestage, Garrett PhD"]


def test_unexplained_star_on_every_author_marks_no_one():
    # 10.1097/00005768-199605001-00942: the one affiliation lost its key
    html = _page(_byline(("Waku, T.", "*"), ("Koda, Y.", "*"), ("Akama, T.", "*")),
                 ["Dept. of Life Sciences, University of Tokyo, and University of Tsukuba, Japan."])
    assert _corr(html) == []


def test_star_on_affiliations_and_on_a_corresponding_note_naming_one_author():
    # 10.1097/pq9.0000000000000412: the template reuses the star for "*Corresponding author. Address: ..."
    html = _page(_byline(("Satti, Komal F. MBBS, MPH", "*"), ("Tanski, Susanne E. MD, MPH", "*"),
                         ("Jiang, Yike MD, PHD", "*,†")),
                 ["From the " + SUP.format("*") + "Dartmouth Hitchcock Medical Center, Lebanon, N.H. "
                  + SUP.format("†") + "Baylor College of Medicine, Houston, Tex.",
                  SUP.format("*") + "Corresponding author. Address: Komal F. Satti, MBBS, MPH, The Children's "
                  "Hospital at Dartmouth-Hitchcock, Lebanon, NH 03756, Email: x"])
    assert _corr(html) == ["Satti, Komal F. MBBS, MPH"]


def test_correspondence_note_after_the_affiliations_in_one_paragraph():
    # 10.1097/00004728-198903000-00017
    html = _page("Levine, Errol; Huntrakoon, Manop",
                 ["Departments of Diagnostic Radiology (E. Levine) and Pathology (M. Huntrakoon), University of "
                  "Kansas Medical Center, Kansas City, KS. Address correspondence and reprint requests to Dr. E. "
                  "Levine at Department of Diagnostic Radiology, Kansas City, KS 66103, U.S.A."])
    assert _corr(html) == ["Levine, Errol"]


def test_surname_inside_another_word_or_shared_by_two_authors():
    # 10.1097/00008877-199912000-00013: "Li" inside "Little Rock"
    html = _page("McMillan, D. E.; Li, Mi",
                 ["Department of Pharmacology and Toxicology, University of Arkansas, Little Rock, AR 72205, USA",
                  "Correspondence to D.E. McMillan, Department of Pharmacology, 4301 West Markham Street, Little "
                  "Rock, AR 72205, USA."])
    assert _corr(html) == ["McMillan, D. E."]
    # 10.1097/00055735-200206000-00001: two authors named Shields
    html = _page("Shields, Carol L. MD; Shields, Jerry A. MD",
                 ["Correspondence to Carol L. Shields, MD, Ocular Oncology Service, Wills Eye Hospital, "
                  "Philadelphia, PA 19107, USA"])
    assert _corr(html) == ["Shields, Carol L. MD"]


def test_note_label_variants():
    # 10.1097/bsd.0000000000000654: "Reprints: Toshitaka" lost its "To" to the label's "to"
    html = _page(_byline(("Yoshii, Toshitaka MD, PhD", "*,†"), ("Hirai, Takashi MD, PhD", "*")),
                 [SUP.format("*") + "Section of Orthopaedic and Spinal Surgery, Graduate School",
                  "Reprints: Toshitaka Yoshii, MD, PhD, Department of Orthopaedic Surgery, Tokyo 113-8519, Japan"])
    assert _corr(html) == ["Yoshii, Toshitaka MD, PhD"]
    # 10.1097/brs.0b013e3181bdafed: "reprints requests", two authors named Bydon
    html = _page(_byline(("Xu, Risheng AM", "*†"), ("Bydon, Mohamed MD", "*"), ("Bydon, Ali MD", "*")),
                 ["From the *Department of Neurosurgery, Johns Hopkins University, Baltimore, MD; and †Medical "
                  "Scientist Training Program, Baltimore, MD.",
                  "Address correspondence and reprints requests to Ali Bydon, MD, Johns Hopkins Hospital, 600 N. "
                  "Wolfe Street, Baltimore, MD 21287"])
    assert _corr(html) == ["Bydon, Ali MD"]
    # 10.1097/00008505-200104000-00012: the name in the next paragraph
    html = _page(_byline(("Bender, SA BA", "*"), ("Schmitz, JP DDS, PhD", "**"), ("Ong, JL PhD", "***")),
                 ["*Dental student, University of Texas Health Science Center at San Antonio, TX.",
                  "**Associate Professor, Department of Oral and Maxillofacial Surgery, San Antonio, TX.",
                  "***Associate Professor, Department of Restorative Dentistry, San Antonio, TX.",
                  "Reprint requests and correspondence to:", "Joo L. Ong, PhD", "7703 Floyd Curl Drive"])
    assert _corr(html) == ["Ong, JL PhD"]


def test_unlabeled_correspondence_block():
    # 10.1097/gox.0000000000004853 (PRS Global Open)
    notes = ["From the " + SUP.format("*") + "Clinica Cavadas, Valencia, Spain " + SUP.format("†")
             + "Universidad Cardenal Herrera-CEU, Valencia, Spain.",
             "Disclosure statements are at the end of this article, following the correspondence information.",
             "Pedro C. Cavadas, MD, PhD, Reconstructive Surgery, Clinica Cavadas, 46021 Valencia, Spain, E-mail: "
             "<span>[email protected]</span>"]
    byline = _byline(("Cavadas, Pedro C. MD, PhD", "*"), ("Padial, Beatriz MD", "*,†"))
    assert _corr(_page(byline, notes)) == ["Cavadas, Pedro C. MD, PhD"]
    # an e-mail for every author marks no one
    notes.append("Beatriz Padial, MD, Universidad Cardenal Herrera-CEU, Valencia, Spain, E-mail: x")
    assert _corr(_page(byline, notes)) == []


def test_note_naming_every_author_keeps_every_flag():
    # 10.1097/njh.0000000000000103
    html = _page("Lem, Ashlea A. DNP, ARNP, AGACNP; Schwartz, Misty PhD, RN",
                 ["Address correspondence to Ashlea A. Lem, DNP, ARNP, AGACNP, 15201 NW 16th St, Slater, IA 50244 "
                  "(x), or Misty Schwartz (y)."])
    assert _corr(html) == ["Lem, Ashlea A. DNP, ARNP, AGACNP", "Schwartz, Misty PhD, RN"]
    # every author starred to a note that says they are the corresponding authors
    html = _page(_byline(("Hopewell, Jemma C.", "*"), ("Reith, Christina", "*")),
                 ["CTSU, Nuffield Department of Population Health, University of Oxford, Oxford, UK",
                  SUP.format("*") + "Authors to whom correspondence should be addressed."])
    assert _corr(html) == ["Hopewell, Jemma C.", "Reith, Christina"]


def test_star_explained_as_corresponding_on_one_author_is_kept():
    html = _page(_byline(("Lee, Nathan J. MD", "1,*"), ("Lehman, Ronald A. MD", "1")),
                 [SUP.format("1") + "Department of Orthopaedics, Columbia University Medical Center, New York, NY",
                  SUP.format("*") + "Corresponding author: x"])
    assert _parser_corr(html) == ["Lee, Nathan J. MD"]
    assert _corr(html) == ["Lee, Nathan J. MD"]
