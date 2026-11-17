"""The Conversation's article pages on theconversation.com (oxjob #2330).

News and commentary by academics, every edition (UK, US, AU, CA, FR, ES, BR, ID ...) on one template. The pages carry
no citation_author tags, so no parser read their byline (the live works get authors from Crossref, except pieces whose
deposit has none: Q&A and interview pieces by the site's own editors). The byline is printed twice:
  - an "Author" / "Authors" list, one <li> per person: name, role line ("Senior Lecturer, School of X, University Y");
    a Q&A piece adds an "Interviewed" list, whose people are not the piece's authors;
  - a one-line synopsis that gives each name its institution: "A, Inst1, B, C, Inst2" puts A at Inst1 and B and C at
    Inst2 (checked against the role lines on 75 sampled pages: no exception).
Names come from the first, institutions from the second (the gold takes the institution only, not the role line).

Not read: the description tag (a teaser, never an abstract; parse.py's description fill may still read it on pages
that word it like the title), the "Disclosure statement" ("X receives funding from ..." is a competing-interests note
about the author, not the work's funding) and the partner notes (the outlet's own funders). No page marks a
corresponding author.
"""
import re

from parseland_lib.publisher.parsers.parser import PublisherParser

_OG_URL = re.compile(r"^https?://(?:www\.)?theconversation\.com/", re.I)
_AUTHORS_HEADING = re.compile(r"^\s*authors?\s*$", re.I)


def _text(tag):
    return " ".join(tag.get_text(" ", strip=True).split())


class TheConversation(PublisherParser):
    parser_name = "the_conversation"
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        # Cheap on every other page: the <head>'s own children only, never a search of the whole document.
        head = self.soup.head
        if head is None:
            return False
        tag = head.find("meta", attrs={"property": "og:url"}, recursive=False)
        return tag is not None and bool(_OG_URL.match(tag.get("content") or ""))

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._byline_names())

    def _byline_names(self):
        names = []
        for group in self.soup.select("div.content-authors-group"):
            heading = group.find(["h2", "h3", "h4"])
            if heading is None or not _AUTHORS_HEADING.match(heading.get_text()):
                continue  # "Interviewed": the people a Q&A piece talks to
            for tag in group.select(".author-name"):
                if (name := _text(tag)) and name not in names:
                    names.append(name)
        return names

    def _synopsis_institutions(self):
        """name -> institutions from the byline synopsis: each run of names takes the institutions printed after it."""
        found, run, after_institution = {}, [], False
        synopsis = self.soup.select_one("div.content-authors-synopsis")
        if synopsis is None:
            return found
        for tag in synopsis.find_all(["span", "em"]):
            classes = tag.get("class") or []
            if tag.name == "span" and "nobr" in classes:
                if after_institution:
                    run, after_institution = [], False
                name = _text(tag)
                run.append(name)
                found.setdefault(name, [])
            elif tag.name == "em" and "institution_name" in classes:
                institution = _text(tag)
                for name in run:
                    if institution and institution not in found[name]:
                        found[name].append(institution)
                after_institution = True
        return found

    def parse(self):
        institutions = self._synopsis_institutions()
        authors = [{"name": name, "affiliations": list(institutions.get(name, [])), "is_corresponding": None}
                   for name in self._byline_names()]
        return {"authors": authors, "abstract": None}
