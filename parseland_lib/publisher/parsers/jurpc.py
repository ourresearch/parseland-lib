"""JurPC (jurpc.de), the German legal internet journal, DOI prefix 10.7328 (oxjob #2339).

Most of its DOI pages are court decisions. Each prints the editors' headnote ("Leitsatz:", "Leitsätze (der
Redaktion)", "Leitsatz (des Einsenders)") under its own <h3>/<h4> heading, in a blue table cell (bgcolor #A4C8F0)
before the reasons. The build labels (label-v1, both labellers on the pages that print one) take that headnote as the
work's abstract, and no other reader finds it: the page has no abstract meta tag, and its Description tag holds a
128-character cut. This parser reads the headnote and keeps the byline as the generic parser reads it (the
citation_author tag: the court for a decision, the writer for an essay). Pages without a headnote (essays, the
facsimile-only 1986-1996 pages) are left to the generic parser, so nothing else on them changes.
"""
import re

from bs4 import Comment, NavigableString

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser

# The editors' (or submitter's) headnote; not an essay's "Leitsätze der Verfasser", the writers' own theses
_HEADNOTE_HEADING = re.compile(r"^Leits(?:atz|ätze)\b(?!\s+der\s+Verfasser)", re.I)
_HEADINGS = ("h1", "h2", "h3", "h4")
# Elements that start a new line in the headnote cell; source line wraps inside a text are plain spaces
_BLOCKS = frozenset("br div li ol p table td tr ul".split())


def _is_headnote_cell(tag):
    return tag.name == "td" and (tag.get("bgcolor") or "").strip().lower() == "#a4c8f0"


def _lines(node, out):
    for child in node.children:
        if isinstance(child, Comment):
            continue
        if isinstance(child, NavigableString):
            out.append(re.sub(r"\s+", " ", str(child)))
        elif child.name not in ("script", "style"):
            block = child.name in _BLOCKS
            if block:
                out.append("\n")
            _lines(child, out)
            if block:
                out.append("\n")


class JurPC(PublisherParser):
    parser_name = "jurpc"

    def is_publisher_specific_parser(self):
        # One scan of <head> on another site's page (#2239: the claim runs on every DOI page)
        head = self.soup.head
        tag = head.find("meta", attrs={"name": "citation_journal_title"}) if head is not None else None
        return tag is not None and (tag.get("content") or "").strip().casefold() == "jurpc"

    def authors_found(self):
        return self.is_publisher_specific_parser() and self._headnote() is not None

    def _headnote(self):
        if not hasattr(self, "_headnote_text"):
            self._headnote_text = self._read_headnote()
        return self._headnote_text

    def _read_headnote(self):
        for heading in self.soup.find_all(("h3", "h4")):
            if not _HEADNOTE_HEADING.match(" ".join(heading.get_text(" ", strip=True).split())):
                continue
            # the first blue cell after the heading, before the next heading ("Gründe", "Tatbestand")
            for tag in heading.find_all_next(_HEADINGS + ("td",)):
                if tag.name in _HEADINGS:
                    return None
                if _is_headnote_cell(tag):
                    out = []
                    _lines(tag, out)
                    lines = [" ".join(line.split()) for line in "".join(out).split("\n")]
                    return "\n".join(line for line in lines if line) or None
            return None
        return None

    def parse(self):
        return {"authors": GenericPublisherParser(self.soup).parse()["authors"], "abstract": self._headnote()}
