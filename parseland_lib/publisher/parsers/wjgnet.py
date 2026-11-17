"""Baishideng Publishing Group article pages on wjgnet.com: World Journal of Gastroenterology, its sister World Journal
titles and the Chinese-language 世界华人消化杂志 (oxjob #2338).

The site runs its own template. Its meta tags give the authors only as one comma-joined citation_authors tag (no
citation_author), so before this parser Parseland read no authors on it. The article header is a fixed set of ids:
- div#dpauthors: the byline, a.author-name-link anchors (data-name) or, on older pages, plain comma-separated names;
- div#dpaff: one <div> per affiliation, "<b>Name, Name, </b>Affiliation";
- div#dpfn: labelled notes, "<b>Corresponding author</b>: Name, MD, ..." ("Correspondence to" on older pages, "通讯作者"
  on Chinese ones), "<b>Co-corresponding authors</b>: A and B.", "<b>Supported by</b> <funding sentence>";
- div#dpabstract: the abstract in its first <div>, then the keyword line and the core tip.
Chinese-language pages repeat the header in English (#dpauthorsen, #dpaffen, #dpfnen, #dpabstracten). The byline,
affiliations and corresponding mark are read from the primary (Chinese) header, as the gold labels give them; the
abstract and funding sentence from the English one when it has them (the rubric's "give the English one").
The reference list is one div.article-ref per entry: its number in the first cell, the citation in the second cell's
plain spans, then bracketed link spans ([PubMed] [DOI] ...), the DOI in a[pub-id-type=doi].
"""
import re

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import same_person, squash

_CORRESPONDING = re.compile(r"^(?:corresponding authors?|correspondence to|通讯作者)$", re.I)
_CO_CORRESPONDING = re.compile(r"^co-corresponding authors?$", re.I)
_FUNDING = re.compile(r"^supported by$", re.I)
_FUNDING_ZH = "基金项目"
_HONORIFIC = re.compile(r"^(?:dr|prof|professor)\.?\s+", re.I)
# Chinese pages close #dpaff with the first author's biography ("在读硕士, 主要从事...", "护师, 研究方向为..."): no affiliation
_BIOGRAPHY = re.compile(r"从事|研究方向")
_ACK_TITLE = re.compile(r"^acknowledg(?:e)?ments?$", re.I)
_SECTION_TITLE_ID = re.compile(r"^sec\d+title$")
_NAME_SEP = re.compile(r"\s*(?:,|、|\band\b)\s*")


def _is_baishideng(soup):
    """The page's dc.publisher tag names Baishideng: the cheap claim. Every parser's claim runs on every DOI page
    (#2239: under 0.5 ms a page it does not claim), so <head> is reached through direct children only and only its
    direct children are searched."""
    html = soup.find("html", recursive=False)
    head = (html or soup).find("head", recursive=False)
    if head is None:
        return False
    tag = head.find("meta", attrs={"name": "dc.publisher"}, recursive=False)
    return tag is not None and "baishideng" in (tag.get("content") or "").lower()


def _text(node):
    """Inline text with no separator between tags (the abstract's <Hypen/> soft hyphens sit inside words), squashed."""
    return squash(node.get_text("").replace("\xa0", " "))


def _names(text):
    return [n for n in (squash(x).strip(" .") for x in _NAME_SEP.split(text or "")) if n]


def _labelled(block):
    """(label, text after the label) for each <div><b>Label</b>: text</div> note directly under `block`."""
    notes = []
    for div in block.find_all("div", recursive=False) if block is not None else []:
        b = div.find("b")
        if b is None:
            continue
        label = squash(b.get_text(" ")).rstrip(":：").strip()
        rest = "".join(s if isinstance(s, str) else s.get_text("") for s in b.next_siblings)
        notes.append((label, re.sub(r"^[:：]\s*", "", squash(rest.replace("\xa0", " ")))))
    return notes


