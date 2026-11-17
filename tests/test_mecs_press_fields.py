"""MECS Press (mecs-press.org: IJMECS, IJCNIS, IJITCS and sister journals) article pages (oxjob #2339).

Markup is cut down from stored pages (17 Nov 2026). The site's current template prints a citation_publisher_title
"MECS Press" meta tag, the byline as one span per author with a footnote <sup> ("1,*"), a numbered affiliation list
closed by "* Corresponding author.", the abstract under an "Abstract" heading and a "Reference" list numbered "[1]".
Before this parser only the generic one read these pages: names from citation_author tags, no corresponding author.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.mecs_press import MECSPress

URL = "https://doi.org/10.5815/ijcnis.2012.08.07"
ABSTRACT = ("The biometric passports are to prevent the illegal entry of traveler into a specific country and limit the "
            "use of counterfeit documents by more accurate identification of an individual. The paper also provides a "
            "cryptographic security analysis of the e-passport using face, fingerprint and iris biometrics.")
REFS = ("<p>[1]A. Author and B. Author, “A first paper,” J. Sec., vol. 1, pp. 1-9, 2009.<br/>"
        "[2]C. Author, “A second paper,” Int. J. Comp., 2010. doi: 10.1080/10494820.2020.1813180.<br/>"
        "[3]D. Author (2022). A third paper. Int. J. Comp. Appl., 184(34), 1-13. "
        "<a href=\"https://doi.org/10.5120/ijca2022922401\">https://doi.org/10.5120/ijca2022922401</a>.</p>")


def _author(name, sup):
    return (f'<span class="fe-paper__item-author-item"><img class="fe-paper__item-author-avatar" src="a.png" alt=""/>'
            f'<span><a href="../../authors/1.html" target="_blank">{name}</a>'
            f'<sup class="fe-paper__item-author-index">{sup}</sup></span></span>')


def _page(byline, affs=("Department of Information Technology, Gobi Arts College, Erode, India",),
          note="<p>* Corresponding author.</p>", refs=REFS, publisher="MECS Press", abstract=ABSTRACT):
    names = [n for n, _ in byline]
    metas = "".join(f'<meta name="citation_author" content="{n}">' for n in names)
    aff_html = "".join(f"<p>{i}. {a}</p>" for i, a in enumerate(affs, 1))
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<meta name="citation_publisher_title" content="{publisher}">
<meta name="citation_paper_title" content="Enhancement of Security in Passport Inspection">{metas}
<meta name="citation_pdf_url" content="https://www.mecs-press.org/ijcnis/ijcnis-v4-n8/IJCNIS-V4-N8-7.pdf">
<title>Enhancement of Security in Passport Inspection</title></head>
<body><div class="fe-content-right__second fe-paper fe-paper-detail">
<div class="fe-paper-detail__item"><h4 class="fe-paper-name">Enhancement of Security in Passport Inspection</h4></div>
<div class="fe-paper-detail__item"><h5 class="fe-paper-detail__title">Author(s)</h5>
<p class="fe-paper__item-author">{''.join(_author(n, s) for n, s in byline)}</p>
<div class="fe-paper-author__company">{aff_html}{note}</div>
<p class="fe-paper-author__date">DOI: <a href="https://doi.org/10.5815/ijcnis.2012.08.07">x</a></p></div>
<div class="fe-paper-detail__item"><h5 class="fe-paper-detail__title">Index Terms</h5><p>Biometrics, e-Passport</p></div>
<div class="fe-paper-detail__item fe-paper-detail__item-abstract"><h5 class="fe-paper-detail__title">Abstract</h5>
<p><p>{abstract}</p></p></div>
<div class="fe-paper-detail__item"><h5 class="fe-paper-detail__title">Cite This Paper</h5><p><p>V.K. Kumar, "x"</p></p></div>
<div class="fe-paper-detail__item fe-paper-detail__reference"><h5 class="fe-paper-detail__title">Reference</h5>
<div>{refs}</div></div>
</div></body></html>"""


BYLINE = [("V.K. Narendira Kumar", "1,*"), ("B. Srinivasan", "2")]


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _raw(html):
    return MECSPress(BeautifulSoup(html, parser="lxml", features="lxml")).parse()


def test_byline_is_read_in_order():
    authors = _parse(_page(BYLINE))["authors"]
    assert [a["name"] for a in authors] == ["V.K. Narendira Kumar", "B. Srinivasan"]


def test_starred_author_is_corresponding():
    authors = _parse(_page([("Ana Lima", "1"), ("Ravi Patel", "2,*"), ("Li Wei", "3")]))["authors"]
    assert [a["is_corresponding"] for a in authors] == [False, True, False]


def test_star_without_the_note_is_not_corresponding():
    # a mark the page never explains is not a corresponding-author mark (label-v1)
    authors = _parse(_page(BYLINE, note=""))["authors"]
    assert not any(a["is_corresponding"] for a in authors)


def test_affiliations_are_not_returned():
    # #2339: affiliations fall under the 1,000-works floor (every sampled work already has them), so not shipped
    assert all(a["affiliations"] == [] for a in _parse(_page(BYLINE))["authors"])


def test_abstract_is_read():
    assert _parse(_page(BYLINE))["abstract"] == ABSTRACT


def test_reference_list_is_read_whole():
    out = _raw(_page(BYLINE))
    refs = out["references"]
    assert [r["position"] for r in refs] == [1, 2, 3]
    assert refs[0]["raw"].startswith("A. Author and B. Author")
    assert [r["doi"] for r in refs] == [None, "10.1080/10494820.2020.1813180", "10.5120/ijca2022922401"]
    assert out["references_complete"] is True


def test_reference_list_one_paragraph_per_entry():
    refs = "<p>[1]A first entry, 2009.</p>\n<p>[2]A second entry, 2010. </p>\n<p>[3]A third entry, 2011.</p>"
    out = _raw(_page(BYLINE, refs=refs))
    assert [r["raw"] for r in out["references"]] == ["A first entry, 2009.", "A second entry, 2010.",
                                                     "A third entry, 2011."]
    assert out["references_complete"] is True


def test_reference_list_with_a_gap_is_not_whole():
    refs = "<p>[1]A first entry, 2009.<br/>[2]A second entry, 2010.<br/>[4]A fourth entry, 2012.</p>"
    out = _raw(_page(BYLINE, refs=refs))
    assert len(out["references"]) == 3
    assert out["references_complete"] is False


def test_issue_table_of_contents_is_not_read():
    # the same template's issue pages list many papers' bylines but are no article page
    html = _page(BYLINE).replace("fe-paper-detail", "fe-paper-list").replace(
        '<meta name="citation_paper_title" content="Enhancement of Security in Passport Inspection">', "")
    assert not MECSPress(BeautifulSoup(html, parser="lxml", features="lxml")).authors_found()


def test_look_alike_page_of_another_publisher_is_not_claimed():
    html = _page(BYLINE, publisher="Another Press")
    parser = MECSPress(BeautifulSoup(html, parser="lxml", features="lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
