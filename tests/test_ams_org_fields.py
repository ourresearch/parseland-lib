"""American Mathematical Society journal pages (ams.org): the "Additional Notes" entry (oxjob #2330).

Markup is cut down from stored ams.org article pages (17 Nov 2026). The article's Additional Information block ends
with "Additional Notes:", where AMS prints the support note ("The first author was partially supported by ...") and,
on some articles, which author is the corresponding author ("The fifth author is the corresponding author"). The
current template lists the block as <li>s; the older one runs label links and <br />s inside one paragraph.
#2239's label-v2 dev gold (an AMS page, both passes) reads the support sentence as the funding statement.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.ams import AmericanMathematicalSociety

URL = "https://www.ams.org/journals/proc/2019-147-06/S0002-9939-2019-14429-1/"
OG = '<meta property="og:title" content="American Mathematical Society"/>'


def _head(names, og=OG):
    metas = "".join(f'<meta name="citation_author" content="{n}"/>'
                    f'<meta name="citation_author_institution" content="University of {n.split(", ")[0]}"/>'
                    for n in names)
    return f'<html><head>{metas}<meta name="citation_title" content="A title"/>{og}</head>'


def _new_template(names, notes, og=OG):
    people = "".join(f"<li><strong>{n}</strong></li><li>Affiliation: University of {n.split(', ')[0]}</li>"
                     f"<li>Email: someone@example.edu</li>" for n in names)
    note = f"<li>Additional Notes: {notes}</li>" if notes is not None else ""
    return (_head(names, og) + '<body><section id="Abstract"><h2>Abstract:</h2> We prove a theorem.</section>'
            '<section id="additionalinformation"><details><summary>Additional Information</summary><ul>'
            f"{people}<li>Received by editor(s): August 7, 2018</li>{note}<li>Communicated by: Someone</li>"
            "<li>&copy; Copyright 2019 American Mathematical Society</li></ul></details></section></body></html>")


def _old_template(names, notes):
    label = '<a href="/jourhtml/abstracthelp.html#addinfo">{}</a>'
    people = "".join(f"<strong>{n}</strong><br />{label.format('Affiliation:')} University of {n.split(', ')[0]}"
                     f"<br />{label.format('Email:')} someone@example.edu<br /><br />" for n in names)
    return (_head(names) + '<body><p align="left"><a name="Abstract" id="Abstract" class="abstractSubHead">Abstract: '
            '</a>We prove a theorem.</p><p align="left"><a name="Additional"></a>' + people +
            f"{label.format('Published electronically:')} June 15, 2021<br />"
            f"{label.format('Additional Notes:')} {notes}<br />"
            f"{label.format('Article copyright:')} &copy; Copyright 2021 American Mathematical Society</p></body></html>")


def _parse(html):
    return AmericanMathematicalSociety(BeautifulSoup(html, "lxml")).parse()


TWO = ["Chuaqui, Martin", "Osgood, Brad"]
FIVE = ["Liu, Chun", "Wang, Cheng", "Wise, Steven", "Yue, Xingye", "Zhou, Shenggao"]


def test_support_note_is_the_funding_statement():
    html = _new_template(TWO, "The first author was partially supported by Fondecyt Grant #1150115.")
    assert _parse(html)["funding_statement"] == "The first author was partially supported by Fondecyt Grant #1150115."
    assert parse_page(html.encode(), "doi", URL)["funding_statement"] == \
        "The first author was partially supported by Fondecyt Grant #1150115."


def test_older_template_note_and_corresponding_author():
    html = _old_template(FIVE, "This work was supported in part by NSF grant DMS-1759535 (first author).<br />\n"
                               "The fifth author is the corresponding author\n")
    parsed = _parse(html)
    assert parsed["funding_statement"] == "This work was supported in part by NSF grant DMS-1759535 (first author)."
    authors = parse_page(html.encode(), "doi", URL)["authors"]
    assert [a["is_corresponding"] for a in authors] == [False, False, False, False, True]


def test_corresponding_note_in_the_current_template():
    html = _new_template(TWO, "Supported by NSFC grant 11671357. The second author is the corresponding author.")
    authors = parse_page(html.encode(), "doi", URL)["authors"]
    assert [a["is_corresponding"] for a in authors] == [False, True]


def test_note_that_is_not_about_funding_is_left_out():
    parsed = _parse(_new_template(TWO, "Dedicated to Professor Peter Duren on the occasion of his 80th birthday."))
    assert parsed.get("funding_statement") is None


def test_no_note_leaves_the_output_as_before():
    html = _new_template(TWO, None)
    assert _parse(html) == {"authors": [{"name": n, "affiliations": [f"University of {n.split(', ')[0]}"],
                                         "is_corresponding": None} for n in TWO],
                            "abstract": "We prove a theorem."}


def test_ordinal_past_the_byline_marks_no_one():
    html = _new_template(TWO, "The third author is the corresponding author.")
    assert [a["is_corresponding"] for a in parse_page(html.encode(), "doi", URL)["authors"]] == [None, None]


def test_look_alike_page_of_another_site_is_not_read():
    """Same Additional Information markup, another publisher's og:title: this parser's parse() also runs (and can win)
    on any page with citation_author tags, so it must not read the notes there."""
    other = '<meta property="og:title" content="Journal of Something"/>'
    html = _new_template(TWO, "The first author was supported by NSF grant 123. The first author is the corresponding "
                              "author.", og=other)
    parser = AmericanMathematicalSociety(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert "funding_statement" not in parser.parse()
    assert not any(a["is_corresponding"] for a in parser.parse()["authors"])
