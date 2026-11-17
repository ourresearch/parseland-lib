"""Gavin Publishers (gavinpublishers.com, open-access journals; oxjob #2339).

The pages carry citation_* meta tags (citation_publisher "Gavin Publishers") but no institution tags, and the older
template writes every author into ONE citation_author tag ("A, B, C"). The page prints the author block itself:

    current template:  <div id="content"><h3 class="citation_author">by A<sup>1*</sup>, B<sup>2</sup></h3>
                       <p><sup>1</sup>Department ...</p> ... <p>*Corresponding author: A, ...</p></div><div id="border">
    older template:    <h1 class="citation_title">...</h1> ... <div><h3><strong>A</strong><strong><sup>1*</sup></strong>
                       ...</h3><p><sup>1</sup>Department ...</p><p>*Corresponding author: ...</p><div id="border">

(the byline is sometimes a <p> or an <h5> instead of the <h3>). A star is a corresponding-author mark only when the
block prints its "Corresponding author" note. One affiliation printed without numbers is every author's (label-v1:
"unlinked"). The body prints "Acknowledgements" and "Funding" as a bold label, alone in a paragraph or run in.
The abstract stays the generic reader's (what Parseland read here before this parser).
"""
import copy
import re

from bs4 import NavigableString, Tag

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser

_SUP_OPEN, _SUP_CLOSE = "\x01", "\x02"
_MARK = re.compile(f"({_SUP_OPEN}[^{_SUP_CLOSE}]*{_SUP_CLOSE})")
_UNICODE_SUPS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")
_UNICODE_SUP_RUN = re.compile("[⁰¹²³⁴⁵⁶⁷⁸⁹]+")
_SEPARATOR = re.compile(r"\s*(?:,|;|&|\band\b)\s*")
_BYLINE_PREFIX = re.compile(r"^\s*(?:by|authors?\s*:)\s+", re.I)
_CORR_NOTE = re.compile(r"^\W*c\s*orrespond(?:ing|ence)\b", re.I)
_BLOCK_END = re.compile(r"^\W*(?:received|accepted|published|citation|copyright|keywords?|abstract)\b", re.I)
_LABEL_NUMBERS = re.compile(r"(\d+)(?:\s*[-–]\s*(\d+))?")
_NUMBERED_LINE = re.compile(r"^\s*(\d{1,2})\s+(\D.*)$")

_ACK = r"acknowledge?ments?(?:\s+and\s+funding)?"
_FUNDING = (r"(?:funding(?:\s+(?:statement|sources?|information|declaration|details|support))?|"
            r"sources?\s+of\s+funding|financial\s+(?:support|disclosures?)|grant\s+support)")
_SECTION_LABEL = re.compile(rf"^\s*(?:(?P<ack>{_ACK})|(?P<funding>{_FUNDING}))\s*(?::\s*(?P<rest>.*))?$", re.I | re.S)


def _mark(text):
    return _SUP_OPEN + text + _SUP_CLOSE


def _squash(text):
    return " ".join((text or "").split())


def _with_marks(el):
    """The element's text with each <sup> wrapped in marks ("A\x011*\x02, B\x012\x02") and <br> as a line break."""
    el = copy.copy(el)  # never change the page: the abstract reader and the fulltext step still read this soup
    while (sup := el.find("sup")) is not None:  # outermost first: a nested <sup> goes with its parent
        sup.replace_with(_mark(sup.get_text("")))
    for br in el.find_all("br"):
        br.replace_with("\n")
    return el.get_text("").replace("\xa0", " ")


def _label_keys(label):
    keys = []
    for first, last in _LABEL_NUMBERS.findall(label):
        lo, hi = int(first), int(last or first)
        keys.extend(str(n) for n in range(lo, hi + 1) if hi - lo < 20)
    return keys


