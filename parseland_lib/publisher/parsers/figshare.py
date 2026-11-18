"""Figshare item pages (oxjob #2289): figshare.com and the portals built on it (aacr.figshare.com, Optica Open,
university repositories). Every page carries <meta name="application-name" content="figshare"> in its <head>.

The generic reader already gets what these pages show from their meta tags: the byline when the item has
citation_author tags, and the item's description. This parser keeps those as they are and adds:
- the funding section: under its own "Funding" heading an item lists each funder as an <h3> in its own block (with,
  for a grant linked to Dimensions, the funding body in a <p> and a "Find out more..." link). The generic heading
  reader stops at the first nested heading, so it read none of them (12 of 31 sampled items, all AACR supplements,
  whose works list no funder). One block a line.
- the byline from the item's DataCite.contributor tags (the people the page prints after "authored by") on items with
  no citation_author tags: without authors or an abstract the dispatcher drops a parse, funding and all.
Items show no affiliations and no corresponding author. The "ARTICLE ABSTRACT" under Related Materials is the
supplemented article's, never the item's (oxjob #1800).
"""
import re

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

_CREATOR_TAGS = {"datacite.creator", "datacite.contributor"}
_PLACEHOLDER = re.compile(r"^(?:n/?a|-+|\.)$", re.I)


class Figshare(PublisherParser):
    parser_name = "Figshare"

    def is_publisher_specific_parser(self):
        # Every DOI page is offered to this parser, so only the small <head> is looked at, and a page without the
        # mark is turned down before anything walks the whole tree (#2239's per-page CPU rule). Kept: authors_found()
        # and the caller both ask.
        if not hasattr(self, "_claimed"):
            head = self.soup.head
            app = head.find("meta", attrs={"name": "application-name"}) if head is not None else None
            self._claimed = app is not None and squash(app.get("content")).lower() == "figshare"
        return self._claimed

    def _generic(self):
        """What the dispatcher returned for this page before this parser: the generic parse when it found something,
        else nothing (parse.py's fill-ins then decide the abstract, as before)."""
        if not hasattr(self, "_generic_result"):
            generic = GenericPublisherParser(self.soup)
            self._generic_result = generic.parse() if generic.authors_found() else {"authors": [], "abstract": None}
        return self._generic_result

    def _creators(self):
        names = []
        head = self.soup.head
        for meta in head.find_all("meta", attrs={"name": True}) if head is not None else []:
            name = squash(meta.get("content"))
            if meta["name"].lower() in _CREATOR_TAGS and name and name not in names:
                names.append(name)
        return [{"name": n, "affiliations": [], "is_corresponding": None} for n in names]

    def _authors(self):
        return self._generic().get("authors") or self._creators()

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._authors())

    @staticmethod
    def _funder(block):
        """One funder block's text: its heading (a grant or funder name) and its lines (the funding body), never the
        "Find out more..." link to the grant's record."""
        if block.find(True) is None:
            return squash(block.get_text(" "))
        parts = (squash(child.get_text(" ")) for child in block.find_all(True, recursive=False)
                 if child.name != "a" or child.find(["h3", "h4", "p"]) is not None)
        return ", ".join(part for part in parts if part)

    def _funding(self):
        from parseland_lib.back_matter import funder_list  # here: back_matter imports this package
        for heading in self.soup.find_all("h2"):
            if squash(heading.get_text()).lower() == "funding":
                # "n/a" typed into a grant card is no funding statement; two or more cards that only name funders
                # are the record's funder list, not a statement (#2239 round 8: 8 of 10 such labelled items)
                funders = [f for block in heading.find_next_siblings()
                           if (f := self._funder(block)) and not _PLACEHOLDER.match(f)]
                return None if funder_list(funders) else "\n".join(funders) or None
        return None

    def parse(self):
        generic = self._generic()
        return {**generic, "authors": self._authors(),
                "funding_statement": generic.get("funding_statement") or self._funding()}
