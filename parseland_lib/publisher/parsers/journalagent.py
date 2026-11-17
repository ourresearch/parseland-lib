"""JournalAgent article pages (jvi.aspx, LookUs Bilisim's journal platform: journalagent.com's own journals and
the Turkish society and Kare journals that run it on their own domains) (oxjob #2289).

The page prints its byline as <span class='JAgAuthors'>: each name (often inside an ORCID link) followed by its <sup>
affiliation number, the corresponding author's name underlined. The citation box under the abstract,
<div id=citat>, states that author: "<b>Corresponding Author: </b>Name, Country" ("Sorumlu Yazar:" on Turkish pages).
No publisher parser claimed these pages, so the generic parser read the citation_author tags and found the
corresponding author only when the box named no one else. journalagent.com's own journals print the "How to cite
this article" line with every name in the same box, and Turkish pages carry no citation_author tags at all: on both,
nobody was marked. This parser reads the byline and marks the author the statement names.

The page prints affiliations (<span class='JAgAffiliations'>) and the abstract too, but the works these pages stand
for already have both from their DOI records (the #2289 sizing found under 1,000 works lacking either, the batch's
floor), so this parser leaves both to the readers that ran before it: no author gets an affiliation here, and the
abstract stays None for parse_page's own readers to fill.

Two pages this parser turns down, leaving them to the readers that ran before it: a soup that stops before the
citation box, and a byline read in the wrong encoding. jarengteah.org declares windows-1254 and serves UTF-8, so the
soup is read as windows-1254 and lxml stops at the first byte that code page lacks ("Ş" is C5 9E): the byline ends
mid-name and the rest of the page is gone. Reading such pages right belongs in parse_page's decoding, not here.
"""
import copy
import re

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import _letters_key, same_person, squash

_BYLINE_CLASS = "JAgAuthors"
_CORRESPONDING_LABEL = re.compile(r"^\s*(?:corresponding author|sorumlu yazar)\s*:?\s*$", re.I)


def _misread(text):
    """True when a text is UTF-8 read as windows-1254 ("AÃ§ıksÃ¶z" for "Açıksöz"): its windows-1254 bytes are
    valid UTF-8 that reads differently. Text read right almost never is ("Şüheda" is DE FC ... in windows-1254)."""
    try:
        return text.encode("cp1254").decode("utf-8") != text
    except (UnicodeEncodeError, UnicodeDecodeError):
        return False


class JournalAgent(PublisherParser):
    parser_name = "journalagent"
    prefer_publisher_authors_over_generic = True  # the printed byline: Turkish pages have no citation_author tags

    def __init__(self, soup):
        super().__init__(soup)
        self._byline = False  # not looked for yet; then the span or None
        self._parsed = None

    def _byline_tag(self):
        """The first <span class='JAgAuthors'> (bilingual pages print the byline once per language), found once.
        Every DOI page asks every parser (#2239: under 0.5 ms a page this parser does not claim), so this is one plain
        walk over the tree comparing tag names, about 0.1 ms a page; a CSS or class_ search costs about four times
        that."""
        if self._byline is False:
            self._byline = None
            for el in self.soup.descendants:
                if el.name == "span":
                    classes = el.get("class")
                    if classes and _BYLINE_CLASS in classes:
                        self._byline = el
                        break
        return self._byline

    def is_publisher_specific_parser(self):
        return self._byline_tag() is not None

    def authors_found(self):
        return self._byline_tag() is not None and bool(self.parse()["authors"])

    def parse(self):
        if self._parsed is None:
            box = self.soup.find("div", id="citat")  # the citation box, last of the article's own blocks
            names = self._names()
            if box is None or any(_misread(name) for name in names):
                names = []  # a cut-off soup or a misread byline (module docstring): not this parser's to read
            authors = [{"name": name, "affiliations": [], "is_corresponding": None} for name in names]
            self._mark_corresponding(authors, box)
            self._parsed = {"authors": authors, "abstract": None}
        return self._parsed

    def _names(self):
        byline = self._byline_tag()
        if byline is None:
            return []
        byline = copy.copy(byline)  # the other parsers still read this soup
        for sup in byline.find_all("sup"):
            sup.decompose()
        return [name for part in byline.get_text("").split(",") if (name := squash(part).strip(" *"))]

    @staticmethod
    def _stated_corresponding(box):
        """The name after "Corresponding Author:" in the citation box, without the country after its comma."""
        for label in box.find_all("b"):
            if not _CORRESPONDING_LABEL.match(label.get_text()):
                continue
            parts = []
            for sib in label.next_siblings:
                if getattr(sib, "name", None) in ("br", "b", "div", "p"):
                    break
                parts.append(sib.get_text() if hasattr(sib, "get_text") else str(sib))
            return squash("".join(parts).split(",")[0]) or None
        return None

    def _mark_corresponding(self, authors, box):
        stated = self._stated_corresponding(box) if authors else None
        if not stated:
            return
        matches = [a for a in authors if _letters_key(a["name"]) == _letters_key(stated)]
        if not matches:
            matches = [a for a in authors if same_person(a["name"], stated)]
        if len(matches) != 1:
            return
        for a in authors:
            a["is_corresponding"] = a is matches[0]
