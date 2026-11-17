"""Gramota Publishing (Издательство «Грамота», Tambov) article pages: the gramota.net archive and the new journal
sites such as philology-journal.ru (oxjob #2339).

Two platforms carry the publisher's 10.30853 DOIs:
- the old gramota.net archive page: a table layout styled by `gramota.css` (`/css/gramota.css` up to 2019,
  `/gramota.css` after). The title is an <h2>; the next row's cell holds the byline in one <b> (names, comma
  separated) and the affiliations after it, one per <br><br> block, never tied to an author; then "Аннотация.",
  "Ключевые слова и фразы:" and "Список литературы:" followed by one <ol> of unnumbered <li>s (the whole list).
- the new journal site (meta publisher "Gramota Publishing, LLC"): h2#abst, h2#ref with ol.a-ref-items whose
  `refnum` attributes number the entries, h2#mat (research materials: the sources studied, a separate list, not
  read), and one div.a-author card per author (full name, then p.a-author-affil).
Neither page marks a corresponding author. Funding sections (h2#fund) are left to parse.py's headed back matter.
The claim reads only the <head>'s own children (a few dozen tags), so pages of other sites cost almost nothing.
"""
import re

from bs4 import NavigableString, Tag

from parseland_lib.publisher.parsers.parser import PublisherParser

WS = re.compile(r"\s+")
ABSTRACT_LABEL = re.compile(r"^\s*Аннотация\s*[.:]?\s*")
REFS_LABEL = re.compile(r"^\s*Список\s+литературы\s*:?\s*$")
REFNUM = re.compile(r"^\s*(\d{1,4})\s*\.?\s*$")
SHOW_MORE = re.compile(r"(?i)show more|load more|показать (?:все|ещ[её])")
OLD, NEW = "old", "new"


def _text(node):
    s = str(node) if isinstance(node, (str, NavigableString)) else node.get_text(" ")
    return WS.sub(" ", s.replace("\xa0", " ")).strip()


def _own_stylesheet(href):
    """The stylesheet is the site's own: a root-relative path or a gramota.net URL, never another host's file."""
    return href.startswith("/") or "gramota.net/" in href


def _split_affiliations(text):
    return [p.strip(" ,.;") for p in text.split(";") if p.strip(" ,.;")]


class Gramota(PublisherParser):
    parser_name = "gramota"
    prefer_publisher_authors_over_generic = True

    def _platform(self):
        if "_kind" not in self.__dict__:
            self._kind = None
            html = self.soup.find("html", recursive=False)
            head = html.find("head", recursive=False) if html is not None else None
            if head is not None:
                for tag in head.find_all(("link", "meta"), recursive=False):
                    if tag.name == "link":
                        href = (tag.get("href") or "").strip().lower()
                        if href.endswith("/gramota.css") and _own_stylesheet(href):
                            self._kind = OLD
                            break
                    elif (tag.get("name") or "").lower() == "publisher" and \
                            (tag.get("content") or "").strip().startswith("Gramota Publishing"):
                        self._kind = NEW
                        break
        return self._kind

    def is_publisher_specific_parser(self):
        return self._platform() is not None

    def authors_found(self):
        return self._platform() is not None and bool(self._read()["authors"])

    def parse(self):
        return self._read()

    # ---- reading ----

    def _read(self):
        if "_cache" not in self.__dict__:
            out = {"authors": [], "abstract": None, "acknowledgments": None, "funding_statement": None,
                   "references": None, "references_complete": False}
            kind = self._platform()
            if kind == OLD:
                out.update(self._read_old())
            elif kind == NEW:
                out.update(self._read_new())
            self._cache = out
        return self._cache

    # the gramota.net archive page

    def _read_old(self):
        out = {}
        title = self.soup.find("h2")
        row = title.find_parent("tr") if title is not None else None
        byline_row = row.find_next_sibling("tr") if row is not None else None
        cell = byline_row.find("td") if byline_row is not None else None
        names_tag = cell.find("b") if cell is not None else None
        if names_tag is None:
            return out
        names = [n for n in (_text(x) for x in _text(names_tag).split(",")) if n]
        blocks, current = [], []
        for el in names_tag.next_siblings:
            if isinstance(el, Tag) and el.name == "br":
                if current:
                    blocks.append(" ".join(current))
                    current = []
            else:
                t = _text(el)
                if t:
                    current.append(t)
        if current:
            blocks.append(" ".join(current))
        affiliations = [a for b in blocks for a in _split_affiliations(b)]
        # one author: the affiliations are theirs; several: the page does not say who has which, so every author
        # gets the whole list (label-v1 "unlinked")
        out["authors"] = [{"name": n, "affiliations": list(affiliations), "is_corresponding": False} for n in names]
        table = title.find_parent("table")
        for b in table.find_all("b") if table is not None else []:
            label = _text(b)
            if out.get("abstract") is None and ABSTRACT_LABEL.match(label) and b.parent is not None:
                text = ABSTRACT_LABEL.sub("", _text(b.parent), count=1).strip()
                out["abstract"] = text or None
            elif REFS_LABEL.match(label):
                out["references"], out["references_complete"] = self._old_references(b)
                break
        return out

    @staticmethod
    def _old_references(label):
        ol = label.find_next_sibling("ol")
        if ol is None:
            return None, False
        entries = [t for t in (_text(li) for li in ol.find_all("li")) if t]
        if not entries:
            return None, False
        refs = [{"position": i, "raw": t, "doi": None} for i, t in enumerate(entries, 1)]
        start = (ol.get("start") or "1").strip()
        container = _text(label.parent)
        outside = len(container) - len(_text(label)) - sum(len(t) for t in entries)
        whole = (start in ("", "1") and len(ol.find_all("ol")) == 0 and not SHOW_MORE.search(container)
                 and outside <= 2 * len(entries) + 10)  # only the joins between entries sit outside them
        return refs, whole

    # the new journal site

    def _read_new(self):
        out = {}
        authors = []
        for card in self.soup.select("div.a-author"):
            name_tag = card.select_one("p.a-author-name")
            name = _text(name_tag) if name_tag is not None else ""
            if not name:
                continue
            affs = [a for p in card.select("p.a-author-affil") for a in _split_affiliations(_text(p))]
            authors.append({"name": name, "affiliations": affs, "is_corresponding": False})
        out["authors"] = authors
        heading = self.soup.find("h2", id="abst")
        if heading is not None:
            parts = []
            for sib in heading.find_next_siblings():
                if sib.name in ("h2", "h3", "ol", "ul", "div"):
                    break
                if sib.name == "p" and _text(sib):
                    parts.append(_text(sib))
            out["abstract"] = " ".join(parts) or None
        heading = self.soup.find("h2", id="ref")
        ol = heading.find_next_sibling() if heading is not None else None
        if ol is not None and ol.name == "ol" and "a-ref-items" in (ol.get("class") or []):
            items = [li for li in ol.find_all("li", recursive=False) if _text(li)]
            if items:
                out["references"] = [{"position": i, "raw": _text(li), "doi": None} for i, li in enumerate(items, 1)]
                nums = [REFNUM.match(li.get("refnum") or "") for li in items]
                out["references_complete"] = (all(nums) and [int(m.group(1)) for m in nums] ==
                                              list(range(1, len(items) + 1)) and not SHOW_MORE.search(_text(ol.parent)))
        return out
