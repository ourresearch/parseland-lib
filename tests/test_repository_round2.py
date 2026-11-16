"""Random-sample loop round 2 (oxjob #2239): record pages' Dublin Core creators, and DOAJ's 'Read online' line."""
from bs4 import BeautifulSoup

from parseland_lib.parse import dublin_core_authors, parse_page
from parseland_lib.publisher.parsers.generic import GenericPublisherParser

ABSTRACT = ("The electron-transfer flavoprotein dehydrogenase links fatty acid oxidation to the respiratory chain. "
            "We report its structure and show how two variants found in patients disturb the transfer of electrons.")


def test_eprints_creators_become_authors_on_record_pages():
    html = """<html><head><meta name="eprints.title" content="A record"/><meta name="eprints.creators_name" content="Şimşek, Sevda"/>
    <meta name="eprints.creators_name" content="Çelik, Süleyman"/><meta name="DC.creator" content="Şimşek, Sevda"/>
    </head><body><p>record</p></body></html>"""
    out = parse_page(html.encode(), "pmh", "https://research.sabanciuniv.edu/id/eprint/44178/")
    assert [a["name"] for a in out["authors"]] == ["Şimşek, Sevda", "Çelik, Süleyman"]


def test_institutional_creators_are_not_authors():
    html = """<html><head><meta name="DC.creator" content="Junta de Andalucía"/>
    <meta name="DC.creator" content="Biblioteca de Andalucía"/></head><body></body></html>"""
    assert dublin_core_authors(BeautifulSoup(html, "lxml")) == []


def test_publisher_pages_keep_their_own_author_dispatch():
    html = '<html><head><meta name="DC.creator" content="Ada Lovelace"/></head><body></body></html>'
    assert parse_page(html.encode(), "doi", "https://example.org/x")["authors"] == []


def test_short_link_line_after_the_heading_is_skipped():
    html = (f"<html><body><section><h2>Abstract</h2><p><a href='/x'>Read online</a></p><p>{ABSTRACT}</p>"
            "<h2>Keywords</h2></section></body></html>")
    assert GenericPublisherParser(BeautifulSoup(html, "lxml")).parse_headed_abstract_section() == ABSTRACT
