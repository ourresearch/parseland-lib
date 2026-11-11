"""T&F chapter JSON-LD that packs several authors into one Person whose given and family name lists don't pair up
(one author has no given name) falls back to the product contributor list (oxjob #2162). Hand-crafted HTML."""
from __future__ import annotations

import json

from bs4 import BeautifulSoup

from parseland_lib.publisher.parsers.taylor import Taylor


def _escape(value: str) -> str:
    return value.replace("&", "&a;").replace('"', "&q;").replace("<", "&l;").replace(">", "&g;")


def _page(given: str, family: str) -> str:
    jsonld = json.dumps({"@context": "https://schema.org", "@type": "Chapter", "name": "A chapter",
                         "url": "https://www.taylorfrancis.com/chapters/edit/10.1201/x-7/a-chapter",
                         "author": {"@type": "Person", "givenName": given, "familyName": family},
                         "publisher": {"name": "Taylor & Francis"}})
    state = json.dumps({"product": {"title": "A chapter", "contributors": [
        {"roles": ["author"], "position": 1, "fullName": "Chandni Verma"},
        {"roles": ["author"], "position": 2, "fullName": "Geetanjali Mishra"},
        {"roles": ["author"], "position": 3, "fullName": "Omkar"}]}})
    return ('<html><head><meta property="og:url" content="https://www.taylorfrancis.com/chapters/edit/10.1201/x-7/a" />'
            f'<script type="application/ld+json">{jsonld}</script></head><body>'
            f'<script type="application/json" id="serverApp-state">{_escape(state)}</script></body></html>')


def _names(page: str):
    return [a.name for a in Taylor(BeautifulSoup(page, features="lxml"))._parse_taylorfrancis_chapter_authors()]


def test_unpaired_jsonld_names_use_the_product_contributors():
    assert _names(_page("Chandni, Geetanjali", "Verma, Mishra, Omkar")) == ["Chandni Verma", "Geetanjali Mishra", "Omkar"]


def test_paired_jsonld_names_still_split():
    assert _names(_page("Chandni, Geetanjali, Ravi", "Verma, Mishra, Omkar")) == [
        "Chandni Verma", "Geetanjali Mishra", "Ravi Omkar"]
