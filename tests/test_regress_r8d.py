"""Round 8d regressions (oxjob #2239, phase 2): the two pages 92bc1d9 made newly worse than production.

- journals.lww.com: record dates in the author-info notes ("Created Date: 08 February 1973; Completed Date: ...") came
  out as affiliations.
- DergiPark 2025 template: a starred English "Primary Author" on the first author marked them corresponding.

Markup is cut down from stored pages of the dev and check1 draws.
"""
from bs4 import BeautifulSoup

from parseland_lib.publisher.parsers.dergipark import corresponding_names
from parseland_lib.publisher.parsers.lippincott import Lippincott


def _soup(html):
    return BeautifulSoup(html, "lxml")


# --- LWW: record dates are never affiliations -------------------------------------------------------------------------

LWW_OG = '<meta property="og:url" content="https://journals.lww.com/x/fulltext/2021/x.aspx">'


def _lww(byline, notes):
    html = (f'<html><head>{LWW_OG}</head><body><section id="ejp-article-authors"><p id="P7">{byline}</p></section>'
            f'<section id="ejp-article-authors-info"><div class="ejp-article-authors-info-holder">{"".join(notes)}'
            f'</div></section></body></html>')
    return [(a.name, a.affiliations) for a in Lippincott(_soup(html)).parse()["authors"]]


def _kw(*words):
    # LWW wraps every word of these old records in <span class="ej-keyword">, each followed by an empty one
    return " ".join(f'<span class="ej-keyword" data-value="{w}">{w}</span><span class="ej-keyword" data-value=""></span>'
                    for w in words)


def test_lww_created_and_completed_date_paragraph_is_not_an_affiliation():
    # dev 8e1d15cf: the only note is the record's two dates, split by ';'
    note = (f'<p id="BT_ID_d61e23">{_kw("Created")} {_kw("Date")}: {_kw("08", "February", "1973")}; '
            f'{_kw("Completed")} {_kw("Date")}: {_kw("08", "February", "1973")}</p>')
    assert _lww(f'{_kw("Checker")}, {_kw("A")}', [note]) == [("Checker, A", [])]


def test_lww_history_lines_are_not_affiliations():
    # check1 3befc302, f27a1947; dev 5d44a2da, 246e5ab4: one history line per paragraph after the affiliation
    out = _lww("Smith, Ann",
               ['<p id="">Department of Orthopaedic Surgery, Gifu University School of Medicine, Gifu, Japan.</p>',
                '<p id="">Online date: November 16, 2020</p>',
                '<p id="">Submitted July 8, 1997. Revision received September 2, 1997. Accepted September 4, 1997.</p>',
                '<p id="">Acknowledgment date: August 27, 2002.</p>',
                '<p id="">First revision date: December 2, 2002. Second revision date: February 3, 2003.</p>',
                '<p id="">Acceptance date: February 11, 2003.</p>',
                '<p id="">Submitted: March 5, 2010.</p>',
                '<p id="">Final revision submitted: March 25, 2010.</p>'])
    assert out == [("Smith, Ann", ["Department of Orthopaedic Surgery, Gifu University School of Medicine, Gifu, Japan."])]


def test_lww_history_segments_of_a_semicolon_paragraph_are_dropped():
    # dev 212b35d6 / 19bfbed8 / check1 fe0a6927: "Manuscript submitted ...; revision received ...; accepted ..."
    out = _lww("Smith, Ann",
               ['<p id="">Department of Surgery, Duke University Medical Center, Durham, North Carolina; '
                'Manuscript submitted May 6,  1997; revision received October 9, 1997; accepted for publication '
                'December 5, 1997; accepted in revised form June 30, 2022.</p>'])
    assert out == [("Smith, Ann", ["Department of Surgery, Duke University Medical Center, Durham, North Carolina"])]


def test_lww_affiliation_opening_with_a_history_word_stays():
    # look-alike: a history word with no date after it is a name, not a record date
    out = _lww("Smith, Ann",
               ['<p id="">Acceptance and Commitment Therapy Unit, Department of Psychology, University of Nevada, '
                'Reno, NV</p>',
                '<p id="">Online Learning Center, Mayo Clinic, Rochester, MN</p>'])
    assert out == [("Smith, Ann", ["Acceptance and Commitment Therapy Unit, Department of Psychology, University of "
                                   "Nevada, Reno, NV", "Online Learning Center, Mayo Clinic, Rochester, MN"])]


def test_lww_line_mixing_a_date_and_an_affiliation_stays():
    # look-alike: only a line that is all record dates goes; one that also names an institution is left as it was
    line = "Submitted July 8, 1997. Department of Surgery, Mercy Hospital, Iowa City, IA."
    assert _lww("Smith, Ann", [f'<p id="">{line}</p>']) == [("Smith, Ann", [line])]


def test_lww_semicolon_paragraph_without_dates_unchanged():
    out = _lww("Smith, Ann",
               ['<p id="">Department of Online Education, University of Iowa; Publication Office, Mercy Hospital, '
                'Boston, MA</p>'])
    assert out == [("Smith, Ann", ["Department of Online Education, University of Iowa",
                                   "Publication Office, Mercy Hospital, Boston, MA"])]


# --- DergiPark 2025 template: "Primary Author" on the first author marks no one ----------------------------------------

def _dergipark_2025(*entries):
    divs = "".join(
        f'<div id="author{i}"><p><a href="/en/pub/@{i}"{f" title={chr(34)}{title}{chr(34)}" if title else ""}>{name}'
        f'{"<sup>*</sup>" if star else ""}</a></p></div>' for i, (name, title, star) in enumerate(entries, 100))
    return _soup(f'<html><body><a href="https://dergipark.org.tr/en/">DergiPark</a>{divs}</body></html>')


def test_dergipark_2025_primary_author_star_on_first_author_marks_no_one():
    # check1 af27a4fc: the star on the first of three reads as "first author"; nothing ties it to correspondence
    soup = _dergipark_2025(("Abdullah Tüzemen", "Primary Author", True), ("Ensar Balkaya", None, False),
                           ("Ceyhun Serçemeli", None, False))
    assert corresponding_names(soup) == []


def test_dergipark_2025_primary_author_star_on_a_later_author_marks_them():
    # check1 cf543741 / 92021365: on the second author "Primary Author" cannot mean the first-listed one
    soup = _dergipark_2025(("Zinnarin Babat", None, False), ("Dilek Çiftçi Baykal", "Primary Author", True))
    assert corresponding_names(soup) == ["Dilek Çiftçi Baykal"]


def test_dergipark_2025_primary_author_star_on_first_and_a_later_author_marks_no_one():
    # precision first: when the first author is among the starred, the label is not read as correspondence at all
    soup = _dergipark_2025(("Ali Kaya", "Primary Author", True), ("Ayşe Vural", None, False),
                           ("Mehmet Öz", "Primary Author", True))
    assert corresponding_names(soup) == []


def test_dergipark_2025_primary_author_star_on_sole_author_marks_no_one():
    assert corresponding_names(_dergipark_2025(("Vedat Esen", "Primary Author", True))) == []


def test_dergipark_2025_sorumlu_yazar_star_on_first_author_still_marks():
    # look-alike: the Turkish label names correspondence, so the first author's star marks them
    soup = _dergipark_2025(("Ali Kaya", "Sorumlu Yazar", True), ("Ayşe Vural", None, False))
    assert corresponding_names(soup) == ["Ali Kaya"]
