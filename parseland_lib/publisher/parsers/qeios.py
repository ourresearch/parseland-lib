import json
import re

from bs4 import BeautifulSoup, Tag

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser


class Qeios(PublisherParser):
    """Qeios (qeios.com): preprints, peer reviews and definitions (oxjob #2330).

    The page is an unrendered Vue template. Its citation_* meta tags give the byline, the abstract and an author's
    institution only when the author picked one from Qeios's own list; the page's `GLOB.publication = {...}` script
    holds the rest. This parser gives the generic parser's reading of the meta tags, plus two things only that script
    has: the affiliation text an author typed (`affiliation_strings`) for an author no citation_author_institution tag
    names one for, and the funding sentence of the Declarations box (`declarations.funding`). A peer review's page
    also embeds the reviewed article (`reviewable`): only the page's own publication is read, never that one.
    """
    parser_name = "qeios"

    _BASE_URL = re.compile(r"^https?://(?:www\.)?qeios\.com/?$", re.I)
    _PUBLICATION = "GLOB.publication = "

    def is_publisher_specific_parser(self):
        if getattr(self, "_claimed", None) is None:
            self._claimed = self._claim()
        return self._claimed

    def _claim(self):
        """Qeios's own <meta name="app-base-url" content="https://www.qeios.com">. Looks only at <html>'s and
        <head>'s direct children: every PublisherParser is asked authors_found() on every DOI page, so a page that is
        not Qeios's must cost almost nothing (oxjob #2239's per-page CPU budget)."""
        head = self._head()
        if head is None:
            return False
        return any(self._BASE_URL.match((meta.get("content") or "").strip())
                   for meta in head.find_all("meta", attrs={"name": "app-base-url"}, recursive=False))

    def _head(self):
        for top in self.soup.contents:
            if isinstance(top, Tag) and top.name == "html":
                return next((c for c in top.contents if isinstance(c, Tag) and c.name == "head"), None)
        return None

    def authors_found(self):
        return bool(self.is_publisher_specific_parser() and self._generic()["authors"])

    def _generic(self):
        if getattr(self, "_generic_result", None) is None:
            self._generic_result = GenericPublisherParser(self.soup).parse()
        return self._generic_result

    def parse(self):
        generic = self._generic()
        result = dict(generic)
        result["authors"] = [dict(a, affiliations=list(a.get("affiliations") or [])) for a in generic["authors"]]
        publication = self._publication()
        if publication:
            self._fill_affiliations(result["authors"], publication.get("presentation_authors"))
            result["funding_statement"] = self._funding(publication)
        return result

    def _publication(self):
        for script in self.soup.find_all("script"):
            text = script.string or ""
            at = text.find(self._PUBLICATION)
            if at < 0:
                continue
            try:
                publication, _ = json.JSONDecoder().raw_decode(text, at + len(self._PUBLICATION))
            except ValueError:
                return None
            return publication if isinstance(publication, dict) else None
        return None

    @staticmethod
    def _name_key(name):
        return re.sub(r"[\W_]+", "", (name or "").casefold())

    def _fill_affiliations(self, authors, records):
        """An author the meta tags give no institution gets the affiliation text their Qeios record holds."""
        if not isinstance(records, list):
            return
        by_name = {}
        for record in records:
            if not isinstance(record, dict):
                continue
            strings = [s.strip() for s in record.get("affiliation_strings") or [] if isinstance(s, str) and s.strip()]
            institution = record.get("research_institution")
            if not strings and isinstance(institution, dict) and isinstance(institution.get("name"), str):
                strings = [institution["name"].strip()] if institution["name"].strip() else []
            key = self._name_key(record.get("full_name"))
            if strings and key:
                by_name.setdefault(key, strings)
        for author in authors:
            if not author["affiliations"] and (strings := by_name.get(self._name_key(author.get("name")))):
                author["affiliations"] = list(strings)

    @staticmethod
    def _funding(publication):
        declarations = publication.get("declarations")
        if not isinstance(declarations, dict) or not isinstance(declarations.get("funding"), str):
            return None
        text = declarations["funding"]
        if "<" in text:
            text = BeautifulSoup(text, "lxml").get_text(" ")
        text = " ".join(text.split())
        return text if any(map(str.isalpha, text)) else None
