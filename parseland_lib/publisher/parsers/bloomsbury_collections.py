import re

from bs4 import NavigableString, Tag

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

# The old Bloomsbury Collections site (Magnolia CMS, theme "collections"): every asset is served from this path.
THEME_ASSETS = re.compile(r"/templating-kit/themes/collections/")
# "Jackie Keily and Julia Hoffbrand (eds)", "Hani A. Faris (ed)": the book's editors, not the chapter's authors
EDITORS = re.compile(r"\((?:eds?|editors?)\.?\)", re.I)


class BloomsburyCollections(PublisherParser):
    """Chapter and book pages of the old Bloomsbury Collections site (oxjob #2268).

    The chapter's own byline is `div.book-section h3.book-author`; without one, a chapter of a monograph is credited
    to the book's author (`div.book-details p.book-author`). Translators ("Translated by ...") and editors ("... (eds)")
    share that byline and are not the chapter's authors. The popover on each name holds a biography, not an
    affiliation, and the "Extract" under the chapter title is the opening of its text, not an abstract: the abstract
    stays what the generic readers found before this parser (a book page's printed description), so only the
    byline changes.
    The newer Bloomsbury platforms (`bloomsbury_assets/`) are a different template and print no byline.
    """
    parser_name = "bloomsbury_collections"
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        return bool(self.soup.find("link", href=THEME_ASSETS) or self.soup.find("script", src=THEME_ASSETS))

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._names())

    @staticmethod
    def _person(strong):
        span = strong.select_one("span.personname")
        return squash(span.get_text(" ")) if span else None

    def _book_names(self):
        """The book byline's authors: each <br>-separated run that no role label leads and no "(eds)" follows."""
        names = []
        for p in self.soup.select("div.book-details p.book-author"):
            runs = [[]]
            for child in p.children:
                if isinstance(child, Tag) and child.name == "br":
                    runs.append([])
                else:
                    runs[-1].append(child)
            for run in runs:
                people = [c for c in run if isinstance(c, Tag) and c.name == "strong" and self._person(c)]
                if not people:
                    continue
                text = "".join(c.get_text() if isinstance(c, Tag) else str(c) for c in run)
                lead = "".join(c if isinstance(c, NavigableString) else "" for c in run[:run.index(people[0])])
                # editors ("(eds)") and runs a role label leads ("Translated by", "Edited by", "Foreword by")
                if EDITORS.search(text) or re.search(r"[^\W\d_]", lead):
                    continue
                names.extend(self._person(s) for s in people)
        return names

    def _names(self):
        chapter = self.soup.select_one("div.book-section h3.book-author")
        if chapter is not None:
            found = [self._person(s) for s in chapter.find_all("strong")]
            if found := [n for n in found if n]:
                return found
        # a chapter of an edited volume with no byline of its own credits no one (the editors edited the book)
        return self._book_names()

    def parse(self):
        authors = [{"name": n, "affiliations": [], "is_corresponding": False} for n in self._names()]
        return {"authors": authors, "abstract": GenericPublisherParser(self.soup).parse()["abstract"]}