def _bold_label(p):
    """True when the paragraph opens with a short bold label ("<p><b>Conflict of Interest</b></p>", "<p><strong>
    Ethics:</strong> ...</p>"): the next section starts there."""
    first = next((c for c in p.children if not (isinstance(c, NavigableString) and not c.strip())), None)
    if not isinstance(first, Tag) or first.name not in ("strong", "b"):
        return False
    label = _squash(first.get_text())
    rest = _squash(p.get_text())[len(label):]
    return 0 < len(label) <= 60 and (not rest or label.endswith(":") or rest.lstrip().startswith(":"))


class GavinPublishers(PublisherParser):
    parser_name = "gavin_publishers"
    prefer_publisher_authors_over_generic = True  # the byline beats the one-tag "A, B, C" of the older template

    def is_publisher_specific_parser(self):
        if getattr(self, "_claimed", None) is None:
            # one tag in the <head>, reached through the top-level nodes: no whole-page walk on other sites' pages
            root = self.soup.find("html", recursive=False)
            head = root.find("head", recursive=False) if root is not None else None
            tag = head.find("meta", attrs={"name": "citation_publisher"}) if head is not None else None
            self._claimed = bool(tag is not None and _squash(tag.get("content")).lower() == "gavin publishers")
        return self._claimed

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self.parse_authors())

    # ---- the author block

    def _block(self):
        """The byline element and the elements printed after it, up to the dates box; None when not found."""
        content = self.soup.find("div", id="content")
        if content is not None and (after := content.find_next_sibling()) is not None and after.get("id") == "border":
            kids = content.find_all(recursive=False)
        elif (border := self.soup.find("div", id="border")) is not None:
            kids = list(reversed(border.find_previous_siblings()))
        elif (title := self.soup.find(["h1", "h4"], class_=["citation_title", "avtitle"])) is not None and (
                byline := title.find_next(["h3", "h5"])) is not None:
            kids = [byline] + byline.find_next_siblings()
        else:
            return None
        kids = [k for k in kids if _squash(k.get_text())]
        if not kids or kids[0].name not in ("h3", "h5", "p"):
            return None
        return kids[0], kids[1:]

    def _byline(self, el):
        """[(name, label)] from the byline, or [] when any part does not read as a name."""
        text = _BYLINE_PREFIX.sub("", _with_marks(el))
        # "Zusterzeel¹": a superscript digit printed as a character, not in a <sup>
        text = _UNICODE_SUP_RUN.sub(lambda m: _mark(m.group(0).translate(_UNICODE_SUPS)), text)
        # a star printed outside any <sup> ("Orozco-Martínez<sup>1</sup>*", "Ankamah*") marks the name before it
        text = "".join(c if c.startswith(_SUP_OPEN) else c.replace("*", _mark("*")) for c in _MARK.split(text))
        parts = [["", ""]]  # [name, label] in byline order; a mark goes to the name it follows
        for chunk in _MARK.split(text):
            if chunk.startswith(_SUP_OPEN):
                (parts[-1] if parts[-1][0].strip() or len(parts) == 1 else parts[-2])[1] += chunk[1:-1]
            else:
                names = _SEPARATOR.split(chunk)
                parts[-1][0] += names[0]
                parts.extend([name, ""] for name in names[1:])
        out = []
        for name, label in parts:
            name = re.sub(r"-\s+", "-", _squash(name)).strip(" ,;:")
            if not name:
                continue
            if len(name) > 80 or len(name.split()) > 7 or re.search(r"\d", name) or not re.search(r"[^\W\d_]", name):
                return []
            out.append((name, label))
        return out

    def _affiliation_lines(self, el):
        """[(key or None, text)] for each line of an affiliation paragraph."""
        lines = []
        for line in _with_marks(el).split("\n"):
            key = None
            if m := re.match(rf"^\s*{_SUP_OPEN}([^{_SUP_CLOSE}]*){_SUP_CLOSE}(.*)$", line, re.S):
                key, line = _squash(m.group(1)).strip("[]()") or None, m.group(2)
            line = _squash(_MARK.sub(" ", line)).strip(" ,;")
            if line:
                lines.append((key, line))
        return lines

    def parse_authors(self):
        if (cached := getattr(self, "_authors", None)) is not None:
            return cached
        self._authors = []
        if (block := self._block()) is None:
            return self._authors
        byline, rest = block
        names = self._byline(byline)
        if not names:
            return self._authors
        lines, notes = [], []
        for el in rest:
            text = _squash(el.get_text(" "))
            if el.name != "p" or _BLOCK_END.match(text):
                break
            if _CORR_NOTE.match(text):
                notes.append(text)
                continue
            if notes:  # the affiliations come before the note
                break
            lines.extend(self._affiliation_lines(el))
        numbered = any(_label_keys(label) for _, label in names)
        if numbered and lines and all(key is None for key, _ in lines):
            # "1 Department ..." with the number as plain text
            keyed = [(m.group(1), m.group(2)) if (m := _NUMBERED_LINE.match(t)) else (None, t) for _, t in lines]
            if all(key for key, _ in keyed):
                lines = keyed
        by_key = {}
        for key, text in lines:
            for k in _label_keys(key or ""):
                by_key.setdefault(k, text)
        unkeyed = [text for key, text in lines if not key]
        starred = bool(notes) and any("*" in label for _, label in names)
        authors = []
        for name, label in names:
            keys = _label_keys(label)
            if keys and by_key:
                affs = [by_key[k] for k in keys if k in by_key]
            elif not numbered and unkeyed and not by_key:
                affs = list(unkeyed)  # printed without numbers: every author's (label-v1 "unlinked")
            elif len(lines) == 1 and not by_key:
                affs = [lines[0][1]]  # one line for everyone, the byline's numbers point at a footnote
            else:
                affs = []
            authors.append({"name": name, "affiliations": list(dict.fromkeys(affs)),
                            "is_corresponding": starred and "*" in label})
        if notes and not starred:
            # no star in the byline: the note names the corresponding author ("Corresponding author: A, Department")
            for note in notes:
                head = re.split(r":", note, maxsplit=1)[-1]
                head = re.split(r",", head, maxsplit=1)[0]
                for author in authors:
                    if GenericPublisherParser._text_has_person(head, author["name"]):
                        author["is_corresponding"] = True
        self._authors = authors
        return authors

    # ---- acknowledgments and funding

    def _back_matter(self):
        found = {}
        article = self.soup.find("article") or self.soup
        for el in article.find_all(["p", "h3", "h4", "h5"]):
            if el.find_parent(["li", "nav", "footer", "header", "a"]) is not None:
                continue
            text = el.get_text(" ")
            if len(text) > 4000 or not (m := _SECTION_LABEL.match(_squash(text))):
                continue
            key = "acknowledgments" if m.group("ack") else "funding_statement"
            if key in found:
                continue
            bold = el.name != "p" or _bold_label(el) or (el.find(["strong", "b"]) is not None and _squash(
                el.find(["strong", "b"]).get_text()).lower().startswith(_squash(text)[:8].lower()))
            if not bold:
                continue
            if rest := _squash(m.group("rest") or ""):
                found[key] = rest
                continue
            paragraphs = []
            for sib in el.find_next_siblings():
                if sib.name != "p" or _bold_label(sib):
                    break
                if t := _squash(sib.get_text(" ")):
                    paragraphs.append(t)
            if paragraphs:
                found[key] = "\n".join(paragraphs)
        return found

    def parse(self):
        authors = self.parse_authors()
        parsed = {"authors": authors,
                  "abstract": GenericPublisherParser(self.soup).parse()["abstract"]}
        back = self._back_matter()
        parsed["acknowledgments"] = back.get("acknowledgments")
        parsed["funding_statement"] = back.get("funding_statement")
        return parsed
