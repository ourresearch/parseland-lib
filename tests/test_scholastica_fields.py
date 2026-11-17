"""Scholastica journal websites (scholasticahq.com and the journals it hosts on their own domains) (oxjob #2289).

Markup cut down from stored Scholastica pages (17 Nov 2026, #2289 template sample). Every page loads its favicon and
stylesheet from assets.scholasticahq.com in its <head>, and keeps the article's record as JSON in a script at the end
of the body (`window.ARTICLE = {...}`): the byline the browser draws, with each author's affiliations, a
`corresponding` flag and a free-text note. The stored page prints the names only, so the generic reader (citation_author
tags) gave no affiliation and no corresponding author. Some articles also print a "Correspondence to:" section
(data-section="corr") that names the corresponding author on its first line.
"""
import json

from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.scholastica import Scholastica

URL = "https://www.joghr.org/article/92099-the-more-the-better"
TITLE = "The more the better? Antenatal care visits and the components of care received"
ABSTRACT = ("Background: The World Health Organization promotes antenatal care as a package of health interventions "
            "women receive during pregnancy. This study examined the association between the number of visits and "
            "the number of components received. Methods: A cross-sectional study of a household survey.")
HEAD = ('<link rel="icon" type="image/x-icon" href="https://assets.scholasticahq.com/assets/favicon-5757.ico">'
        '<link rel="stylesheet" href="https://assets.scholasticahq.com/dist/journal-website/styles.2fc3.css">')
NAMES = ["Nshimirimana Clement", "Tom Smekens", "Lenka Benova"]
ITM = ("Department of Public Health", "Institute of Tropical Medicine, Antwerpen, Belgium")


def _author(name, i, affs=(), corresponding=False, note=None, **extra):
    first, _, last = name.rpartition(" ")
    return {"id": 100 + i, "name": name, "first_name": first, "last_name": last, "position": i, "note": note,
            "author_type": "person", "organization": None, "corresponding": corresponding,
            "affiliations": [{"id": 900 + 10 * i + j, "institution_name": inst, "department": dept, "position": j,
                              "ror_id": None, "full_name": ", ".join(p for p in (dept, inst) if p)}
                             for j, (dept, inst) in enumerate(affs)], **extra}


def _page(authors, head=HEAD, body="", record=True):
    names = [a["name"] for a in authors]
    metas = "".join(f'<meta name="citation_author" content="{n}">' for n in names)
    script = (f'<script>\n  window.ARTICLE = {json.dumps({"id": 92099, "title": TITLE, "authors": authors})};\n'
              '  </script>') if record else ""
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>{TITLE} | Published in Journal</title>'
            f'<link rel="canonical" href="{URL}"><base href="/">{head}'
            f'<meta name="citation_title" content="{TITLE}">{metas}'
            f'<meta name="citation_abstract" content="{ABSTRACT}"></head>'
            f'<body><div class="article-body">{body}</div><script>window.JOURNAL = {{"id": 1}};</script>{script}'
            '</body></html>')


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _affs(html):
    return [[aff["name"] for aff in a["affiliations"]] for a in _parse(html)["authors"]]


def _corr(html):
    return [a["name"] for a in _parse(html)["authors"] if a["is_corresponding"]]


def test_affiliations_come_from_the_article_record():
    authors = [_author(NAMES[0], 0, [ITM]), _author(NAMES[1], 1, [ITM, (None, "University of Bern")]),
               _author(NAMES[2], 2)]
    full = "Department of Public Health, Institute of Tropical Medicine, Antwerpen, Belgium"
    assert _affs(_page(authors)) == [[full], [full, "University of Bern"], []]


def test_an_empty_affiliation_record_is_no_affiliation():
    author = _author(NAMES[0], 0)
    author["affiliations"] = [{"id": 1, "institution_name": None, "department": None, "position": None,
                               "ror_id": None, "full_name": None}]
    assert _affs(_page([author, _author(NAMES[1], 1)])) == [[], []]


