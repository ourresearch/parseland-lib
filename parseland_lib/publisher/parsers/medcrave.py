"""MedCrave Online (medcraveonline.com, DOI prefix 10.15406) article pages (oxjob #2338).

The site runs its own PHP template on ~80 journals. The article header is ``h4.allauthornames``: names separated by
commas, each followed by numbered ``<sup>`` affiliation marks, an ORCID ``<sup>`` and, after one author, an envelope
``<sup><i class="fa fa-envelope">`` (it opens a captcha for that author's e-mail). The next ``<p>`` lists the
affiliations, one per ``<br>`` line, numbered by a leading ``<sup>`` when there are several; then a
"<strong>Correspondence:</strong> Name, address" line. The body is ``h1.atsdhdNew`` headings (``h1.atsdhd`` on older
pages), each followed by its ``div.fultextNew`` (``div.fultext``); "References" holds one ``<ol>`` of ``li.ref``.
Its citation_author meta tag is broken (``content=">``) and its citation_author_institution tag empty, so before this
parser Parseland read no byline on these pages.
"""
import re

from bs4 import Comment, NavigableString, Tag
from unidecode import unidecode

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

_PUBLISHER_TAG = re.compile(r"^citation_publisher$")
_SEPARATOR = re.compile(r"\s*(?:,|;|&|\band\b)\s*")
_TITLE = re.compile(r"^(?:dr|prof)\.?\s+", re.I)
_SKIP = {"script", "style", "div", "form", "noscript", "button"}
_HEADER_END = re.compile(r"^\s*(?:received|citation|published|accepted)\b", re.I)
_CORRESPONDENCE = re.compile(r"^\s*correspondence\s*:?", re.I)
_TITLES = {"dr", "prof", "professor", "mr", "mrs", "ms", "phd", "md"}
_HEADINGS = "h1.atsdhdNew, h1.atsdhd"
_ACK_HEADING = re.compile(r"^acknowledge?ments?$", re.I)
_FUNDING_HEADING = re.compile(r"^(?:funding(?: information| sources?| statement)?|financial support|"
                              r"sources? of (?:funding|support))$", re.I)
_REFERENCES_HEADING = re.compile(r"^references?$", re.I)
_MORE = re.compile(r"show (?:more|all)|load (?:more|all)|view (?:more|all)", re.I)
_MIN_STATEMENT = 20  # "None.", "No funding.": the template's slot says the page has none (as back_matter reads it)


def _tokens(name):
    """Folded name tokens without titles: 'Professor Andrew W. Taylor-Robinson' -> andrew w taylor robinson."""
    return [t for t in re.split(r"[^a-z]+", unidecode(name or "").lower()) if t and t not in _TITLES]


def _same_author(byline_name, named):
    """True when the correspondence line's name is this byline name: the same tokens, or a shared surname with the
    given names' initials agreeing ('Acosta G' / 'Gerardo Acosta', 'Sigamoney K' / 'Kohila Vani Sigamoney'), or one
    name the other plus words ('Byron Velasquez' / 'Byron Velasquez Ron')."""
    a, b = _tokens(byline_name), _tokens(named)
    if not a or not b:
        return False
    if set(a) == set(b):
        return True
    shared = {t for t in a if len(t) > 2} & {t for t in b if len(t) > 2}
    if not shared:
        return False
    rest_a = [t for t in a if t not in shared]
    rest_b = [t for t in b if t not in shared]
    if not rest_a or not rest_b:
        return True
    initials_a = "".join(t if len(t) <= 2 else t[0] for t in rest_a)
    initials_b = "".join(t if len(t) <= 2 else t[0] for t in rest_b)
    return initials_a[0] == initials_b[0]


