"""nbpublish.com: NB-Media's journal site (Russian humanities and social-science journals, DOI prefixes 10.7256 and
10.25136; the company's own PHP CMS, shared with e-notabene.ru) (oxjob #2338).

An article page prints one <table class="article"> per author, its <td class="author_desc"> holding the author twice:
the Russian <b>name</b> with its lines (ORCID, degree, position and organisation, postal address) and then the English
<b>name</b> with the same lines translated, then an e-mail table. The meta tags hold no affiliations and put the whole
byline in ONE citation_author tag ("Рубин В.А., Спиридонова Е.В."). Pages fetched since 2022 are stored with every
Cyrillic letter dropped (the site serves windows-1251): there only the English half can be read.

The reference list is printed twice, as "Библиография" and as its English version "References", each numbered
(old pages: a table of rows, <a name="1">1</a>; new pages: <a name="eng1">1</a> spans). The English version is read,
the Russian one only when the page has no English list.

A peer-review report's DOI (10.25136/review.N) resolves to the reviewed article's page scrolled to the report
("...?id=81038#review_37244"): the same HTML, so this parser cannot tell the report's page from the article's. It
leaves every page with a reviews block to the generic parser (as before), so that no report is credited to the
article's authors. The e-mail shown for every author is not a corresponding-author mark (label-v1).
"""
import re

from bs4 import NavigableString, Tag

from parseland_lib.publisher.parsers.parser import PublisherParser

SITE = re.compile(r"^https?://(www\.)?nbpublish\.com/", re.I)
LETTERS = re.compile(r"[^\W\d_]{2}")
# a line that is only a degree or a rank, never an affiliation ("кандидат исторических наук", "PhD in Law", "доцент")
DEGREE = re.compile(r"^(кандидат|доктор)(\s+[\w-]+){1,2}(\s+наук)?\.?$|"
                    r"^(ph\.?\s?d\.?|doctor|candidate|d\.?sc\.?|dr\.?)(\s+(of|in)\b)?[^,;]{0,50}$|"
                    r"^(доцент|профессор|академик|professor|docent|associate professor)\.?$", re.I)
ORG_WORD = re.compile(r"univers|institut|academ|college|school|depart|facult|университет|институт|академи|кафедр", re.I)
ORCID = re.compile(r"^orcid\b", re.I)
DOI = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+)")
MORE = re.compile(r"show (all|more)|load (all|more)|показать (все|ещ[её])", re.I)


def _line(parts):
    text = re.sub(r"\s+", " ", "".join(parts)).strip()
    return re.sub(r"(,\s*)+,", ",", text).strip(" ,;")  # an empty slot leaves ", ," behind


def _segments(td):
    """The author cell as [("name", text) | ("line", text)], in page order, up to the e-mail table."""
    out, cur = [], []
    for node in td.children:
        if isinstance(node, Tag) and node.name in ("br", "b", "table"):
            if text := _line(cur):
                out.append(("line", text))
            cur = []
            if node.name == "table":
                break
            if node.name == "b":
                out.append(("name", _line([node.get_text(" ")])))
        elif isinstance(node, Tag):
            cur.append(node.get_text(" "))
        elif isinstance(node, NavigableString):
            cur.append(str(node))
    if text := _line(cur):
        out.append(("line", text))
    return out


def _person(segments):
    """(name, affiliation lines) of the first language version that has a readable name: the Russian one, else (its
    letters dropped in storage) the English one."""
    versions = []
    for kind, text in segments:
        if kind == "name":
            versions.append([text, []])
        elif versions:
            versions[-1][1].append(text)
    for name, lines in versions:
        if LETTERS.search(name):
            return name, [l for l in lines if LETTERS.search(l) and not ORCID.match(l)
                          and not (DEGREE.match(l) and not ORG_WORD.search(l))]
    return None, []


class NBPublish(PublisherParser):
    parser_name = "nbpublish"

    def is_publisher_specific_parser(self):
        """The site's own citation_abstract_html_url tag (one tag, read from <head> only)."""
        if getattr(self, "_claim", None) is None:
            head = self.soup.head
            tag = head.find("meta", attrs={"name": "citation_abstract_html_url"}) if head else None
            self._claim = bool(tag and SITE.match((tag.get("content") or "").strip()))
        return self._claim

    def _cells(self):
        return [td for td in self.soup.select("table.article td.author_desc") if td.find("b", recursive=False)]

    def authors_found(self):
        # a page with a reviews block may be a review report's DOI: left to the generic parser (see the docstring)
        return (self.is_publisher_specific_parser() and not self.soup.find("div", id="reviews")
                and bool(self._cells()))

    def parse_authors(self):
        authors = []
        for td in self._cells():
            name, lines = _person(_segments(td))
            if name:
                authors.append({"name": name, "affiliations": [", ".join(lines)] if lines else [],
                                "is_corresponding": False})
        return authors

    def _list_after(self, heading):
        """The numbered entries after <div class="subpart_title">heading</div>, up to the next such title."""
        entries = []
        for node in heading.next_elements:
            if isinstance(node, Tag) and node.name == "div" and (
                    "subpart_title" in (node.get("class") or []) or node.get("id") == "reviews"):
                break
            if not (isinstance(node, Tag) and node.name == "a" and node.get("name")):
                continue
            number = node.get_text(" ", strip=True)
            if not number.isdecimal():
                continue
            # old pages: the number alone in the row's first cell; new pages: the number opens the entry's own <span>
            # (the nearest one: the page leaves outer span.annotation tags unclosed around whole sections)
            cell = node.find_parent("td")
            if cell is not None and cell.get_text("", strip=True).rstrip(".") == number:
                holder = cell.find_parent("tr")
            else:
                holder = node.parent
            if holder is None or holder.name not in ("tr", "span"):
                continue
            text = re.sub(r"\s+", " ", holder.get_text(" ")).strip()
            raw = re.sub(r"^" + number + r"\s*\.\s*", "", text).strip()
            if raw:
                entries.append((int(number), raw, holder))
        return entries

    def parse_references(self):
        titles = {}
        for div in self.soup.find_all("div", class_="subpart_title"):
            titles.setdefault(div.get_text(" ", strip=True).lower(), div)
        heading = titles.get("references") or titles.get("библиография")
        entries = self._list_after(heading) if heading else []
        if not entries:
            return None, False
        refs = []
        for _, raw, holder in entries:
            doi = None
            for a in holder.find_all("a", href=True):
                if "doi.org/" in a["href"] and (m := DOI.search(a["href"])):
                    doi = m.group(1)
                    break
            if doi is None and (m := re.search(r"\bDOI:?\s*(10\.\d{4,9}/\S+)", raw, re.I)):
                doi = m.group(1)
            refs.append({"position": len(refs) + 1, "raw": raw, "doi": doi.rstrip(".,;)") if doi else None})
        numbers = [n for n, _, _ in entries]
        whole = numbers == list(range(1, len(numbers) + 1)) and not any(MORE.search(r["raw"]) for r in refs)
        return refs, whole

    def parse(self):
        refs, whole = self.parse_references()
        # the abstract is left to parse_page's readers (the "Abstract:" block, as before this parser)
        return {"authors": self.parse_authors(), "abstract": None,
                "acknowledgments": None, "funding_statement": None,
                "references": refs, "references_complete": bool(refs) and whole}
