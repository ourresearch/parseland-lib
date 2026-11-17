"""
ASCE Library: the corresponding author is the one the page labels, or the one e-mail tied to some authors; an e-mail
on every author, or a numbered affiliation, marks no one (oxjob #2288).

ascelibrary.org's 2022 Literatum "core" template (div[property=author]) was claimed by no reader of its own, so the
AAAS parser won the page and took the <sup> in each author block for a mark. That <sup> is the affiliation's number,
present for every author, so every author on ~96 sampled ASCE conference papers came out corresponding. #1791's gold
(label-v1): an e-mail shown for every author is not a mark; one tied to some authors is; "(corresponding author)" is.
Markup cut down from stored pages (10.1061/9780784484869.175, 10.1061/9780784486733.005).
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.asce import AmericanSocietyOfCivilEngineers

URL = "https://ascelibrary.org/doi/10.1061/9780784484869.175"


def person(n, given, family, aff, email=False):
    """One core-template author block: the e-mail icon in the heading and 'Email:' at the affiliation's end."""
    icon = ('<a href="/cdn-cgi/l/email-protection#1c48" property="email" aria-label="Email address">'
            '<span class="__cf_email__" data-cfemail="b4e0">[email&#160;protected]</span></a>') if email else ""
    tail = (' Email: <a href="/cdn-cgi/l/email-protection#7521" property="email" aria-label="Email address">'
            '<span class="__cf_email__" data-cfemail="1347">[email&#160;protected]</span></a>') if email else ""
    return (f'<div id="con{n}" property="author" typeof="Person"><div class="heading">'
            f'<span property="givenName">{given}</span> <span property="familyName">{family}</span>{icon}</div>'
            f'<div class="content"><div class="affiliations"><div property="affiliation" typeof="Organization">'
            f'<span property="name"><sup>{n}</sup>{aff}{tail}</span></div></div>'
            f'<div class="core-author-link"><a href="/authored-by/{family}/{given}" rel="nofollow">'
            f'View all articles by this author</a></div></div></div>')


def html(people):
    blocks = "".join(person(n, *p) for n, p in enumerate(people, 1))
    metas = "".join(f'<meta name="citation_author" content="{p[1]}, {p[0]}"/>' for p in people)
    return (f'<html><head><meta property="og:url" content="{URL}"/>'
            f'<link rel="stylesheet" href="/pb-assets/css/build-1700000000000.css"/>{metas}'
            f'<meta name="citation_title" content="Pavement sensors"/></head><body><div data-pb-dropzone="main">'
            f'<section id="abstract"><div role="paragraph">We study pavement sensors in the field.</div></section>'
            f'<section class="core-authors">{blocks}</section></div></body></html>')


def asce_corr(people):
    out = AmericanSocietyOfCivilEngineers(BeautifulSoup(html(people), "lxml")).parse()
    return [a["name"] for a in out["authors"] if a["is_corresponding"]]


def page_corr(people):
    return [a["name"] for a in parse_page(html(people).encode(), "doi", URL)["authors"] if a["is_corresponding"]]


UNIV = "Professor, Dept. of Civil Engineering, Michigan State Univ., East Lansing, MI"


def test_email_on_every_author_marks_no_one():
    people = [("Ann", "Lee", "Dept. of Civil Engineering, Univ. A.", True),
              ("Bo", "Kim", "Stantec.", True), ("Cy", "Ruiz", "Dept. of Public Works.", True)]
    assert asce_corr(people) == []
    assert page_corr(people) == []


def test_no_email_and_no_label_marks_no_one():
    people = [("Ann", "Lee", "Tensar, Alpharetta, GA"), ("Bo", "Kim", "Tensar, Alpharetta, GA")]
    assert asce_corr(people) == []
    assert page_corr(people) == []


def test_email_on_one_author_marks_that_author():
    people = [("Raja", "Jaladurgam", UNIV), ("Surya Sarat Chandra", "Congress", UNIV, True), ("Bora", "Cetin", UNIV)]
    assert asce_corr(people) == ["Surya Sarat Chandra Congress"]
    assert page_corr(people) == ["Surya Sarat Chandra Congress"]


def test_label_marks_its_author_even_when_every_author_has_an_email():
    people = [("Xiang", "Qiu", "Changsha Univ. of Science and Technology, Changsha 410114, China.", True),
              ("Zhuo", "Jia", "Changsha Univ. of Science and Technology, Changsha 410114, China "
                              "(corresponding author).", True)]
    assert asce_corr(people) == ["Zhuo Jia"]
    assert page_corr(people) == ["Zhuo Jia"]


def test_label_on_every_author_keeps_every_flag():
    people = [("Ann", "Lee", "Univ. A (corresponding author).", True),
              ("Bo", "Kim", "Univ. B (corresponding author).", True)]
    assert asce_corr(people) == ["Ann Lee", "Bo Kim"]
    assert page_corr(people) == ["Ann Lee", "Bo Kim"]


def test_lone_author_with_email_still_marked():
    assert asce_corr([("Huimin", "Zhao", UNIV, True)]) == ["Huimin Zhao"]


def test_names_affiliations_and_abstract_read_as_before():
    # the same values the AAAS parser gave these pages: "given family", each affiliation's text, the abstract block
    out = parse_page(html([("Tasha", "King-Davis", "Administrator, City of Memphis.", True),
                           ("John", "Abrera", "Operational Analytics Leader, Stantec.")]).encode(), "doi", URL)
    assert [a["name"] for a in out["authors"]] == ["Tasha King-Davis", "John Abrera"]
    assert out["authors"][1]["affiliations"] == [{"name": "2Operational Analytics Leader, Stantec."}]
    assert out["abstract"] == "We study pavement sensors in the field."
