"""Texila Journal (texilajournal.com) article pages (oxjob #2210).

The site runs its own PHP template with no citation_* meta tags. An article page prints the DOI, one
"<b>Authors</b> : name, name, ..." line, an "Abstract:" heading and a "References:" heading whose entries are
Word-pasted paragraphs numbered "[1].", "[2]" ... It shows no affiliations, corresponding author, acknowledgments or
funding statement. Issue pages ("edition/...") list many articles under repeated headings and are not read.
"""
import re
from urllib.parse import urlparse

from bs4 import Comment

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

HOSTS = {"texilajournal.com", "www.texilajournal.com"}
REF_NUMBER = re.compile(r"^\[(\d{1,4})\]\s*\.?\s*")
DOI = re.compile(r"\b10\.\d{4,9}/[^\s\"<>]+")
KEYWORDS = re.compile(r"\bKey\s*words?\s*:", re.IGNORECASE)
MORE_MARKERS = re.compile(r"\b(show|load|view|see) (more|all)\b|\bpage \d+ of \d+\b", re.IGNORECASE)


def _clean_doi(doi):
    doi = doi.rstrip(".,;:]/'\"")
    while doi.endswith(")") and doi.count("(") < doi.count(")"):
        doi = doi[:-1].rstrip(".,;:]/'\"")
    return doi


class TexilaJournal(PublisherParser):
    parser_name = "texila_journal"

    def is_publisher_specific_parser(self):
        """The site's own scripts (commonfiles/js/common.js and the rest) load from its host."""
        for tag in self.soup.find_all("script", src=True):
            src = tag["src"].strip()
            if src.startswith("//"):
                src = "https:" + src
            if urlparse(src).netloc.lower() in HOSTS:
                return True
        return False

    def _box(self, heading):
        """The block under the page's one h3 reading `heading`; None when it is missing or repeated (issue pages)."""
        found = [h for h in self.soup.find_all("h3") if squash(h.get_text()) == heading]
        return (found[0], found[0].parent) if len(found) == 1 else (None, None)

    def _byline(self):
        labels = [b for b in self.soup.find_all("b") if squash(b.get_text()) == "Authors"]
        if len(labels) != 1:
            return None
        m = re.match(r"^Authors\s*:\s*(.+)$", squash(labels[0].parent.get_text()))
        return m.group(1) if m else None

    def authors_found(self):
        return bool(self._byline()) and self._box("Abstract:")[1] is not None

    def parse_authors(self):
        names = [squash(n).strip(" ,;") for n in (self._byline() or "").split(",")]
        return [{"name": n, "affiliations": [], "is_corresponding": False} for n in names if n]

    def parse_abstract(self):
        heading, box = self._box("Abstract:")
        if box is None:
            return None
        paragraphs, inline = [], []
        for node in heading.next_siblings:
            if isinstance(node, Comment):
                continue
            if getattr(node, "name", None) in ("p", "div"):
                paragraphs.append("".join(inline))
                inline = []
                paragraphs.append(node.get_text())
            else:
                inline.append(node.get_text() if hasattr(node, "get_text") else str(node))
        paragraphs.append("".join(inline))
        kept = []
        for text in (squash(p) for p in paragraphs):
            if m := KEYWORDS.search(text):
                text = squash(text[:m.start()])
                if text:
                    kept.append(text)
                break
            if text:
                kept.append(text)
        return "\n".join(kept) or None

    def parse_references(self):
        """[{"position", "raw", "doi"}] in page order, and whether the page positively shows the whole list."""
        heading, box = self._box("References:")
        if box is None:
            return None, False
        blocks = [t for t in box.find_all(["p", "li"]) if not t.find(["p", "li"])]
        refs, numbers = [], []
        for block in blocks:
            text = squash(block.get_text())
            if not text:
                continue
            m = REF_NUMBER.match(text)
            numbers.append(int(m.group(1)) if m else None)
            raw = text[m.end():] if m else text
            doi = DOI.search(raw)
            refs.append({"position": len(refs) + 1, "raw": raw, "doi": _clean_doi(doi.group(0)) if doi else None})
        if not refs:
            return None, False
        # reference text outside the numbered paragraphs, or a "show more" marker, means we can't vouch for the list
        outside = any(squash(s) for s in box.find_all(string=True)
                      if not isinstance(s, Comment) and not s.find_parent(["p", "li"]) and s.find_parent("h3") is None)
        complete = (numbers == list(range(1, len(refs) + 1)) and not outside
                    and not MORE_MARKERS.search(squash(box.get_text())))
        return refs, complete

    def parse(self):
        references, complete = self.parse_references()
        return {
            "authors": self.parse_authors(),
            "abstract": self.parse_abstract(),
            "acknowledgments": None,
            "funding_statement": None,
            "references": references,
            "references_complete": complete,
        }
