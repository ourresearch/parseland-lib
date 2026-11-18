"""Round 8c regressions (oxjob #2239, phase 2): pages that round 8 made newly worse than production, by mechanism.

Markup is cut down from stored pages of the dev and check1 draws.
"""
from bs4 import BeautifulSoup

from parseland_lib.publisher.parsers.dergipark import corresponding_names
from parseland_lib.publisher.parsers.karger import Karger
from parseland_lib.publisher.parsers.lippincott import Lippincott
from parseland_lib.publisher.parsers.rfppl import RedFlower
from parseland_lib.publisher.parsers.spie import SPIE
from parseland_lib.repository.parsers.zenodo import Zenodo


def _soup(html):
    return BeautifulSoup(html, "lxml")


# --- SPIE: an author with an ORCID link keeps their name and place ---------------------------------------------------

def _spie(byline, metas=()):
    tags = "".join(f'<meta name="citation_author" content="{m}">' for m in metas)
    return SPIE(_soup(
        f'<html><head>{tags}</head><body><a class="logo" href="http://spie.org">SPIE</a>'
        f'<div id="affiliations"><b>{byline}</b><br/><br/> <sup>1</sup>Air Force Research Lab. (United States) <br/>'
        f' <sup>2</sup>Virginia Polytechnic Institute and State Univ. (United States) <br/></div></body></html>')).parse()


ORCID = ('<a href="https://orcid.org/0009-0007-4272-5033"><img class="ORCIDIcon" src="/orcid_16x16.png"/>'
         '<span class="authorORCIDPrint">https://orcid.org/0009-0007-4272-5033</span></a>')


def test_spie_author_with_orcid_link_keeps_name_and_affiliation():
    # 2d48c94e: "R. Raghunathan<a orcid/>,<sup>2</sup>" read as "" and was dropped, shifting the list
    out = _spie(f" J. K. Mee,<sup>1</sup> R. Raghunathan{ORCID},<sup>2</sup> D. Murrell,<sup>2</sup>")
    assert [(a.name, a.affiliations) for a in out["authors"]] == [
        ("J. K. Mee", ["Air Force Research Lab. (United States)"]),
        ("R. Raghunathan", ["Virginia Polytechnic Institute and State Univ. (United States)"]),
        ("D. Murrell", ["Virginia Polytechnic Institute and State Univ. (United States)"])]


def test_spie_first_author_with_orcid_and_split_name_text():
    # e6a03a8c / b6756ee8: the first author carries the link; a name written over two lines is one name
    out = _spie(f"R. Khabibullin{ORCID},<sup>1,2</sup> Zhikai\n Zhu,<sup>2</sup>")
    assert [a.name for a in out["authors"]] == ["R. Khabibullin", "Zhikai Zhu"]


def test_spie_unreadable_name_falls_back_to_citation_author_in_place():
    out = _spie("<i>x</i>,<sup>1</sup> D. Murrell,<sup>2</sup>", metas=["J. K. Mee", "D. Murrell"])
    assert [a.name for a in out["authors"]] == ["J. K. Mee", "D. Murrell"]


def test_spie_plain_byline_unchanged():
    out = _spie(" J. K. Mee,<sup>1</sup> D. Murrell,<sup>2</sup>")
    assert [a.name for a in out["authors"]] == ["J. K. Mee", "D. Murrell"]


# --- LWW: author-info lines --------------------------------------------------------------------------------------------

LWW_OG = '<meta property="og:url" content="https://journals.lww.com/x/fulltext/2021/x.aspx">'
CF_EMAIL = '<a class="__cf_email__" data-cfemail="3c5e" href="/cdn-cgi/l/email-protection">[email&#160;protected]</a>'


def _lww(byline, notes):
    html = (f'<html><head>{LWW_OG}</head><body><section id="ejp-article-authors"><p id="P7">{byline}</p></section>'
            f'<section id="ejp-article-authors-info"><div class="ejp-article-authors-info-holder">{"".join(notes)}'
            f'</div></section></body></html>')
    return [(a.name, a.affiliations) for a in Lippincott(_soup(html)).parse()["authors"]]


