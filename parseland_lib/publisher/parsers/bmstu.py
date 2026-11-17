"""Bauman Moscow State Technical University journals (BaumanPress, DOI prefix 10.18698), oxjob #2339.

One CMS (built by AKMedia) serves every BMSTU journal on its own bmstu.ru host: Вестник МГТУ им. Н.Э. Баумана (three
series), Инженерный журнал: наука и инновации, Известия вузов. Машиностроение, Гуманитарный вестник, Политехнический
молодежный журнал, each in Russian and in English (/eng/). The pages carry no citation_* or og: meta tags, so the
generic parser read nothing from them. Every article page has one metadata block: a byline ("Авторы:" / "Authors:"
in bold, then one link per author to /authors/N.html), the issue, the DOI as a dx.doi.org/10.18698 link, the section.
Two layouts hold it:

- "header" (Инженерный журнал): section.block.article > <header> holds the block; the next <section> holds the
  abstract <p>, then "<b>Литература</b>" (or "References") and the entries as "<b>[n]</b> text<br/>".
- "table" (the other journals): table.mini holds the block; its next siblings are the abstract <p> (sometimes under a
  "<p><strong>Abstract</strong></p>" label and followed by "Please cite this article ..."), then an <h1>/<h2>/<b>
  "Литература" / "References" heading and the entries as "<p><b>[n]</b> text</p>" or "<b>[n]</b> text<br/>".

The pages print no affiliations and no corresponding-author mark (label-v1: none). Issue tables of contents use the
same table.mini per listed article but print no DOI in it, so they are not claimed.
"""
import re

from bs4 import Comment, NavigableString, Tag

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

# The CMS titles every page "<article title> | <journal>". Checked first: another site's page costs one <title> read.
_JOURNAL_IN_TITLE = re.compile(r"Баумана|Bauman|BMSTU|Инженерный журнал: наука и инновации|Engineering Journal: Science"
                               r"|Известия высших учебных заведений\. Машиностроение", re.I)
_BYLINE_LABEL = re.compile(r"^\s*(?:Авторы|Authors)\s*:\s*$")
_OWN_DOI = re.compile(r"doi\.org/10\.18698/")
_AUTHOR_LINK = re.compile(r"/authors/\d+\.html")
_REF_HEADING = re.compile(r"^\s*(?:Литература|Список литературы|References)\s*:?\s*$", re.I)
_REF_LABEL = re.compile(r"^\s*\[(\d{1,3})\]\s*$")
_ABSTRACT_LABEL = re.compile(r"^\s*(?:Аннотация|Abstract)\s*[.:]?\s*$", re.I)
# A paragraph after the abstract that is not part of it: the citation line and its label, or the funding note
# ("The research was carried out with the financial support of the Russian Science Foundation ...", "Работа
# выполнена при финансовой поддержке РФФИ ...").
_AFTER_ABSTRACT = re.compile(r"^\s*(?:Please cite|Просьба ссылаться|Для цитирования|Ссылка на статью)", re.I)
_FUNDING_NOTE = re.compile(r"^\s*(?:(?:The|This) (?:research|study|work|paper)|Работа|Исследование|Статья)\b.{0,80}?"
                           r"(?:support|fund|financ|grant|поддерж|финанс|грант)", re.I)
_BLOCK_STOPS = {"div", "script", "section", "nav", "table", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "form"}


_BARE_NBSP = re.compile(r"&nbsp;?")  # the CMS prints "Борзых&nbspС.В." (no ";"), which lxml keeps as text


def _clean(text):
    return squash(_BARE_NBSP.sub(" ", (text or "").replace("\xa0", " ").replace("\xad", "")))


def _is_ref_heading(node):
    return isinstance(node, Tag) and node.name in ("b", "strong", "h1", "h2", "h3", "p") \
        and bool(_REF_HEADING.match(node.get_text(" ", strip=True)))


def _ref_label(node):
    if isinstance(node, Tag) and node.name in ("b", "strong"):
        m = _REF_LABEL.match(node.get_text(strip=True))
        return int(m.group(1)) if m else None
    return None


