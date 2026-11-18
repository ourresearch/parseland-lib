"""TREN e-docs record pages (Theological Research Exchange Network, tren.com; DOI prefix 10.2986) (oxjob #2339).

A 10.2986 DOI resolves to TREN's search page showing the one matching thesis record: a label/value table whose rows
read School, Author ("FAMILY, Given", then degree and year links), Pages and TREN Id. The page has no citation_* meta
tags, so the generic parser reads nothing. The School row is the degree-granting school, which label-v1 takes as the
sole author's affiliation. There is no abstract, correspondence mark or back matter on these pages.
"""
import re
from functools import cached_property

from parseland_lib.publisher.parsers.parser import PublisherParser

_SITE_NAME = "TREN.com"
_AUTHOR_HREF = re.compile(r"[?&]exact=TRUE&author=")
_SUFFIX = re.compile(r"^(Jr|Sr|II|III|IV|V)\.?$", re.I)


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _given_family(name):
    """'SUMMERS, Christopher A.' -> 'Christopher A. SUMMERS'; 'SMITH, John, Jr.' -> 'John SMITH Jr.'."""
    parts = [p.strip() for p in _clean(name).split(",") if p.strip()]
    if len(parts) == 3 and _SUFFIX.match(parts[2]):
        return f"{parts[1]} {parts[0]} {parts[2]}"
    if len(parts) == 2:
        return f"{parts[1]} {parts[0]}"
    return _clean(name).strip(" ,")


class TREN(PublisherParser):
    parser_name = "tren"
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        return self._claimed

    @cached_property
    def _claimed(self):
        return self._in_head() and self._record is not None

    def _in_head(self):
        """Every record page's <head> says og:site_name "TREN.com". The <head> is taken as a direct child of <html>,
        so other sites' pages cost a look at <head>, never a walk of the whole tree."""
        root = self.soup.html
        head = root.find("head", recursive=False) if root is not None else None
        return head is not None and head.find("meta", attrs={"property": "og:site_name", "content": _SITE_NAME}) is not None

    @cached_property
    def _record(self):
        """{label: value cell} of the page's one record, or None when the page shows no record or several (a results
        list): exactly one 'TREN Id:' row and one 'Author:' row."""
        found = {}
        for font in self.soup.find_all("font", attrs={"size": "1"}):
            label = _clean(font.get_text())
            if label not in ("School:", "Author:", "TREN Id:"):
                continue
            cell = font.find_parent("td")
            row = cell.find_parent("tr") if cell else None
            cells = row.find_all("td", recursive=False) if row else []
            if len(cells) >= 2:
                found.setdefault(label, []).append(cells[-1])
        one = len(found.get("TREN Id:", [])) == 1 and len(found.get("Author:", [])) == 1
        return {label: cells[0] for label, cells in found.items()} if one else None

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._authors())

    def _authors(self):
        rows = self._record or {}
        cell = rows.get("Author:")
        if cell is None:
            return []
        school = _clean(rows["School:"].get_text()) if "School:" in rows else ""
        authors = []
        for link in cell.find_all("a", href=_AUTHOR_HREF):
            name = _given_family(link.get_text())
            if name:
                authors.append({"name": name, "affiliations": [school] if school else [], "is_corresponding": False})
        return authors

    def parse(self):
        return {"authors": self._authors(), "abstract": None}
