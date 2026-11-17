"""Schweizerbart science publishers (schweizerbart.de), geoscience and biology journals on the publisher's own
template (oxjob #2338).

Every article page prints its abstract in ``p.paper_abstract`` blocks, one per language version, each under an
``<h2>`` that names it: "Abstract", "Kurzfassung", "Résumé". The generic heading reader (#2239) reads the block
headed "Abstract". Nothing read the block on pages that print only a "Kurzfassung" (the German journals and the
back volumes of the Zeitschrift der Deutschen Geologischen Gesellschaft): 17 of 76 sampled pages, about 9,300 works
whose record has no abstract.

So this parser reads the abstract only on pages with no block headed "Abstract", and leaves every other page to the
reader that handles it today. It returns no authors: the byline (``<h2><b>Last, First; Last, First</b></h2>``, one
``citation_authors`` tag) is already on the works from Crossref (79 of 80 sampled), and the pages print no
affiliations, no corresponding mark, and a reference count but never the list.
"""
import re

from parseland_lib.abstract_language import is_english
from parseland_lib.publisher.parsers.parser import PublisherParser

_PUBLISHER = "schweizerbart"
_ENGLISH_HEADING = re.compile(r"^\s*abstracts?\s*[:.]?\s*$", re.I)
_HEADING = re.compile(r"^h[1-6]$")


def _head(soup):
    html = soup.find("html", recursive=False)
    return (html or soup).find("head", recursive=False)


class Schweizerbart(PublisherParser):
    parser_name = "schweizerbart"

    def is_publisher_specific_parser(self):
        """The citation_publisher tag in <head>, read alone: every parser's claim runs on every page (#2239, under
        0.5 ms a page it does not claim). On all 73 sampled article pages; the site's "Page not found" shells have
        no such tag."""
        if not hasattr(self, "_claimed"):
            head = _head(self.soup)
            meta = head.find("meta", attrs={"name": "citation_publisher"}) if head is not None else None
            self._claimed = meta is not None and _PUBLISHER in (meta.get("content") or "").lower()
        return self._claimed

    def authors_found(self):
        return self.is_publisher_specific_parser() and self.soup.select_one("p.paper_abstract") is not None

    def _abstract_blocks(self):
        """[(heading, text)] for each abstract block the page prints, in page order, empty ones left out."""
        blocks = []
        for block in self.soup.select("p.paper_abstract"):
            heading = block.find_previous_sibling(_HEADING)
            text = " ".join(block.get_text(" ", strip=True).split())
            if text:
                blocks.append((heading.get_text(" ", strip=True) if heading is not None else "", text))
        return blocks

    def parse_abstract(self):
        blocks = self._abstract_blocks()
        if not blocks or any(_ENGLISH_HEADING.match(heading) for heading, _ in blocks):
            return None  # the generic heading reader reads the "Abstract" block, as before this parser
        # label-v1: "If several language versions are shown, give the English one, else the first."
        return next((text for _, text in blocks if is_english(text)), blocks[0][1])

    def parse(self):
        return {"authors": [], "abstract": self.parse_abstract()}
