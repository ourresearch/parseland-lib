"""Corresponding authors on Research Square's current pages, from the page's embedded Next.js data (oxjob #2153).

Markup is cut down from stored researchsquare.com pages sampled 11 Nov 2026 (#2153 EXPLORE § 1). The byline shown before a
click is collapsed ("A, B, and 4 more"); the expanded list with its "Corresponding author" label is drawn from
`__NEXT_DATA__` -> props.pageProps.initialData.authors[].correspondingAuthor. The old `div.authors-expanded` block that
ResearchSquare.parse reads is gone, so the citation_author meta tags won and no one was marked: 196 of 200 sampled
pages whose work showed no corresponding author flag one (gold v1.3 dev: the flag is the gold's corresponding author on
16 of 16 Research Square pages).
"""
import json

from parseland_lib.parse import parse_page

URL = "https://www.researchsquare.com/article/rs-9737509/v1"


def _page(authors, doi="10.21203/rs.3.rs-9737509/v1", flags=None):
    flags = flags if flags is not None else [False] * len(authors)
    data = {"props": {"pageProps": {"initialData": {
        "doi": doi,
        "authors": [{"id": i, "order_by": i, "name": n, "email": "x@y.org" if f else "", "orcid": "",
                     "institution": "Hasanuddin University", "correspondingAuthor": f}
                    for i, (n, f) in enumerate(zip(authors, flags))],
    }}}, "page": "/article/[identity]/[[...version]]"}
    metas = "".join(f'<meta property="citation_author" content="{n}"/>' for n in authors)
    byline = ", ".join(authors[:3]) + (f", and {len(authors) - 3} more" if len(authors) > 3 else "")
    return (f'<html><head><meta property="og:url" content="{URL}"/>{metas}'
            f'<meta name="citation_doi" content="{doi}"/></head><body><h1><p>A title</p></h1>'
            f'<button type="button"><p class="tw-text-sm">{byline}</p></button>'
            f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script></body></html>')


def _parse(html):
    return parse_page(html.encode(), "doi", URL)["authors"]


def _corr(html):
    return [a["name"] for a in _parse(html) if a["is_corresponding"]]


def test_flagged_author_is_marked():
    names = ["Hamed Noralla Bakheet Ali", "Muhammad Hatta Jamil", "Eymal B. Demmallio", "Muslim Salam"]
    authors = _parse(_page(names, flags=[True, False, False, False]))
    assert [a["name"] for a in authors] == names  # the author list itself is unchanged
    assert [a["is_corresponding"] for a in authors] == [True, False, False, False]


def test_last_author_and_two_flags():
    names = ["Dawei Zhou", "Zhimin Li", "Shaolan Zhang", "Jianxin Zhou", "Guangzhi Shi"]
    assert _corr(_page(names, flags=[False, False, False, False, True])) == ["Guangzhi Shi"]
    assert _corr(_page(names, flags=[False, True, False, False, True])) == ["Zhimin Li", "Guangzhi Shi"]


def test_surname_first_json_name_matches_byline():
    html = _page(["Eberechukwu Njoku", "Oluwasola Abayomi Adelusi", "Ade Bello"], flags=[True, False, False])
    html = html.replace('"name": "Eberechukwu Njoku"', '"name": "Njoku, Eberechukwu"')
    assert _corr(html) == ["Eberechukwu Njoku"]


def test_no_flag_or_every_author_flagged_marks_no_one():
    names = ["Dawei Zhou", "Zhimin Li", "Shaolan Zhang"]
    assert _corr(_page(names)) == []
    assert _corr(_page(names, flags=[True, True, True])) == []


def test_other_doi_prefix_is_ignored():
    names = ["Dawei Zhou", "Zhimin Li", "Shaolan Zhang"]
    assert _corr(_page(names, doi="10.1234/other.1", flags=[True, False, False])) == []
