"""Scholastica journal websites (oxjob #2289): scholasticahq.com and the journals it hosts on their own domains
(ncmedicaljournal.com, joghr.org, imapsource.org, jheor.org ...). Every page loads its favicon and stylesheet from
assets.scholasticahq.com in its <head>.

The byline is drawn in the browser from `window.ARTICLE`, a JSON copy of the article's record in a script at the end of
the body; the stored page prints the names only. The generic reader takes the names from the citation_author tags and
the abstract from citation_abstract. This parser keeps the generic reader's abstract and reads the authors from the
record (the rubric counts embedded page data as the page's statement):
- each author's affiliations, `affiliations[].full_name` (department, institution and place in one string). A record
  whose fields are all empty is no affiliation (older articles carry one per author).
- the corresponding author: the record's `corresponding` flag; else an author note that opens with "Corresponding
  author" (the site shows the note in that author's pop-up); else the article's own "Correspondence to:" section
  (data-section="corr") naming the author on its first line; else the generic reader's marks.
Acknowledgments and funding are printed under their own headings, which parse.py's shared heading reader already reads.
The reference list (#article-citations, and `citations` in the record with each entry's DOI) is not read: in the
template's sample under 1,000 works lack references (#2289 sizing).
"""
import json
import re

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import name_position, same_person, squash

_ASSETS = "assets.scholasticahq.com"
_RECORD = re.compile(r"window\.ARTICLE\s*=\s*")
# "Corresponding author", "**Corresponding Author:**", "Corresponding author email: ...", "Correspondence: ..."
_CORRESPONDING_NOTE = re.compile(r"^\W*correspond(?:ing\s+author|ence)\b", re.I)
_AUTHOR_ROLES = {None, "", "author"}  # contributor_type: other contributors (translators ...) are not authors


def _head(soup):
    """The document's <head> without walking the tree: <html>'s direct children only (every DOI page asks)."""
    for top in soup.contents:
        if getattr(top, "name", None) == "html":
            return next((child for child in top.contents if getattr(child, "name", None) == "head"), None)
    return None


def _affiliation(record):
    if not isinstance(record, dict):
        return ""
    return squash(record.get("full_name")) or ", ".join(
        part for part in (squash(record.get("department")), squash(record.get("institution_name"))) if part)


class Scholastica(PublisherParser):
    parser_name = "scholastica"
    prefer_publisher_authors_over_generic = True

    def __init__(self, soup):
        super().__init__(soup)
        self._claimed = None
        self._record = None

    def is_publisher_specific_parser(self):
        # Every DOI page is offered to this parser: only <head>'s own <link> tags are looked at, so a page of another
        # platform is turned down without a walk of its tree (#2239's per-page CPU rule).
        if self._claimed is None:
            head = _head(self.soup)
            self._claimed = head is not None and any(
                _ASSETS in (link.get("href") or "") for link in head.find_all("link", recursive=False))
        return self._claimed

    def _article(self):
        """The page's `window.ARTICLE` record, or {} (a page whose app shell holds no record)."""
        if self._record is None:
            self._record = {}
            for script in reversed(self.soup.find_all("script")):
                text = script.string
                if not text or "window.ARTICLE" not in text:
                    continue
                if m := _RECORD.search(text):
                    try:
                        value, _ = json.JSONDecoder().raw_decode(text, m.end())
                    except ValueError:
                        value = None
                    if isinstance(value, dict):
                        self._record = value
                break
        return self._record

    def _people(self):
        people = [a for a in self._article().get("authors") or [] if isinstance(a, dict)
                  and a.get("contributor_type") in _AUTHOR_ROLES and squash(a.get("name"))]
        if all(isinstance(a.get("position"), int) for a in people):  # byline order; else the list's own order
            people.sort(key=lambda a: a["position"])
        return people

    def authors_found(self):
        return bool(self.is_publisher_specific_parser() and self._people())

    @staticmethod
    def _note_marks(person, people):
        note = squash(person.get("note"))
        if not _CORRESPONDING_NOTE.match(note):
            return False
        # a note that names another of the article's authors (and not this one) is that author's statement
        if name_position(squash(person["name"]), note) is None and any(
                name_position(squash(other["name"]), note) is not None for other in people if other is not person):
            return False
        return True

    def _correspondence_line(self):
        """The first line of the article's "Correspondence to:" section, or None."""
        heading = self.soup.find(attrs={"data-section": "corr"})
        block = heading.find_next_sibling() if heading is not None else None
        if block is None or block.name != "p":
            return None
        return next((line for line in map(squash, block.get_text("\n").split("\n")) if line), None)

    def parse(self):
        generic = GenericPublisherParser(self.soup)
        found = generic.parse() if generic.authors_found() else {"authors": [], "abstract": None}
        people = self._people()
        authors = []
        for person in people:
            affiliations = []
            for text in map(_affiliation, person.get("affiliations") or []):
                if text and text not in affiliations:
                    affiliations.append(text)
            marked = person.get("corresponding") is True or self._note_marks(person, people)
            authors.append({"name": squash(person["name"]), "affiliations": affiliations, "is_corresponding": marked})
        if authors and not any(a["is_corresponding"] for a in authors):
            line = self._correspondence_line()
            named = [a for a in authors if line and name_position(a["name"], line) is not None]
            if len(named) == 1:
                named[0]["is_corresponding"] = True
            else:  # the generic reader's marks (a correspondence block in the body), by name
                marks = [a["name"] for a in found.get("authors") or [] if a.get("is_corresponding")]
                for a in authors:
                    a["is_corresponding"] = any(same_person(a["name"], name) for name in marks)
        return {"authors": authors, "abstract": found.get("abstract")}
