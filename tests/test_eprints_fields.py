"""Authors on EPrints repository record pages reached by DOI (oxjob #2268).

Markup is cut down from stored EPrints 3.3 / 3.4 summary pages (REAL at mtak.hu, TUprints, Maynooth's journal archive).
EPrints prints its byline from the record's creators and gives them in eprints.creators_name / DC.creator tags; most
EPrints sites print no citation_author tags, so on the DOI path no parser read a byline (the Dublin Core reader in
parse.py runs on repository (pmh) pages only). Sites that do print citation_author tags (ZORA at uzh.ch) stay with the
generic parser. Journal platforms that copy the eprints.* tag family for Google Scholar (IATED's digital library, some
WordPress journal themes) are not EPrints and are not claimed.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.eprints import EPrints

URL = "https://real.example.hu/93231/"
GENERATOR = '<meta name="Generator" content="EPrints 3.3.15" />'


def _page(creators, extra_head="", body="", generator=GENERATOR):
    metas = "".join(f'<meta name="eprints.creators_name" content="{n}" />' for n in creators)
    dc = "".join(f'<meta name="DC.creator" content="{n}" />' for n in creators)
    return (f'<html><head>{generator}<meta name="eprints.eprintid" content="93231" />'
            f'<meta name="eprints.type" content="article" />{metas}'
            f'<meta name="eprints.title" content="A record title" /><meta name="DC.title" content="A record title" />'
            f'{dc}{extra_head}</head><body><div class="ep_summary_content"><p>'
            f'{" and ".join(creators)} (2019) A record title. Magyar Urológia, 2019 (1). pp. 3-6.</p>{body}'
            f'</div></body></html>')


def _authors(html):
    return [a["name"] for a in parse_page(html.encode(), "doi", URL)["authors"]]


def test_creators_are_the_byline_in_page_order():
    names = ["Berczi, Csaba", "Kiss, Zoltán", "Flaskó, Tibor"]
    assert _authors(_page(names)) == names


def test_group_creator_is_one_author():
    # mil.co's Colombian maritime repository credits its directorate: one group author, as the page prints it
    assert _authors(_page(["Dirección General Marítima, DIMAR"])) == ["Dirección General Marítima, DIMAR"]


def test_empty_creator_row_is_skipped():
    assert _authors(_page(["Corry, Geoffrey", ", ", "Hynes, Pat"])) == ["Corry, Geoffrey", "Hynes, Pat"]


def test_edited_volume_has_no_authors():
    # an edited volume lists eprints.editors_name only ("A cura di: ..."): editors are not authors
    html = _page([], extra_head='<meta name="eprints.editors_name" content="Botti, Federica" />')
    assert _authors(html) == []


def test_no_affiliation_and_no_corresponding_mark():
    # eprints.creators_id is the depositor's record of e-mails, never shown as a mark on the page
    html = _page(["Berczi, Csaba", "Kiss, Zoltán"], extra_head='<meta name="eprints.creators_id" content="b@x.hu" />')
    authors = parse_page(html.encode(), "doi", URL)["authors"]
    assert [a["affiliations"] for a in authors] == [[], []]
    assert not any(a["is_corresponding"] for a in authors)


def test_abstract_tag_still_read():
    text = ("This paper considers the dynamics of the process used in creating the political conditions to bring "
            "an end to the violence, with lessons drawn for other peace processes and for mediators who work in them, "
            "and it sets out what the authors learned over two decades of practice.")
    html = _page(["Corry, Geoffrey", "Hynes, Pat"],
                 extra_head=f'<meta name="eprints.abstract" content="{text}" /><meta name="DC.description" content="{text}" />')
    out = parse_page(html.encode(), "doi", URL)
    assert [a["name"] for a in out["authors"]] == ["Corry, Geoffrey", "Hynes, Pat"]
    assert out["abstract"] == text


def test_page_with_citation_author_tags_stays_with_the_generic_parser():
    # ZORA (uzh.ch) prints citation_author tags; they win as before
    extra = "".join(f'<meta name="citation_author" content="{n}" />' for n in ["Verner, Martin", "Bayer, Nicole"])
    html = _page(["Verner, Martin", "Bayer, Nicole"], extra_head=extra)
    assert not EPrints(BeautifulSoup(html, "lxml")).authors_found()
    assert _authors(html) == ["Verner, Martin", "Bayer, Nicole"]


def test_journal_platform_copying_eprints_tags_is_not_claimed():
    # IATED's digital library and some WordPress journal themes print eprints.* tags but are not EPrints
    html = _page(["E. Segredo-Morales", "O. Díaz"], generator="")
    parser = EPrints(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    assert _authors(html) == []


def test_dspace_page_is_not_claimed():
    html = _page(["Silva, Ana"], generator='<meta name="Generator" content="DSpace 6.3" />')
    assert not EPrints(BeautifulSoup(html, "lxml")).is_publisher_specific_parser()
