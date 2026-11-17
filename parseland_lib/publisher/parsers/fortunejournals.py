"""Fortune Journals (fortunejournals.com: open-access medical and life-science journals; oxjob #2339).

Every stored article page is one PHP template. article.fullTextBody holds the title (div.heading-v4), then the byline
as the first <p><strong> (after an "Article Information" heading on the older pages), one <p> per affiliation led by
its <sup> key ("1", "a"; a page with one affiliation prints it without a key, for every author), and a
"*Corresponding Author: <name>, <address>" line (p.correspondingStyles on most pages). Byline names carry the keys as
<sup> ("Name<sup>1,2*</sup>"; older pages "Name*" or "A and B*"). The page ends with "References" over one <ol>.
The 2026 redesign (article.ft-card, 1 of 80 sampled pages) prints the same blocks in the card's first div.ft-body.

Until this parser only the generic one read these pages: the abstract (under its "Abstract" heading) and, on a few,
the citation_author tags; never an affiliation, rarely the corresponding author, never the reference list. The
abstract is left to parse_page's heading reader, and acknowledgments and funding to its headed back-matter reader:
both read these pages today.
Not read: abstract-only pages (/abstract/...) and reference lists that are not one <ol> after their heading.
"""
import re

from bs4 import Comment, NavigableString, Tag

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

_PUBLISHER = "fortune journals"
_CORR_LABEL = re.compile(r"^\W*corresponding\s+authors?\W*", re.I)
_FRONT_END = re.compile(r"^\W*(?:received|accepted|published|citation)\b", re.I)
_NAME_SPLIT = re.compile(r"\s*(?:,|;|&|\band\b)\s*")
# a piece of the byline that is only degrees ("Ben Okoro, MD, MPH") or a suffix: not an author
_DEGREE = (r"(?:M\.?D|Ph\.?\s?D|PharmD|M\.?A|R\.?N|MSN|BSN|M\.?P\.?H|M\.?Sc|B\.?Sc|MBBS|DVM|DDS|BDS|MDS|M\.?S|FRCS|"
           r"FACS|FRCP|MRCP|DNP|MBA|MPhil|Jr|Sr|II|III)\.?")
_DEGREES_ONLY = re.compile(rf"^(?:{_DEGREE}[\s,]*)+$")
# any other all-capitals abbreviation standing alone between commas ("MHS", "FACC", "DNB"): a degree, never a name
_ABBREVIATION = re.compile(r"^(?:[A-Z]\.?){2,5}$")
# degrees printed after a name without a comma ("Chen Wei PhD"); never MD / MA / MS, which are also initials here
_TRAILING_DEGREE = re.compile(r"(?:\s+(?:Ph\.?\s?D|PharmD|MBBS|M\.?P\.?H|M\.?Sc|B\.?Sc)\.?)+$")
_TITLE = re.compile(r"^(?:(?:Dr|Prof)\.?\s+)+", re.I)
_RANGE = re.compile(r"(\d{1,2})\s*[-–]\s*(\d{1,2})")
# an affiliation's key: "1", "12", "a", "2*" (not "th" in "5<sup>th</sup> year")
_AFF_KEY = re.compile(r"^\s*(\d{1,2}|[a-z])\s*\*?\s*$")
_HEADINGS = ("h2", "h3", "h4", "h5")
_REFERENCES = re.compile(r"^\s*references?\s*:?\s*$", re.I)
_MORE = re.compile(r"\b(?:show|load|view|see) (?:all|more)\b", re.I)


def _publisher_tag(soup):
    """The citation_publisher tag in <head>. Every parser's claim runs on every page (#2239: under 0.5 ms a page it
    does not claim), so <head> is reached through direct children only and searched alone."""
    html = soup.find("html", recursive=False)
    head = (html or soup).find("head", recursive=False)
    return head.find("meta", attrs={"name": "citation_publisher"}) if head is not None else None


