"""Spandidos Publications (spandidos-publications.com, oxjob #2338): Oncology Letters, Molecular Medicine Reports, the
International Journal of Oncology and the house's other journals, ~83K works.

The citation_* meta tags carry the names, affiliations and abstract, so the generic parser's reading is kept whole.
Added is what it misses:
  - the corresponding author: the byline (ul#authorshipNames) marks it <li class="corresponding" title="<e-mail>">,
    one or two authors on every page since about 2008 (no title on some 2009 pages); older pages mark no one;
  - the reference list the full-text pages print as table.ref-list (a number cell, then the entry with its
    "View Article" (doi.org), "Google Scholar" and "PubMed/NCBI" links).
Acknowledgments and funding are printed under plain <h4> headings, which parse.py's heading reader already reads.
"""
import copy
import re

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import same_person, squash

_PUBLISHER = "Spandidos Publications"
_LINK_SEPARATORS = re.compile(r"(?:\s*:)+\s*$")  # "... 2003. : :" once the entry's link labels are cut out


def _key(name):
    """A name's letters and digits in first-last order: the meta tags write "Chou,Pai-Chien", the byline "Pai-Chien
    Chou" (541 of 541 byline names on the 76 stored pages read matched one tag this way)."""
    last, comma, first = name.partition(",")
    return re.sub(r"[\W_]+", "", (f"{first} {last}" if comma else name).lower())


class Spandidos(PublisherParser):
    parser_name = "spandidos_publications"
    prefer_publisher_authors_over_generic = True
    _claimed = None

    def is_publisher_specific_parser(self):
        # Every parser's claim runs on every DOI page (#2239: under 0.5 ms a page it does not claim), so the first test
        # is one tag among <head>'s direct children, <head> reached through direct children too (soup.head walks the
        # whole tree of a page that has none); the byline is looked for only on pages that pass it. The answer is
        # kept: authors_found(), parse() and the caller all ask.
        if self._claimed is None:
            html = self.soup.find("html", recursive=False)
            head = (html or self.soup).find("head", recursive=False)
            meta = head.find("meta", attrs={"name": "citation_publisher"}, recursive=False) if head else None
            self._claimed = bool(meta is not None and (meta.get("content") or "").strip() == _PUBLISHER
                                 and self.soup.find("ul", id="authorshipNames"))
        return self._claimed

    def authors_found(self):
        return self.is_publisher_specific_parser()

    def parse(self):
        out = dict(GenericPublisherParser(self.soup).parse())  # a fresh instance: its author dicts are ours to mark
        self._mark_corresponding(out.get("authors") or [])
        references, whole = self._references()
        if references:
            out["references"] = references
            out["references_complete"] = whole
        return out

    def _mark_corresponding(self, authors):
        """The byline's marked names set the flag on the parsed authors with that name: on every copy when the meta
        tags list an author twice (1 of 76 pages), else on the one author same_person() matches."""
        byline = self.soup.find("ul", id="authorshipNames")
        marked = [squash(li.get_text(" ")) for li in byline.find_all("li", recursive=False)
                  if "corresponding" in (li.get("class") or [])] if byline else []
        hits = set()
        for name in marked:
            matches = [a for a in authors if _key(a["name"]) == _key(name)]
            if not matches:
                matches = [a for a in authors if same_person(a["name"], name)]
                matches = matches if len(matches) == 1 else []
            hits.update(id(a) for a in matches)
        if hits:
            for a in authors:
                a["is_corresponding"] = id(a) in hits

    def _references(self):
        """(entries, whole) from the page's one table.ref-list. Whole when every row has a number and a text and the
        numbers run 1..n ("1" or "1."); the pages print the full list, with no "show more"."""
        # imported here: back_matter imports this package's utils, which imports every parser
        from parseland_lib.back_matter import _entry_doi, _numbering_whole
        tables = self.soup.select("table.ref-list")
        rows = [tr for table in tables for tr in table.select(":scope > tr, :scope > tbody > tr")]
        refs, labels = [], []
        for tr in rows:
            label = tr.select_one("td.ref-label span.label")
            content = tr.select_one("td.ref-content")
            if content is None:
                continue
            text_block = copy.copy(content)  # the link labels are cut out; the page's own soup stays whole
            for link in text_block.select('a[target="xrefwindow"]'):
                link.decompose()
            text = _LINK_SEPARATORS.sub("", squash(text_block.get_text(" ")))
            text = re.sub(r" ([,.;:)\]])", r"\1", text)  # get_text(" ") spaces inline markup: "2003 ." -> "2003."
            if not text:
                continue
            labels.append(label.get_text(strip=True) if label else None)
            refs.append({"position": len(refs) + 1, "raw": text, "doi": _entry_doi(content, text)})
        whole = (len(tables) == 1 and len(refs) == len(rows) and None not in labels
                 and _numbering_whole(labels))
        return refs, bool(refs) and whole
