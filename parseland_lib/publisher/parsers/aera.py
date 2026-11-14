"""AERA Online Paper Repository (www.aera.net, DOI prefix 10.3102), oxjob #2210.

The repository viewer is a DNN page with no citation_* meta tags. Each paper's record is one RadGrid table of
"label:" / value rows: "Author(s):" reads "Name, Affiliation; Name, Affiliation" (an affiliation may hold commas, so
only the first comma splits), "Abstract:" holds the abstract. The "Owner Email:" row is the uploader's contact, not a
corresponding-author mark, so no one is marked. The record shows no acknowledgments, funding or references.
"""
import re

from parseland_lib.publisher.parsers.parser import PublisherParser

_GRID_ID = re.compile(r"ViewRepository.*_rgDetails_ctl00$")


def _clean(text):
    return " ".join((text or "").split())


class AERA(PublisherParser):
    parser_name = "aera_online_paper_repository"

    def is_publisher_specific_parser(self):
        title = self.soup.title
        return bool(title and "AERA Online Paper Repository" in title.get_text()
                    and self.soup.find("table", id=_GRID_ID))

    def _rows(self):
        grid = self.soup.find("table", id=_GRID_ID)
        rows = {}
        if not grid:
            return rows
        for tr in grid.find_all("tr"):
            cells = tr.find_all("td", recursive=False)
            if len(cells) >= 2:
                label = _clean(cells[0].get_text()).rstrip(":").strip().lower()
                rows.setdefault(label, _clean(cells[1].get_text()))
        return rows

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._rows().get("author(s)"))

    def parse(self):
        rows = self._rows()
        authors = []
        for entry in (rows.get("author(s)") or "").split(";"):
            entry = entry.strip()
            if not entry:
                continue
            name, _, aff = entry.partition(",")
            name, aff = name.strip(), aff.strip()
            if name:
                authors.append({"name": name, "affiliations": [aff] if aff else [], "is_corresponding": False})
        return {
            "authors": authors,
            "abstract": rows.get("abstract") or None,
            "acknowledgments": None,
            "funding_statement": None,
            "references": None,
            "references_complete": False,
        }
