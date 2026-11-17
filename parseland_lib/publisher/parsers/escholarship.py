"""eScholarship item pages (escholarship.org/uc/item/..., University of California), oxjob #2338.

The site's own journals and repository deposits (DOI prefix 10.5070 and journals hosted there: WestJEM 10.5811,
SFEWS 10.15447 ...). Every item page carries citation_author tags, which the generic parser reads, and no
citation_author_institution tag: each author's institution is only in the page state the site embeds for its React app,
<script>window.jscholApp_initialPageData = {..., "authors": [{"name", "institution", "email"}], ...}</script>
(label-v1 takes the affiliation from there). So this parser keeps the generic parser's reading (byline, marks,
abstract) and adds each author's institution.

- The state's e-mail is the depositor's contact, not a corresponding-author mark (label-v1).
- The state's "abstract" holds placeholders ("[No abstract]", "Poem", "Letter to the Editor") the meta tags leave out:
  the abstract stays the generic reader's.
- The state's "sidebar" lists related items with their own authors and institutions: only the top-level "authors".
- An institution may hold several affiliations: one per paragraph, per ";" or per line, and a line that names no
  organisation (a street address, "Sacramento, CA 95814 USA") belongs to the line before it.

The claim is the canonical link to /uc/item/, read among <head>'s own children; newer pages print their head tags
inside <div class="react-head-temp"> in <head>, which lxml moves to the start of <body>, so that block's own children
are read too. Other sites' pages cost a look at <head>'s children and the body's first element, never a tree walk.
Pages stored without the page state (server-rendered without it, about one in eight) are left to the generic parser.
"""
import copy
import html
import json
import re

from bs4 import Tag

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser

_ITEM_URL = re.compile(r"^https?://(?:www\.)?escholarship\.org/uc/item/")
_STATE = "window.jscholApp_initialPageData = "
# A line of an institution that names an organisation starts a new affiliation; one that doesn't is an address line.
_ORG_WORD = re.compile(
    r"universi|college|institut|hospital|cent(?:er|re)|school|department|dept\b|division|faculty|laborator|clinic|"
    r"council|board|service|survey|agency|program|foundation|ministry|museum|library|society|association|academy|"
    r"office|unit\b|station|company|corporation|\binc\b|\bltd\b|\bllc\b|group|system|authority|commission|"
    r"\buc\s|\bcal\s|world|organi[sz]ation|consult|research|health|medical|campus|polytechnic|escuela|universid",
    re.I)


def _key(name):
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def _split_institution(text):
    """`text` as a list of affiliations: paragraphs and ";" split it, and so does each line naming an organisation."""
    affs = []
    for part in re.split(r"\n\s*\n|;", html.unescape(text or "")):
        current = []
        for line in part.splitlines():
            line = " ".join(line.split()).strip(" ,")
            if not line:
                continue
            if current and _ORG_WORD.search(line):
                affs.append(", ".join(current))
                current = []
            current.append(line)
        if current:
            affs.append(", ".join(current))
    return affs


class EScholarship(PublisherParser):
    parser_name = "escholarship"
    # The page's own state names its authors; on full-text pages (Dermatology Online Journal) another parser read
    # body text as a byline and won with it.
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        if getattr(self, "_claimed", None) is None:
            self._claimed = self._claim()
        return self._claimed

    def _claim(self):
        """The canonical link names an item page. It is a child of <head>, or of the <div class="react-head-temp">
        the site prints in <head> and lxml moves to the start of <body>: only those two blocks' own children are read."""
        head, body = self.soup.head, self.soup.body
        link = head.find("link", rel="canonical", recursive=False) if head is not None else None
        if link is None and body is not None:
            first = next((c for c in body.children if isinstance(c, Tag)), None)
            if first is not None and first.name == "div" and "react-head-temp" in (first.get("class") or []):
                link = first.find("link", rel="canonical", recursive=False)
        return bool(link and _ITEM_URL.match(link.get("href") or ""))

    def _state_authors(self):
        if getattr(self, "_authors", None) is None:
            self._authors = []
            body = self.soup.body
            for script in body.find_all("script", recursive=False) if body is not None else []:
                text = script.string or ""
                if text.startswith(_STATE):
                    try:
                        state, _ = json.JSONDecoder().raw_decode(text[len(_STATE):])
                    except ValueError:
                        break
                    authors = state.get("authors") if isinstance(state, dict) else None
                    self._authors = [a for a in authors or [] if isinstance(a, dict)]
                    break
        return self._authors

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._state_authors())

    def parse(self):
        parsed = GenericPublisherParser(self.soup).parse()
        authors = copy.deepcopy(parsed["authors"])
        state = self._state_authors()
        names = [_key(a.get("name")) for a in state]
        if [_key(a["name"]) for a in authors] == names:
            pairs = zip(authors, state)
        else:  # the tags and the state list different people: only names found once in the state
            by_name = {k: a for k, a in zip(names, state) if names.count(k) == 1}
            pairs = [(a, by_name.get(_key(a["name"]))) for a in authors]
        for author, entry in pairs:
            if entry and isinstance(entry.get("institution"), str) and not author["affiliations"]:
                author["affiliations"] = _split_institution(entry["institution"])
        return {"authors": authors, "abstract": parsed["abstract"]}
