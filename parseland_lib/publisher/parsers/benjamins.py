"""John Benjamins catalog pages: benjamins.com/catalog/<book>.<item> (oxjob #2210).

Every book item (chapter, preface, index ...) has its own page. Two kinds of byline:

- Items of a monograph name their authors only in one semicolon-separated `citation_authors` meta tag
  ("Family, Given; Family, Given"). That tag can also carry the book's editors, translators or foreword writers
  ("Casad, Eugene H.; Panther, Klaus-Uwe; Thornburg, Linda L." on a book whose title box shows only Casad), so a
  name counts only when the visible byline under the book title in the title box shows it.
- Chapters of edited volumes carry `citation_author` tags and a contributors block (name, ROR-linked affiliation)
  in the article info. Their title-box byline is the book's "Edited by ..." line, which credits no author of the item.

Newer chapters show their reference list in a "References (N)" tab; the stated N is the evidence of a whole list.
"""
import re
import unicodedata
from urllib.parse import unquote

from bs4 import Comment, NavigableString, Tag

from parseland_lib.publisher.parsers.parser import PublisherParser

CATALOG_URL = re.compile(r"^https?://(www\.)?benjamins\.com/catalog/", re.I)
EDITORS_LINE = re.compile(r"^\s*(edited by|edited and|herausgegeben von|sous la direction de|eds?\.)", re.I)
REFERENCES_TAB = re.compile(r"^\s*references\b", re.I)
STATED_COUNT = re.compile(r"^\s*references\s*\((\d+)\)\s*$", re.I)
MORE_MARKER = re.compile(r"\b(show|load|view|see) (more|all)\b", re.I)
DOI = re.compile(r"10\.\d{4,9}/\S+")


def _fold(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[‘’ʼ`´]", "'", s)
    return re.sub(r"\s+", " ", s).strip().casefold()


def _text(tag):
    return re.sub(r"\s+", " ", tag.get_text("")).strip()


def _reference_text(item):
    # each entry ends in a Google Scholar link whose logo is an <svg> with a text <desc>
    strings = (s for s in item.find_all(string=True)
               if not isinstance(s, Comment) and not s.find_parent(["svg", "button"])
               and not s.find_parent("a", href=re.compile(r"scholar\.google\.")))
    return re.sub(r"\s+", " ", "".join(strings)).strip()


class Benjamins(PublisherParser):
    parser_name = "benjamins"
    # A monograph chapter's authors carry no affiliations; they still beat the generic parser's empty list.
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        og = self.soup.find("meta", property="og:url")
        return bool(og and CATALOG_URL.match(og.get("content") or ""))

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(
            self._contributors() or self.soup.find("meta", attrs={"name": "citation_authors"}))

    def _contributors(self):
        # direct child of the article info only: a table-of-contents page nests other chapters' contributors
        # inside its .toc-entry rows
        return self.soup.select("div.articleinfo > div.contributors div.member")

    def _contributor_authors(self):
        authors = []
        for member in self._contributors():
            name_tag = member.select_one("span.name [itemprop=author]") or member.select_one("span.name")
            if not name_tag or not (name := _text(name_tag)):
                continue
            affs = [a for a in (_text(t) for t in member.select("span.affiliation")) if a]
            authors.append({"name": name, "affiliations": affs, "is_corresponding": False})
        return authors

    def _byline(self):
        """The title box's line under the book title: the book's authors, or its "Edited by ..." line."""
        box = self.soup.select_one("div.titlebox div.text")
        book = box and box.select_one("a.catalog:not(.series-link)")
        info = box and box.select_one("span.titleboxinfo")
        if not book or not info:
            return None
        lines, line = [], []
        for el in book.next_elements:
            if el is info:
                break
            if isinstance(el, Tag) and el.name == "br":
                lines.append("".join(line))
                line = []
            elif isinstance(el, NavigableString) and not isinstance(el, Comment):
                line.append(str(el))
        lines.append("".join(line))
        lines = [ln.strip() for ln in lines if ln.strip()]
        return lines[-1] if lines else None

    def _meta_authors_shown_in_byline(self):
        tag = self.soup.find("meta", attrs={"name": "citation_authors"})
        byline = self._byline()
        if not tag or not tag.get("content") or not byline or EDITORS_LINE.match(byline):
            return []
        shown = _fold(byline)
        authors = []
        for raw in tag["content"].split(";"):
            family, _, given = raw.partition(",")
            name = re.sub(r"\s+", " ", f"{given} {family}").strip()
            if name and re.search(rf"(?<!\w){re.escape(_fold(name))}(?!\w)", shown):
                authors.append({"name": name, "affiliations": [], "is_corresponding": False})
        return authors

    def _references(self):
        tabs = [d for d in self.soup.select("details")
                if d.find("summary") and REFERENCES_TAB.match(d.find("summary").get_text(" ", strip=True))
                and d.select("section.ref-list div.reference")]
        if not tabs:
            return None, False
        tab = tabs[0]
        refs = []
        for item in tab.select("section.ref-list div.reference"):
            link = item.select_one("span.doi a.doilink")
            doi = DOI.search(unquote(link.get("href") or "")) if link else None
            refs.append({"position": len(refs) + 1, "raw": _reference_text(item), "doi": doi.group(0) if doi else None})
        count = STATED_COUNT.match(tab.find("summary").get_text(" ", strip=True))
        complete = (len(tabs) == 1 and bool(count) and int(count.group(1)) == len(refs)
                    and not MORE_MARKER.search(tab.get_text(" ")))
        return refs, complete

    def parse(self):
        references, complete = self._references()
        return {
            "authors": self._contributor_authors() or self._meta_authors_shown_in_byline(),
            "abstract": self.parse_abstract_meta_tags(include_seo_tags=False),
            "acknowledgments": None,
            "funding_statement": None,
            "references": references,
            "references_complete": complete,
        }
