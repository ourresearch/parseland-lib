"""Duncker & Humblot eLibrary (elibrary.duncker-humblot.com, CloudPublish platform): byline and author notes (oxjob #2338).

The generic parser reads the citation_author tags. The site's pages show more than those tags hold:
- the byline under the title (`div.section__right > p`, one link per person to /authors/<Family, Given>) is the
  only place book reviews and book chapters name their author: they carry no citation_author tags;
- an edited volume's byline reads "Editors: ..." and has no tags either; label-v1 lists the editors when they are
  the only people the work credits;
- every affiliation sits in the "Author Details" notes of an article's Additional Information panel: one `<p>` per
  author, "Dr. Albrecht Hoppe, Domstiftsarchiv Brandenburg, ..." (the name, then the affiliation and its address),
  each closed by a `ul.list-none` holding a biography, an e-mail link and a Google Scholar link.
The abstract stays the generic reader's (the page's citation_abstract or its "Abstract" block), unchanged.

Left alone, on purpose (#2338 sizing, 76 sample pages, 564 works each):
- corresponding authors: the e-mail link each note carries is shown for every author, not a mark (label-v1);
- the reference list (`ol#reference-list-references`): one sampled work lacked references, under the 1,000-works floor;
- books' "About The Author" text and the notes' list items: biographies, not affiliations;
- a note that gives only a place ("40468 Düsseldorf, Deutschland", "Detroit/Michigan"): no employer or institute;
- the older eLibrary template (pure-css pages, `/publication/b/id/...`), 6 of 76 pages: no `div.section__right` byline,
  so authors_found() is False there and the generic parser keeps them.
"""
import re
import unicodedata

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser

_TITLE_PREFIX = "Duncker & Humblot"  # every eLibrary page's <title>: "Duncker & Humblot - Berlin: <work title>"
_HOST = "elibrary.duncker-humblot.com"
_EDITORS = re.compile(r"^\s*(editors?|hrsg|herausgeber)", re.I)
_TITLE_WORDS = {"ra", "pd", "prof", "dr", "dipl", "ing", "mba", "ma", "llm", "phd", "habil", "apl", "jun", "em"}
_MARKER = re.compile(r"^\s*\d+\s*(?=[^\W\d])")  # a footnote number glued to the name: "1Hugues Höfer, ..."
_CONTACT = re.compile(r"[,;.]?\s*\b(?:e-?mail|internet|homepage|web)\s*:.*$", re.I | re.S)
_EMAIL = re.compile(r"\S+@\S+")
_BIOGRAPHY = re.compile(r"^(geb\.|born\b)", re.I)  # "Bull, Prof. Dr. jur., geb. 1936, Universitätsprofessor (em.)."
_POSTCODE = re.compile(r"^(?:[A-Z]{1,2}-)?\d{4,5}\s+\S")  # "40468 Düsseldorf", "CH-6045 Meggen"
_STREET = re.compile(r"^[^\W\d]+(?:[ -][^\W\d]+)?\s+\d+\s*[a-z]?$")  # "Hauptstraße 177"
_COUNTRIES = {"deutschland", "germany", "österreich", "austria", "schweiz", "switzerland", "usa", "u.s.a", "uk"}


def _fold(word):
    word = unicodedata.normalize("NFKD", word)
    return "".join(c for c in word if not unicodedata.combining(c)).casefold().strip(".,;:()")


def _name_tokens(name):
    tokens = set()
    for word in re.split(r"[\s,]+", name):
        if f := _fold(word):
            tokens.add(f)
            tokens.update(p for p in f.split("-") if p)
    return tokens


def _is_title(word):
    f = _fold(word)
    return f in _TITLE_WORDS or (word.endswith(".") and bool(re.fullmatch(r"[^\W\d_][\w.-]*\.", word)))


def _strip_name(text, tokens):
    """(True, rest) when the note opens with this author's name (in either order, with degrees); else (False, None)."""
    segments = _MARKER.sub("", text).split(",")
    named, i = False, 0
    while i < len(segments):
        words = segments[i].split()
        if not words:
            break
        kinds = ["name" if _fold(w) in tokens else "title" if _is_title(w) else "other" for w in words]
        if "other" in kinds:
            break
        named = named or "name" in kinds
        i += 1
    if not named:
        return False, None
    return True, ",".join(segments[i:])