def test_lww_c001_affiliation_paragraph_is_not_a_correspondence_note():
    # 7247ad95: Anesthesiology's "From the Department ..." paragraph has id "c001"; it was dropped as a note, and the
    # supplemental-content and history notices took its place
    out = _lww("Willingham, Mark D. M.D.; Vila, Molly R. M.D.",
               ['<p id="c001">From the Department of Anesthesiology, Washington University School of Medicine, St. '
                'Louis, Missouri (M.D.W.); the Midwest Anesthesia Partners, LLC, Chicago, Illinois (M.R.V.).</p>',
                '<p id="">Supplemental Digital Content is available for this article.</p>',
                '<p id="">Submitted for publication April 4, 2020. Accepted for publication February 22, 2021.</p>',
                f'<p id="c1">Address correspondence to Dr. Vila: Midwest Anesthesia Partners. {CF_EMAIL}.</p>'])
    for _, affs in out:
        assert affs[0].startswith("From the Department of Anesthesiology")
        assert not any("Supplemental" in a or "Submitted" in a or "correspondence" in a for a in affs)


def test_lww_notices_are_not_affiliations():
    out = _lww("Smith, Ann",
               ['<p id="">Supplemental Digital Content is available for this article.</p>',
                '<p id="">Submitted for publication April 4, 2020.</p>'])
    assert out == [("Smith, Ann", [])]


def test_lww_c_id_paragraph_with_email_is_still_a_note():
    out = _lww("Smith, Ann",
               ['<p id="">Department of Surgery, Mercy Hospital, Iowa City, IA</p>',
                f'<p id="c1">Ann Smith, 1 Main Street, Iowa City, IA. {CF_EMAIL}</p>'])
    assert out == [("Smith, Ann", ["Department of Surgery, Mercy Hospital, Iowa City, IA"])]


def test_lww_biography_and_editor_credit_are_not_affiliations():
    # aed13c02: the author's biography and the column editor's credit line
    out = _lww("Stonerook, Ethan MS, MMS, PA-C",
               ['<p id=""><strong>Ethan Stonerook</strong> is assistant professor at the Wake Forest University PA '
                'program. He practices clinically at Novant Health Cancer Institute in Winston-Salem, NC.</p>',
                '<p id=""><strong>Brian T. Maurer, PA-C</strong>, department editor</p>'])
    assert out == [("Stonerook, Ethan MS, MMS, PA-C", [])]


def test_lww_bold_lead_of_an_affiliation_stays():
    out = _lww("Smith, Ann", ['<p id=""><strong>Department of Surgery</strong>, Mercy Hospital, Iowa City, IA</p>'])
    assert out == [("Smith, Ann", ["Department of Surgery, Mercy Hospital, Iowa City, IA"])]


def test_lww_cross_reference_and_unit_number():
    # aa27a7bf: "Unit 572 INSERM" was keyed "572" (no author has that mark) and "See original paper on page 1171"
    # stood as the affiliation
    out = _lww("Swynghedauw, Bernard",
               ['<p id="AF_ID_d1">Unit 572 INSERM, Hôpital Lariboisière, Paris, France.</p>',
                '<p id="BT_ID_d1">See original paper on page 1171</p>',
                f'<p id="BT_ID_d1">Correspondence and requests for reprints to Bernard Swynghedauw, U572 INSERM, '
                f'Paris, France. e-mail: {CF_EMAIL}</p>'])
    assert out == [("Swynghedauw, Bernard", ["Unit 572 INSERM, Hôpital Lariboisière, Paris, France."])]


