"""science-gate.com: IASE's International Journal of Advanced and Applied Sciences (oxjob #2210).

One hand-made template on every page since 2022 (a table layout, no platform): an "Author(s):" heading over a
comma-separated byline whose <sup> numbers point into the "Affiliation(s):" list and whose "*" the page explains as
"* Corresponding Author."; then Abstract, Acknowledgment, an optional Funding section and "References (N)" over one
<ol>. Pages from 2024 on also carry citation_author meta tags, but those attach the institution only to the first
author; 2023 pages carry none. So everything is read from the visible page.
"""
import re

from bs4 import Comment, NavigableString, Tag

from parseland_lib.publisher.parsers.parser import PublisherParser

DOMAIN = "science-gate.com"
NO_ACK = re.compile(r"no acknowledge?ments?\.?", re.I)
MORE = re.compile(r"show more|load all|view all|more references", re.I)
DOI = re.compile(r"doi\.org/(10\.\d{4,9}/\S+)", re.I)


def _clean(text):
    return re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()


def _flatten(tag):
    """Text of tag with each <sup> as {..} and each <br> as a newline."""
    out = []
    for child in tag.children:
        if isinstance(child, Comment):
            continue
        if isinstance(child, NavigableString):
            out.append(str(child))
        elif isinstance(child, Tag):
            if child.name == "sup":
                out.append("{" + child.get_text() + "}")
            elif child.name == "br":
                out.append("\n")
            else:
                out.append(_flatten(child))
    return "".join(out)


class ScienceGate(PublisherParser):
    parser_name = "science_gate"

    def is_publisher_specific_parser(self):
        for name in ("citation_abstract_html_url", "citation_pdf_url"):
            tag = self.soup.find("meta", attrs={"name": name})
            if tag and DOMAIN in (tag.get("content") or ""):
                return True
        return bool(self.domain_in_canonical_link(DOMAIN))

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._byline())

    def _heading(self, pattern):
        rx = re.compile(pattern, re.I)
        for tag in self.soup.find_all(["h2", "h3", "h4", "p"]):
            if rx.fullmatch(_clean(tag.get_text()).rstrip(":").strip()):
                return tag
        return None

    def _after(self, pattern):
        """The element right after a heading."""
        head = self._heading(pattern)
        nxt = head.find_next_sibling() if head else None
        return nxt if nxt is not None and nxt.name == "p" else None

    def _section(self, pattern):
        """Body paragraphs under a heading: the indented <p>s that follow it."""
        head = self._heading(pattern)
        if not head:
            return None
        paras = []
        for sib in head.find_next_siblings():
            if sib.name != "p" or "margin-left" not in (sib.get("style") or ""):
                break
            if txt := _clean(sib.get_text()):
                paras.append(txt)
        return "\n".join(paras) or None

    def _byline(self):
        p = self._after(r"Author\(s\)")
        if not p:
            return []
        authors = []
        for piece in re.split(r",(?![^{]*\})", _flatten(p)):
            marks = "".join(re.findall(r"\{([^}]*)\}", piece))
            name = _clean(re.sub(r"\{[^}]*\}|\*", " ", piece))
            name = re.sub(r"^and\s+", "", name).strip(" ,")
            if name:
                authors.append({"name": name, "nums": re.findall(r"\d+", marks), "star": "*" in piece})
        return authors

    def _affiliations(self):
        """({number: affiliation}, [unnumbered affiliations])."""
        p = self._after(r"Affiliation\(s\)")
        if not p:
            return {}, []
        text = _flatten(p)
        numbered = {}
        for num, aff in re.findall(r"\{\s*(\d+)\s*\}([^{]*)", text):
            if aff := _clean(aff).strip(" ,;"):
                numbered[num] = aff
        if numbered:
            return numbered, []
        lines = [_clean(re.sub(r"\{[^}]*\}", " ", line)).strip(" ,;") for line in text.split("\n")]
        return {}, [line for line in lines if line]

    def _references(self):
        head = self._heading(r"References\s*\(\s*\d+\s*\)") or self._heading(r"References")
        if not head:
            return None, False
        ol = head.find_next_sibling()
        if ol is None or ol.name != "ol":
            # shortcut: one page in 54 prints its list as bare <p>s; left alone (#2210 RESULT.json)
            return None, False
        refs = []
        for li in ol.find_all("li", recursive=False):
            doi = None
            for a in li.find_all("a", href=True):
                if m := DOI.search(a["href"]):
                    doi = doi or m.group(1).rstrip(".")
            # the "[Google Scholar]" search link is the site's, not the reference's (brackets sit outside it on 2025+ pages)
            parts = [str(s) for s in li.find_all(string=True)
                     if not isinstance(s, Comment) and not ((a := s.find_parent("a")) and
                                                            "scholar.google" in (a.get("href") or ""))]
            if raw := _clean(re.sub(r"\[\s*\]", " ", "".join(parts))):
                refs.append({"position": len(refs) + 1, "raw": raw, "doi": doi})
        stated = re.search(r"\((\d+)\)", _clean(head.get_text()))
        start = (ol.get("start") or "1").strip()
        complete = bool(
            refs and stated and int(stated.group(1)) == len(refs)
            and start in ("", "1") and not MORE.search(ol.get_text())
        )
        return refs or None, complete

    def parse(self):
        byline = self._byline()
        numbered, unnumbered = self._affiliations()
        explained = bool(re.search(r"\*\s*Corresponding Author", _clean(self.soup.get_text())))
        authors = []
        for a in byline:
            if numbered:
                affs = [numbered[n] for n in a["nums"] if n in numbered]
            else:
                affs = list(unnumbered)
            authors.append({"name": a["name"], "affiliations": affs, "is_corresponding": explained and a["star"]})

        abstract = self._section(r"Abstract")
        if not abstract and (tag := self.soup.select_one("p.article_abstract")):
            abstract = _clean(tag.get_text()) or None

        ack = self._section(r"Acknowledge?ments?")
        if ack and NO_ACK.fullmatch(ack):
            ack = None

        refs, complete = self._references()
        return {
            "authors": authors,
            "abstract": abstract,
            "acknowledgments": ack,
            "funding_statement": self._section(r"Funding|Funding (statement|information)|Financial support"),
            "references": refs,
            "references_complete": complete,
        }
