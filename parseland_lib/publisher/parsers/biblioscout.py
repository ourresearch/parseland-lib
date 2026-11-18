"""BiblioScout (biblioscout.net): the eLibrary of Verlag Österreich, Franz Steiner Verlag and their imprints, oxjob #2338.

Every record page is one "block--product" layout with <link rel="canonical" href="https://biblioscout.net/...">. The
generic parser already reads what most pages give (citation_author names, the citation_abstract), and this parser
keeps its answer. It adds two things the generic parser misses:
- authors on the Franz Steiner book template, which names them only in DC.creator tags (no citation_author);
- the reference list articles print as `div#references ul.u-list--references > li`, each entry numbered "1. ...".
The "Author information" block under a book holds biographies, not affiliations (label-v1), so no affiliations are
read; no page marks a corresponding author or prints acknowledgments or funding.
Not claimed: elibrary.verlagoesterreich.at's older record pages, stored under the same DOIs (no canonical link, a
Bootstrap 3 "article_tabs" layout), which the generic parser reads as before.
"""
import re

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser

_SITE = "://biblioscout.net/"
_NUMBER = re.compile(r"^\s*(\d{1,4})\.\s*")
_DOI = re.compile(r"10\.\d{4,9}/[^\s\"<>]+")
_MORE = re.compile(r"\b(?:show|load|view) (?:all|more)\b|\bmehr anzeigen\b|\balle anzeigen\b", re.I)


def _clean(text):
    return " ".join((text or "").split())


class BiblioScout(PublisherParser):
    parser_name = "biblioscout"

    def is_publisher_specific_parser(self):
        # cached: the dispatcher calls authors_found() and then this on the same instance. Cheap first (#2239: every
        # parser's claim runs on every page): the canonical link, looked up in <head> only.
        claim = self.__dict__.get("_claim")
        if claim is None:
            head = self.soup.head
            link = head.find("link", rel="canonical") if head is not None else None
            claim = bool(link is not None and _SITE in (link.get("href") or "")
                         and self.soup.find("div", class_="block--product") is not None)
            self._claim = claim
        return claim

    def authors_found(self):
        return self.is_publisher_specific_parser()

    def _dc_creators(self):
        scope = self.soup.head or self.soup
        names = []
        for tag in scope.find_all("meta", attrs={"name": "DC.creator"}):
            name = _clean(tag.get("content"))
            if name and name not in names:
                names.append(name)
        return [{"name": name, "affiliations": [], "is_corresponding": None} for name in names]

    def _references(self):
        block = self.soup.find(id="references")
        items = block.select("ul.u-list--references > li") if block is not None else []
        refs, numbers = [], []
        for item in items:
            text = _clean(item.get_text())
            number = _NUMBER.match(text)
            numbers.append(int(number.group(1)) if number else None)
            raw = text[number.end():] if number else text
            doi = None
            for link in item.find_all("a", href=True):
                if "doi.org/" in link["href"] and (found := _DOI.search(link["href"])):
                    doi = found.group(0)
                    break
            refs.append({"position": len(refs) + 1, "raw": raw, "doi": doi})
        if not refs:
            return None, False
        # whole: entries numbered 1..n with no gap, and no pager, summary or "show more" in the list's block
        whole = (numbers == list(range(1, len(refs) + 1))
                 and not block.select(".pagination, .summary, .load-more, .show-more")
                 and not _MORE.search(block.get_text(" ")))
        return refs, whole

    def parse(self):
        # read this page's own parts first: the generic parser's section reader may take headings out of the soup
        creators = self._dc_creators()
        references, complete = self._references()
        parsed = dict(GenericPublisherParser(self.soup).parse())
        if not parsed.get("authors"):
            parsed["authors"] = creators
        parsed.update(acknowledgments=None, funding_statement=None, references=references,
                      references_complete=complete)
        return parsed