def test_lww_number_after_a_joining_word_still_keys_a_line():
    out = _lww("Ochi, Satoshi<sup>1</sup>; Campbell, Mary Jo<sup>2</sup>",
               ['<p id="">1Player Development, USTA, Boca Raton, Florida; and 2Player Development, USTA, Carson, '
                'California</p>'])
    assert out == [("Ochi, Satoshi", ["Player Development, USTA, Boca Raton, Florida"]),
                   ("Campbell, Mary Jo", ["Player Development, USTA, Carson, California"])]


def test_lww_history_and_contact_lines_are_not_affiliations():
    out = _lww("Yeo, Theresa Pluth PhD, RN",
               ['<p id="">Department of Nursing, Johns Hopkins University, Baltimore, MD</p>',
                '<p id="">Revised 21 April, 2019</p>', '<p id="">First published online March 6, 2025</p>',
                f'<p id="">Contact author: Theresa Pluth Yeo, {CF_EMAIL}.</p>'])
    assert out == [("Yeo, Theresa Pluth PhD, RN", ["Department of Nursing, Johns Hopkins University, Baltimore, MD"])]


def test_lww_biography_with_credentials_is_not_an_affiliation():
    out = _lww("Warner, Sheena MS, CRNA, APN",
               ['<p id="">Sheena Warner, MS, CRNA, APN, is an incoming PhD student, School of Nursing, Emory '
                'University, Atlanta, Georgia, USA.</p>'])
    assert out == [("Warner, Sheena MS, CRNA, APN", [])]


def test_lww_leading_number_still_keys_a_line():
    out = _lww("Smith, Ann<sup>1</sup>; Jones, Bo<sup>2</sup>",
               ['<p id="">1Department of Surgery, Mercy Hospital</p>', '<p id="">2Department of Medicine, Mercy</p>'])
    assert out == [("Smith, Ann", ["Department of Surgery, Mercy Hospital"]),
                   ("Jones, Bo", ["Department of Medicine, Mercy"])]


def test_lww_double_star_is_its_own_mark():
    # ae91eae4: "**Center ..." was keyed "*", so the **-only authors got nothing and the *-only authors both lines
    out = _lww("DiGioia, Anthony M. MD<sup>*,**</sup>; Blackwell, Mike MS<sup>**</sup>; Moody, James E. MA<sup>*</sup>",
               ['<p id="BT_ID_1">Reprint requests to Anthony M. Digioia, MD, Center for Orthopaedic Research.</p>',
                '<p id="AF_ID_1">From the *Center for Orthopaedic Research, UPMC Shadyside, Pittsburgh, PA; '
                '**Center for Medical Robotics, Carnegie Mellon University, Pittsburgh, PA.</p>'])
    cor, cmu = "Center for Orthopaedic Research, UPMC Shadyside, Pittsburgh, PA", \
        "Center for Medical Robotics, Carnegie Mellon University, Pittsburgh, PA."
    assert out == [("DiGioia, Anthony M. MD", [cor, cmu]), ("Blackwell, Mike MS", [cmu]),
                   ("Moody, James E. MA", [cor])]


def test_lww_marks_inside_a_shared_line():
    # caf5790e: "and the Departments of †Pathology, ‡Radiation Oncology, and §Orthopedic Surgery ..., University of
    # Florida" is one line shared by the †, ‡ and § authors
    out = _lww("Virkus, Walter W. MD<sup>*</sup>; Mollabashy, Allaaddin MD<sup>**</sup>; Reith, John D. MD<sup>†</sup>;"
               " Berrey, B. Hudson MD<sup>§</sup>",
               ['<p id="AF_ID_1">From the *Department of Orthopedic Surgery, Rush Medical College, Chicago, IL; the '
                '**Department of Orthopedic Surgery, Henry Ford Health System, Detroit, MI; and the Departments of '
                '†Pathology, ‡Radiation Oncology, and §Orthopedic Surgery and Rehabilitation, University of Florida, '
                'Gainesville, FL.</p>'])
    florida = ("Departments of Pathology, Radiation Oncology, and Orthopedic Surgery and Rehabilitation, University of "
               "Florida, Gainesville, FL")
    assert out == [("Virkus, Walter W. MD", ["Department of Orthopedic Surgery, Rush Medical College, Chicago, IL"]),
                   ("Mollabashy, Allaaddin MD",
                    ["Department of Orthopedic Surgery, Henry Ford Health System, Detroit, MI"]),
                   ("Reith, John D. MD", [florida]), ("Berrey, B. Hudson MD", [florida])]


