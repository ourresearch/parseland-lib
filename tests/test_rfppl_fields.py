"""Red Flower Publication (rfppl.co.in) article pages (oxjob #2339).

Markup cut down from stored view_abstract.php pages: a layout table where the row after td.articleTitle holds the byline
(names with glued markers) and the next row (or a second <p>) the affiliation line; "Corresponding Author : <name>, ..."
sits in the abstract block. Names are invented.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.rfppl import RedFlower

URL = "https://rfppl.co.in/view_abstract.php?jid=9&art_id=1"
ABSTRACT = ("Background: This study looks at something in a hospital population over three years. Methods: We counted "
            "cases and compared groups with standard tests. Results: Most cases were in adults and the rest were in "
            "children. Conclusion: The pattern holds across the period studied and should guide future work.")


def _page(byline_rows, corr="", title="Red Flower Publications"):
    return f"""<style>div.pagination {{ padding: 2px; }}</style>
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<html><head><title>{title}</title><link rel="stylesheet" href="css/style.css"/></head><body>
<table class="NewShadow">
<tr><td colspan="3"><span class="Heading1">Indian Journal of Something</span></td></tr>
<tr><td height="30" colspan="3" align="center" class="articleTitle"><span class="inner-content">Original Article</span>
<br><br><span class="Heading1" style="font-size:15px;">A Study of Something in Adults</span></td></tr>
{byline_rows}
<tr><td colspan="3"><div class="inner-content">DOI: http://dx.doi.org/10.21088/ijx.1234.5678.1</div></td></tr>
<tr><td colspan="3"><div style="padding-left:8px;" class="inner-content"><strong>Abstract</strong><br><p>{ABSTRACT}</p>
<p>Keywords: Something; Adults.</p>{corr}</div></td></tr>
</table></body></html>"""


def _old_rows(names, affs):
    return (f'<tr><td height="40" colspan="3" align="center">{names}</td></tr>'
            f'<tr><td colspan="3" class="inner-content" style="text-align:center;">{affs}</td></tr>')


def _new_rows(names, affs):
    return f'<tr><td colspan="3"><p style="margin: 6px;">{names}</p><p style="margin: 6px;">{affs}</p></td></tr>'


def _authors(html):
    out = parse_page(html.encode(), "doi", URL)
    return [(a["name"], [x["name"] for x in a["affiliations"]], a["is_corresponding"]) for a in out["authors"]]


ADDRESS = "Department of Pathology, Sample Medical College, Pune, Maharashtra 411001, India."


def test_digit_markers_job_titles_share_the_address_and_corresponding_by_initial():
    html = _page(_old_rows("Asha Kumar Rao1, Bina Desai2, Chetan V. Iyer3",
                           f"1Professor and Head, 2Tutor and Senior Resident 3Assistant Professor, {ADDRESS}"),
                 corr="<br><strong>Corresponding Author </strong>: B. Desai, Tutor, Department of Pathology, Pune.")
    assert _authors(html) == [
        ("Asha Kumar Rao", [ADDRESS], False),
        ("Bina Desai", [ADDRESS], True),
        ("Chetan V. Iyer", [f"Assistant Professor, {ADDRESS}"], False),
    ]


def test_text_before_the_first_marker_is_the_unprinted_first_marker():
    html = _page(_old_rows("Asha Rao1, Bina Desai2",
                           "Assistant Professor, Department of Medicine 2Professor, Department of Surgery, "
                           "Sample Institute of Medical Sciences, Delhi"))
    assert _authors(html) == [
        ("Asha Rao", ["Assistant Professor, Department of Medicine"], False),
        ("Bina Desai", ["Professor, Department of Surgery, Sample Institute of Medical Sciences, Delhi"], False),
    ]


def test_star_markers_in_the_newer_layout():
    html = _page(_new_rows("Dr. Asha Rao*, Bina Desai**, Chetan Iyer***",
                           "*PhD Scholar, **Assistant Professor ***Professor &amp; Director, Dept. of Anatomy, "
                           "Sample University, Jamnagar."),
                 corr="<strong>Corresponding Author</strong> : Chetan Iyer***")
    assert _authors(html) == [
        ("Asha Rao", ["Dept. of Anatomy, Sample University, Jamnagar."], False),
        ("Bina Desai", ["Dept. of Anatomy, Sample University, Jamnagar."], False),
        ("Chetan Iyer", ["Professor & Director, Dept. of Anatomy, Sample University, Jamnagar."], True),
    ]


def test_letter_markers_are_stripped_from_names():
    html = _page(_old_rows("Rao Asha V.a, H. Desai B.b",
                           f"aPost Graduate bAssociate Professor, {ADDRESS}"),
                 corr="<br><strong>Corresponding Author </strong>: Desai Bina H., Associate Professor, Pune.")
    assert _authors(html) == [
        ("Rao Asha V.", [ADDRESS], False),
        ("H. Desai B.", [f"Associate Professor, {ADDRESS}"], True),
    ]


def test_range_and_dotted_markers():
    html = _page(_old_rows("Asha Rao1, Bina Desai2., Chetan Iyer3, Deepa Nair4",
                           "1Senior Resident, Department of Surgery, Sample Hospital, Delhi, 2.Professor, "
                           "Department of Anatomy, Other College, Kollam, 3-4Senior Resident, Department of Plastic "
                           "Surgery, Third Institute of Medical Education, Pondicherry 605006, India."))
    got = _authors(html)
    assert [a[0] for a in got] == ["Asha Rao", "Bina Desai", "Chetan Iyer", "Deepa Nair"]
    assert got[1][1] == ["Professor, Department of Anatomy, Other College, Kollam"]
    assert got[2][1] == got[3][1] == ["Senior Resident, Department of Plastic Surgery, Third Institute of Medical "
                                      "Education, Pondicherry 605006, India."]


def test_unmarked_list_one_per_author_and_a_bare_job_title_gets_nothing():
    aff = "Assistant Professor, Dept. of Community Medicine, Sample Institute of Medical Sciences, Bidar, India."
    html = _page(_old_rows("Asha Rao, Bina Desai, Chetan Iyer", f"{aff} , {aff} ,  Assistant Professor, "),
                 corr="<br><strong>Corresponding Author </strong>: Asha Rao")
    assert _authors(html) == [("Asha Rao", [aff], True), ("Bina Desai", [aff], False), ("Chetan Iyer", [], False)]


def test_corresponding_line_naming_no_author_marks_no_one():
    html = _page(_old_rows("Asha Rao1, Bina Desai2", f"1,2Assistant Professor, {ADDRESS}"),
                 corr="<br><strong>Corresponding Author </strong>: Assistant Professor, Department of Pathology")
    assert [a[2] for a in _authors(html)] == [False, False]


def test_abstract_is_still_read():
    html = _page(_old_rows("Asha Rao1, Bina Desai2", f"1,2Assistant Professor, {ADDRESS}"))
    assert parse_page(html.encode(), "doi", URL)["abstract"].startswith("Background: This study")


def test_affiliation_row_repeating_the_names_gives_no_affiliations():
    html = _page(_old_rows("Asha Rao1, Bina Desai2", "Asha Rao1, Bina Desai2"))
    assert _authors(html) == [("Asha Rao", [], False), ("Bina Desai", [], False)]


def test_look_alike_layout_on_another_site_is_not_claimed():
    html = _page(_old_rows("Asha Rao1, Bina Desai2", f"1,2Assistant Professor, {ADDRESS}"),
                 title="Some Other Publisher")
    parser = RedFlower(BeautifulSoup(html, "lxml"))
    assert not parser.authors_found() and not parser.is_publisher_specific_parser()


def test_issue_contents_page_of_the_same_site_is_not_claimed():
    toc = ('<html><head><title>Red Flower Publications</title></head><body><table><tr><td>'
           '<a href="view_abstract.php?art_id=1" class="articleTitle">A Study of Something</a></td></tr>'
           '<tr><td height="40">Asha Rao*, Bina Desai** | DOI: http://dx.doi.org/10.21088/x.1</td></tr>'
           '</table></body></html>')
    parser = RedFlower(BeautifulSoup(toc, "lxml"))
    assert not parser.authors_found()