class Wjgnet(PublisherParser):
    parser_name = "wjgnet"
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        return _is_baishideng(self.soup)

    def authors_found(self):
        return _is_baishideng(self.soup) and bool(self._byline())

    def parse(self):
        authors = [{"name": n, "affiliations": [], "is_corresponding": False} for n in self._byline()]
        self._add_affiliations(authors)
        self._mark_corresponding(authors)
        references = self._references()
        return {"authors": authors,
                "abstract": self._abstract(),
                "acknowledgments": self._acknowledgments(),
                "funding_statement": self._funding(),
                "references": references or None,
                "references_complete": bool(references) and
                [r["position"] for r in references] == list(range(1, len(references) + 1))}

    def _byline(self):
        tag = self.soup.find(id="dpauthors")
        if tag is None:
            return []
        links = tag.select("a.author-name-link")
        if links:
            return [n for n in (squash(a.get("data-name") or a.get_text(" ")) for a in links) if n]
        return _names(tag.get_text(" "))

    @staticmethod
    def _match(authors, name):
        hits = [a for a in authors if same_person(a["name"], name)]
        return hits[0] if len(hits) == 1 else None

    def _add_affiliations(self, authors):
        block = self.soup.find(id="dpaff")
        for div in block.find_all("div", recursive=False) if block is not None else []:
            b = div.find("b")
            if b is None:
                continue
            text = squash("".join(s if isinstance(s, str) else s.get_text("") for s in b.next_siblings)
                          .replace("\xa0", " "))
            if not text or _BIOGRAPHY.search(text):
                continue
            for name in _names(b.get_text(" ")):
                if (author := self._match(authors, name)) and text not in author["affiliations"]:
                    author["affiliations"].append(text)

    def _mark_corresponding(self, authors):
        names = []
        for label, text in _labelled(self.soup.find(id="dpfn")):
            if _CO_CORRESPONDING.match(label):
                names += _names(text)
            elif _CORRESPONDING.match(label):
                # the note opens with the name, then degrees, titles and the address: "Velik Lazarov, MD, ..."
                names += _names(_HONORIFIC.sub("", re.split(r"[,，]", text, 1)[0]))
        for name in names:
            if author := self._match(authors, name):
                author["is_corresponding"] = True

    def _abstract(self):
        for block_id in ("dpabstracten", "dpabstract"):
            block = self.soup.find(id=block_id)
            first = block.find("div", recursive=False) if block is not None else None
            if first is None:
                continue
            paragraphs = [_text(p) for p in first.find_all("p")] or [_text(first)]
            if text := "\n".join(p for p in paragraphs if p):
                return text
        return None

    def _funding(self):
        notes = [(label, text) for label, text in
                 _labelled(self.soup.find(id="dpfnen")) + _labelled(self.soup.find(id="dpfn")) if text]
        return (next((text for label, text in notes if _FUNDING.match(label)), None)
                or next((text for label, text in notes if label == _FUNDING_ZH), None))

    def _acknowledgments(self):
        paragraphs = []
        for title in self.soup.find_all("div", id=_SECTION_TITLE_ID):
            if _ACK_TITLE.match(_text(title)):
                paragraphs += [_text(p) for p in title.parent.find_all("p", recursive=False)]
        return "\n".join(p for p in paragraphs if p) or None

    def _references(self):
        references = []
        for entry in self.soup.find_all("div", class_="article-ref"):
            cells = entry.find_all("td")
            if len(cells) < 2:
                continue
            number = re.match(r"\s*(\d+)", cells[0].get_text())
            parts = [t for t in (_text(s) for s in cells[1].find_all("span", recursive=False)) if t and t[0] != "["]
            if not number or not parts:
                continue
            doi = cells[1].find("a", attrs={"pub-id-type": "doi"})
            doi = squash(doi.get("pub-id")) if doi is not None else ""
            references.append({"position": int(number.group(1)), "raw": " ".join(parts),
                               "doi": doi if doi.startswith("10.") else None})
        return references
