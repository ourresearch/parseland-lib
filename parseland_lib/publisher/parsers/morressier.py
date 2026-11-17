"""Morressier poster and abstract pages (oxjob #2338): conference posters with DOIs under 10.26226/morressier.*, served
by Morressier's Next.js app. The page prints none of the byline in its HTML: the poster's record sits in the
`<script id="__NEXT_DATA__">` JSON, which both label-v1 labellers read (the visible author block is empty).

Two app versions are stored:
- current (route /event/[eventId]/article/[article_id]): props.pageProps.data.document, with `authors` as user
  records (full_name, organization, department) and `_co_authors` as free-text names;
- older (route /article, about 1 page in 8): props.initialState.posters, whose `authors` are user ids resolved
  against initialState.users.
On about half the stored pages `document` is null (the poster is embargoed or gone: the page shows only the
conference header). Those pages are not read here.

Each registered author has one affiliation on the page, printed as two fields; it is returned as one string,
"department, organization". A department with no organization is a city or a lab on the stored pages ("Warsaw"),
not an affiliation, so it is left out. The JSON's e-mail addresses are never shown on the page: no author is marked
corresponding. The poster's abstract is `paper_abstract`; a trailing "References" block printed inside it is cut.
"""
import json
import re

import unidecode

from parseland_lib.publisher.parsers.parser import PublisherParser

# An entry of `_co_authors` that is initials only ("S.", "M.B.", "Sz."): some events store "Surname", "S." as two
# entries.
_INITIALS_ONLY = re.compile(r"^(?:[A-Z][a-z]?\.?[\s-]*)+$")
# A reference list printed at the end of the abstract field ("References:1) Solomon C ...", "\nReferences\n...").
_REFERENCES_START = re.compile(r"\n\s*(?:references?|bibliography)\b\s*:?", re.I)


def _fold(name):
    return re.sub(r"[^a-z]+", " ", unidecode.unidecode(name or "").lower()).split()


def _same_initialed(a, b):
    """True when two renderings name one person with the given names cut to initials: "A. Piotrowski" / "Andrzej
    Piotrowski", "Gogberashvili, K." / "Ketevan Gogberashvili". They share a full word, and the initials of the
    words left over agree."""
    ta, tb = _fold(a), _fold(b)
    shared = {t for t in ta if len(t) > 1} & {t for t in tb if len(t) > 1}
    if not shared:
        return False
    ia = {t[0] for t in ta if t not in shared}
    ib = {t[0] for t in tb if t not in shared}
    return not ia or not ib or ia <= ib or ib <= ia


def _co_author_names(entries):
    names = [e.strip() for e in entries or [] if isinstance(e, str) and e.strip()]
    # "Bauduin", "S.", "Giltay", "E.", ...: one name in two entries, surname then initials
    if len(names) >= 2 and len(names) % 2 == 0 and all(_INITIALS_ONLY.match(n) for n in names[1::2]) and not any(
            _INITIALS_ONLY.match(n) for n in names[::2]):
        return [f"{s}, {i}" for s, i in zip(names[::2], names[1::2])]
    return [n for n in names if not _INITIALS_ONLY.match(n)]


def _affiliation(user):
    org = (user.get("organization") or "").strip()
    dept = (user.get("department") or "").strip()
    if not org:
        return []
    if not dept or dept.lower() in org.lower():
        return [org]
    return [f"{dept}, {org}"]


def _abstract(doc):
    text = doc.get("paper_abstract")
    if not isinstance(text, str):
        return None
    m = _REFERENCES_START.search(text, 100)
    if m:
        text = text[:m.start()]
    text = " ".join(text.split())
    return text or None


class Morressier(PublisherParser):
    parser_name = "morressier"
    # the page's own byline is the JSON's; the generic parser finds nothing on these pages
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        # Every parser is asked on every DOI page, so the claim is one meta tag in the small <head> (#2239's per-page
        # CPU rule): Morressier's app sets <meta name="twitter:site" content="@Morressier"> on every page, both app
        # versions and the 404 page. The answer is kept: authors_found(), parse() and the caller all ask.
        if getattr(self, "_claimed", None) is None:
            head = self.soup.head
            meta = head.find("meta", attrs={"name": "twitter:site"}) if head is not None else None
            self._claimed = meta is not None and (meta.get("content") or "").strip().lower() == "@morressier"
        return self._claimed

    def _record(self):
        """(document, users by id) for the page's poster, or (None, {}) when the page has none."""
        if hasattr(self, "_rec"):
            return self._rec
        self._rec = (None, {})
        tag = self.soup.find("script", id="__NEXT_DATA__")
        try:
            data = json.loads(tag.string) if tag is not None and tag.string else {}
        except ValueError:
            data = {}
        props = data.get("props") if isinstance(data, dict) else None
        if not isinstance(props, dict):
            return self._rec
        if isinstance(props.get("initialState"), dict):  # older app: /article?id=...
            state = props["initialState"]
            posters = [p for p in state.get("posters") or [] if isinstance(p, dict)]
            want = (data.get("query") or {}).get("id") if isinstance(data.get("query"), dict) else None
            doc = next((p for p in posters if want and p.get("id") == want), None)
            if doc is None and len(posters) == 1:
                doc = posters[0]
            users = {u.get("id"): u for u in state.get("users") or [] if isinstance(u, dict)}
            if doc is not None:
                self._rec = (doc, users)
            return self._rec
        page_data = (props.get("pageProps") or {}).get("data") if isinstance(props.get("pageProps"), dict) else None
        doc = page_data.get("document") if isinstance(page_data, dict) else None
        if isinstance(doc, dict):
            self._rec = (doc, {})
        return self._rec

    def authors_found(self):
        if not self.is_publisher_specific_parser():
            return False
        parsed = self.parse()
        return bool(parsed["authors"] or parsed["abstract"])

    def parse_authors(self):
        doc, users = self._record()
        if doc is None:
            return []
        authors, seen = [], set()
        for entry in doc.get("authors") or []:
            user = users.get(entry) if isinstance(entry, str) else entry
            if not isinstance(user, dict):
                continue
            name = " ".join((user.get("full_name") or "").split())
            key = user.get("_id") or user.get("id") or name.lower()
            if not name or key in seen:  # invited co-authors who never signed up have an e-mail and no name
                continue
            seen.add(key)
            authors.append({"name": name, "affiliations": _affiliation(user), "is_corresponding": False})
        for name in _co_author_names(doc.get("_co_authors")):
            if any(_same_initialed(name, a["name"]) for a in authors):  # the uploader again, as "A. Piotrowski"
                continue
            authors.append({"name": name, "affiliations": [], "is_corresponding": False})
        return authors

    def parse(self):
        if not hasattr(self, "_parsed"):
            doc, _ = self._record()
            self._parsed = {"authors": self.parse_authors(), "abstract": _abstract(doc) if doc is not None else None}
        return self._parsed
