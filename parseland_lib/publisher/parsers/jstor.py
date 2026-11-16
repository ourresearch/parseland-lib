"""JSTOR pages (www.jstor.org/stable/...) (oxjob #2239, phase 2).

No parser read these pages, so they parsed with no authors. A journal item's page credits its authors in one of
three places:
- the byline of the rendered page, inside <div class="turnaway-content__article-summary-info"> (the template before
  it: "turn-away-content__..."): <div class="author-font">Shawn M. Burn and Alison M. Konrad</div>
- a review's reviewer line in the same block: <div class="contrib">Review by: Henrike Donner</div> (the "Reviewed
  Work: ... by ..." line above it names the reviewed work's authors, who are not the review's)
- an unrendered page (an empty <div id="turnaway-mount-point">) only in its citation description:
  <meta name="description" content="W. H. Werkmeister, On "Describing a World", Philosophy and Phenomenological
  Research, Vol. 11, No. 3 (Mar., 1951), pp. 303-326">. The authors are what stands before the title, and the title
  is known from <title>On "Describing a World" on JSTOR</title>. With no title to anchor on ("Review: [Untitled]":
  "Roger F. Malina, Leonardo, Vol. 24 ...") the citation doesn't say where the names end, so it gives nothing.

A BOOK's page gives nothing, on purpose. It carries schema.org Book JSON-LD with the book's authors and blurb, but
most stored book pages were fetched for one chapter of the book: JSTOR turns a chapter request away to the book's
page ("/stable/<book>?turn_away=true"), and the HTML is the same whichever DOI it was fetched for. A book's authors
are not automatically a chapter's (edited volumes), a book's blurb is not a chapter's abstract, and the gate's gold
gives those pages neither. Only the stored URL tells the two apart, and parsers don't see it.

The abstract is left to the shared readers: they already read the page's "Abstract" block and turn down its "Journal
Information" and "Publisher Information" texts.
"""
import re
from functools import cached_property

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

_ASSET_HOST = re.compile(r"^(?:https?:)?//www\.jstor\.org/assets/")
_STABLE_URL = re.compile(r"^https?://www\.jstor\.org/stable/")
_TITLE_SUFFIX = re.compile(r"\s+on JSTOR$")
# the rendered item's summary block, in the current template and the one before it ("turn-away-")
_SUMMARY = "div.turnaway-content__article-summary-info, div.turn-away-content__article-summary-info"
# "..., Political Psychology, Vol. 8, No. 1 (Mar., 1987), pp. 125-138" / "..., p. 477": a journal item's citation
_CITATION_END = re.compile(r", pp?\. [^,]+$")
_REVIEWER_LABEL = "Review by:"
_NAME_SEPARATOR = re.compile(r",\s+|\s+and\s+|\s+&\s+")
_SUFFIX = re.compile(r"^(?:jr|sr|ii|iii|iv)\.?$", re.I)
# A part of an author list that is not one person's name: a body ("Committee on Standards and Ethics" splits at its
# "and"), a role ("Translated by ..."), a date or anything bracketed.
_NOT_A_PERSON = re.compile(
    r"\d|[:;()\[\]\"“”]|\b(?:by|with|edited|translated|compiled|introduction|foreword|et al|committee|society|"
    r"association|university|institute|department|council|board|staff|editors?)\b", re.I)


def _names(text):
    """The names in a JSTOR author list ("A, B and C" in a byline, "A, B, C" in a citation), in order. [] when any
    part doesn't read as one person's name: a wrong author list is worse than none."""
    names = []
    for part in _NAME_SEPARATOR.split(squash(text)):
        part = part.strip()
        if not part:
            continue
        if names and _SUFFIX.match(part):
            names[-1] += ", " + part  # "Virgil Brack, Jr."
        else:
            names.append(part)
    if not names or len(names) > 50:
        return []
    for name in names:
        # one word alone is more often a list split in the wrong place than a mononym
        if not 2 <= len(name.split()) <= 6 or len(name) > 60 or _NOT_A_PERSON.search(name):
            return []
    return names


class JSTOR(PublisherParser):
    parser_name = "jstor"
    # the page's own byline, when another publisher's reader also finds something on the page
    prefer_publisher_authors_over_generic = True

    def _item_title(self):
        """The item's title from '<title> X on JSTOR </title>', or None on any page that isn't JSTOR's own (its
        canonical link, or the stylesheet every JSTOR page loads from its own asset host). A look at the small
        <head> only, so no other site's page pays for a search of its body."""
        head = self.soup.head
        if head is None or head.title is None:
            return None
        title = squash(head.title.get_text())
        if not _TITLE_SUFFIX.search(title):
            return None
        canonical = head.find("link", rel="canonical")
        if not (canonical is not None and _STABLE_URL.match(canonical.get("href") or "")) \
                and head.find("link", href=_ASSET_HOST) is None:
            return None
        return _TITLE_SUFFIX.sub("", title)

    def is_publisher_specific_parser(self):
        return self._item_title() is not None

    @cached_property
    def _author_names(self):
        title = self._item_title()
        if title is None:
            return []
        summary = self.soup.select_one(_SUMMARY)
        if summary is not None:
            if (byline := summary.select_one("div.author-font")) is not None:
                return _names(byline.get_text(" "))  # an empty byline: an unsigned item
            for contrib in summary.select("div.contrib"):
                text = squash(contrib.get_text(" "))
                if text.startswith(_REVIEWER_LABEL):
                    return _names(text[len(_REVIEWER_LABEL):])
        return self._citation_authors(title)

    def _citation_authors(self, title):
        """The authors a journal item's citation description names before its title."""
        meta = self.soup.head.find("meta", attrs={"name": "description"})
        citation = squash(meta.get("content")) if meta is not None else ""
        if not title or not _CITATION_END.search(citation):
            return []  # a book's blurb, a chapter's "Index, Class Matters, pp. 203-214" has no title match below
        # a review's page title is "Review: <title>", its citation carries the bare title
        for known in (title, re.sub(r"^Review:\s*", "", title)):
            if citation.startswith(known + ", "):
                return []  # the citation opens with the title: nobody is credited
            if (at := citation.find(", " + known + ", ")) > 0:
                return _names(citation[:at])
        return []

    def authors_found(self):
        return bool(self._author_names)

    def parse(self):
        return {
            "authors": [{"name": name, "affiliations": [], "is_corresponding": False}
                        for name in self._author_names],
            "abstract": None,
        }
