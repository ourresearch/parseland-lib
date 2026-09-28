import json
import re

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser


class Ubiquity(PublisherParser):
    """Ubiquity Press journal platform (Next.js, live since ~mid-2024).

    The re-platformed article pages emit citation_author but no
    citation_author_institution, so the generic parser returns every author
    with no affiliation: pages fetched before 2024-02 parsed with affiliations
    90%+ of the time, pages fetched since 2024-07 ~0% (oxjob #833). The
    affiliations are still on the page, in the Next.js flight payload
    (``self.__next_f.push``) as the article's ``authors`` array:
    ``{"first_name", "last_name", "institution", "country", "corresponding",
    "social": {"orcid"}, "fullName"}``.

    ``institution`` is emitted verbatim. It is byte-identical to the string
    the old platform published, and raw affiliation strings are exact-match
    keys downstream (institution matching, curations), so appending
    ``country`` or otherwise rewriting it would re-key every Ubiquity
    affiliation.
    """
    parser_name = "ubiquity"

    ASSET_HOST = "journal-assets.ubiquity.press"
    FLIGHT_PUSH = re.compile(r"^\s*self\.__next_f\.push\((.*)\)\s*;?\s*$", re.S)
    AUTHORS_KEY = re.compile(r'"authors":\[\{')

    def __init__(self, soup):
        super().__init__(soup)
        self._flight = None
        self._authors = None

    def is_publisher_specific_parser(self):
        if self.soup.select_one(f'script[src*="{self.ASSET_HOST}"]'):
            return True
        return self.ASSET_HOST in self.flight_text()

    def authors_found(self):
        return bool(self.json_authors())

    def flight_text(self):
        """Concatenated string payload of every ``self.__next_f.push([1, "..."])``."""
        if self._flight is None:
            parts = []
            for script in self.soup.find_all("script"):
                m = self.FLIGHT_PUSH.match(script.string or "")
                if not m:
                    continue
                try:
                    chunk = json.loads(m.group(1))
                except ValueError:
                    continue
                if len(chunk) > 1 and isinstance(chunk[1], str):
                    parts.append(chunk[1])
            self._flight = "".join(parts)
        return self._flight

    def meta_names(self):
        return [m.get("content", "").strip() for m in
                self.soup.select('meta[name="citation_author"]')
                if m.get("content", "").strip()]

    @staticmethod
    def _key(s):
        return re.sub(r"\W+", "", (s or "").lower())

    def json_authors(self):
        """The article's author list: the first ``authors`` array of author
        objects whose last names line up with the citation_author meta tags
        (related-article cards carry author arrays too)."""
        if self._authors is not None:
            return self._authors
        self._authors = []
        text = self.flight_text()
        meta = [self._key(n) for n in self.meta_names()]
        decoder = json.JSONDecoder()
        for m in self.AUTHORS_KEY.finditer(text):
            try:
                candidate, _ = decoder.raw_decode(text, m.end() - 2)
            except ValueError:
                continue
            if not all(isinstance(a, dict) and "last_name" in a
                       for a in candidate):
                continue
            if meta:
                last = [self._key(a.get("last_name")) for a in candidate]
                # meta names come as "Casal, Bruno" or "Bruno Casal"
                matched = sum(1 for l, n in zip(last, meta) if l and l in n)
                if len(last) != len(meta) or matched * 2 <= len(meta):
                    continue
            self._authors = candidate
            break
        return self._authors

    def parse(self):
        generic = GenericPublisherParser(self.soup).parse()
        json_authors = self.json_authors()
        # Keep the citation_author name the generic parser has always emitted,
        # so the only change on these pages is the affiliations.
        meta = self.meta_names()
        if len(meta) != len(json_authors):
            meta = []
        authors = []
        for i, a in enumerate(json_authors):
            name = meta[i] if meta else (a.get("fullName") or
                    f'{a.get("first_name") or ""} {a.get("last_name") or ""}').strip()
            institution = a.get("institution") or ""
            authors.append({
                "name": name,
                "affiliations": [institution] if institution.strip() else [],
                "is_corresponding": a.get("corresponding")
                if isinstance(a.get("corresponding"), bool) else None,
            })
        if not any(a["affiliations"] for a in authors) and any(
                a.get("affiliations") for a in generic.get("authors") or []):
            return generic
        return {"authors": authors, "abstract": generic.get("abstract")}
