"""MECS Press (mecs-press.org: IJMECS, IJCNIS, IJITCS, IJISA and sister journals) article pages (oxjob #2339).

The site's current template (every new article, and older ones it has re-rendered) prints a citation_publisher_title
"MECS Press" meta tag and, in div.fe-paper-detail, the byline as one span.fe-paper__item-author-item per author with a
footnote <sup> ("1,*"), the numbered affiliations in div.fe-paper-author__company closed by "* Corresponding
author.", the abstract under an "Abstract" heading and a "Reference" list numbered "[1]", "[2]" ... (one <p> per
entry, or one <p> broken by <br>). Before this parser only the generic one read these pages: names from the
citation_author tags and the abstract, but not the starred corresponding author.

Affiliations are left out on purpose (#2339 sizing): every sampled work on this template already has them, so they
fall under the swarm's 1,000-works floor. The site's older template (no citation_publisher_title, a comma-separated
byline, no marks) is not claimed: the generic parser already reads all it shows but its reference list.
"""
import copy
import re

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import cleanup_raw_name, squash

_PUBLISHER = "MECS Press"
_REF_NUMBER = re.compile(r"^\[(\d{1,3})\]\s*")
_LINE_BREAK = " "


def _publisher_meta(soup):
    """The citation_publisher_title tag says MECS Press: the cheap first test of the claim. Every parser's claim runs on
    every page (#2239: under 0.5 ms a page it does not claim), so the tag is looked for among <head>'s direct children
    only and nothing walks the whole tree until this passes."""
    html = soup.find("html", recursive=False)
    head = (html or soup).find("head", recursive=False)
    if head is None:
        return False
    tag = head.find("meta", attrs={"name": "citation_publisher_title"}, recursive=False)
    return tag is not None and squash(tag.get("content")) == _PUBLISHER


class MECSPress(PublisherParser):
    parser_name = "mecs_press"
    # the byline carries the corresponding-author mark the citation_author tags lack
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        return _publisher_meta(self.soup)

    def _article(self):
        return self.soup.select_one("div.fe-paper-detail")

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self.parse_authors())

    def parse_authors(self):
        article = self._article()
        if article is None:
            return []
        company = article.select_one("div.fe-paper-author__company")
        # a star is a corresponding-author mark only where the page explains it (label-v1)
        explained = company is not None and "corresponding author" in company.get_text().lower()
        authors = []
        for item in article.select("p.fe-paper__item-author > span.fe-paper__item-author-item"):
            sup = item.find("sup")
            link = item.find("a")
            if link is not None:
                name = squash(link.get_text())
            else:
                item = copy.copy(item)
                if (s := item.find("sup")) is not None:
                    s.decompose()
                name = squash(item.get_text())
            name = cleanup_raw_name(name)
            if not name:
                continue
            marked = sup is not None and "*" in sup.get_text()
            authors.append({"name": name, "affiliations": [], "is_corresponding": bool(explained and marked)})
        return authors

    def parse_abstract(self):
        block = self.soup.select_one("div.fe-paper-detail__item-abstract")
        if block is None:
            return None
        paragraphs = [squash(p.get_text()) for p in block.find_all("p") if p.find("p") is None]
        return "\n".join(p for p in paragraphs if p) or None

    def parse_references(self):
        """(entries, whole): the "Reference" list, one entry per "[n]". Whole only when every line opens with its
        number and the numbers run 1..n."""
        # imported here: back_matter imports the parsers package, which imports this module
        from parseland_lib.back_matter import _printed_doi
        block = self.soup.select_one("div.fe-paper-detail__reference")
        if block is None:
            return None, False
        block = copy.copy(block)
        if (heading := block.find("h5")) is not None:
            heading.decompose()
        for br in block.find_all("br"):
            br.replace_with(_LINE_BREAK)
        paragraphs = [p for p in block.find_all("p") if p.find("p") is None] or [block]
        lines = [squash(line) for p in paragraphs for line in p.get_text().split(_LINE_BREAK)]
        entries, numbers, whole = [], [], True
        for line in lines:
            if not line:
                continue
            if m := _REF_NUMBER.match(line):
                numbers.append(int(m.group(1)))
                entries.append(line[m.end():])
            elif entries:
                entries[-1] = f"{entries[-1]} {line}"  # an entry broken by a line break
            else:
                whole = False  # text before the first number
                entries.append(line)
        refs = [{"position": i, "raw": raw, "doi": _printed_doi(raw)} for i, raw in enumerate(entries, 1) if raw]
        if not refs:
            return None, False
        whole = whole and len(refs) == len(entries) and numbers == list(range(1, len(refs) + 1))
        return refs, whole

    def parse(self):
        out = {"authors": self.parse_authors(), "abstract": self.parse_abstract()}
        refs, whole = self.parse_references()
        if refs:
            out.update(references=refs, references_complete=whole)
        return out