class MedCrave(PublisherParser):
    parser_name = "medcrave"
    # The byline is the page's own; the meta tags hold no authors (their citation_author tag is broken).
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        # Every parser is asked authors_found() on every DOI page, so the claim goes first and stays cheap (#2239's
        # per-page CPU rule): the citation_publisher tag, looked for in the small <head> only (all 47 sampled article
        # pages carry it there; a page-wide search would cost every other page a walk of its whole tree). Kept: the
        # caller, authors_found() and parse() all ask.
        if getattr(self, "_claimed", None) is None:
            head = self.soup.head
            meta = head.find("meta", attrs={"name": _PUBLISHER_TAG}) if head is not None else None
            self._claimed = meta is not None and "medcrave" in (meta.get("content") or "").lower()
        return self._claimed

    def authors_found(self):
        return bool(self.is_publisher_specific_parser() and self._byline_tag() is not None)

    def _byline_tag(self):
        if not hasattr(self, "_h4"):
            self._h4 = self.soup.select_one("h4.allauthornames")
        return self._h4

    # ---- byline

    @staticmethod
    def _byline(h4):
        """[{'name', 'keys', 'envelope'}] in page order. A <sup> closes the name before it; the envelope's <sup> marks
        the author it follows. The captcha pop-up and its scripts inside the <h4> are skipped."""
        authors, buf = [], []

        def close():
            name = squash("".join(buf))
            buf.clear()
            name = _TITLE.sub("", name).strip(" .,;")
            if name:
                authors.append({"name": name, "keys": [], "envelope": False})

        for node in h4.children:
            if isinstance(node, Comment):
                continue
            if isinstance(node, NavigableString):
                pieces = _SEPARATOR.split(str(node).replace("\xa0", " "))
                for i, piece in enumerate(pieces):
                    if i > 0:
                        close()
                    buf.append(piece)
                continue
            if not isinstance(node, Tag) or node.name in _SKIP:
                continue
            if node.name == "sup":
                close()
                if not authors:
                    continue
                if node.find("i", class_="fa-envelope") is not None:
                    authors[-1]["envelope"] = True
                elif node.find("a", href=re.compile("orcid")) is None:
                    authors[-1]["keys"] += re.findall(r"\d+", node.get_text())
                continue
            buf.append(node.get_text())
        close()
        return authors

    @staticmethod
    def _header_paragraphs(h4):
        """The <p>s between the byline and the "Received" / "Citation" lines."""
        for sib in h4.find_next_siblings():
            if sib.name != "p":
                break
            if _HEADER_END.match(sib.get_text()):
                break
            yield sib

    @staticmethod
    def _affiliation_lines(p):
        """[(keys, text)] for each <br>-separated line of the affiliations paragraph."""
        lines, keys, parts = [], [], []

        def close():
            text = squash("".join(parts)).strip(" ,;")
            if text:
                lines.append((list(keys), text))
            keys.clear()
            parts.clear()

        for node in p.children:
            if isinstance(node, Comment):
                continue
            if isinstance(node, Tag) and node.name == "br":
                close()
            elif isinstance(node, Tag) and node.name == "sup":
                if not squash("".join(parts)):  # a leading mark is the line's number
                    keys += re.findall(r"\d+", node.get_text())
                else:
                    parts.append(node.get_text())
            elif isinstance(node, NavigableString):
                parts.append(str(node).replace("\xa0", " "))
            elif isinstance(node, Tag):
                parts.append(node.get_text())
        close()
        return lines

    def parse_authors(self):
        h4 = self._byline_tag()
        byline = self._byline(h4)
        aff_lines, named = [], None
        for p in self._header_paragraphs(h4):
            text = squash(p.get_text())
            if _CORRESPONDENCE.match(text):
                named = squash(_CORRESPONDENCE.sub("", text, count=1)).split(",")[0]
            elif not aff_lines and named is None:
                aff_lines = self._affiliation_lines(p)
        keyed = {}
        for keys, text in aff_lines:
            for k in keys:
                keyed.setdefault(k, []).append(text)
        linked = bool(keyed) and any(a["keys"] for a in byline)
        authors = []
        for a in byline:
            if linked:
                affs = [x for k in a["keys"] for x in keyed.get(k, [])]
            else:  # one unnumbered line (or numbers on one side only): every author has the whole list
                affs = [text for _, text in aff_lines]
            authors.append({"name": a["name"], "affiliations": list(dict.fromkeys(affs)),
                            "is_corresponding": a["envelope"]})
        if named:
            hits = [a for a in authors if _same_author(a["name"], named)]
            if len(hits) > 1:  # two authors share a surname: the one whose tokens are the line's
                hits = [a for a in hits if set(_tokens(a["name"])) == set(_tokens(named))]
            if len(hits) == 1:
                hits[0]["is_corresponding"] = True
        return authors

    # ---- sections

    def _section(self, pattern):
        """The block after the first body heading the pattern names (a div; on older pages the reference list's <ol>
        follows its heading directly), or None."""
        for heading in self.soup.select(_HEADINGS):
            if pattern.match(squash(heading.get_text()).rstrip(" :.")):
                body = heading.find_next_sibling()
                return body if body is not None and body.name in ("div", "ol") else None
        return None

    def _statement(self, pattern):
        body = self._section(pattern)
        if body is None:
            return None
        paragraphs = [squash(p.get_text()) for p in body.find_all("p")] or [squash(body.get_text())]
        text = "\n".join(p for p in paragraphs if p)
        return text if len(text) >= _MIN_STATEMENT else None

    def parse_references(self):
        """(references, complete). Whole only when the section is one <ol> (no start above 1, no list nested in it), its
        items carry no ids or ids ref1..refN in order, and no text sits outside the items."""
        from parseland_lib.back_matter import _entry_doi  # imported here: back_matter imports this package's utils

        body = self._section(_REFERENCES_HEADING)
        if body is None:
            return None, False
        lists = ([body] if body.name == "ol" else []) + body.find_all("ol")
        if not lists:
            return None, False
        items = body.find_all("li")
        refs = []
        for li in items:
            raw = squash(li.get_text())
            if raw:
                refs.append({"position": len(refs) + 1, "raw": raw, "doi": _entry_doi(li, raw)})
        if not refs:
            return None, False
        ids = [li.get("id") for li in items]
        outside = squash("".join(s for s in body.find_all(string=True)
                                 if not isinstance(s, Comment) and s.find_parent("li") is None))
        complete = (len(lists) == 1 and (lists[0].get("start") or "1").strip() in ("", "1")
                    and (all(i is None for i in ids) or ids == [f"ref{n}" for n in range(1, len(ids) + 1)])
                    and len(refs) == len(items) and not outside and not _MORE.search(body.get_text()))
        return refs, complete

    def parse(self):
        references, complete = self.parse_references()
        # The abstract stays what Parseland read before this parser (the generic reader: the page's abstract meta tag):
        # every work on these pages already has one, and the printed text differs only in spacing.
        return {"authors": self.parse_authors(),
                "abstract": GenericPublisherParser(self.soup).parse()["abstract"],
                "acknowledgments": self._statement(_ACK_HEADING),
                "funding_statement": self._statement(_FUNDING_HEADING),
                "references": references,
                "references_complete": complete}
