"""American Scientific Publishing Group (americaspg.com) article pages (oxjob #2210).

The current article template ("articleinfo/<journal>/show/<id>") prints the byline as <span class="font-16"> names
whose <sup> holds the affiliation number, then one numbered <li class="font-14"> per affiliation ending in
" - (e-mail)". Abstract and references are "box2" panels; references are Word-pasted <p>s numbered "[n]" or "n.".
A "*" in some bylines is never explained on the page, so it is not read as a corresponding-author mark (label-v1).
The older template (an "auth-details" block with "Affiliation :" lines) is left to the generic parser.
"""
import re

from bs4 import NavigableString

from parseland_lib.publisher.parsers.parser import PublisherParser

BLOCKS = ["p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "td", "blockquote"]
EMAIL_TAIL = re.compile(r"\s+-\s*\([^()]*\)?\s*$")
MARKERS = {"bracket": re.compile(r"^\[(\d{1,4})\]\s*"), "dot": re.compile(r"^(\d{1,4})[.)]\s+")}
DOI = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+)")
MORE = re.compile(r"\b(show|load|view|see) (more|all)\b", re.I)


def _strings(tag, skip=None):
    """Visible text nodes under tag, in order (no comments, scripts or styles), each with its nearest block."""
    for s in tag.find_all(string=True):
        if type(s) is not NavigableString or (skip and skip(s)):
            continue
        yield s, s.find_parent(BLOCKS)


def _text(tag, skip=None, sep="\n"):
    """Text of tag with one line per block element and whitespace collapsed inside each line."""
    parts, cur, last = [], [], None
    for s, block in _strings(tag, skip):
        if block is not last and cur:
            parts.append("".join(cur))
            cur = []
        last = block
        cur.append(str(s))
    parts.append("".join(cur))
    return sep.join(t for t in (re.sub(r"\s+", " ", p).strip() for p in parts) if t)


def _doi(found):
    """A DOI cut out of running text, without the sentence's closing punctuation or an unbalanced ")"."""
    d = found.rstrip(".,;:]")
    while d.endswith(")") and d.count(")") > d.count("("):
        d = d[:-1].rstrip(".,;:]")
    return d


class AmericasPG(PublisherParser):
    parser_name = "americaspg"

    def is_publisher_specific_parser(self):
        return self.substr_in_citation_publisher("American Scientific Publishing Group")

    def _byline(self):
        for p in self.soup.select("div.box2 p.font-16"):
            spans = p.find_all("span", class_="font-16", recursive=False)
            if spans:
                return p, spans
        return None, []

    def authors_found(self):
        return bool(self.is_publisher_specific_parser() and self._byline()[1])

    def _affiliations(self, byline):
        affs = {}
        for li in byline.find_parent("div").find_all("li", class_="font-14"):
            num = li.find("span", class_="left")
            if not num or not num.get_text(strip=True).isdecimal():
                continue
            text = _text(li, skip=lambda s, num=num: s.find_parent("span", class_="left") is num, sep=" ")
            if text := EMAIL_TAIL.sub("", text).strip(" ,;"):
                affs[num.get_text(strip=True)] = text
        return affs

    def _authors(self):
        byline, spans = self._byline()
        affs = self._affiliations(byline)
        authors = []
        for span in spans:
            name = _text(span, skip=lambda s: s.find_parent("sup") is not None, sep=" ").strip(" ,;*")
            if not name:
                continue
            sup = span.find("sup")
            nums = re.findall(r"\d+", sup.get_text(" ")) if sup else []
            authors.append({"name": name, "affiliations": [affs[n] for n in nums if n in affs],
                            "is_corresponding": False})
        return authors

    def _panel(self, heading):
        for box in self.soup.select("div.box2"):
            h5 = box.find("h5")
            if h5 and h5.get_text(" ", strip=True).lower().startswith(heading):
                return box, h5
        return None, None

    def _abstract(self):
        box, h5 = self._panel("abstract")
        if box:
            text = _text(box, skip=lambda s: s.find_parent("h5") is h5)
            if text:
                return text
        return self.parse_abstract_meta_tags(include_seo_tags=False)

    def _references(self):
        """[{position, raw, doi}] and whether the page shows the whole list (numbers 1..n, nothing outside them)."""
        box, h5 = self._panel("references")
        if not box:
            return [], False
        items = [(p, _text(p, sep=" ")) for p in box.find_all("p")]
        items = [(p, t) for p, t in items if t]
        if not items:
            return [], False
        style = next((k for k, rx in MARKERS.items() if rx.match(items[0][1])), None)
        entries, last, whole = [], 0, style is not None
        for p, text in items:
            m = MARKERS[style].match(text) if style else None
            if m and int(m.group(1)) > last:
                whole = whole and int(m.group(1)) == last + 1
                last = int(m.group(1))
                entries.append({"raw": text[m.end():].strip(), "tags": [p]})
            elif style and entries:  # a wrapped line of the reference above
                entries[-1]["raw"] += " " + text
                entries[-1]["tags"].append(p)
            else:
                entries.append({"raw": text, "tags": [p]})
        outside = any(s.strip() for s, _ in _strings(box, skip=lambda s: s.find_parent("h5") is h5 or s.find_parent("p")))
        whole = whole and not outside and not MORE.search(box.get_text(" "))
        refs = []
        for i, e in enumerate(entries, 1):
            hrefs = " ".join(a.get("href", "") for t in e["tags"] for a in t.find_all("a"))
            m = DOI.search(e["raw"]) or DOI.search(hrefs)
            refs.append({"position": i, "raw": e["raw"], "doi": _doi(m.group(1)) if m else None})
        return refs, whole

    def parse(self):
        references, complete = self._references()
        return {"authors": self._authors(), "abstract": self._abstract(),
                "acknowledgments": None, "funding_statement": None,
                "references": references, "references_complete": bool(references) and complete}