def _keys(marker):
    """'1,2*' -> {'1', '2'}; '1-2,*' -> {'1', '2'}; 'a,b' -> {'a', 'b'}."""
    keys = set()
    for lo, hi in _RANGE.findall(marker):
        if int(lo) < int(hi) <= int(lo) + 20:
            keys |= {str(i) for i in range(int(lo), int(hi) + 1)}
    marker = _RANGE.sub(" ", marker)
    keys |= set(re.findall(r"\d{1,2}", marker)) | set(re.findall(r"(?<![a-z])[a-z](?![a-z])", marker))
    return keys


def _tokens(node, out):
    """The byline as ('t', text) and ('m', superscript) pieces in reading order."""
    for child in node.children:
        if isinstance(child, Comment):
            continue
        if isinstance(child, NavigableString):
            out.append(("t", str(child)))
        elif isinstance(child, Tag):
            if child.name == "sup":
                out.append(("m", child.get_text()))
            elif child.name == "br":
                out.append(("t", ", "))
            else:
                _tokens(child, out)
    return out


def _merged(tokens):
    merged = []
    for kind, text in tokens:
        if merged and merged[-1][0] == kind:
            merged[-1] = (kind, merged[-1][1] + text)
        else:
            merged.append((kind, text))
    return merged


def _clean_name(piece):
    """(name, starred) of one byline piece, or None when it names no one."""
    piece = squash(piece).strip(" .,;:")
    starred = piece.endswith("*")
    piece = _TITLE.sub("", piece.rstrip("*").strip(" ,"))
    piece = _TRAILING_DEGREE.sub("", piece).strip(" ,")
    if not piece or _DEGREES_ONLY.match(piece) or _ABBREVIATION.match(piece) or not any(c.isalpha() for c in piece):
        return None
    return piece, starred


def _name_tokens(name):
    return {t for t in re.findall(r"\w+", name.lower()) if len(t) > 1}


