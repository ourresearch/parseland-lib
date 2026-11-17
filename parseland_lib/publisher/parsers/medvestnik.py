"""Bionika Media journal pages (DOI prefix 10.18565: Фарматека, Урология, Акушерство и гинекология, Терапия,
Клиническая нефрология, Эпидемиология и инфекционные болезни), oxjob #2339.

The publisher's DOIs land on three generations of its own platform, none with citation_* meta tags, so the generic
parser read nothing from them. Every page names the platform in its <head> (bionika-digital.ru: the "ws" meta tag of
the current apps, the head.js loader script of the older journal sites), and each generation prints one byline:

- "lib": the doctors' library lib.medvestnik.ru (the newest DOIs). div.article holds p.base (the affiliations, "1) ...;"
  lines), div.c-typography-lead (the abstract, then "Для цитирования", "Вклад авторов", "Финансирование: ...") and
  div.authors with one span.author per name. The body is a paywalled preview: no reference list.
- "journal": the current journal apps (aig-journal.ru). #main-content's <blockquote> holds div.quote (the names, comma
  separated, in an <h3>) and div.author (the affiliations); the abstract is the bare text after the blockquote, up to
  the "Ключевые слова" heading; "Список литературы" is an <ol> or "N." paragraphs.
- "archive": the older journal sites (urologyjournal.ru, pharmateca.ru, therapy-journal.ru ...), #page-archive-article.
  <blockquote> holds a <p> of names (some carry affiliation numbers: "Р.М. Мамина (1, 2)") and a <small> of
  affiliations; the first div.well is the abstract, the second the keywords; "Литература" follows, and "Об авторах /
  Для корреспонденции" names the corresponding author as "Автор для связи: И.Г. Ракипов" (letter-spaced on some).

Gold (label-v1): affiliations without markers are unlinked, so every author gets the whole list; the "Об авторах / Для
корреспонденции" heading over every author's e-mail is not a corresponding mark, "Автор для связи" is.
"""
import re

from bs4 import Comment, NavigableString, Tag

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

_PLATFORM = "bionika-digital.ru"
_LIB_APP = '"app":"lib"'
_DOI_LINK = re.compile(r"doi\.org/10\.")
# (layout, the byline element)
_BYLINES = (("lib", "div.article div.authors"),
            ("journal", "#main-content blockquote div.quote"),
            ("archive", "#page-archive-article blockquote > p"))
_CONTAINERS = {"lib": "div.article", "journal": "#main-content", "archive": "#page-archive-article"}
_AFFILIATIONS = {"lib": "div.article p.base", "journal": "#main-content blockquote div.author",
                 "archive": "#page-archive-article blockquote > small"}
_AFF_NUMBER = re.compile(r"^\s*(\d{1,2})\s*\)?\s*(?=\S)")
_ONE_LINE_LIST = re.compile(r";\s*(?=\d{1,2}\s*\)?\s)")
_NAME_MARKS = re.compile(r"\s*\(([\d,\s]+)\)\s*$")  # "Р.М. Мамина (1, 2)"
_OUTSIDE_PARENS_COMMA = re.compile(r",\s*(?![^()]*\))")
_ABSTRACT_LABEL = re.compile(r"^\s*Аннотация\s*[.:]\s*")
# Lines of the lead block that are back matter, not the abstract.
_LEAD_BACK_MATTER = re.compile(r"^\s*(?:Для цитирования|Вклад авторов|Конфликт интересов|Финансирование|Ключевые слова"
                               r"|Источник\w* финансирования)\s*[:.]")
_KEYWORDS = re.compile(r"^\s*Ключевые слова\s*:")
_FUNDING = re.compile(r"(?:Финансирование|Источник(?:и)? финансирования)\s*[:.]\s*")
_CONTACT = re.compile(r"А\s*в\s*т\s*о\s*р\s*д\s*л\s*я\s*с\s*в\s*я\s*з\s*и\s*:\s*")
_REF_HEADING = re.compile(r"^\s*(?:Список\s+литературы|Литература)\s*$", re.I)
_REF_NUMBER = re.compile(r"^\s*(\d{1,3})\s*[.)]\s*(?=\S)")
_RECEIVED = re.compile(r"^\s*(?:Поступила|Принята)")
_BREAKS = {"br", "p", "div", "li"}  # a new line in a block's text
_INLINE = {"a", "b", "i", "em", "strong", "sup", "sub", "span", "u", "small"}


