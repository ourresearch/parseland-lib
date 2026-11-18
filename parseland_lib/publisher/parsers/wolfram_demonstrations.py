"""Wolfram Demonstrations Project (demonstrations.wolfram.com), the DOI prefix 10.3840 (oxjob #2339).

Each Demonstration has a DOI (registered as a dataset, 2007-2008) and an item page with no citation_* meta tags. Before
this parser Parseland read no author from these pages, and an abstract only when the description meta tag (cut at 400
characters) was over 200 characters long. The page itself prints both:

- byline: ``p.contributed-by``, "Contributed by: <a>Name</a> and <a>Name</a> (Month Year)", the names linked to
  author.html (older pages: search.html). Credits after the date ("Based on a program by:", "Additional contributions
  by:", "From: <book> by ...") are not the item's authors, and the site's own Permanent Citation leaves them out too;
- abstract: the description section, ``div#section-description``, one ``p#descriptionSectionParagraph`` per paragraph
  (the paragraphs after "[more]" are in the page, hidden). Inline formulas are images with no text.

No page shows affiliations (one in 71 sampled puts a school in brackets after the name, left out), a corresponding
author, acknowledgments, funding or references.
"""
import re

from bs4 import Tag

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

_SITE_TITLE = "Wolfram Demonstrations Project"  # every page's <title> ends with it: "<item> - Wolfram Demonstrations ..."
_ITEM_CSS = "/app-files/assets/css/demonstration.css"  # linked from <head> on item pages only (not the site's 404)
_LEAD = re.compile(r"^\s*contributed\s+by\s*:\s*", re.I)
_BRACKETS = re.compile(r"\([^)]*\)")
_NAME_SEP = re.compile(r"\s*,\s*(?:and\s+)?|\s+and\s+|\s*&\s*")


def _is_item_page(soup):
    """The claim's cheap test: the page's title names the site and a link beside it is the item page's stylesheet.
    Every parser's claim runs on every DOI page (#2239: under 0.5 ms a page it does not claim), so only the direct
    children of <head> are read, and of <body> when <head> holds no title: a keywords tag with a stray quote makes
    lxml close <head> early and move the rest of it, title and links, to the top of <body> (1 sampled page in 72)."""
    html = soup.find("html", recursive=False) or soup
    for scope in (html.find("head", recursive=False), html.find("body", recursive=False)):
        title = scope.find("title", recursive=False) if scope is not None else None
        if title is not None:
            return title.get_text().strip().endswith(_SITE_TITLE) and any(
                (link.get("href") or "").endswith(_ITEM_CSS) for link in scope.find_all("link", recursive=False))
    return False


def _is_byline_end(node):
    """The date span "(September 2007)" or a line break: what follows is another credit or the licence line."""
    return isinstance(node, Tag) and (node.name == "br" or node.get("id") == "publishdate")


class WolframDemonstrations(PublisherParser):
    parser_name = "wolfram_demonstrations"
    prefer_publisher_authors_over_generic = True  # the byline is the only place the page names its authors

    def is_publisher_specific_parser(self):
        if (claim := getattr(self, "_claim", None)) is None:  # computed once: authors_found() and the caller ask too
            claim = self._claim = _is_item_page(self.soup)
        return claim

    def _byline(self):
        return self.soup.find("p", class_="contributed-by")

    def authors_found(self):
        return self.is_publisher_specific_parser() and self._byline() is not None

    def _names(self):
        """The contributors before the date, in byline order: the linked names, else the names in the text."""
        lead = []
        for node in self._byline().children:
            if _is_byline_end(node):
                break
            lead.append(node)
        names = [squash(a.get_text()) for node in lead if isinstance(node, Tag)
                 for a in ([node] if node.name == "a" else node.find_all("a"))]
        if not any(names):
            text = _LEAD.sub("", squash(" ".join(node.get_text() for node in lead)))
            names = _NAME_SEP.split(squash(_BRACKETS.sub(" ", text)))
        return list(dict.fromkeys(name for name in names if name))

    def _abstract(self):
        section = self.soup.find("div", id="section-description")
        if section is None:
            return None
        paragraphs = [squash(p.get_text()) for p in section.find_all("p", id="descriptionSectionParagraph")]
        return "\n".join(p for p in paragraphs if p) or None

    def parse(self):
        authors = [{"name": name, "affiliations": [], "is_corresponding": False} for name in self._names()]
        return {"authors": authors, "abstract": self._abstract()}
