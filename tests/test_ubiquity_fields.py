"""Ubiquity Press platform, pages-router variant: authors, affiliations and the corresponding author from
``__NEXT_DATA__`` (oxjob #2289).

Ubiquity journals on its Next.js pages-router front end (``*.ubiquityjournal.website`` API, e.g. Methodist DeBakey
Cardiovascular Journal, Journal of the Belgian Society of Radiology, eGEMs) print every author in the byline with an
envelope link on the corresponding author only, but their head carries ONE citation_author tag (the last author's):
Parseland read one author of three, of nine. The whole author list, each author's institution and the
``corresponding`` flag (the envelope) are in ``__NEXT_DATA__``'s ``props.pageProps.data.authors``. Markup cut down
from stored pages; names are made up.
"""
from __future__ import annotations

import json

from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.ubiquity import Ubiquity

API = "https://api.account.up-j-demo.ubiquityjournal.website/api/journal/1"


def _author(first, last, institution, corresponding=False, email="info@ubiquitypress.com"):
    return {"first_name": first, "last_name": last, "institution": institution, "country": "US", "email": email,
            "bio": "", "corresponding": corresponding,
            "social": {"twitter": "", "linkedin": "", "instagram": "", "orcid": ""}}


AUTHORS = [
    _author("Ann", "Example", "Mayo Clinic, Rochester, Minnesota", corresponding=True),
    _author("Bo", "Sample", "Mayo Clinic, Rochester, Minnesota"),
    _author("Cy J.", "Tester", "University at Buffalo"),
]


def _next_data(authors, api=API, page="/articles/[...slug]"):
    return {"props": {"pageProps": {"data": {
        "publication_id": 770, "submission_id": 563, "doi": "10.9999/demo-11-2-109", "title": "A demo article",
        "abstract": "<p>We reviewed the underlying principles of demo ablation.</p>", "authors": authors,
        "galleys": [{"label": "PDF"}], "citations": []}},
        "loadProps": {"core": {"base_url": "https://journal.example.org"}}},
        "page": page, "query": {"slug": ["10.9999", "demo-11-2-109"]}, "buildId": "x",
        "runtimeConfig": {"API_URL": api, "SERVICE_CODE": "up-j-demo"}}


def _byline(authors):
    items = []
    for a in authors:
        name = f'{a["first_name"]} {a["last_name"]}'
        mail = (f'<a class="jnl-vodygu" href="mailto:{a["email"]}" title="Email {name}">'
                f'<svg class="svg-inline--fa fa-envelope" data-icon="envelope"></svg>'
                f'<div class="visually-hidden">Email {name}</div></a>') if a["corresponding"] else ""
        items.append(f'<li class="jnl-1t819t2">{name}{mail}</li>')
    return f'<h4>Authors:</h4><ul class="jnl-5kov97">{"".join(items)}</ul>'


def _page(authors=AUTHORS, data=None, meta_last_only=True):
    shown = authors[-1:] if meta_last_only else authors
    metas = "".join(f'<meta name="citation_author" content="{a["first_name"]} {a["last_name"]}"/>'
                    f'<meta name="citation_author_email" content="info@ubiquitypress.com"/>'
                    f'<meta name="citation_author_institution" content="{a["institution"]}"/>' for a in shown)
    metas += ('<meta name="citation_abstract" content="We reviewed the underlying principles of demo ablation."/>'
              '<meta name="next-head-count" content="47"/>')
    payload = json.dumps(data if data is not None else _next_data(authors), ensure_ascii=False)
    return (f'<html><head><meta charset="utf-8"/><title>A demo article</title>{metas}'
            f'<script src="/_next/static/chunks/main-05772a7caf41aecb.js" defer=""></script></head>'
            f'<body><div id="__next"><h1>A demo article</h1>{_byline(authors)}</div>'
            f'<script id="__NEXT_DATA__" type="application/json">{payload}</script></body></html>')


def _parse(html):
    return parse_page(html.encode(), "doi", "https://doi.org/10.9999/demo-11-2-109")


def test_every_author_from_next_data_not_only_the_last_meta_author():
    got = _parse(_page())["authors"]
    assert [a["name"] for a in got] == ["Ann Example", "Bo Sample", "Cy J. Tester"]


def test_each_author_gets_own_institution_verbatim():
    got = _parse(_page())["authors"]
    assert [[x["name"] for x in a["affiliations"]] for a in got] == [
        ["Mayo Clinic, Rochester, Minnesota"], ["Mayo Clinic, Rochester, Minnesota"], ["University at Buffalo"]]


def test_corresponding_is_the_author_with_the_envelope():
    got = _parse(_page())["authors"]
    assert [a["is_corresponding"] for a in got] == [True, False, False]


def test_corresponding_with_a_real_address():
    authors = [_author("Dee", "Mailer", "SUNY Buffalo", corresponding=True, email="dee@example.edu"),
               _author("Eve", "Other", "University at Buffalo")]
    got = _parse(_page(authors))["authors"]
    assert [(a["name"], a["is_corresponding"]) for a in got] == [("Dee Mailer", True), ("Eve Other", False)]


def test_empty_institution_gives_no_affiliation():
    authors = AUTHORS[:2] + [_author("Fay", "Blank", "")]
    got = _parse(_page(authors))["authors"]
    assert got[2]["name"] == "Fay Blank" and got[2]["affiliations"] == []
    assert got[0]["affiliations"] == [{"name": "Mayo Clinic, Rochester, Minnesota"}]


def test_abstract_still_read():
    assert _parse(_page())["abstract"].startswith("We reviewed the underlying principles")


def test_claimed_by_the_template_mark():
    p = Ubiquity(BeautifulSoup(_page(), "lxml"))
    assert p.authors_found() and p.is_publisher_specific_parser()


def test_parse_returns_plain_strings():
    out = Ubiquity(BeautifulSoup(_page(), "lxml")).parse()
    assert out["authors"][2] == {"name": "Cy J. Tester", "affiliations": ["University at Buffalo"],
                                 "is_corresponding": False}


def test_other_next_js_site_with_author_json_is_not_claimed():
    # The nearest look-alike: another publisher's Next.js pages-router page whose __NEXT_DATA__ carries an
    # article with an authors array of the same shape (first_name / last_name / institution / corresponding),
    # but whose API is not Ubiquity's.
    data = _next_data(AUTHORS, api="https://api.other-press.example.com/v2")
    p = Ubiquity(BeautifulSoup(_page(data=data), "lxml"))
    assert not p.authors_found()
    assert not p.is_publisher_specific_parser()


def test_plain_page_is_not_claimed():
    html = ('<html><head><meta name="citation_author" content="Ann Example"/></head>'
            '<body><h1>T</h1><script>var x = 1;</script></body></html>')
    p = Ubiquity(BeautifulSoup(html, "lxml"))
    assert not p.authors_found()
    assert not p.is_publisher_specific_parser()


def test_next_data_without_authors_is_not_claimed():
    data = _next_data(AUTHORS)
    data["props"]["pageProps"]["data"] = {"title": "An issue page"}
    p = Ubiquity(BeautifulSoup(_page(data=data), "lxml"))
    assert not p.authors_found()
