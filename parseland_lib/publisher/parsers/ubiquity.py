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

    The same platform's pages-router front end (journals whose API is
    ``api.account.<code>.ubiquityjournal.website``; oxjob #2289) prints every
    author in the byline, with an envelope on the corresponding author only,
    but its head carries ONE citation_author tag, the last author's, so the
    generic parser read one author of three or of nine and no corresponding
    author. Its ``__NEXT_DATA__`` holds the article as
    ``props.pageProps.data`` with the whole ``authors`` array
    (``first_name``, ``last_name``, ``institution``, ``corresponding``: the
    envelope). That array is the article's own, so it is read as it stands.
    """
    parser_name = "ubiquity"

    ASSET_HOST = "journal-assets.ubiquity.press"
    # The pages-router variant's API host, in __NEXT_DATA__'s runtimeConfig (API_URL) on every such page.
    PLATFORM_API = ".ubiquityjournal.website/"
    FLIGHT_PUSH = re.compile(r"^\s*self\.__next_f\.push\((.*)\)\s*;?\s*$", re.S)
    FLIGHT_START = ("self.__next_f", "(self.__next_f")
    AUTHORS_KEY = re.compile(r'"authors":\[\{')

    def __init__(self, soup):
        super().__init__(soup)
        self._flight = None
        self._authors = None
        self._page_data = None
        self._flight_marked = None

    def is_publisher_specific_parser(self):
        if self.page_data():
            return True
        if self.soup.select_one(f'script[src*="{self.ASSET_HOST}"]'):
            return True
        return self.ASSET_HOST in self.flight_text()

    def authors_found(self):
        # Production asks every parser this on every DOI page (#2239's per-page CPU rule): only the direct
        # children of <head> and <body> are looked at before the page is known to be Ubiquity's.
        if self.page_data():
            return bool(self.page_data()["authors"])
        return self.flight_marked() and bool(self.json_authors())

    def _top_level(self):
        """The direct children of <head> and <body>: where Next.js puts its scripts and __NEXT_DATA__."""
        for scope in (self.soup.head, self.soup.body):
            if scope is not None:
                yield from (c for c in scope.children if getattr(c, "name", None))

    def flight_marked(self):
        """True when the page loads Ubiquity's assets or carries a Next.js flight payload, at the top level
        (the app-router variant): the one gate before the flight text is assembled."""
        if self._flight_marked is None:
            self._flight_marked = any(
                (c.name == "script" and (self.ASSET_HOST in (c.get("src") or "")
                                         or (c.string or "").lstrip().startswith(self.FLIGHT_START)))
                or (c.name == "link" and self.ASSET_HOST in (c.get("href") or ""))
                for c in self._top_level())
        return self._flight_marked

    def page_data(self):
        """The pages-router variant's article (``__NEXT_DATA__`` props.pageProps.data) when it has an authors
        list, else {}."""
        if self._page_data is None:
            self._page_data = {}
            body = self.soup.body
            tag = next((c for c in body.children if getattr(c, "name", None) == "script"
                        and c.get("id") == "__NEXT_DATA__"), None) if body is not None else None
            text = tag.string if tag is not None else None
            if text and self.PLATFORM_API in text:
                try:
                    data = json.loads(text)["props"]["pageProps"]["data"]
                except (ValueError, KeyError, TypeError):
                    data = None
                if isinstance(data, dict) and isinstance(data.get("authors"), list) and all(
                        isinstance(a, dict) and "last_name" in a for a in data["authors"]):
                    self._page_data = data
        return self._page_data

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

    @staticmethod
    def _corresponding(author):
        return author.get("corresponding") if isinstance(author.get("corresponding"), bool) else None

    def parse_page_data(self, generic):
        authors = []
        for a in self.page_data()["authors"]:
            name = " ".join(f'{a.get("first_name") or ""} {a.get("last_name") or ""}'.split())
            if not name:
                continue
            institution = a.get("institution") or ""
            authors.append({
                "name": name,
                "affiliations": [institution] if institution.strip() else [],
                "is_corresponding": self._corresponding(a),
            })
        return {"authors": authors, "abstract": generic.get("abstract")}

    def parse(self):
        generic = GenericPublisherParser(self.soup).parse()
        if self.page_data():
            return self.parse_page_data(generic)
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
                "is_corresponding": self._corresponding(a),
            })
        if not any(a["affiliations"] for a in authors) and any(
                a.get("affiliations") for a in generic.get("authors") or []):
            return generic
        return {"authors": authors, "abstract": generic.get("abstract")}
