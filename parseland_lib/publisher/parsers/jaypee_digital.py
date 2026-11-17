"""Jaypee Digital chapter pages (jaypeedigital.com, Jaypee Brothers Medical Publishers, DOI prefix 10.5005), oxjob #2330.

A DOI of a Jaypee book chapter (10.5005/jp/books/...) lands on a Jaypee Digital chapter page with no citation_* meta
tags. Its div.bookDetailsPage is a grid of label / value cells: "Author" is a numbered list ("1. Surname Given", one
per <br>) and "Author Affiliations" a numbered list in the same order; an author's affiliation is the entry with the
same number, kept whole (an entry often joins several variants of one address, and label-v1 keeps it as one string).
The "Abstract" tab is usually empty. Nothing marks a corresponding author, and the page shows no acknowledgments,
funding or references. Book pages (no "Author" row; citation_* meta tags) are left to the generic parser.
"""
import re

from bs4 import NavigableString, Tag

from parseland_lib.publisher.parsers.parser import PublisherParser

_SITE_TITLE = "JaypeeDigital"
_NUMBERED = re.compile(r"^(\d{1,3})\.\s*(.*)$", re.S)


def _squash(text):
    return " ".join((text or "").split())


def _title_text(soup):
    """The <title> in <head>, reached through direct children only: every parser's claim runs on every DOI page
    (#2239: under 0.5 ms a page it does not claim), so nothing walks the whole tree here."""
    html = soup.find("html", recursive=False)
    head = (html or soup).find("head", recursive=False)
    title = head.find("title", recursive=False) if head is not None else None
    return title.get_text() if title is not None else ""


def _lines(cell):
    """A value cell's text, one line per <br>."""
    lines, current = [], []
    for node in cell.children:
        if isinstance(node, Tag) and node.name == "br":
            lines.append(_squash("".join(current)))
            current = []
        elif isinstance(node, Tag):
            current.append(node.get_text(" "))
        elif isinstance(node, NavigableString) and type(node) is NavigableString:
            current.append(str(node))
    lines.append(_squash("".join(current)))
    return [line for line in lines if line]


def _numbered_entries(cell):
    """{number: text} from a numbered list cell. A line without a number continues the entry before it; a list with
    no numbers at all is numbered by position."""
    entries, last = {}, None
    for i, line in enumerate(_lines(cell) if cell is not None else [], 1):
        m = _NUMBERED.match(line)
        if m:
            last = int(m.group(1))
            entries[last] = _squash(m.group(2))
        elif last is not None:
            entries[last] = _squash(f"{entries[last]} {line}")
        else:
            entries[i] = line
    return {k: v for k, v in entries.items() if v}


class JaypeeDigital(PublisherParser):
    parser_name = "jaypee_digital"
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        return _title_text(self.soup).strip().startswith(_SITE_TITLE)

    def _cells(self):
        """The details grid's cells by label ("author", "author affiliations", ...)."""
        grid = self.soup.select_one("div.bookDetailsPage")
        cells = {}
        if grid is None:
            return cells
        for label in grid.select("div.font-weight-bold"):
            value = label.find_next_sibling("div")
            if value is not None:
                cells.setdefault(_squash(label.get_text()).rstrip(":").lower(), value)
        return cells

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(_numbered_entries(self._cells().get("author")))

    def _abstract(self):
        tabs = self.soup.select_one("div.custTabbing")
        if tabs is None:
            return None
        for li in tabs.select("ul.tabs > li"):
            if _squash(li.get_text()).lower() == "abstract" and li.get("rel"):
                rel = li["rel"][0] if isinstance(li["rel"], list) else li["rel"]
                content = tabs.find("div", id=rel)
                text = _squash(content.get_text(" ")) if content is not None else ""
                return text or None
        return None

    def parse(self):
        cells = self._cells()
        names = _numbered_entries(cells.get("author"))
        affs = _numbered_entries(cells.get("author affiliations"))
        authors = [{"name": name, "affiliations": [affs[n]] if n in affs else [], "is_corresponding": False}
                   for n, name in sorted(names.items())]
        return {
            "authors": authors,
            "abstract": self._abstract(),
            "acknowledgments": None,
            "funding_statement": None,
            "references": None,
            "references_complete": False,
        }
