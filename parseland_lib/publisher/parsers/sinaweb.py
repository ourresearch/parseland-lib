import copy
import re

from parseland_lib.publisher.parsers.egyptian_knowledge_bank import ekb_corresponding_marks
from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import same_person, squash

# Sinaweb serves an article at /article_<id>.html (or /article_<id>_en.html) and prints the same id in citation_id;
# Yektaweb, the other Iranian journal platform, uses /article-1-<id>-en.html and prints no citation_id
_ARTICLE_URL = re.compile(r"/article_(\d+)(?:_[a-z]{2})?\.html?$")
# a heading line inside the reference panel, not a reference: "References", "کتابنگاری", "منابع", "المصادر"
_LIST_HEADING = re.compile(r"^(?:references?|bibliography|کتابنگاری|کتابنامه|فهرست منابع|منابع|مراجع|المراجع|المصادر)"
                           r"\s*:?$", re.I)


def _head_meta(head, name):
    tag = head.find("meta", attrs={"name": name})
    return (tag.get("content") or "").strip() if tag is not None else ""


def is_sinaweb_page(soup):
    """An article page of a Sinaweb journal outside ekb.eg (egyptian_knowledge_bank.py reads those).

    Every parser's claim runs on every DOI page (oxjob #2239's per-page CPU budget), so this reads two meta tags in
    the page's <head> only, found without searching the document: a page with no <head> is not Sinaweb's."""
    html = soup.find("html", recursive=False)
    head = html.find("head", recursive=False) if html is not None else None
    if head is None:
        return False
    url = _head_meta(head, "citation_abstract_html_url")
    match = _ARTICLE_URL.search(url)
    return bool(match) and "ekb.eg" not in url and _head_meta(head, "citation_id") == match.group(1)


def _lines(item):
    """The lines of one reference-panel block: Sinaweb prints a block per line the journal typed, or the whole list
    in one block with <br> between references."""
    item = copy.copy(item)  # the other parsers still read this soup
    for br in item.find_all("br"):
        br.replace_with("\n")
    return [squash(line) for line in item.get_text().split("\n")]


class Sinaweb(PublisherParser):
    """Sinaweb journal pages beyond ekb.eg (oxjob #2289): about 140 sites, mostly Iranian and Iraqi universities.

    The meta-tag parser reads these pages' authors, affiliations and abstract, and this parser keeps its reading. It
    adds what that reading misses:
    - the corresponding author the byline marks: an envelope `mailto` titled "Email to Corresponding Author" (Persian
      "ارسال ایمیل به نویسنده اصلی"), or with no envelope a Font Awesome asterisk that singles an author out; the
      marks egyptian_knowledge_bank.py reads on ekb.eg (#2216), mapped the same way;
    - the reference panel (#collapsesRef, or an accordion panel headed References / مراجع / منابع): whole only as a
      single <ol>, or as lines numbered 1..n, since the panel holds whatever the journal typed.
    authors_found() leaves pages where the meta-tag parser finds nothing to the other parsers, as before.
    """
    parser_name = "sinaweb"

    def is_publisher_specific_parser(self):
        if not hasattr(self, "_claim"):  # authors_found() and the dispatcher both ask: work it out once
            self._claim = is_sinaweb_page(self.soup)
        return self._claim

    def _generic(self):
        if not hasattr(self, "_generic_parsed"):
            self._generic_parsed = GenericPublisherParser(self.soup).parse()
        return self._generic_parsed

    def authors_found(self):
        if not self.is_publisher_specific_parser():
            return False
        parsed = self._generic()
        return bool(parsed.get("authors") or parsed.get("abstract"))

    def parse(self):
        parsed = dict(self._generic())
        self._mark_corresponding(parsed.get("authors") or [])
        references, complete = self.parse_references()
        if references:
            parsed.update(references=references, references_complete=complete)
        return parsed

    def _mark_corresponding(self, authors):
        """Mark the authors the byline marks, when the meta-tag parser marked no one. The byline and the
        citation_author tags list the same authors in the same order, so a mark maps by position when the counts
        agree and by name otherwise; a mark that matches no author, or more than one, is dropped."""
        if not authors or any(a.get("is_corresponding") for a in authors):
            return
        names, marked = ekb_corresponding_marks(self.soup)
        for i in marked:
            if len(names) == len(authors):
                hits = [authors[i]]
            else:
                hits = [a for a in authors if same_person(a["name"], names[i])]
            if len(hits) == 1:
                hits[0]["is_corresponding"] = True

    def _reference_panel(self):
        panel = self.soup.find(id="collapsesRef")
        if panel is not None:
            return panel
        for toggle in self.soup.select('a.accordion-toggle[href^="#"]'):
            if _LIST_HEADING.match(squash(toggle.get_text(" "))):
                return self.soup.find(id=toggle["href"][1:])
        return None

    def parse_references(self):
        """(references, complete) from the article's reference panel."""
        panel = self._reference_panel()
        if panel is None:
            return [], False
        # imported here: back_matter imports parsers.utils, whose package imports every parser, this one included
        from parseland_lib.back_matter import (_TYPED_NUMBER, _entry_doi, _entry_text, _has_broken_entry,
                                               _numbering_whole, _printed_doi)
        lists = panel.find_all("ol")
        if lists:
            items = [li for ol in lists for li in ol.find_all("li", recursive=False)]
            entries = [(text, li) for li in items if (text := _entry_text(li))]
            rest = copy.copy(panel)
            for ol in rest.find_all("ol"):
                ol.decompose()
            outside = [t for t in rest.stripped_strings if not _LIST_HEADING.match(t)]
            whole = (len(lists) == 1 and (lists[0].get("start") or "1").strip() in ("0", "1") and not outside)
        else:
            entries, whole = [], True
            for item in panel.select("div.padding-3.margin-top-3"):
                lines = [line for line in _lines(item) if line]
                for line in lines:
                    if _LIST_HEADING.match(line):
                        whole = whole and not entries  # a second list after the first (Persian, then English)
                    else:
                        entries.append((line, item if len(lines) == 1 else None))
            numbers = [m.group(1) if (m := _TYPED_NUMBER.match(text)) else None for text, _ in entries]
            whole = whole and None not in numbers and _numbering_whole(numbers)
            if whole:
                entries = [(_TYPED_NUMBER.sub("", text, count=1), item) for text, item in entries]
        refs = [{"position": n, "raw": text, "doi": _entry_doi(item, text) if item is not None else _printed_doi(text)}
                for n, (text, item) in enumerate(entries, 1)]
        complete = bool(refs) and whole and not _has_broken_entry([r["raw"] for r in refs])
        return refs, complete
