"""opticsjournal.net (Chinese Laser Press, 中国光学期刊网) article pages (oxjob #2210).

The abstract page shows the byline (names with superscript affiliation numbers), the numbered affiliation list, a
Chinese and an English abstract, the full text and the numbered reference list. Each numbered Chinese affiliation may be
followed by an unnumbered English translation (class "uniten"); the gold keeps the numbered Chinese line only, as it
does on other bilingual Chinese journal pages. A bare "*" in the byline has no legend on the page, so it is not read as
a corresponding-author mark (label-v1).
"""
import copy
import re

from parseland_lib.publisher.parsers.parser import PublisherParser

DOMAIN = "opticsjournal.net"
CJK = re.compile(r"[一-鿿]")
DOI = re.compile(r"10\.\d{4,9}/\S+")


def _text(tag):
    return re.sub(r"\s+", " ", tag.get_text()).strip()


class OpticsJournal(PublisherParser):
    parser_name = "opticsjournal"

    def is_publisher_specific_parser(self):
        return bool(self.domain_in_meta_og_url(DOMAIN) or self.domain_in_canonical_link(DOMAIN))

    def _article(self):
        return self.soup.select_one("div.ArticleContent div.article")

    def authors_found(self):
        art = self._article()
        return bool(art and art.select_one("div.authors a.au-link") and self.is_publisher_specific_parser())

    def _affiliations(self, art):
        """{number: text} for numbered lines, and the unnumbered lines (English translations dropped)."""
        numbered, plain = {}, []
        for item in art.select("div.authors-dpt div.items div.item"):
            sup = item.find("sup")
            if sup:
                mark = sup.get_text(strip=True)
                text = _text(item)
                text = text[len(mark):].strip() if text.startswith(mark) else text
                if text:
                    numbered[re.sub(r"[^0-9A-Za-z]", "", mark)] = text
            elif "uniten" not in (item.get("class") or []):
                if text := _text(item):
                    plain.append(text)
        if any(CJK.search(t) for t in plain):
            plain = [t for t in plain if CJK.search(t)]
        return numbered, plain

    def _authors(self, art):
        numbered, plain = self._affiliations(art)
        authors = []
        for span in art.select("div.authors > span"):
            link = span.select_one("a.au-link")
            if not link or not (name := _text(link)):
                continue
            sup = span.find("sup")
            # "1,2,*" or "2,3,*†": affiliation numbers, then marks without a legend ("*", "**", "†")
            keys = [re.sub(r"[^0-9A-Za-z]", "", k) for k in re.split(r"[,，]", sup.get_text())] if sup else []
            affs = [numbered[k] for k in keys if k in numbered]
            if not numbered:
                affs = list(plain)
            authors.append({"name": name, "affiliations": affs, "is_corresponding": None})
        return authors

    def _abstract(self, art):
        blocks = {}
        for block in art.select("div.abstract-cn"):
            title, con = block.select_one("div.abstract-cn-tit"), block.select_one("div.abstract-cn-con")
            if title and con:
                blocks.setdefault(_text(title).lower(), con)
        con = blocks.get("abstract") or blocks.get("摘要")
        if con is None:
            return None
        con = copy.copy(con)  # never edit the page other parsers read
        for junk in con.find_all(["audio", "button", "script", "style"]):
            junk.decompose()
        for link in con.find_all("a", href=re.compile(r"^javascript", re.I)):
            link.decompose()
        for label in con.find_all("title"):  # structured abstract: "Objective", "Methods" ... kept inline
            label.replace_with(f"\n{label.get_text(strip=True)} ")
        text = "\n".join(re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in con.get_text().split("\n"))
        return text.strip() or None

    def parse_references(self):
        """(references, complete): the numbered list; an unnumbered line is the previous entry's translation."""
        container = self.soup.select_one("div.art-reference div.con-text")
        if container is None:
            return None, False
        refs = []
        for p in container.find_all("p", recursive=False):
            num = p.select_one("span.ref-number")
            if num is None:
                if refs and (extra := _text(p)):
                    refs[-1]["raw"] += " " + extra
                continue
            m = re.fullmatch(r"\[(\d+)\]", num.get_text(strip=True))
            raw = copy.copy(p)
            raw.select_one("span.ref-number").decompose()
            doi = None
            for a in p.find_all("a", href=True):
                if "doi.org" in a["href"] and (d := DOI.search(a["href"])):
                    doi = d.group(0).rstrip(".,;")
                    break
            refs.append({"position": len(refs) + 1, "number": int(m.group(1)) if m else None,
                         "raw": _text(raw), "doi": doi})
        if not refs:
            return None, False
        complete = [r["number"] for r in refs] == list(range(1, len(refs) + 1))
        for r in refs:
            del r["number"]
        return refs, complete

    def parse_acknowledgments(self):
        return None  # the abstract page prints no acknowledgments section

    def parse_funding_statement(self):
        return None  # nor a funding statement

    def parse(self):
        art = self._article()
        authors = self._authors(art) if art else []
        if not authors:
            authors = self.parse_author_meta_tags()
        refs, complete = self.parse_references()
        return {"authors": authors,
                "abstract": (self._abstract(art) if art else None) or self.parse_abstract_meta_tags(),
                "acknowledgments": self.parse_acknowledgments(),
                "funding_statement": self.parse_funding_statement(),
                "references": refs,
                "references_complete": complete}