def test_lww_shared_line_opening_the_note_drops_from_the():
    out = _lww("Liu, Chia-Ju MD<sup>*</sup>; Cheng, Jason MD<sup>†</sup>",
               ['<p id="">From the Departments of *Nuclear Medicine, and †Oncology, National Taiwan University '
                'Hospital; and the College of Medicine, Taipei, Taiwan.</p>'])
    shared = "Departments of Nuclear Medicine, and Oncology, National Taiwan University Hospital"
    assert out == [("Liu, Chia-Ju MD", [shared]), ("Cheng, Jason MD", [shared])]


def test_lww_symbol_the_byline_does_not_use_leaves_a_shared_line_unkeyed():
    out = _lww("Smith, Ann; Jones, Bo",
               ['<p id="">From the Department of Surgery, Mercy Hospital; and the Clinic Suite #4, Mercy Plaza</p>'])
    assert out == [("Smith, Ann", ["From the Department of Surgery, Mercy Hospital",
                                   "and the Clinic Suite #4, Mercy Plaza"]),
                   ("Jones, Bo", ["From the Department of Surgery, Mercy Hospital",
                                  "and the Clinic Suite #4, Mercy Plaza"])]


# --- Zenodo: a role label is not an affiliation -----------------------------------------------------------------------

def _zenodo(affiliation):
    ld = ('{"@type": "ScholarlyArticle", "creator": [{"@type": "Person", "affiliation": "%s", "name": "Gisler, Thomas"}]}'
          % affiliation)
    html = (f'<html><head><meta property="og:url" content="https://zenodo.org/records/1"></head><body>'
            f'<script type="application/ld+json">{ld}</script></body></html>')
    return Zenodo(_soup(html)).parse()["authors"][0]["affiliations"]


def test_zenodo_role_label_is_not_an_affiliation():
    assert _zenodo("(Autor/in)") == []
    assert _zenodo("(Hrsg.)") == []


def test_zenodo_real_affiliation_stays():
    assert _zenodo("Universität Bern") == ["Universität Bern"]


# --- DergiPark ----------------------------------------------------------------------------------------------------------

def test_dergipark_corresponding_author_without_profile_link():
    # 3c3c3ae4: the second author has no profile, so her name is a <span title="Sorumlu Yazar"> with the star
    html = ('<html><head><meta name="generator" content="uds"></head><body><table class="record_properties"><tr><td>'
            '<p id="author904928"><a href="/tr/pub/@ibrahim-turan" title="Sorumlu Yazar">İbrahim Turan'
            '<span class="fa fa-star-of-life primary-author-icon"></span></a></p>'
            '<p id="author904929"><span title="Sorumlu Yazar">Ayşe Vural'
            '<span class="fa fa-star-of-life primary-author-icon"></span>'
            '<a class="article-claim-authorship" href="javascript: ">Bu kişi benim</a></span></p>'
            '<p id="author904930"><a href="/tr/pub/@x" title="Sorumlu Yazar">Ali Kaya</a></p>'
            '</td></tr></table></body></html>')
    assert corresponding_names(_soup(html)) == ["İbrahim Turan", "Ayşe Vural"]


def _dergipark_2025(*entries):
    divs = "".join(
        f'<div id="author{i}"><p><a href="/en/pub/@{i}"{f" title={chr(34)}{title}{chr(34)}" if title else ""}>{name}'
        f'{"<sup>*</sup>" if star else ""}</a></p></div>' for i, (name, title, star) in enumerate(entries, 100))
    return _soup(f'<html><body><a href="https://dergipark.org.tr/en/">DergiPark</a>{divs}</body></html>')