def _only_a_place(text):
    segments = [s.strip(" .") for s in text.split(",") if s.strip(" .")]

    def place(s):
        if _POSTCODE.match(s) or _STREET.match(s) or s.casefold() in _COUNTRIES:
            return True
        # one short place name alone: "Ankara", "Detroit/Michigan" (a domain such as "erlassjahr.de" is kept)
        return len(segments) == 1 and "." not in s and (len(s.split()) == 1 or ("/" in s and len(s.split()) <= 2))

    return bool(segments) and all(place(s) for s in segments)


def _affiliations(rest):
    rest = _EMAIL.sub("", _CONTACT.sub("", rest or ""))
    out = []
    for part in rest.split(";"):
        part = re.sub(r"\s+", " ", part).strip(" ,")
        if part and not _BIOGRAPHY.match(part) and not _only_a_place(part):
            out.append(part)
    return out


class DunckerHumblot(PublisherParser):
    parser_name = "duncker_humblot"
    # the byline names book reviewers, chapter authors and volume editors that no citation_author tag holds
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        # Cheap claim first (#2239: every parser's claim runs on every page): the <head>'s <title> and its links
        # only, never the whole tree. Cached: the dispatcher calls authors_found() and then this on one instance.
        claim = self.__dict__.get("_claim")
        if claim is None:
            head = self.soup.head
            title = head.find("title") if head else None
            claim = bool(title and title.get_text().strip().startswith(_TITLE_PREFIX)) and any(
                _HOST in (tag.get("href") or "") for tag in head.find_all("link"))
            self._claim = claim
        return claim

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._byline())

    def _byline(self):
        byline = self.__dict__.get("_byline_names")
        if byline is None:
            authors, editors = [], []
            for p in self.soup.select("div.section__right > p"):
                links = p.select('a[href*="/authors/"]')
                if not links:
                    continue
                text, first = p.get_text(" ", strip=True), links[0].get_text(" ", strip=True)
                label = text[:text.find(first)] if first in text else ""  # "Editors: " before the first name
                names = [n for a in links if (n := a.get_text(" ", strip=True))]
                if _EDITORS.match(label):
                    editors.extend(names)
                elif ":" not in label:  # another role ("Translators:") is not an author
                    authors.extend(names)
            byline = self._byline_names = authors or editors
        return byline

    def _notes(self):
        """The Author Details notes: (group, text) for each <p> of the panel closed by a ul.list-none."""
        panel = self.soup.select_one("section.additional-info")
        notes, pending, group = [], [], 0
        for child in panel.children if panel else []:
            if child.name == "p":
                pending.append(child.get_text(" ", strip=True))
            elif child.name == "ul" and "list-none" in (child.get("class") or []):
                notes.extend((group, t) for t in pending if t)
                pending, group = [], group + 1
            elif child.name in ("h4", "dl"):
                pending = []
        return notes, group

    def parse(self):
        names = self._byline()
        # a name the citation_author tags also hold keeps the tag's spelling (books write it "Given Family" there),
        # so pages the generic parser already read keep the same author strings
        tags = [m["content"].strip() for m in (self.soup.head or self.soup).find_all("meta", attrs={"name": "citation_author"})
                if (m.get("content") or "").strip()]
        tokens = [_name_tokens(n) for n in names]
        names = [next((t for t in tags if _name_tokens(t) == tok), n) for n, tok in zip(names, tokens)]
        authors = [{"name": n, "affiliations": [], "is_corresponding": None} for n in names]
        notes, groups = self._notes()
        for group, text in notes:
            hit = None
            for i, t in enumerate(tokens):
                named, rest = _strip_name(text, t)
                if named:
                    hit = (i, rest)
                    break
            if hit is None and groups == len(authors) and not any(_is_title(w) for w in text.split(",")[0].split()):
                hit = (group, text)  # notes that name nobody ("Dr. ..." names someone), one per author: in byline order
            if hit is None:
                continue
            for aff in _affiliations(hit[1]):
                if aff not in authors[hit[0]]["affiliations"]:
                    authors[hit[0]]["affiliations"].append(aff)
        return {"authors": authors, "abstract": GenericPublisherParser(self.soup).parse()["abstract"]}
