"""eLIBRARY.RU item pages (elibrary.ru/item.asp?id=N), oxjob #2268.

Many Russian journals' DOIs (and some 10.1134 / 10.7868 / 10.31857 originals) resolve to the work's record on the
Russian Science Citation Index platform eLIBRARY.RU. The page is old table markup with no citation_* meta tags, so the
generic parser read nothing but its description tag. The record prints, in order:

- the title (p.bigtext) and under it the Russian byline: each author an inline-block div whose name is a dark-blue
  <font> (in a <b>), followed by affiliation numbers in a <sup> ("1", "1,2"); then numbered affiliation lines
  "<sup>1</sup>&nbsp;Organisation, City<br>" (the organisation in a <font>, a tooltip span around it on profiled ones);
- "АННОТАЦИЯ": div#abstract1, cut with "..." when long, the whole text in the hidden div#abstract2;
- "ИНФОРМАЦИЯ О ФИНАНСОВОЙ ПОДДЕРЖКЕ": the funding statement;
- "ОПИСАНИЕ НА АНГЛИЙСКОМ ЯЗЫКЕ" (or "НА ДРУГОМ ЯЗЫКЕ"): a second-language title, byline and abstract
  (div#eabstract1, whole text in div#eabstract2).

Gold (label-v1, #1791 dev gold) keeps the page's primary byline as printed and gives the English abstract when the
page shows one. The corresponding author carries an asterisk the page explains in its tooltip
(<span class='astmd help' title='Автор, отвечающий за переписку'>*</span>, "author responsible for correspondence").
Anonymous visitors see no reference list or acknowledgments.
"""
import re

from bs4 import NavigableString, Tag

from parseland_lib.abstract_language import is_english
from parseland_lib.publisher.parsers.parser import PublisherParser

_HEADER = "ИНФОРМАЦИЯ О ПУБЛИКАЦИИ"  # the item page's header panel ("publication information")
_FUNDING_LABEL = "ИНФОРМАЦИЯ О ФИНАНСОВОЙ ПОДДЕРЖКЕ"
_NAME_COLOR = "#00008f"
_CORRESPONDENCE = "переписк"  # "Автор, отвечающий за переписку": the asterisk's own tooltip


def _clean(text):
    return " ".join((text or "").replace("\xa0", " ").split())


def _is_byline_entry(tag):
    return isinstance(tag, Tag) and tag.name == "div" and "inline-block" in (tag.get("style") or "")


def _number_mark(tag):
    """The affiliation number when `tag` is a <font> holding only a <sup>, else None."""
    if not (isinstance(tag, Tag) and tag.name == "font"):
        return None
    sup = tag.find("sup")
    if sup is None or _clean(tag.get_text()) != _clean(sup.get_text()):
        return None
    return _clean(sup.get_text()) or None


class ELibraryRu(PublisherParser):
    parser_name = "elibrary_ru"
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        logo = self.soup.find("img", id="elibrary_logo")
        if logo is None or "elibrary_logo" not in (logo.get("src") or ""):
            return False
        header = self.soup.select_one("div.header-panel")
        return bool(header and _HEADER in header.get_text() and self.soup.select_one("p.bigtext"))

    def _byline_cell(self):
        title = self.soup.select_one("p.bigtext")
        cell = title.find_next("td", attrs={"width": "514"}) if title else None
        if cell is None or not any(_is_byline_entry(child) for child in cell.children):
            return None
        return cell

    def authors_found(self):
        return self.is_publisher_specific_parser() and self._byline_cell() is not None

    def _authors(self):
        cell = self._byline_cell()
        if cell is None:
            return []
        entries, affiliations, current = [], {}, None
        for child in cell.children:
            if _is_byline_entry(child):
                name_tag = child.find("font", attrs={"color": re.compile(f"^{_NAME_COLOR}$", re.I)})
                name = _clean(name_tag.get_text()).strip(" ,") if name_tag else ""
                numbers = [n.strip() for sup in child.find_all("sup") for n in sup.get_text().split(",") if n.strip()]
                corresponding = any(_CORRESPONDENCE in (mark.get("title") or "").lower()
                                    for mark in child.select("span.astmd"))
                if name:
                    entries.append((name, numbers, corresponding))
                continue
            if (number := _number_mark(child)) is not None:
                current = number
                affiliations[current] = ""
            elif isinstance(child, Tag) and child.name == "br":
                current = None
            elif current is not None:  # the line's text: the organisation's <font> or tooltip span, then any "City" after it
                affiliations[current] += child.get_text() if isinstance(child, Tag) else (
                    str(child) if type(child) is NavigableString else "")  # not a Comment
        affiliations = {k: _clean(v) for k, v in affiliations.items()}
        return [{"name": name,
                 "affiliations": [affiliations[n] for n in numbers if affiliations.get(n)],
                 "is_corresponding": corresponding} for name, numbers, corresponding in entries]

    def _abstract_block(self, prefix):
        """The whole text of the page's abstract1/2 (prefix "") or eabstract1/2 (prefix "e") pair, or None."""
        for suffix in ("2", "1"):  # 2 is the whole text; 1 is cut with "..." when 2 exists
            block = self.soup.find("div", id=f"{prefix}abstract{suffix}")
            if block is not None and (text := _clean(block.get_text(" "))):
                return text
        return None

    def _abstract(self):
        main, other = self._abstract_block(""), self._abstract_block("e")
        for text in (main, other):
            if text and is_english(text):
                return text
        return main or other

    def _funding_statement(self):
        for label in self.soup.find_all("font"):
            if _clean(label.get_text()).rstrip(":") != _FUNDING_LABEL:
                continue
            table = label.find_parent("table")
            rows = [tr for tr in table.find_all("tr") if tr.find_parent("table") is table] if table else []
            if len(rows) >= 2 and (cells := rows[1].find_all("td", recursive=False)):  # label row, then its text
                return _clean(cells[-1].get_text(" ")) or None
        return None

    def parse(self):
        return {
            "authors": self._authors(),
            "abstract": self._abstract(),
            "acknowledgments": None,
            "funding_statement": self._funding_statement(),
            "references": None,
            "references_complete": False,
        }
