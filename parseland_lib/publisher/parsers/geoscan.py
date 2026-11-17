"""Natural Resources Canada's GEOSCAN record pages (DOI prefix 10.4095, canada.ca; oxjob #2338).

The Geological Survey of Canada's maps, open files, bulletins and CANMET reports resolve to a GEOSCAN "Fastlink" page
(geoscan.nrcan.gc.ca starweb; title "GEOSCAN Search Results: Fastlink"). The record is one <table class="table"> of
<th>label</th><td>value</td> rows; the byline is the "Author" row: "Coyle, M; Kiss, F; Goldak Airborne Surveys",
family name first, a corporate author as it is, an ORCID icon link after a name, editors marked "(ed.)". The page has
no author meta tags, so no parser read that row and these reports had no authors.

Only the byline is read here. The page marks no affiliation and no corresponding author. Its "Abstract" row is left to
the generic heading reader, which already reads it (#2338 sizing: the abstract gap is under the 1,000-works floor),
and the page shows no acknowledgments, funding statement or reference list.
"""
import re

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

TITLE = "GEOSCAN"  # every record page's <title> starts so ("GEOSCAN Search Results: Fastlink")
EDITOR = re.compile(r"\s*\(eds?\.?\)\s*$", re.I)
# A corporate author may carry a comma too ("Canada Bureau of Geology and Topography, Topographical Survey"): never
# turned round like a person's "Family, Initials"
ORG = re.compile(r"\b(?:surveys?|bureau|branch|department|dept|division|committee|centre|center|commission|ministry"
                 r"|office|laborator\w*|programs?|programmes?|association|society|institut\w*|universit\w*"
                 r"|government|services?|agency|board|council|corporation|company|ltd|limited|inc|group|canada"
                 r"|consultants?)\b", re.I)


def _name(entry):
    """'Coyle, M' -> 'M Coyle'; 'Farrell, R -E' -> 'R-E Farrell'; a corporate author stays as it is."""
    family, comma, given = entry.partition(",")
    person = comma and given.strip() and not ORG.search(entry)
    name = f"{given.strip()} {family.strip()}" if person else entry
    return squash(re.sub(r"\s+-", "-", name))


class Geoscan(PublisherParser):
    parser_name = "geoscan"
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        if getattr(self, "_claim", None) is None:  # cheap: the first <title> inside <head>, nothing else
            head = self.soup.head
            title = head.find("title") if head is not None else None
            self._claim = title is not None and title.get_text().strip().startswith(TITLE)
        return self._claim

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._authors())

    def parse(self):
        return {"authors": self._authors(), "abstract": None,
                "acknowledgments": None, "funding_statement": None, "references": None, "references_complete": False}

    def _authors(self):
        if getattr(self, "_cache", None) is None:
            self._cache = self._read_byline()
        return self._cache

    def _read_byline(self):
        th = self.soup.find("th", string=lambda s: s and s.strip() == "Author")
        td = th.find_next_sibling("td") if th is not None else None
        if td is None:
            return []
        entries = [squash(e) for e in td.get_text("").split(";")]  # ORCID links hold only an icon: no text
        entries = [e for e in entries if e]
        # label-v1: editors only when nobody else is credited
        authors = [e for e in entries if not EDITOR.search(e)] or [EDITOR.sub("", e) for e in entries]
        return [{"name": _name(e), "affiliations": [], "is_corresponding": False} for e in authors if _name(e)]