def _clean(text):
    return squash((text or "").replace("\xad", "").replace("\xa0", " ").replace(" ", " "))


def _lines(nodes):
    """The text of `nodes` (tags and strings), one line per <br> or newline in the markup."""
    parts = []
    for node in nodes:
        if isinstance(node, Comment):
            continue
        if isinstance(node, NavigableString):
            parts.append(str(node))
        elif node.name == "br":
            parts.append("\n")
        else:
            for sub in node.descendants:
                if isinstance(sub, NavigableString) and not isinstance(sub, Comment):
                    parts.append(str(sub))
                elif sub.name in _BREAKS:
                    parts.append("\n")
    return [line for line in (_clean(x) for x in "".join(parts).split("\n")) if line]


def _numbered(lines):
    """{number: affiliation} when the lines carry numbers that run 1..n, else None."""
    found = [_AFF_NUMBER.match(line) for line in lines]
    if not all(found) or [int(m.group(1)) for m in found] != list(range(1, len(lines) + 1)):
        return None
    return {int(m.group(1)): _strip_aff(line[m.end():]) for m, line in zip(found, lines)}


def _strip_aff(text):
    return text.strip().rstrip(";,").strip()


class Medvestnik(PublisherParser):
    parser_name = "bionika_media"
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        if getattr(self, "_layout", None) is None:
            self._layout = self._claim() or ""
        return bool(self._layout)

    def authors_found(self):
        return self.is_publisher_specific_parser()

    def _platform_head(self):
        """The platform's mark in <head>: checked first, so another site's page costs a <head> scan, no more."""
        head = self.soup.head
        if head is None:
            return None
        ws = head.find("meta", attrs={"name": "ws"})
        if ws is not None and _PLATFORM in (ws.get("content") or ""):
            return ws.get("content")
        for script in head.find_all("script", src=False):
            if _PLATFORM in (script.string or ""):
                return ""
        return None

    def _claim(self):
        ws = self._platform_head()
        if ws is None:
            return None
        for layout, selector in _BYLINES:
            if self.soup.select_one(selector) is None:
                continue
            if layout == "lib" and _LIB_APP not in ws:
                return None  # the platform's news and reference apps share the markup; only the library holds articles
            if layout == "journal" and self.soup.select_one("#main-content").find("a", href=_DOI_LINK) is None:
                return None  # "#main-content" is the apps' generic column: an article there carries its DOI ribbon
            return layout  # "#page-archive-article" names the old sites' article page (one in 28 prints no DOI)
        return None

    # ---- authors and affiliations

    def _names(self):
        byline = self.soup.select_one(dict(_BYLINES)[self._layout])
        if self._layout == "lib":
            return [_clean(s.get_text()) for s in byline.select("span.author")]
        text = _clean(byline.get_text(" "))
        return [n.strip(" ,;") for n in _OUTSIDE_PARENS_COMMA.split(text) if n.strip(" ,;")]

    def _affiliation_lines(self):
        block = self.soup.select_one(_AFFILIATIONS[self._layout])
        lines = []
        for line in _lines([block]) if block is not None else []:
            if lines and lines[-1].endswith(","):
                lines[-1] += " " + line  # one affiliation broken before its city: "..., \nг. Екатеринбург, Россия"
            else:
                lines.append(line)
        if len(lines) == 1 and _AFF_NUMBER.match(lines[0]):
            lines = _ONE_LINE_LIST.split(lines[0])  # "1 ФГБОУ ВО АГМУ ..., Россия; 2 ФГБУ «НМИЦ гематологии» ..."
        return lines

    def _authors(self):
        lines = self._affiliation_lines()
        numbered = _numbered(lines) if len(lines) > 1 else None
        if numbered is None and len(lines) == 1:
            m = re.match(r"^\s*1\s*\)\s*", lines[0])
            numbered = {1: _strip_aff(lines[0][m.end():] if m else lines[0])}
        affs = list(numbered.values()) if numbered else [_strip_aff(line) for line in lines]
        authors = []
        for name in self._names():
            marks = _NAME_MARKS.search(name)
            if marks and numbered:
                wanted = [int(x) for x in re.findall(r"\d+", marks.group(1))]
                own = [numbered[i] for i in wanted if i in numbered]
                name = name[:marks.start()].strip()
            else:
                own = list(affs)  # unlinked: every author gets the whole list
                if marks:
                    name = name[:marks.start()].strip()
            if name:
                authors.append({"name": name, "affiliations": own, "is_corresponding": False})
        return authors

    def _mark_corresponding(self, authors):
        if self._layout != "archive" or not authors:
            return
        found = self.soup.find(string=_CONTACT)
        if found is None:
            return
        rest = _clean(str(found)[_CONTACT.search(str(found)).end():])
        name = re.split(r"\s+[–—-]\s+|[,;]", rest, maxsplit=1)[0]
        words = {w.casefold() for w in re.findall(r"[^\W\d_]{2,}", name)}
        hits = [a for a in authors if words & {w.casefold() for w in re.findall(r"[^\W\d_]{2,}", a["name"])}]
        if len(hits) == 1:
            hits[0]["is_corresponding"] = True

    # ---- abstract

    def _abstract(self):
        if self._layout == "lib":
            lead = self.soup.select_one("div.article div.c-typography-lead")
            first = lead.find("p") if lead is not None else None
            lines = _lines([first]) if first is not None else []
        elif self._layout == "archive":
            wells = self.soup.select("#page-archive-article div.well")
            first = wells[0] if wells else None
            lines = _lines([first]) if first is not None and not _KEYWORDS.match(first.get_text()) else []
        else:
            quote = self.soup.select_one("#main-content blockquote")
            nodes = []
            for node in quote.next_siblings:
                if isinstance(node, Tag) and node.name not in _INLINE and node.name != "br":
                    break
                nodes.append(node)
            lines = _lines(nodes)
            if lines and _AFF_NUMBER.match(lines[0]) and lines[0].lstrip()[1:2] == ")":
                lines = []  # an English affiliation list printed where the abstract goes, not an abstract
        # "Для цитирования", "Вклад авторов", "Финансирование": back matter printed in the abstract's block
        lines = lines[:next((i for i, line in enumerate(lines) if _LEAD_BACK_MATTER.match(line)), len(lines))]
        if not lines:
            return None
        lines[0] = _ABSTRACT_LABEL.sub("", lines[0])
        text = "\n".join(line for line in lines if line)
        return text if len(text) > 100 else None

    # ---- back matter

    def _funding(self):
        container = self.soup.select_one(_CONTAINERS[self._layout])
        found = container.find(string=_FUNDING) if container is not None else None
        if found is None:
            return None
        text = str(found)
        statement = _clean(text[_FUNDING.search(text).end():])
        return statement or None

    def _references(self):
        heading = self.soup.find(["h2", "h3"], string=_REF_HEADING)
        if heading is None:
            return None, False
        items, paragraphs = [], []
        for node in heading.next_elements:
            if isinstance(node, Tag):
                if node.name in ("h1", "h2", "h3"):
                    break
                if node.name == "li":
                    items.append(node)
                elif node.name == "p" and node.find("p") is None:
                    paragraphs.append(node)
        from parseland_lib.back_matter import _clean_doi, _pick_doi, _printed_doi
        refs, complete = [], False
        if items:
            lists = {id(li.parent) for li in items}
            start = items[0].parent.get("start") if items[0].parent is not None else None
            for li in items:
                text = _clean(li.get_text(" "))
                if text:
                    refs.append(text)
            complete = len(lists) == 1 and start in (None, "1", "") and len(refs) == len(items)
            entries = list(zip(items, refs))
        else:
            numbers, entries, stray = [], [], False
            for p in paragraphs:
                text = _clean(p.get_text(" "))
                if not text or _RECEIVED.match(text):
                    continue
                m = _REF_NUMBER.match(text)
                if not m:
                    stray = True
                    continue
                numbers.append(int(m.group(1)))
                entries.append((p, text[m.end():].strip()))
            complete = bool(entries) and not stray and numbers == list(range(1, len(numbers) + 1))
        out = []
        for i, (tag, raw) in enumerate(entries, 1):
            link = tag.find("a", href=_DOI_LINK)
            doi = _pick_doi(_clean_doi(link["href"]) if link else None, _printed_doi(raw))
            out.append({"position": i, "raw": raw, "doi": doi})
        return (out or None), bool(out) and complete

    def parse(self):
        if not self.is_publisher_specific_parser():
            return self.no_authors_output()
        authors = self._authors()
        self._mark_corresponding(authors)
        references, complete = self._references()
        return {"authors": authors, "abstract": self._abstract(), "acknowledgments": None,
                "funding_statement": self._funding(), "references": references, "references_complete": complete}
