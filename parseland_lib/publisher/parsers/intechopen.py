"""IntechOpen book chapters (www.intechopen.com/chapters/N) (oxjob #2330).

The chapter page's "Author Information" block (`#section-chapter-and-author`) lists each author as `li.authorsItem`:
the name in `h4.author`, a trailing `<span>*</span>` on the author the block's "*Address all correspondence to:" note
is about, and the affiliations in `span.position li`. The meta tags carry names only, so the generic parser read no
affiliation on these pages, and marked a corresponding author on chapters that star no one.

Not read here: a book's own page (`/books/N`, the editors) and an old chapter shown only as a PDF (a "Written By" name
line): neither has the block, so they stay with the generic parser. The page-state JSON at the end of the page holds
author profiles (current institutions, often of other chapters): never read. Acknowledgments and reference lists come
from parse.py's shared back-matter readers, which already read this site's pages.
"""
import re

from bs4 import Comment, NavigableString

from parseland_lib.publisher.parsers.parser import PublisherParser

_SECTION_ID = "section-chapter-and-author"
_NOTE = re.compile(r"^\*\s*Address all correspondence", re.I)


def _squash(text):
    return re.sub(r"\s+", " ", text or "").strip()


class IntechOpen(PublisherParser):
    parser_name = "IntechOpen"
    # the Author Information block is the byline; the citation_author tags drop an author on some pages
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        # Every DOI page is offered to this parser, so the cheap test goes first: the og:url tag, or the site's own
        # asset host in a <style> of the small <head> (chapter pages served without their meta tags), looked for in
        # the head only. The whole-tree lookup of the Author Information block runs only on IntechOpen pages.
        if not hasattr(self, "_claimed"):
            self._claimed = self._intechopen_head() and self._section() is not None
        return self._claimed

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._section().select("li.authorsItem"))

    def _intechopen_head(self):
        # the <html> element's own child only: soup.head searches the whole tree when a page has no <head>
        root = self.soup.html
        head = root.find("head", recursive=False) if root is not None else None
        if head is None:
            return False
        og_url = head.find("meta", property="og:url")
        if og_url is not None:
            return "intechopen.com/" in (og_url.get("content") or "")
        return any("cdnintech.com/web/frontend/" in (style.string or "") for style in head.find_all("style"))

    def _section(self):
        if not hasattr(self, "_block"):
            self._block = self.soup.find(id=_SECTION_ID)
        return self._block

    def _authors(self):
        block = self._section()
        noted = any(_NOTE.match(_squash(p.get_text(" "))) for p in block.find_all("p"))
        authors, by_name = [], {}
        for item in block.select("li.authorsItem"):
            heading = item.find("h4")
            if heading is None:
                continue
            starred, parts = False, []
            for child in heading.children:
                if getattr(child, "name", None) == "span" and child.get_text(strip=True) == "*":
                    starred = True
                elif getattr(child, "name", None) is not None:
                    parts.append(child.get_text(" "))
                elif isinstance(child, NavigableString) and not isinstance(child, Comment):  # not Vue's "<!---->"
                    parts.append(str(child))
            name = _squash(" ".join(parts)).rstrip("*").strip()
            if not name:
                continue
            affiliations = [aff for li in item.select("span.position li") if (aff := _squash(li.get_text(" ")))]
            if name in by_name:  # a name listed twice is one author (the byline and the tags list it once)
                known = by_name[name]
                known["affiliations"] += [a for a in affiliations if a not in known["affiliations"]]
                known["is_corresponding"] = known["is_corresponding"] or (starred and noted)
                continue
            by_name[name] = {"name": name, "affiliations": affiliations, "is_corresponding": starred and noted}
            authors.append(by_name[name])
        return authors

    def _abstract(self):
        # the block headed "Abstract"; an introductory chapter shows the book's description in the same block,
        # under the book's title, and that is not the chapter's abstract
        for intro in self.soup.select("div.intro"):
            heading = intro.find("h2")
            if heading is None or _squash(heading.get_text()).lower() != "abstract":
                continue
            body = intro.select_one("div.body") or intro
            text = _squash(" ".join(p.get_text(" ") for p in body.find_all("p")) or body.get_text(" "))
            return text or None
        return None

    def parse(self):
        return {"authors": self._authors(), "abstract": self._abstract()}
