"""Begell House Digital Library pages (oxjob #2338): dl.begellhouse.com journal articles and References & Proceedings
papers, and begellhouse.com's ebook platform (edited-volume chapters). Every one carries
<meta name="citation_publisher" content="Begel House Inc."> (the dl site's spelling) or "Begell House" (ebook platform).

The generic reader already gets the byline and abstract from the citation_* meta tags, and on journal pages each
author's institution (citation_author_institution); this parser keeps that output as it is and adds what only the
page's own markup says:
- affiliations on proceedings and ebook pages, which write no institution tags: the byline prints each one in an <i>
  under the author's name (div.article-author on dl, div.article-authors-list > p on the ebook platform), several
  joined by "; ". Filled only for authors the meta tags gave none.
- the reference list on journal pages: an <ol> under a "REFERENCES" title (div.article-references). The same markup,
  titled "CITED BY" (id citedby_crossref_citations), lists works citing the article and is never read.
"""
import re

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

_PUBLISHERS = {"begel house inc.", "begell house", "begell house inc."}
_CORRESPONDING_NOTE = re.compile(r"\(\s*corresponding author.*$", re.I | re.S)
_SHOW_MORE = re.compile(r"show (?:all|more)|load (?:all|more)|view all|more references", re.I)


def _key(name):
    """A name compared across the meta tags and the byline, word order ignored ("Duran , Orlando" = "Orlando Duran")."""
    return tuple(sorted(re.findall(r"\w+", (name or "").casefold())))


class BegellHouse(PublisherParser):
    parser_name = "begell_house"
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        # Every DOI page is offered to this parser, so the claim is one meta tag looked for in the small <head> only
        # (#2239's per-page CPU rule); the answer is kept, since authors_found() and the caller both ask.
        if not hasattr(self, "_claimed"):
            head = self.soup.head
            tag = head.find("meta", attrs={"name": "citation_publisher"}) if head is not None else None
            self._claimed = bool(tag and squash(tag.get("content")).casefold() in _PUBLISHERS
                                 and self.soup.select_one("div.article-authors, div.article-authors-list"))
        return self._claimed

    def _generic(self):
        if not hasattr(self, "_generic_result"):
            self._generic_result = GenericPublisherParser(self.soup).parse()
        return self._generic_result

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._generic().get("authors"))

    def _byline(self):
        """[(name, [affiliation, ...])] in byline order."""
        entries = []
        for entry in self.soup.select("div.article-authors > div.article-author, div.article-authors-list > p"):
            name_tag = entry.find(["b", "strong"])
            if name_tag is None:
                continue
            name = squash(_CORRESPONDING_NOTE.sub("", name_tag.get_text(" ")))
            aff_tag = entry.find("i")
            affs = [squash(a) for a in aff_tag.get_text(" ").split(";")] if aff_tag is not None else []
            entries.append((name, [a for a in affs if a]))
        return entries

    def _with_byline_affiliations(self, authors):
        entries = self._byline()
        if not entries or not any(affs for _, affs in entries):
            return authors
        keys = [_key(name) for name, _ in entries]
        out = []
        for i, author in enumerate(authors):
            author = dict(author)
            if not author.get("affiliations"):
                key = _key(author.get("name"))
                if key and keys.count(key) == 1:
                    author["affiliations"] = list(entries[keys.index(key)][1])
                elif len(entries) == len(authors) and not key:
                    author["affiliations"] = list(entries[i][1])
            out.append(author)
        return out

    def _references(self):
        """(references, references_complete) from the REFERENCES box; (None, False) when the page shows none."""
        from parseland_lib.back_matter import _printed_doi  # here, not at the top: back_matter imports this package
        for box in self.soup.select("div.article-references"):
            title = box.select_one(".article-references-title")
            if title is None or squash(title.get_text()).upper() != "REFERENCES" or title.get("id"):
                continue  # "CITED BY": works citing this one
            lists = box.find_all("ol")
            if len(lists) != 1:
                return None, False
            texts = [squash(li.get_text(" ")) for li in lists[0].find_all("li", recursive=False)]
            refs = [{"position": n, "raw": t, "doi": _printed_doi(t)} for n, t in enumerate(texts, 1) if t]
            if not refs:
                return None, False
            outside = [squash(s) for s in box.find_all(string=True)
                       if s.strip() and s.find_parent("li") is None and s.find_parent(class_="article-references-title") is None]
            start = (lists[0].get("start") or "1").strip()
            whole = (start == "1" and len(refs) == len(texts) and not outside and not _SHOW_MORE.search(box.get_text(" ")))
            return refs, whole
        return None, False

    def parse(self):
        result = dict(self._generic())
        result["authors"] = self._with_byline_affiliations(result.get("authors") or [])
        references, complete = self._references()
        result.update(acknowledgments=None, funding_statement=None, references=references,
                      references_complete=complete)
        return result
