"""Atlantis Press article pages on atlantis-press.com (oxjob #2330).

The site's own template (proceedings papers, book chapters, journal articles) prints the record as label/value lists:
the byline, a "Corresponding Author" row, then <dl> rows for DOI, Keywords and the abstract
(<dt id="abstract-0">Abstract</dt><dd>...</dd>; pages before about 2019 say id="abstract"). The <dd> holds the whole
abstract and nothing else. Some authors end their abstract without a full stop, and the shared heading reader turns
such a text down as a cut preview (it ends mid-sentence), so those pages lost an abstract the page prints in full.
This parser reads that field and leaves everything else to the generic parser, whose byline (citation_author tags and
the "Corresponding Author" row) is right on these pages.

Not read (sized on the works side, #2330): the affiliations that pages from about 2022 print under each name. Every
sampled work with such a page already has affiliations, so reading them gains no work. Atlantis proceedings that
moved to Springer Link are Springer's pages, not this template (their citation_abstract_html_url is on
link.springer.com).
"""
import re

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser

_ABSTRACT_URL = re.compile(r"^https?://(?:www\.)?atlantis-press\.com/")
_ABSTRACT_LABEL = re.compile(r"^abstract(?:-0)?$")


class AtlantisPress(PublisherParser):
    parser_name = "atlantis_press"

    def is_publisher_specific_parser(self):
        # Cheap on every other page: the <head>'s own children only, never a search of the whole document.
        head = self.soup.head
        if head is None:
            return False
        tag = head.find("meta", attrs={"name": "citation_abstract_html_url"}, recursive=False)
        return tag is not None and bool(_ABSTRACT_URL.match(tag.get("content") or ""))

    def authors_found(self):
        # only pages that print the abstract field: on the rest the generic parser's answer stands unchanged
        return self.is_publisher_specific_parser() and self._abstract_value() is not None

    def _abstract_value(self):
        label = self.soup.find("dt", id=_ABSTRACT_LABEL)
        if label is None or label.get_text(strip=True) != "Abstract":
            return None
        return label.find_next_sibling()  # the <dd> right after the label

    def parse_abstract(self):
        value = self._abstract_value()
        if value is None or value.name != "dd":
            return None
        return " ".join(value.get_text(" ", strip=True).split()) or None

    def parse(self):
        generic = GenericPublisherParser(self.soup)
        result = dict(generic.parse()) if generic.authors_found() else {"authors": [], "abstract": None}
        if abstract := self.parse_abstract():
            result["abstract"] = abstract
        return result