class Bmstu(PublisherParser):
    parser_name = "bmstu"
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        if getattr(self, "_byline", False) is False:
            self._byline = self._claim()
        return self._byline is not None

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._names())

    def _claim(self):
        """The article's byline label, or None. The <title> test runs first; the byline and its block's
        10.18698 DOI link are looked for only on pages whose title names a BMSTU journal."""
        head = self.soup.head
        title = head.find("title") if head is not None else None
        if title is None or not _JOURNAL_IN_TITLE.search(title.get_text()):
            return None
        labels = self.soup.find_all(["strong", "b"], string=_BYLINE_LABEL)
        if len(labels) != 1:
            return None  # an issue's table of contents prints one byline per article
        block = self._block(labels[0])
        if block is None or block.find("a", href=_OWN_DOI) is None:
            return None
        return labels[0]

    @staticmethod
    def _block(label):
        """The metadata block around the byline: the article's <header> or its table.mini."""
        for parent in label.parents:
            if parent.name == "header" or (parent.name == "table" and "mini" in (parent.get("class") or [])):
                return parent
            if parent.name in ("body", "html"):
                return None
        return None

    # ---- authors

    def _names(self):
        if getattr(self, "_name_list", None) is None:
            line = self._byline.parent
            names = [_clean(a.get_text(" ")) for a in line.find_all("a", href=_AUTHOR_LINK)]
            if not names:  # a byline typed without links
                text = _clean(line.get_text(" ")).split(":", 1)[-1]
                names = [n.strip(" ,;") for n in text.split(",") if n.strip(" ,;")]
            self._name_list = [n for n in names if n]
        return self._name_list

    # ---- the nodes after the metadata block, in order: abstract, then the references

    def _after_block(self):
        block = self._block(self._byline)
        if block.name == "header":
            body = block.find_next_sibling("section")
            return list(body.children) if body is not None else []
        return list(block.next_siblings)

    def _abstract(self, nodes):
        paragraphs = []
        for node in nodes:
            if isinstance(node, Comment) or (isinstance(node, NavigableString) and not node.strip()):
                continue
            if not isinstance(node, Tag) or node.name == "br":
                if paragraphs:
                    break
                continue
            if node.name != "p" or _is_ref_heading(node) or node.find(_ref_label_tag) is not None:
                break
            text = _clean(node.get_text(" "))
            if not text:
                if paragraphs:
                    break
                continue
            if _ABSTRACT_LABEL.match(text):
                continue
            if _AFTER_ABSTRACT.match(text) or (paragraphs and _FUNDING_NOTE.match(text)):
                break
            paragraphs.append(text)
        return "\n".join(paragraphs) or None

    def _references(self, nodes):
        """[(number, raw, doi)] after the references heading, in page order."""
        from parseland_lib.back_matter import _clean_doi, _pick_doi, _printed_doi  # back_matter imports this package

        heading = None
        for node in nodes:
            if not isinstance(node, Tag):
                continue
            if _is_ref_heading(node):
                heading = node
                break
            found = node.find(_is_ref_heading)
            if found is not None:
                heading = found
                break
        if heading is None:
            return []
        entries = []
        for label in heading.find_all_next(_ref_label_tag):
            if self._block(label) is not None:
                break
            parts, links = [], []
            for sib in label.next_siblings:
                if _ref_label(sib) is not None:
                    break
                if isinstance(sib, Comment):
                    continue
                if isinstance(sib, NavigableString):
                    parts.append(str(sib))
                    continue
                if sib.name in _BLOCK_STOPS:
                    break
                if sib.name == "br":
                    parts.append(" ")
                    continue
                parts.append(sib.get_text(" "))
                links += [a.get("href") or "" for a in ([sib] if sib.name == "a" else sib.find_all("a"))]
            raw = _clean("".join(parts))
            if not raw:
                continue
            link_doi = next((_clean_doi(h) for h in links if "doi.org/10." in h), None)
            entries.append((_ref_label(label), raw, _pick_doi(link_doi, _printed_doi(raw))))
        return entries

    def parse(self):
        if not self.is_publisher_specific_parser():
            return self.no_authors_output()
        nodes = self._after_block()
        out = {"authors": [{"name": n, "affiliations": [], "is_corresponding": False} for n in self._names()],
               "abstract": self._abstract(nodes)}
        entries = self._references(nodes)
        if entries:
            numbers = [n for n, _, _ in entries]
            out["references"] = [{"position": i, "raw": raw, "doi": doi} for i, (_, raw, doi) in enumerate(entries, 1)]
            out["references_complete"] = numbers == list(range(1, len(entries) + 1))
        return out


def _ref_label_tag(tag):
    return _ref_label(tag) is not None