class FortuneJournals(PublisherParser):
    parser_name = "fortune_journals"
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        tag = _publisher_tag(self.soup)
        return tag is not None and squash(tag.get("content")).lower() == _PUBLISHER

    def authors_found(self):
        return bool(self._front()[0])

    def _front(self):
        """(authors, article) for a page this parser reads, else ([], None)."""
        if hasattr(self, "_front_cache"):
            return self._front_cache
        self._front_cache = [], None
        if not self.is_publisher_specific_parser():
            return self._front_cache
        article = self.soup.find("article", class_="fullTextBody")
        front = article
        if article is None:  # the 2026 redesign prints the same front matter in the card's first div.ft-body
            article = self.soup.find("article", class_="ft-card")
            front = article.find("div", class_="ft-body") if article is not None else None
        if front is None:
            return self._front_cache
        byline, affs, corr = self._scan(front)
        if byline is None:
            return self._front_cache
        authors = self._authors(byline, affs, corr)
        self._front_cache = authors, article
        return self._front_cache

    @staticmethod
    def _scan(container):
        """(byline <p>, affiliation <p>s, corresponding line) among the container's own blocks."""
        byline, affs, corr = None, [], None
        for el in container.find_all(True, recursive=False):
            if "abstract-display" in (el.get("class") or []):
                break
            if el.name != "p":
                if byline is not None and el.name in _HEADINGS:
                    break
                continue
            text = squash(el.get_text(" "))
            if not text:
                continue
            if _CORR_LABEL.match(text):
                corr = corr or text
                continue
            if _FRONT_END.match(text):
                if byline is not None:
                    break
                continue
            if byline is None:
                if el.find("strong") is not None:
                    byline = el
                continue
            if corr is None:  # the affiliations stand between the byline and the corresponding line
                affs.append(el)
        return byline, affs, corr

    @staticmethod
    def _affiliations(paragraphs):
        """({key: affiliation}, [affiliations printed without a key])."""
        chunks = []  # [key or None, [text]]
        for p in paragraphs:
            chunks.append([None, []])
            for child in p.descendants:
                if isinstance(child, Tag) and child.name == "sup" and (m := _AFF_KEY.match(child.get_text())):
                    chunks.append([m.group(1), []])
                elif isinstance(child, Tag) and child.name == "br":
                    chunks[-1][1].append(" ")
                elif isinstance(child, NavigableString) and not isinstance(child, Comment):
                    sup = child.find_parent("sup")
                    if sup is None or not _AFF_KEY.match(sup.get_text()):  # not the key's own text
                        chunks[-1][1].append(str(child))
        keyed, unkeyed = {}, []
        for key, parts in chunks:
            if text := squash("".join(parts)).strip(" ,;"):
                if key is None:
                    unkeyed.append(text)
                else:
                    keyed.setdefault(key, text)
        return keyed, unkeyed

    def _authors(self, byline, aff_paragraphs, corr):
        authors = []  # [name, keys, starred]
        for kind, text in _merged(_tokens(byline, [])):
            if kind == "m":
                if authors:
                    authors[-1][1] |= _keys(text)
                    authors[-1][2] = authors[-1][2] or "*" in text
                continue
            for piece in _NAME_SPLIT.split(text):
                if cleaned := _clean_name(piece):
                    authors.append([cleaned[0], set(), cleaned[1]])
        if not authors:
            return []
        keyed, unkeyed = self._affiliations(aff_paragraphs)
        # "unlinked" (label-v1): affiliations the page does not tie to authors go to every author; so do keyed ones when
        # no byline name carries a key
        if keyed and not any(keys & keyed.keys() for _, keys, _ in authors):
            keyed, unkeyed = {}, list(keyed.values()) + unkeyed
        everyone = unkeyed if not keyed else []
        # a star marks the corresponding author only where the page says what it means (label-v1 rubric)
        starred = {i for i, a in enumerate(authors) if a[2]} if corr else set()
        if corr and not starred:
            head = _name_tokens(_CORR_LABEL.sub("", corr)[:120])
            starred = {i for i, a in enumerate(authors) if (t := _name_tokens(a[0])) and t <= head}
        out = []
        for i, (name, keys, _) in enumerate(authors):
            affs = [keyed[k] for k in sorted(keys, key=lambda k: (not k.isdigit(), int(k) if k.isdigit() else k))
                    if k in keyed] if keyed else list(everyone)
            out.append({"name": name, "affiliations": affs, "is_corresponding": i in starred if corr else None})
        return out

    def _references(self, article):
        """(references, references_complete) from the <ol> right after the "References" heading."""
        # imported here: back_matter and parse import this package, so a module-level import is circular
        from parseland_lib.back_matter import _entry_doi
        from parseland_lib.parse import _entries_look_whole
        for label in reversed(article.find_all(list(_HEADINGS) + ["strong", "p"], string=_REFERENCES)):
            block = label if label.name in _HEADINGS or label.name == "p" else \
                label.find_parent(list(_HEADINGS) + ["p"]) or label
            ol = block.find_next_sibling()
            if ol is None or ol.name != "ol":
                continue
            items = ol.find_all("li", recursive=False)
            refs = []
            for li in items:
                raw = squash(li.get_text(" "))
                raw = re.sub(r" ([,.;:)\]])", r"\1", raw)
                if raw:
                    refs.append({"position": len(refs) + 1, "raw": raw, "doi": _entry_doi(li, raw)})
            start = (ol.get("start") or "1").strip()
            complete = bool(refs) and len(refs) == len(items) and start in ("", "1") \
                and not ol.find("ol") and not _MORE.search(ol.get_text(" ")) \
                and _entries_look_whole([r["raw"] for r in refs])
            return refs, complete
        return [], False

    def parse(self):
        authors, article = self._front()
        references, complete = self._references(article) if article is not None else ([], False)
        return {"authors": authors, "abstract": None,
                "references": references or None, "references_complete": complete}
