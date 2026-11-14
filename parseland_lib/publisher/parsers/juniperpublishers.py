"""Juniper Publishers (juniperpublishers.com, DOI prefix 10.19080) article pages (oxjob #2210).

The site runs its own PHP template on ~60 journals. The article header is ``h3.authors`` (names with numbered
``<sup>`` affiliation marks and a ``*``), ``<p><i>`` affiliation lines, and a "*Corresponding author:" (or
"*Corresponding Address:") note; the body is ``h2.heading`` sections, the first of which is the abstract when the
article has one, and the references are one ``<ol>``. Its citation_author meta tags are in a different order from the
byline and hang institutions on the wrong authors, and its description meta tag is the introduction's first sentence,
so the generic parser got affiliations wrong and no abstract.
"""
import re

from bs4 import Comment, NavigableString, Tag

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import same_person

_SEPARATOR = re.compile(r"\s*(?:,|;|&|\band\b)\s*")
_TITLE = re.compile(r"^(?:dr|prof)\.?\s+", re.I)
_HEADER_END = re.compile(r"submission|submitted|published|correspond|how to cite", re.I)
_NOTE = re.compile(r"\*\s*correspond", re.I)
_NOTE_NAME = re.compile(r"correspond\w*\s+(?:author|address)\s*:?\s*(.+)", re.I | re.S)
_ABSTRACT_HEADINGS = {"abstract", "summary"}
_ABSTRACT_END = re.compile(r"^\s*(?:key\s*words?|abbreviations?)\b", re.I)
_ACK_HEADING = re.compile(r"^acknowledge?ments?\b", re.I)
_FUNDING_HEADING = re.compile(r"^(?:funding|financial support|source of funding|funding (?:information|sources?))$", re.I)
_DOI_LINK = re.compile(r"(?:dx\.)?doi\.org/(10\.\d{4,9}/[^\s?#]+)", re.I)
_DOI_TEXT = re.compile(r"\bdoi:?\s*(10\.\d{4,9}/\S+)", re.I)
_MORE = re.compile(r"show (?:more|all)|load (?:more|all)|view (?:more|all)", re.I)


def _clean(text):
    return re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()


def _heading_text(heading):
    return _clean(heading.get_text(" ")).strip(" :.")


