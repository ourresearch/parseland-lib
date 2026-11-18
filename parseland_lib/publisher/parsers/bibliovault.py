"""BiblioVault book records (www.bibliovault.org; University of Chicago Press DOIs 10.7208/chicago/...), oxjob #2339.

A book's DOI and each of its chapters' DOIs resolve to the same record page: title, byline, the book's description
under "ABOUT THIS BOOK", the author biography, reviews and the table of contents (for books whose chapters have DOIs,
each chapter's DOI, keywords and abstract). The labels (label-v1) take the description as the book's abstract; it is
never a chapter's abstract, and the book's editors are not a chapter's authors (dev gold). A parser sees only the page,
and the page is the same for every DOI that resolves to it, so the description is read only on a record that lists no
chapter DOIs: that page can only be the book's own. Records that list chapter DOIs are left to a reader that knows the
requested DOI (the record URL's "chapter=" parameter or the DOI), which needs shared code. Description paragraphs that
are review quotes ("...—William Cronon, Yale Review", on older records) are left out.

No authors are read: the byline is the book's, and every sampled book's work already has its authors. The record shows
no affiliations (only the author biography), no corresponding author, acknowledgments, funding or reference list.
"""
import copy
import re

from parseland_lib.publisher.parsers.parser import PublisherParser

_REVIEW_QUOTE = re.compile(r'^["“].*[—–]\s*[A-Z][^.!?"“”—–]{1,150}$', re.S)


def _clean(text):
    return " ".join((text or "").split())


class BiblioVault(PublisherParser):
    parser_name = "bibliovault"

    def is_publisher_specific_parser(self):
        # cheap on other sites' pages: one look in <head> for BiblioVault's unAPI server link
        head = self.soup.head
        if head is None:
            return False
        link = head.find("link", attrs={"rel": "unapi-server"})
        return bool(link and "bibliovault.org" in (link.get("href") or ""))

    def _lists_chapter_dois(self):
        toc = self.soup.find("div", id="toc")
        if toc is not None and (toc.find(class_="expand_more") or "DOI:" in toc.get_text()):
            return True
        # any DOI line besides the book's own in the record block
        return len(self.soup.find_all(string=re.compile(r"\bDOI:"))) > 1

    def _description(self):
        box = self.soup.find("div", id="mkcopy")
        if box is None:
            return None
        heading = box.find("h3")
        if heading is None or _clean(heading.get_text()).upper() != "ABOUT THIS BOOK":
            return None
        box = copy.copy(box)  # never change the shared soup: other readers use it after this parser
        box.find("h3").decompose()
        for br in box.find_all("br"):
            br.replace_with("\n")
        for block in box.find_all(["p", "div"]):
            block.insert_before("\n\n")
            block.insert_after("\n\n")
        paragraphs = [_clean(p) for p in re.split(r"\n\s*\n", box.get_text())]
        paragraphs = [p for p in paragraphs if p and not _REVIEW_QUOTE.match(p)]
        text = "\n".join(paragraphs)
        return text if len(text) >= 100 else None

    def authors_found(self):
        return (self.is_publisher_specific_parser() and not self._lists_chapter_dois()
                and bool(self._description()))

    def parse(self):
        abstract = None if self._lists_chapter_dois() else self._description()
        return {
            "authors": [],
            "abstract": abstract,
            "acknowledgments": None,
            "funding_statement": None,
            "references": None,
            "references_complete": False,
        }
