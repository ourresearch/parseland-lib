"""doiSerbia (National Library of Serbia, doiserbia.nb.rs) article pages: corresponding authors (oxjob #2338).

Markup is cut down from stored doiSerbia pages (17 Nov 2026). The page's citation_author meta tags carry no
correspondence flag, so the generic parser marks no one. The visible byline prints each author on its own line as
"<b>Family Given</b> (affiliation), e-mail", and shows an e-mail for the corresponding author only. Gold v1.3 marks the
one author whose e-mail the author list shows (an e-mail printed for every author, or for a sole author, is not a
mark: label-v1).
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.doiserbia import DOISerbia

URL = "https://doiserbia.nb.rs/Article.aspx?ID=1451-93722000046K"
OG = '<meta content="http://www.doiserbia.nb.rs/Article.aspx?ID=1451-93722000046K" property="og:url"/>'
ABSTRACT = "In this study, characteristic drying behaviour and kinetics of blue mussels are studied with three methods."
AFF = "(Department of Chemical Engineering, Yildiz Technical University, Istanbul, Turkey)"


def _page(meta_names, byline_names, emails, og=OG, orcid=False):
    metas = "".join(f'<meta content="{n}" name="citation_author"/>' for n in meta_names)
    lines = []
    for i, name in enumerate(byline_names):
        bold = f'<span style="font-weight: bold;">{name}</span>'
        if orcid:
            bold = (f'<a itemprop="sameAs" content="0000-0002-0819-8539" href="https://orcid.org/0000-0002-0819-8539">'
                    f'{bold} <img src="https://orcid.org/orcid_16x16.png" alt="ORCID iD icon"></a>')
        lines.append(bold + " " + AFF + (f", {emails[i]}" if emails.get(i) else "") + "<br>")
    return (f'<html><head><meta name="robots" content="index,follow"/>{og}'
            f'<meta content="Drying characteristics of blue mussels" name="citation_title"/>{metas}'
            f'<meta content="{ABSTRACT}" name="citation_abstract"/></head><body><form>'
            '<div id="ContentRight"><div class="right_articles">'
            '<span id="ContentPlaceHolder1_ArticleDetails2_labelArticleTitle"><p><strong>Drying characteristics'
            '</strong></p></span>'
            f'<span id="ContentPlaceHolder1_ArticleDetails2_labelArticleAuthors"><p><i>{"".join(lines)}</i></p></span>'
            f'<span id="ContentPlaceHolder1_ArticleDetails2_labelArticleAbstract"><p>{ABSTRACT}</p></span>'
            '</div></div></form></body></html>')


META = ["Kipcak,  Azmi Seyhun", "Derun,  Emek Moroydor", "Tugrul,  Nurcan"]
BYLINE = ["Kipcak Azmi Seyhun", "Derun Emek Moroydor", "Tugrul Nurcan"]


def _out(html):
    return parse_page(html.encode(), "doi", URL)


def _corr(html):
    return [a["name"] for a in _out(html)["authors"] if a["is_corresponding"]]


def test_lone_email_marks_that_author():
    out = _out(_page(META, BYLINE, {0: "skipcak@yildiz.edu.tr"}))
    assert [a["is_corresponding"] for a in out["authors"]] == [True, False, False]


def test_lone_email_on_a_later_author():
    assert _corr(_page(META, BYLINE, {2: "nt@yildiz.edu.tr"})) == ["Tugrul,  Nurcan"]


def test_byline_with_orcid_links():
    assert _corr(_page(META, BYLINE, {1: "ed@yildiz.edu.tr"}, orcid=True)) == ["Derun,  Emek Moroydor"]


def test_two_of_several_emails_marks_both():
    names = META + ["Doymaz,  Ibrahim"]
    byline = BYLINE + ["Doymaz Ibrahim"]
    assert _corr(_page(names, byline, {0: "a@x.tr", 3: "d@x.tr"})) == ["Kipcak,  Azmi Seyhun", "Doymaz,  Ibrahim"]


def test_every_author_with_an_email_marks_no_one():
    out = _out(_page(META, BYLINE, {0: "a@x.tr", 1: "b@x.tr", 2: "c@x.tr"}))
    assert [a["is_corresponding"] for a in out["authors"]] == [None, None, None]


def test_sole_author_with_an_email_is_not_marked():
    assert _corr(_page(["Choi,  Jae Gil"], ["Choi Jae Gil"], {0: "jgchoi@dankook.ac.kr"})) == []


def test_no_email_keeps_the_generic_output():
    out = _out(_page(META, BYLINE, {}))
    assert [a["name"] for a in out["authors"]] == META
    assert [a["is_corresponding"] for a in out["authors"]] == [None, None, None]
    assert out["abstract"] == ABSTRACT


def test_byline_names_matched_when_counts_differ():
    # one meta author fewer than the byline lines: match by name, never by position
    meta = ["Derun,  Emek Moroydor", "Tugrul,  Nurcan"]
    assert _corr(_page(meta, BYLINE, {2: "nt@yildiz.edu.tr"})) == ["Tugrul,  Nurcan"]


def test_names_and_abstract_unchanged():
    out = _out(_page(META, BYLINE, {0: "skipcak@yildiz.edu.tr"}))
    assert [a["name"] for a in out["authors"]] == META
    assert all(a["affiliations"] == [] for a in out["authors"])
    assert out["abstract"] == ABSTRACT


def test_lookalike_aspnet_page_from_another_site_not_claimed():
    other = '<meta content="https://scindeks.ceon.rs/Article.aspx?artid=0350-08611001003D" property="og:url"/>'
    html = _page(META, BYLINE, {0: "skipcak@yildiz.edu.tr"}, og=other)
    soup = BeautifulSoup(html, parser="lxml", features="lxml")
    assert not DOISerbia(soup).is_publisher_specific_parser()
    assert not DOISerbia(soup).authors_found()
    assert _corr(html) == []


def test_og_url_outside_head_not_claimed():
    html = _page(META, BYLINE, {0: "a@x.tr"}, og="").replace("<form>", "<form>" + OG)
    assert not DOISerbia(BeautifulSoup(html, parser="lxml", features="lxml")).authors_found()
