"""IUPAC Gold Book term pages (goldbook.iupac.org, DOIs 10.1351/goldbook.*) (oxjob #2338).

Until this parser no parser read these pages and no work got an author. The 3.0.1 term pages (the 2019 site, stored
for the backfill's 2008-dated term DOIs) credit the Compendium's corporate author in the term card's footer:
"Cite as: IUPAC. Compendium of Chemical Terminology, 2nd ed. ... Compiled by A. D. McNaught and A. Wilkinson ...". The
page's author meta tag spells the name out ("The International Union of Pure and Applied Chemistry (IUPAC)"): one group
author (label-v1), never the compilers or the site's editors.

Not claimed or not read:
- 5.0.0 term pages print "Citation: '<term>' in IUPAC Compendium of Chemical Terminology, 5th ed. International Union of
  Pure and Applied Chemistry; 2025.": IUPAC is the publisher there, and the author meta tag is the whole site's (the
  home page carries it too), so they credit no author (the two build labels split; settled to none).
- The Gold Book home page (DOIs that resolve to it): no dc.identifier, not a term page.
- A term's definition is not an abstract; its "Source:" line names the Recommendation the term comes from (the works
  already carry it as their one reference), so no reference list either.
- Pure and Applied Chemistry pages (10.1351/pac*) are De Gruyter's, read by de_gruyter.py.
"""
import re

from parseland_lib.publisher.parsers.parser import PublisherParser

_GOLD_BOOK_DOI = ("https://doi.org/10.1351/goldbook.", "http://doi.org/10.1351/goldbook.", "10.1351/goldbook.")
_CITE_AS = re.compile(r"^\s*cite\s+as\s*:?\s*IUPAC\.", re.I)


def _head(soup):
    """<head>, reached through direct children only: every parser's claim runs on every DOI page (#2239: under 0.5 ms a
    page it does not claim), so nothing here walks the whole tree."""
    html = soup.find("html", recursive=False)
    return (html or soup).find("head", recursive=False)


def _head_meta(soup, name):
    head = _head(soup)
    tag = head.find("meta", attrs={"name": name}, recursive=False) if head is not None else None
    return (tag.get("content") or "").strip() if tag is not None else ""


class IupacGoldBook(PublisherParser):
    parser_name = "iupac_gold_book"
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        # the term's own DOI in <head>; only Gold Book term pages carry a 10.1351/goldbook.* identifier
        return _head_meta(self.soup, "dc.identifier").startswith(_GOLD_BOOK_DOI)

    def _cite_as_credit(self):
        """The term card's "Cite as: IUPAC. ..." footer (3.0.1 pages); None on 5.0.0 pages ("Citation: ...")."""
        for footer in self.soup.select("#notecard div.panel-footer"):
            if _CITE_AS.match(" ".join(footer.get_text(" ", strip=True).split())):
                return footer
        return None

    def authors_found(self):
        return bool(self.is_publisher_specific_parser() and self._cite_as_credit() is not None)

    def parse(self):
        if not self.authors_found():
            return {"authors": [], "abstract": None}
        named = _head_meta(self.soup, "author")
        name = named if "IUPAC" in named else "IUPAC"
        return {"authors": [{"name": name, "affiliations": [], "is_corresponding": False}], "abstract": None}
