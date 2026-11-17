"""Media Sphera (mediasphera.ru) article pages (oxjob #2338).

Russian medical journals on a 1C-Bitrix site whose template is "MediaSphera" (/local/templates/MediaSphera/). Most
article pages carry no citation_* meta tags, so no parser read their byline; pages that do carry them give an
institution to some authors only. The page's byline pop-up (div.articlePage-main-block-author__list) lists every
author: the name, then one paragraph of affiliations separated by ";" (often with a <br>), then an ORCID / SPIN / Scopus
list. The reference list is one <ol> in div.bibliography ("Список литературы:", "List of references:", "References:").
The abstract is the one the generic parser read before (the description tag, which the page prints in its abstract
block; citation_abstract on pages that have one), so it stays as it was on every article page.
No page marks a corresponding author except one older page's note ("Автор, ответственный за переписку"), left alone.
About half the stored DOI pages are an empty "Просмотр статьи" shell with no template mark: never claimed.
"""
import re

from bs4 import Comment, NavigableString

from parseland_lib.publisher.parsers.parser import PublisherParser

TEMPLATE_MARK = "/local/templates/MediaSphera/"
WS = re.compile(r"\s+")
DOI_IN_LINK = re.compile(r"doi\.org/(10\.\d{4,9}/\S+)", re.I)
DOI_IN_TEXT = re.compile(r"(?:\bdoi:?\s*|doi\.org/)(10\.\d{4,9}/\S+)", re.I)
MORE_MARKER = re.compile(r"показать (?:все|ещё|еще)|show (?:more|all)|load more", re.I)


def _clean(text):
    return WS.sub(" ", text or "").strip()


def _lines(block):
    """The text of `block`, cut at each <br> and ";" (the site separates affiliations with ";<br>")."""
    lines, current = [], []
    for el in block.descendants:
        if isinstance(el, NavigableString) and not isinstance(el, Comment):
            current.append(str(el))
        elif getattr(el, "name", None) == "br":
            lines.append("".join(current))
            current = []
    lines.append("".join(current))
    return [part for line in lines for part in line.split(";")]


def _doi(li):
    for a in li.find_all("a", href=True):
        if m := DOI_IN_LINK.search(a["href"]):
            return m.group(1).rstrip(".,;")
    if m := DOI_IN_TEXT.search(li.get_text(" ")):
        return m.group(1).rstrip(".,;")
    return None


class MediaSphera(PublisherParser):
    parser_name = "mediasphera"
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        # Cheap claim first (#2239: every parser's authors_found() runs on every page): the template's favicon link,
        # a direct child of <head>, never a walk of the whole tree. Cached: the dispatcher calls authors_found() and
        # then this on the same instance.
        claim = self.__dict__.get("_claim")
        if claim is None:
            head = self.soup.head
            icon = head.find("link", rel="icon", recursive=False) if head is not None else None
            claim = self._claim = icon is not None and TEMPLATE_MARK in (icon.get("href") or "")
        return claim

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._items())

    def _items(self):
        return self.soup.select("div.articlePage-main-block-author__list div.author__list-item")

    def parse(self):
        refs, complete = self._references()
        # the generic parser's abstract readers, in its order (its Atypon section reader never matches these pages)
        abstract = self.parse_abstract_meta_tags(include_seo_tags=False) or self.parse_printed_seo_description()
        return {"authors": self._authors(), "abstract": abstract, "acknowledgments": None, "funding_statement": None,
                "references": refs, "references_complete": complete}

    def _authors(self):
        authors = []
        for item in self._items():
            name_tag = item.select_one(".author__list-item-name")
            name = _clean(name_tag.get_text(" ")) if name_tag else ""
            if not name:
                continue
            affiliations = []
            # the first info block holds the affiliations; the one with a <ul> holds the author's ids (ORCID, SPIN)
            for info in item.find_all("div", class_="author__list-item-info", recursive=False):
                if info.find("ul"):
                    continue
                for part in _lines(info):
                    if (aff := _clean(part)) and aff not in affiliations:
                        affiliations.append(aff)
            authors.append({"name": name, "affiliations": affiliations, "is_corresponding": False})
        return authors

    def _references(self):
        lists = [b for b in self.soup.select("div.bibliography") if b.select_one("ol > li")]
        if not lists:
            return None, False
        block = lists[0]
        ol = block.find("ol")
        refs = []
        for li in ol.find_all("li", recursive=False):
            if raw := _clean("".join(li.strings)):
                refs.append({"position": len(refs) + 1, "raw": raw, "doi": _doi(li)})
        if not refs:
            return None, False
        # whole when the page shows one list, in one <ol> that starts at 1, every item with text, nothing printed in
        # the block outside the list and its title, and no "show more" marker
        outside = "".join(_clean(el.get_text(" ")) for el in block.find_all(recursive=False)
                          if el is not ol and "title" not in (el.get("class") or []))
        complete = (len(lists) == 1 and len(block.find_all("ol")) == 1 and ol.get("start") in (None, "1")
                    and len(refs) == len(ol.find_all("li", recursive=False)) and not outside
                    and not MORE_MARKER.search(block.get_text(" ")))
        return refs, complete