class JuniperPublishers(PublisherParser):
    parser_name = "juniper_publishers"

    def is_publisher_specific_parser(self):
        # citation_publisher on current pages; pages from 2017-18 carry no citation meta tags but the site's icon
        return bool(self.substr_in_citation_publisher("Juniper Publishers")
                    or self.soup.select_one('link[href*="Juniper-icon"]'))

    def authors_found(self):
        return bool(self.is_publisher_specific_parser() and self.soup.select_one("h3.authors"))

    # ---- byline

    @staticmethod
    def _byline_tokens(h3):
        """('sup', text) for each superscript and ('text', text) for the rest, in page order."""
        for node in h3.descendants:
            if isinstance(node, Tag) and node.name == "sup":
                yield "sup", node.get_text()
            elif isinstance(node, NavigableString) and not isinstance(node, Comment) and node.find_parent("sup") is None:
                yield "text", str(node)

    def _byline(self, h3):
        """[{'name', 'keys', 'star'}]. A superscript closes its author's name: Juniper sometimes leaves out the comma
        ("Stanley HO<sup>1</sup>* Okhuahesogie E<sup>1</sup>"), and a star just after the mark is that author's."""
        authors, cur, closed = [], None, False
        for kind, value in self._byline_tokens(h3):
            if kind == "sup":
                if cur is not None:
                    cur["keys"] += re.findall(r"\d+", value)
                    cur["star"] = cur["star"] or "*" in value
                    closed = True
                continue
            value = value.replace("\xa0", " ")
            if closed and cur is not None and value.lstrip().startswith("*"):
                cur["star"] = True
                value = value.lstrip().lstrip("*")
            for i, piece in enumerate(_SEPARATOR.split(value)):
                if i > 0:
                    closed = True
                star = "*" in piece
                name = _clean(piece.replace("*", ""))
                if name:
                    if cur is None or closed:
                        cur = {"name": name, "keys": [], "star": False}
                        authors.append(cur)
                        closed = False
                    else:
                        cur["name"] = f"{cur['name']} {name}"
                if star and cur is not None:
                    cur["star"] = True
        for a in authors:
            a["name"] = _TITLE.sub("", a["name"]).strip(" .,")
        return [a for a in authors if a["name"]]

    @staticmethod
    def _affiliations(h3):
        """({key: [affiliation]}, [unnumbered affiliation]) from the italic lines under the byline."""
        keyed, common = {}, []
        for p in h3.find_next_siblings():
            if p.name != "p" or _HEADER_END.search(p.get_text()):
                break
            if p.find("i") is None:
                continue
            keys = [k for sup in p.find_all("sup") for k in re.findall(r"\d+", sup.get_text())]
            text = _clean("".join(s for s in p.find_all(string=True) if s.find_parent("sup") is None))
            if keys:  # "<sup>1</sup>1Department of ..." repeats the mark
                text = re.sub(rf"^{re.escape(keys[0])}(?=[A-Z])", "", text).strip()
            if not text:
                continue
            if keys:
                for k in keys:
                    keyed.setdefault(k, []).append(text)
            else:
                common.append(text)
        return keyed, common

    def _corresponding_note(self, h3):
        for tag in h3.find_all_next(["p", "strong"], limit=30):
            if _NOTE.search(tag.get_text()):
                return tag.find_parent("p") or tag
        return None

    def parse_authors(self):
        h3 = self.soup.select_one("h3.authors")
        byline = self._byline(h3)
        keyed, common = self._affiliations(h3)
        note = self._corresponding_note(h3)
        authors = []
        for a in byline:
            affs = [x for k in a["keys"] for x in keyed.get(k, [])] or list(common)
            authors.append({"name": a["name"], "affiliations": list(dict.fromkeys(affs)),
                            "is_corresponding": bool(note is not None and a["star"])})
        if note is not None and not any(a["star"] for a in byline):
            # no star in the byline: the note names the corresponding author ("*Corresponding author: Bo Kim, ...")
            if m := _NOTE_NAME.search(_clean(note.get_text())):
                named = m.group(1).split(",")[0]
                hits = [a for a in authors if same_person(a["name"], named)]
                if len(hits) == 1:
                    hits[0]["is_corresponding"] = True
        return authors

    # ---- sections

    def _headings(self):
        return self.soup.select("h2.heading")

    @staticmethod
    def _section_paragraphs(heading, stop=None):
        paras = []
        for sib in heading.next_siblings:
            if not isinstance(sib, Tag):
                continue
            if sib.name == "h2" or "dropdown" in (sib.get("class") or []) or sib.find("h2") is not None:
                break
            text = _clean(sib.get_text())
            if stop is not None and stop.match(text):
                break
            if text:
                paras.append(text)
        return paras

    def parse_abstract(self):
        headings = self._headings()
        if not headings or _heading_text(headings[0]).lower() not in _ABSTRACT_HEADINGS:
            return None
        return "\n".join(self._section_paragraphs(headings[0], _ABSTRACT_END)) or None

    def _section_text(self, pattern):
        for heading in self._headings():
            if pattern.search(_heading_text(heading)):
                return "\n".join(self._section_paragraphs(heading)) or None
        return None

    @staticmethod
    def _doi(li):
        for a in li.find_all("a", href=True):
            if m := _DOI_LINK.search(a["href"]):
                return m.group(1).rstrip(".,;")
        if m := _DOI_TEXT.search(li.get_text()):
            return m.group(1).rstrip(".,;")
        return None

    def parse_references(self):
        """(references, complete). Whole only when the list's numbers run 1..n across its <ol>s (a list split in two
        continues with start="23"), no list is nested in another, and no text sits outside the items."""
        heading = next((h for h in self._headings() if re.match(r"^references?\b", _heading_text(h), re.I)), None)
        if heading is None:
            return None, False
        refs, complete, expected = [], True, 1
        for sib in heading.next_siblings:
            if not isinstance(sib, Tag):
                continue
            if sib.name == "h2" or "dropdown" in (sib.get("class") or []) or sib.find("h2") is not None:
                break
            if sib.name != "ol":
                if _clean(sib.get_text()):
                    complete = False  # reference text outside the list
                continue
            start = int(sib["start"]) if (sib.get("start") or "").isdecimal() else 1
            if start != expected or sib.find("ol") is not None or _MORE.search(sib.get_text()):
                complete = False
            for li in sib.find_all("li", recursive=False):
                raw = _clean(li.get_text())
                if not raw:
                    continue
                refs.append({"position": len(refs) + 1, "raw": raw, "doi": self._doi(li)})
            expected = start + len(sib.find_all("li", recursive=False))
        if not refs:
            return None, False
        return refs, complete

    def parse(self):
        references, complete = self.parse_references()
        return {"authors": self.parse_authors(),
                "abstract": self.parse_abstract(),
                "acknowledgments": self._section_text(_ACK_HEADING),
                "funding_statement": self._section_text(_FUNDING_HEADING),
                "references": references,
                "references_complete": complete}
