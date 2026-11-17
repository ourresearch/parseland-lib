"""A&V Publications article pages: rjptonline.org (Research Journal of Pharmacy and Technology) and its sister
journals on the same ASP.NET platform (ajmjournal.com, ajner.com, ijneronline.com, ajpaonline.com, rjpdft.com, ...),
oxjob #2339.

The abstract page (``AbstractView.aspx?PID=...``) prints citation_* meta tags, which the generic parser reads (authors,
abstract); this parser keeps that reading and adds only the corresponding author. The page marks it in the
"Address:" block, ``span#ContentPlaceHolder1_AuthorAddress``: its first line is the byline, with each author's
affiliation numbers glued to the name as plain text and a star on the corresponding author
("Kavitha A N1*, Monica C2"), and its last line explains the star ("*Corresponding Author"). The generic star reader
needs the name to end at a word boundary, so a star after glued digits was missed (35 of 76 sampled pages, 17 Nov
2026). A block whose byline stars no one (several authors, the legend printed anyway) marks no one.

Claim: the abstract-page URL in ``citation_abstract_html_url`` and A&V's DOI prefix 10.52711 in ``citation_doi``, both
read from <head>'s direct children only (every parser's claim runs on every DOI page: #2239, under 0.5 ms a page it
does not claim).
"""
import copy
import re
from urllib.parse import urlsplit

from bs4 import NavigableString, Tag

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import _letters_key, same_person, squash

DOI_PREFIX = "10.52711/"
ADDRESS_ID = "ContentPlaceHolder1_AuthorAddress"
_LEGEND = re.compile(r"[*∗]\s*(?:corresponding\s+author|address\s+for\s+correspondence|correspondence)", re.I)
_SPLIT = re.compile(r",\s+|\s+and\s+|\s*&\s*|;\s*")
_MARKS = re.compile(r"[\d\s,*∗†‡#]*$")  # what follows a byline name: affiliation numbers and the star


def _head_metas(soup):
    """citation_abstract_html_url and citation_doi from <head>'s direct children; nothing walks the whole tree."""
    html = soup.find("html", recursive=False)
    head = (html or soup).find("head", recursive=False)
    found = {}
    if head is None:
        return found
    for tag in head.find_all("meta", recursive=False):
        name = tag.get("name")
        if name in ("citation_abstract_html_url", "citation_doi") and name not in found:
            found[name] = (tag.get("content") or "").strip()
    return found


def _is_abstract_page_url(url):
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return parts.path.lower().endswith("/abstractview.aspx") and "pid=" in parts.query.lower()


def starred_byline_names(address):
    """The names the address block's byline stars, when its legend explains the star; else []."""
    if not _LEGEND.search(address.get_text(" ")):
        return []
    line = []
    for node in address.contents:
        if isinstance(node, Tag) and node.name == "br":
            break
        line.append(str(node) if isinstance(node, NavigableString) else node.get_text())
    starred, names = [], []
    for piece in _SPLIT.split(squash("".join(line).replace("\xa0", " "))):
        marks = _MARKS.search(piece).group(0)
        name = piece[: len(piece) - len(marks)].strip()
        star = "*" in marks or "∗" in marks
        if not name:  # "Name1, 2*": the star's piece split off the name it belongs to
            if star and names:
                starred.append(names[-1])
            continue
        names.append(name)
        if star:
            starred.append(name)
    return starred


class RJPTOnline(PublisherParser):
    parser_name = "rjptonline"
    prefer_publisher_authors_over_generic = True

    def __init__(self, soup):
        super().__init__(soup)
        self._claimed = None
        self._parsed = None

    def is_publisher_specific_parser(self):
        if self._claimed is None:
            metas = _head_metas(self.soup)
            self._claimed = (metas.get("citation_doi", "").lower().startswith(DOI_PREFIX)
                             and _is_abstract_page_url(metas.get("citation_abstract_html_url", "")))
        return self._claimed

    def _address(self):
        return self.soup.find("span", id=ADDRESS_ID)

    def authors_found(self):
        return self.is_publisher_specific_parser() and self._address() is not None

    def parse(self):
        if self._parsed is None:
            generic = GenericPublisherParser(self.soup).parse()
            authors = copy.deepcopy(generic.get("authors") or [])
            address = self._address()
            if address is not None:
                self._mark_corresponding(authors, starred_byline_names(address))
            self._parsed = {"authors": authors, "abstract": generic.get("abstract")}
        return self._parsed

    @staticmethod
    def _mark_corresponding(authors, starred):
        """Each starred name marks the one author it names, spelled the same or else the same person ("A. Anka Rao"
        and "A. Narayana Rao" are the same person to same_person); a name matching none or several is skipped."""
        marked = set()
        for name in starred:
            matches = ([i for i, a in enumerate(authors) if _letters_key(a["name"]) == _letters_key(name)]
                       or [i for i, a in enumerate(authors) if same_person(a["name"], name)])
            if len(matches) == 1:
                marked.add(matches[0])
        if marked:
            for i, a in enumerate(authors):
                a["is_corresponding"] = i in marked