def test_the_records_flag_marks_the_corresponding_author():
    authors = [_author(NAMES[0], 0, [ITM]), _author(NAMES[1], 1, [ITM], corresponding=True), _author(NAMES[2], 2)]
    assert _corr(_page(authors)) == [NAMES[1]]


def test_an_author_note_that_says_corresponding_author_marks_that_author():
    authors = [_author(NAMES[0], 0, corresponding=None), _author(NAMES[1], 1, corresponding=None),
               _author(NAMES[2], 2, corresponding=None, note="Corresponding author")]
    assert _corr(_page(authors)) == [NAMES[2]]
    authors[2]["note"] = "**Corresponding author:**\nProf. Dr Lenka Benova\nE-mail: lb@example.org"
    assert _corr(_page(authors)) == [NAMES[2]]


def test_a_note_that_names_another_author_or_only_gives_an_email_is_no_mark():
    authors = [_author(NAMES[0], 0, note="Corresponding author: Tom Smekens, ts@example.org"),
               _author(NAMES[1], 1), _author(NAMES[2], 2, note="Lenka Benova (lb@example.org) is a researcher.")]
    assert _corr(_page(authors)) == []


def test_the_correspondence_section_marks_the_author_it_names():
    body = ('<h2 id="disclosure-of-interest-coi" data-section="coi">Disclosure of interest</h2>'
            '<p>The authors declare that they have no competing interests.</p>'
            '<h2 id="correspondence-to-corr" data-section="corr">Correspondence to:</h2>'
            '<p>Nshimirimana Clement.<br>Department of public health, Institute of Tropical Medicine, Antwerpen, '
            'Belgium<br>E-mail: <a href="/cdn-cgi/l/email-protection">[email protected]</a></p>')
    authors = [_author(n, i, [ITM]) for i, n in enumerate(NAMES)]
    assert _corr(_page(authors, body=body)) == [NAMES[0]]


def test_names_follow_the_record_in_byline_order_with_organisations_and_without_other_contributors():
    authors = [_author("Bright Harbour", 1, author_type="organization"), _author("Jane Roe", 0, [ITM]),
               _author("Pat Lee", 2, contributor_type="translator")]
    authors[0].update(first_name=None, last_name=None, organization="Bright Harbour")
    out = _parse(_page(authors))["authors"]
    assert [a["name"] for a in out] == ["Jane Roe", "Bright Harbour"]


def test_the_abstract_is_the_one_the_generic_reader_gave():
    authors = [_author(NAMES[0], 0, [ITM])]
    claimed, unclaimed = _parse(_page(authors)), _parse(_page(authors, head=""))
    assert claimed["authors"][0]["affiliations"] and not unclaimed["authors"][0]["affiliations"]
    assert claimed["abstract"] == unclaimed["abstract"] and claimed["abstract"].startswith("Background")


def test_a_page_without_the_record_is_left_to_the_generic_reader():
    html = _page([_author(n, i, [ITM]) for i, n in enumerate(NAMES)], record=False)
    assert not Scholastica(BeautifulSoup(html, "lxml")).authors_found()
    assert [a["name"] for a in _parse(html)["authors"]] == NAMES and _affs(html) == [[], [], []]


def test_a_look_alike_page_of_another_platform_is_not_claimed():
    # the same window.ARTICLE global and a Scholastica image in the body, but no Scholastica asset in the <head>
    body = '<img src="https://assets.scholasticahq.com/assets/powered-by.png">'
    html = _page([_author(NAMES[0], 0, [ITM], corresponding=True)], head='<link rel="icon" href="/favicon.ico">',
                 body=body)
    soup = BeautifulSoup(html, "lxml")
    assert not Scholastica(soup).is_publisher_specific_parser() and not Scholastica(soup).authors_found()
    assert _affs(html) == [[]] and _corr(html) == []
