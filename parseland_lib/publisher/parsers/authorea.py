"""Authorea preprint pages (www.authorea.com/users/<id>/articles/<id>-<slug>; oxjob #2338).

The byline is a preview list plus one pop-up per author (div.author-popover, in byline order): the name, the
institution and, for the corresponding author only, a "Corresponding Author: <e-mail>" line. About one page in six
writes no citation_author tags, so the generic reader finds no authors there and the work never learns its
corresponding author (about 5K works in the 17 Nov sample). This parser reads the byline from the pop-ups; on pages
that do write the tags it gives the same names and marks as the generic reader (48 of 50 sample pages; the other two
follow the printed byline where the tags differ from it).

Not read here: the pop-ups' institutions (under the swarm's 1,000-works floor: the works lack one on about one page
in 80) and the abstract, which stays the generic reader's. Wiley's newer pages (www.authorea.com/doi/full/...) carry
no pop-ups and stay with the generic reader, which reads their institution tags.
"""
import re

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

_CORRESPONDING = re.compile(r"\bCorresponding Author\b", re.I)


class Authorea(PublisherParser):
    parser_name = "authorea"
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        # Every DOI page is offered to this parser (#2239's per-page CPU rule): the claim is the canonical link,
        # looked up in the small <head> only, and the answer is kept (the dispatcher asks twice).
        claim = self.__dict__.get("_claim")
        if claim is None:
            head = self.soup.head
            link = head.find("link", rel="canonical") if head is not None else None
            claim = bool(link is not None and "authorea.com/" in (link.get("href") or ""))
            self._claim = claim
        return claim

    def _popovers(self):
        if "_pops" not in self.__dict__:
            self._pops = self.soup.select("div.author-popover") if self.is_publisher_specific_parser() else []
        return self._pops

    def authors_found(self):
        return bool(self._popovers())

    def parse(self):
        authors = []
        for pop in self._popovers():
            name_tag = pop.select_one(".author-popover-name")
            name = squash(name_tag.get_text(" ")) if name_tag is not None else ""
            if not name:
                continue
            authors.append({"name": name,
                            "affiliations": [],
                            "is_corresponding": bool(_CORRESPONDING.search(pop.get_text(" ")))})
        return {"authors": authors, "abstract": GenericPublisherParser(self.soup).parse()["abstract"]}
