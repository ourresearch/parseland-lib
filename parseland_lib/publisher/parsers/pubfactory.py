import copy
import re

from bs4 import Comment

from parseland_lib.publisher.parsers.ams import AmericanMathematicalSociety
from parseland_lib.publisher.parsers.brill import Brill
from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import name_position, same_person, squash

# "Correspondence:", "Address correspondence to", "Corresponding author:" opening a contributor note.
_CORRESP_LABEL = re.compile(r"^(?:address\s+)?(?:correspondence|corresponding\s+author)(?:\s+to)?\s*:?\s*", re.I)


class PubFactory(PublisherParser):
    """PubFactory journal pages (jnccn.org, kidneynews.org, elibrary.imf.org, ...; oxjob #2289).

    No publisher parser claims them, so the citation_author meta tags win and carry no correspondence flag. The
    platform prints the article's NLM contributor notes as div.contributor-note > contributor-notes, where
    div.corresp holds "Correspondence: <name>, <degrees>, <address>". This parser keeps the generic reading of the page
    and only marks the author that note names. It fires only on pages that carry such a note, so every other
    PubFactory page reads as before. Brill and AMS pages stay with their own parsers.
    """
    parser_name = "pubfactory"

    def _is_pubfactory(self):
        # The platform's server comment ("...irl.pubfactory.net") sits before <html>: a few top-level nodes, never a
        # tree search, so the check costs nothing on other templates' pages (#2239's claim-cost rule).
        for node in self.soup.contents[:12]:
            if isinstance(node, Comment) and ".pubfactory." in node:
                return True
        return False

    def _claims(self):
        return (self._is_pubfactory() and not Brill(self.soup).is_publisher_specific_parser()
                and not AmericanMathematicalSociety(self.soup).is_publisher_specific_parser())

    def is_publisher_specific_parser(self):
        return self._claims()

    def _correspondence_names(self):
        names = []
        for note in self.soup.select("div.contributor-note div.corresp"):
            text = squash(note.get_text(" "))
            if not (label := _CORRESP_LABEL.match(text)):
                continue
            names.append(text[label.end():].split(",")[0].strip())
        return [n for n in names if n]

    def authors_found(self):
        return self._claims() and bool(self._correspondence_names()) and bool(self.parse_author_meta_tags())

    @staticmethod
    def _matches(authors, name):
        found = [a for a in authors if same_person(a["name"], name)]
        return found or [a for a in authors if name_position(a["name"], name) == 0]

    def parse(self):
        result = copy.deepcopy(GenericPublisherParser(self.soup).parse())
        authors = result.get("authors") or []
        if authors and not any(a.get("is_corresponding") for a in authors):
            for name in self._correspondence_names():
                if len(matched := self._matches(authors, name)) == 1:
                    matched[0]["is_corresponding"] = True
            if any(a.get("is_corresponding") for a in authors):
                for a in authors:
                    if a.get("is_corresponding") is None:
                        a["is_corresponding"] = False
        return result
