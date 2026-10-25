"""Affiliations on OUP book chapters and Taylor & Francis book chapters (oxjob #1809).

Markup is cut down from stored production pages. OUP chapter pages (academic.oup.com/book/.../chapter/...) take names
from schema meta tags and keep each author's card, with OUP's structured affiliations, in div.at-ChapterAuthors; the
parser never read those cards. taylorfrancis.com pages keep each chapter contributor's affiliations in the page's
Angular TransferState JSON (product.contributors[].affiliations); older stored pages hold them only there, newer ones
also print one comma-joined citation_author_institution tag that the generic parser gave to one author.
"""
import json

from parseland_lib.parse import parse_page


def _affs(out):
    return [(a["name"], [x["name"] for x in a["affiliations"]]) for a in out["authors"]]


def _oup_card(name, affiliations=()):
    affs = "".join(f'<div class="aff"><div class="institution">{a}</div></div>' for a in affiliations)
    block = f'<div class="info-card-affilitation">{affs}</div>' if affiliations else ""
    return f"""
    <div class="al-author-name book-info__author js-flyout-wrap">
      <a class="linked-name js-linked-name book-info__author-link" href="javascript:;">{name}</a>
      <div class="al-author-info-wrap arrow-up book-info__author-info stats-author-info-panel">
        <div class="info-card-author authorInfo_ChapterTopInfoChapter">
          <div class="name-role-wrap"><div class="info-card-name"> {name} </div></div>
          {block}
          <div class="info-card-search-label"> Find on </div>
        </div>
      </div>
    </div>"""


def _oup_chapter_page(meta_names, cards):
    metas = "".join(f'<meta name="citation_author" content="{n}">' for n in meta_names)
    return f"""<html><head>
    <meta property="og:url" content="https://academic.oup.com/book/54659/chapter/422637511">{metas}
    </head><body><div class="widget widget-ChapterTopInfo"><div class="chapterTopInfo content-metadata_wrap">
    <h1 class="chapter-title at-chapter-title">The production of neutrons</h1>
    <div class="chapter-authors at-ChapterAuthors"><div class="al-authors-list chapter__author-list">
    {"".join(_oup_card(n, a) for n, a in cards)}
    </div></div></div></div></body></html>""".encode()


def test_oup_chapter_cards_give_meta_tag_authors_their_affiliations():
    # 10.1093/oso/9780198519706.003.0003: only Carlile's card carries affiliations
    html = _oup_chapter_page(
        ["Willis, B T M", "Carlile, C J"],
        [("B T M Willis", ()), ("C J Carlile", ("University of Oxford, U.K", "Lund University, Sweden"))])
    out = parse_page(html, "doi", "https://academic.oup.com/book/54659/chapter/422637511")
    assert _affs(out) == [("Willis, B T M", []),
                          ("Carlile, C J", ["University of Oxford, U.K", "Lund University, Sweden"])]


def test_oup_chapter_card_matching_no_author_or_an_editor_card_changes_nothing():
    html = _oup_chapter_page(
        ["Helft, Paul R."],
        [("Paul R. Helft (ed.)", ()), ("Someone Else", ("Indiana University School of Medicine",))])
    out = parse_page(html, "doi", "https://academic.oup.com/book/63406/chapter/576410044")
    assert _affs(out) == [("Helft, Paul R.", [])]


def _tf_encode(obj):
    return json.dumps(obj).replace("&", "&a;").replace('"', "&q;")


def _tf_page(contributors, jsonld_authors, institution_meta=None):
    state = {"product": {"_id": "b4d87522", "type": "chapter", "title": "Introduction", "contributors": contributors}}
    jsonld = {"@context": "https://schema.org", "@type": "Chapter", "name": "Introduction",
              "url": "https://www.taylorfrancis.com/chapters/edit/10.4324/9780203881866-8/introduction",
              "publisher": {"@type": "Organization", "name": "Taylor & Francis"}, "author": jsonld_authors}
    metas = "".join(f'<meta name="citation_author" content="{c["fullName"]}">' for c in contributors)
    if institution_meta:
        metas += f'<meta name="citation_author_institution" content="{institution_meta}">'
    return f"""<html><head>
    <meta property="og:url" content="https://www.taylorfrancis.com/chapters/edit/10.4324/9780203881866-8/introduction">
    {metas}<script type="application/ld+json">{json.dumps(jsonld)}</script>
    </head><body><script id="product-detail-page-state" type="application/json">{_tf_encode(state)}</script>
    </body></html>""".encode()


def _contributor(given, family, affiliations, position):
    # affiliation names as T&F stores them; None is an empty record ({"name": null, ...}), common on these pages
    return {"givenName": given, "familyName": family, "fullName": f"{given} {family}", "roles": ["author"],
            "position": position, "affiliations": [{"name": a, "department": None, "address": None}
                                                   for a in affiliations]}


def test_tandf_chapter_contributor_affiliations_reach_their_authors():
    # 10.4324/9780203881866-8 (older stored page: the affiliations are only in the page JSON)
    html = _tf_page(
        [_contributor("Mithu", "Alur", ["National Resource Centre for Inclusion, India"], 1),
         _contributor("Michael", "Bach", ["University of Manitoba, Canada"], 2)],
        {"@type": "Person", "givenName": "Mithu, Michael", "familyName": "Alur, Bach"})
    out = parse_page(html, "doi", "https://www.taylorfrancis.com/chapters/edit/10.4324/9780203881866-8/introduction")
    assert _affs(out) == [("Mithu Alur", ["National Resource Centre for Inclusion, India"]),
                          ("Michael Bach", ["University of Manitoba, Canada"])]


def test_tandf_joined_institution_tag_is_split_per_author_from_the_page_json():
    # 10.1201/9781003078081-12: the generic parser gave both strings, comma-joined, to the last author
    html = _tf_page(
        [_contributor("R.", "Bielecki", ["Construction Authority Hamburg"], 1),
         _contributor("J.", "Schreyer", ["STUVA"], 2)],
        [{"@type": "Person", "givenName": "R.", "familyName": "Bielecki"},
         {"@type": "Person", "givenName": "J.", "familyName": "Schreyer"}],
        institution_meta="Construction Authority Hamburg,STUVA")
    out = parse_page(html, "doi", "https://www.taylorfrancis.com/chapters/edit/10.1201/9781003078081-12/x")
    assert _affs(out) == [("R. Bielecki", ["Construction Authority Hamburg"]), ("J. Schreyer", ["STUVA"])]


def test_tandf_empty_or_unnamed_affiliations_add_nothing():
    html = _tf_page([_contributor("Emma", "Heywood", [None], 1)],
                    {"@type": "Person", "givenName": "Emma", "familyName": "Heywood"})
    out = parse_page(html, "doi", "https://www.taylorfrancis.com/chapters/mono/10.4324/9781315542171-4/x")
    assert _affs(out) == [("Emma Heywood", [])]
