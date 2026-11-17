"""Hans Publishers (hanspub.org, 汉斯出版社) article pages (oxjob #2289).

The site's only author tags are a semicolon list (citation_authors) and dc.creator, with no affiliations, so the generic
parser read no one. The byline prints each author as a search link ("...searchfield=authors..."), grouped by
affiliation: "A：aff 1；B, C<sup>*</sup>：aff 2", where an author with several affiliations lists them split by "；" too.
The page then prints the Chinese abstract (div_abs_zw) and the English one (div_abs_yw), the full text, whose closing
sections are headed <p class="E-Title1"> ("致谢", "基金项目", "NOTES"), and the reference list as a table numbered
[1]..[n].
"""
import re

from bs4 import NavigableString, Tag

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

# the site's citation_publisher value: "中文学术期刊,汉斯出版社,Hans Publishers"
_PUBLISHER_MARKS = ("Hans Publishers", "汉斯出版社")
_AUTHOR_LINK = re.compile(r"searchfield=authors", re.I)
_AFF_SPLIT = re.compile(r"[；;]")
_CORRESPONDING_NOTE = re.compile(r"^\*\s*通讯作者")  # "* 通讯作者。" (some pages say "* 第一作者", first author)
_ACK_HEADING = re.compile(r"^(?:致\s*谢|acknowledge?ments?)\s*[:：]?$", re.I)
_FUNDING_HEADING = re.compile(r"^(?:基金(?:项目)?|funding)\s*[:：]?$", re.I)
_REF_NUMBER = re.compile(r"^\[(\d+)\]$")
_DOI_LINK = re.compile(r"^https?://(?:dx\.)?doi\.org/(10\.\S+)$", re.I)


def _head(soup):
    """<head>, reached through direct children only (every parser's claim runs on every page: #2239's 0.5 ms rule)."""
    html = soup.find("html", recursive=False)
    return (html or soup).find("head", recursive=False)


class HansPublishers(PublisherParser):
    parser_name = "hans_publishers"
    # the byline names every author with an affiliation; the meta tags give names only
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        # The cheap test first and kept: the citation_publisher tag in the small <head>. Nothing walks the whole page
        # until it passes.
        if getattr(self, "_claimed", None) is None:
            head = _head(self.soup)
            meta = head.find("meta", attrs={"name": "citation_publisher"}) if head is not None else None
            content = (meta.get("content") or "") if meta is not None else ""
            self._claimed = any(mark in content for mark in _PUBLISHER_MARKS)
        return self._claimed

    def authors_found(self):
        return self.is_publisher_specific_parser() and self._first_author_link() is not None

    def _first_author_link(self):
        """The byline's first author search link (found once); the byline is that link and the siblings after it."""
        if not hasattr(self, "_first_link"):
            self._first_link = self.soup.find("a", href=_AUTHOR_LINK)
        return self._first_link

    def parse(self):
        return {"authors": self._authors(), "abstract": self._abstract(), **self._back_matter(), **self._references()}

    def _authors(self):
        first = self._first_author_link()
        if first is None:
            return []
        corresponding_note = any(_CORRESPONDING_NOTE.match(p.get_text(strip=True))
                                 for s in self.soup.find_all(string=re.compile("通讯作者"))
                                 if (p := s.find_parent("p")) is not None)
        authors, group, aff_text = [], [], None

        def close_group():
            affs = [a for part in _AFF_SPLIT.split(aff_text or "") if (a := squash(part).strip("，, "))]
            for author in group:
                author["affiliations"] = list(affs)
            group.clear()

        for node in [first, *first.next_siblings]:
            if isinstance(node, Tag) and node.name == "br":
                break
            if isinstance(node, Tag) and node.name == "a" and _AUTHOR_LINK.search(node.get("href") or ""):
                if aff_text is not None:  # an affiliation was read: this link starts the next group
                    close_group()
                    aff_text = None
                name = squash("".join(s for s in node.find_all(string=True) if s.find_parent("sup") is None))
                star = any(sup.get_text(strip=True) == "*" for sup in node.find_all("sup"))
                if name:
                    author = {"name": name, "affiliations": [], "is_corresponding": bool(star and corresponding_note)}
                    authors.append(author)
                    group.append(author)
                continue
            text = str(node) if isinstance(node, NavigableString) else (
                node.get_text() if isinstance(node, Tag) else "")
            if aff_text is None:
                if (m := re.search(r"[：:]", text)) and group:
                    aff_text = text[m.end():]
            else:
                aff_text += text
        close_group()
        return authors

    def _abstract(self):
        """The English abstract, else the Chinese one, without its label."""
        for div_id in ("ctl00_ContentPlaceHolder1_div_abs_yw", "ctl00_ContentPlaceHolder1_div_abs_zw"):
            if (div := self.soup.find("div", id=div_id)) is not None:
                text = re.sub(r"^(?:abstract|摘要)\s*[:：]\s*", "", squash(div.get_text(" ")), flags=re.I)
                if len(text) > 20:
                    return text
        return None

    def _back_matter(self):
        """The full text's "致谢" and "基金项目" sections: the paragraphs after the heading up to the next heading."""
        out = {"acknowledgments": None, "funding_statement": None}
        for heading in self.soup.find_all("p", class_="E-Title1"):
            title = squash(heading.get_text(" "))
            key = "acknowledgments" if _ACK_HEADING.match(title) else (
                "funding_statement" if _FUNDING_HEADING.match(title) else None)
            if key is None or out[key]:
                continue
            lines = []
            for sib in heading.find_next_siblings():
                if sib.name == "p" and "E-Title1" in (sib.get("class") or []):
                    break
                if line := squash(sib.get_text(" ")):
                    lines.append(line)
            out[key] = "\n".join(lines) or None
        return out

    def _references(self):
        """The reference table: rows "[n]" | text, with the entry's DOI link. Whole when [1]..[n] run with no gap
        (the site prints every entry; there is no "show more")."""
        first = self.soup.find("a", attrs={"name": "ref1"})
        table = first.find_parent("table") if first is not None else None
        if table is None:
            return {"references": None, "references_complete": False}
        refs, numbers = [], []
        for row in table.find_all("tr"):
            cells = row.find_all("td", recursive=False)
            if len(cells) != 2:
                continue
            number = _REF_NUMBER.match(cells[0].get_text(strip=True))
            raw = squash(cells[1].get_text(" "))
            if not raw:
                continue
            doi = next((m.group(1) for a in cells[1].find_all("a", href=True)
                        if (m := _DOI_LINK.match(a["href"].strip()))), None)
            numbers.append(int(number.group(1)) if number else None)
            refs.append({"position": len(refs) + 1, "raw": raw, "doi": doi})
        complete = bool(refs) and numbers == list(range(1, len(refs) + 1))
        return {"references": refs or None, "references_complete": complete}
