"""Tech Science Press, www.techscience.com (oxjob #2210, Parseland swarm pilot).

One header block (div.bq2: h1, then the byline <p>) in two layouts:
  - issue pages: p.authors, p.affiliation ("1 Dept ...<br/>2 ..."), p.Corresponding ("* Corresponding Author: ...");
  - online-first pages (/online/detail/): one <p> holding the byline, a <br/>, the numbered affiliation lines and the
    "* Corresponding Author(s): ..." / "* Correspondence: ..." note, with no citation meta tags at all.
The abstract is the text under the "Abstract" heading of div.bq4, up to its first <hr/>. The meta description is a
truncated SEO blurb ("... | Find, read and cite all the research you need on Tech Science Press"), so it is never used.
These are abstract pages: acknowledgments, funding and the reference list live on the full-text page (/html), so the
three new fields are always absent here (citation_reference meta tags carry no numbering or stated count).
"""
import re

from bs4 import NavigableString, Tag

from parseland_lib.publisher.parsers.parser import PublisherParser

_NOTE = re.compile(r"^\s*\*\s*Correspond\w*(?:\s+Authors?)?\s*[:：]?\s*(.*)$", re.I | re.S)
_NUMBERED = re.compile(r"^\s*(\d{1,2})\s*([^\d\s].*)$", re.S)  # "3Division of ..." happens too


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _lines(tag):
    """The text of a tag split at its <br/> tags (nested block <p>s, e.g. cite-info, end it)."""
    lines, cur = [], []
    for node in tag.children:
        if isinstance(node, Tag) and node.name == "br":
            lines.append(_clean("".join(cur)))
            cur = []
        elif isinstance(node, Tag) and node.name in ("p", "div"):
            break
        elif isinstance(node, Tag) and node.name == "img":
            continue
        else:
            cur.append(node.get_text() if isinstance(node, Tag) else str(node))
    lines.append(_clean("".join(cur)))
    return lines


class TechSciencePress(PublisherParser):
    parser_name = "techscience"

    def is_publisher_specific_parser(self):
        if self.domain_in_meta_og_url("techscience.com"):
            return True
        # online-first pages carry no og/citation meta; the site's own stylesheet is the marker
        for link in self.soup.find_all("link", rel="stylesheet", href=True):
            if re.match(r"^https?://www\.techscience\.com/static/", link["href"]):
                return True
        return False

    def _byline(self):
        h1 = self.soup.select_one("div.bq2 > h1")
        if not h1:
            return None
        p = h1.find_next_sibling("p")
        if not p or not p.find("sup"):
            return None
        return p

    def authors_found(self):
        return self.is_publisher_specific_parser() and self._byline() is not None

    @staticmethod
    def _parse_byline(p):
        authors = []  # [name, markers]
        for node in p.children:
            if isinstance(node, Tag) and node.name == "br":
                break
            if isinstance(node, Tag) and node.name == "sup":
                if authors:
                    authors[-1][1].extend(m.strip() for m in node.get_text().split(",") if m.strip())
                continue
            text = node.get_text() if isinstance(node, Tag) else str(node)
            parts = re.split(r",|\band\b", text)
            for i, part in enumerate(parts):
                name = _clean(part)
                if not name:
                    continue
                if i == 0 and authors and not authors[-1][1] and not re.match(r"^\s*(,|and\b)", text):
                    authors[-1][0] = _clean(authors[-1][0] + " " + name)  # a name split by inline markup
                else:
                    authors.append([name, []])
        return authors

    def _affiliation_and_note_lines(self, p):
        aff_p = p.find_next_sibling("p", class_="affiliation")
        if aff_p is not None:
            lines = _lines(aff_p)
            note_p = p.find_next_sibling("p", class_="Corresponding")
            notes = [_clean(note_p.get_text())] if note_p is not None else []
            return [l for l in lines if l], notes
        lines = _lines(p)[1:]  # the byline itself is the first line
        affs, notes = [], []
        for line in lines:
            if not line:
                continue
            if line.startswith("*"):
                notes.append(line)
            elif line.startswith("(") or line.startswith("#"):
                continue
            elif not notes:
                affs.append(line)
        return affs, notes

    def parse_authors(self):
        p = self._byline()
        if p is None:
            return []
        byline = self._parse_byline(p)
        aff_lines, notes = self._affiliation_and_note_lines(p)
        numbered, unnumbered = {}, []
        for line in aff_lines:
            if line.startswith("#") or line.startswith("("):
                continue
            m = _NUMBERED.match(line)
            if m:
                numbered[m.group(1)] = _clean(m.group(2))
            else:
                unnumbered.append(line)
        note_text = " ".join(m.group(1) for n in notes if (m := _NOTE.match(n)))
        has_note = any(_NOTE.match(n) for n in notes)
        starred = has_note and any("*" in marks for _, marks in byline)
        authors = []
        for name, marks in byline:
            if numbered:
                affs = [numbered[m] for m in marks if m in numbered]
            else:
                affs = list(unnumbered)
            if starred:
                corr = "*" in marks
            elif has_note:
                corr = bool(re.search(r"(^|[\s:;,])" + re.escape(name) + r"\s*[.,;]", note_text))
            else:
                corr = False
            authors.append({"name": name, "affiliations": affs, "is_corresponding": corr})
        return authors

    def parse_abstract(self):
        block = self.soup.select_one("div.bq4")
        if block is None:
            return None
        heading = None
        for h in block.find_all(["h2", "h3"]):
            if _clean(h.get_text()).lower() == "abstract":
                heading = h
                break
        if heading is None:
            return None
        parts = []
        for node in heading.next_siblings:
            if isinstance(node, Tag) and (node.name == "hr" or node.name in ("h2", "h3")):
                break
            parts.append(node.get_text() if isinstance(node, Tag) else str(node))
        text = _clean("".join(parts))
        return text or None

    def parse(self):
        return {
            "authors": self.parse_authors(),
            "abstract": self.parse_abstract(),
            "acknowledgments": None,
            "funding_statement": None,
            "references": None,
            "references_complete": False,
        }