def test_dergipark_2025_primary_author_star_on_one_of_two_marks_them():
    # cf543741: the English interface's "Primary Author" with its '*' on one of two authors
    soup = _dergipark_2025(("Trailokya Panigrahi", None, False), ("Eureka Pattnayak", "Primary Author", True))
    assert corresponding_names(soup) == ["Eureka Pattnayak"]


def test_dergipark_2025_primary_author_star_on_sole_author_marks_no_one():
    # 00e1f51f: a sole author's star singles no one out
    assert corresponding_names(_dergipark_2025(("Vedat Esen", "Primary Author", True))) == []


def test_dergipark_2025_sorumlu_yazar_unchanged():
    soup = _dergipark_2025(("Ali Kaya", "Sorumlu Yazar", True), ("Ayşe Vural", None, False))
    assert corresponding_names(soup) == ["Ali Kaya"]


# --- Red Flower (rfppl.co.in): a list of letter marks --------------------------------------------------------------

def _rfppl(names, affs):
    parser = RedFlower(_soup("<html></html>"))
    authors = parser._split_names(names)
    parser._affiliations(authors, affs)
    return [(a[0], a[2]) for a in authors]


def test_rfppl_letter_list_mark_keys_each_letter():
    # 81edbc95: "b,dSenior Resident" is the b author's line as well as the d author's
    dept = "Department of general Surgery, Kasturba Medical College, Manipal, Karnataka 576104, India."
    out = _rfppl("Chethan Kishanchanda, Akshay Nadkarnib, Nagesh Biradarc, Balaji Jayasankard, Deeban Ramasamye",
                 f"aAssociate Professor b,dSenior Resident cAssistant Professor eIntern, {dept}")
    assert out[:4] == [("Chethan Kishanchand", [dept]), ("Akshay Nadkarni", [dept]), ("Nagesh Biradar", [dept]),
                       ("Balaji Jayasankar", [dept])]


def test_rfppl_single_letter_marks_unchanged():
    out = _rfppl("Aditya V.a, H. Prabhu M.b", "aPost Graduate, Dept. of Surgery, KMC bAssociate Professor, "
                                             "Dept. of Medicine, KMC")
    assert out == [("Aditya V.", ["Post Graduate, Dept. of Surgery, KMC"]),
                   ("H. Prabhu M.", ["Associate Professor, Dept. of Medicine, KMC"])]


# --- Karger: a contact block that names two authors ------------------------------------------------------------------

def _karger(contact):
    html = ('<html><head><meta property="og:url" content="https://karger.com/Article/FullText/1"></head><body>'
            '<span class="autoren">Saithong S.<sup>a</sup><span class="color">·</span>Chiewchengchol D.<sup>a</sup>'
            '<span class="color">·</span>Leelahavanichkul A.<sup>a</sup><br/></span>'
            '<div id="cAffi"><sup>a</sup>Department of Microbiology, Chulalongkorn University, Bangkok, Thailand</div>'
            f'<div id="cAuthors">{contact}</div></body></html>')
    return [(a["name"], a["is_corresponding"]) for a in Karger(_soup(html)).parse()["authors"]]


def test_karger_two_contact_lines_mark_both():
    # 83c6e08e
    out = _karger("<p>Direkrit Chiewchengchol, cdirekrit@live.com</p><p>Asada Leelahavanichkul, a@gmail.com</p>")
    assert [n for n, c in out if c] == ["Chiewchengchol D.", "Leelahavanichkul A."]


def test_karger_address_lines_mark_no_one_else():
    out = _karger("<p>Dr. Direkrit Chiewchengchol</p><p>Department of Microbiology, Chulalongkorn University</p>"
                  "<p>Bangkok 10330 (Thailand)</p>")
    assert [n for n, c in out if c] == ["Chiewchengchol D."]
