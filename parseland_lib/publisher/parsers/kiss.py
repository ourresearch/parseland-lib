"""KISS (kiss.kstudy.com, Korean Studies Information Service System) article pages (oxjob #2338).

KISS prints the byline as "Korean name ( Romanized name ) , ..." and the abstract once per language version, the
Korean one first, in two page layouts:
- the article page /Detail/Ar?key=...: byline `div.wrap_journal_index div.author`, an abstract accordion ("초록" or
  "Abstract") with one <p> per version. It comes in two renders: one with citation_* tags (the generic parser read the
  Korean names and the Korean citation_abstract) and an older one with none (head og:url is the site root), where
  Parseland read nothing.
- the older /thesis/thesis-view.asp page: byline `section.pub-info div.writers`, a "초록 보기" section with one <pre>
  per version. Its one citation_author tag holds the whole byline, which the generic parser read as one author.
This parser reads both from the printed page. Names are given as the page states them: the per-author
citation_author tags where the page has one for each byline entry (the Detail page's: the Korean form), else the
printed byline entries verbatim ("이재언 ( Lee Jae Earn )", as both labellers wrote them on this site); a romanized
name alone, "( Kassie Belay Addisu )", loses its parentheses. The abstract is the English version when the page shows
one, else the first ("If several language versions are shown, give the English one", label-v1).

KISS prints no affiliations, no corresponding-author mark and, on every sampled page, an empty "References (0)" list.
"""
import re

from bs4 import Comment, NavigableString

from parseland_lib.abstract_language import is_english
from parseland_lib.publisher.parsers.parser import PublisherParser

_BYLINE = "div.wrap_journal_index div.author, section.pub-info div.writers"
_ABSTRACT_HEADINGS = ("초록", "Abstract")
# "( Kassie Belay Addisu )": a byline entry with no Korean form, only the romanized one
_ROMANIZED_ONLY = re.compile(r"^\(\s*(?P<roman>[^()]+?)\s*\)$")
_HANGUL_CJK = re.compile("[\u1100-\u11ff\u3040-\u30ff\u3130-\u318f\u4e00-\u9fff\uac00-\ud7a3]")  # Hangul, kana, CJK


def _clean(text):
    return " ".join((text or "").split())


def _paragraphs(node):
    """The node's text with its line breaks (newlines, <br>) kept as paragraph breaks: KISS prints each paragraph on
    its own line."""
    text = "".join("\n" if getattr(d, "name", None) == "br" else str(d) if isinstance(d, NavigableString)
                   and not isinstance(d, Comment) else "" for d in node.descendants)
    return "\n".join(line for line in map(_clean, text.splitlines()) if line)


def _split_byline(text):
    """Split on commas outside parentheses: "전양소(금원) ( Jeon Yang-so ) , 김선철 ( Kim Sun Chul )"."""
    parts, depth, cur = [], 0, []
    for ch in text:
        depth += ch == "("
        depth = max(0, depth - (ch == ")"))
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def _name(entry):
    return m.group("roman") if (m := _ROMANIZED_ONLY.match(entry)) else entry


class KISS(PublisherParser):
    parser_name = "kiss"
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        # Every parser's claim runs on every DOI page (oxjob #2239's per-page CPU rule): look first in the small
        # <head> for KISS's og:url, and only then for the article page's byline.
        claim = self.__dict__.get("_kiss_claim")
        if claim is None:
            head = self.soup.head
            og_url = head.find("meta", attrs={"property": "og:url"}) if head is not None else None
            claim = bool(og_url and "kiss.kstudy.com" in (og_url.get("content") or "")
                         and self.soup.select_one(_BYLINE))
            self._kiss_claim = claim
        return claim

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._authors())

    def parse(self):
        return {"authors": self._authors(), "abstract": self._abstract(),
                "acknowledgments": None, "funding_statement": None,
                "references": None, "references_complete": False}

    def _authors(self):
        if self.__dict__.get("_kiss_authors") is None:
            byline = self.soup.select_one(_BYLINE)
            names = [_name(e) for e in _split_byline(_clean(byline.get_text(" ")))] if byline else []
            # the Detail page's tags give one name per entry; the thesis-view page's one tag holds the whole byline
            tags = [_clean(t.get("content")) for t in self.soup.find_all("meta", attrs={"name": "citation_author"})]
            if names and len(tags) == len(names) and all(tags):
                names = tags
            self._kiss_authors = [{"name": n, "affiliations": [], "is_corresponding": None} for n in names if n]
        return self._kiss_authors

    def _abstract(self):
        versions = None
        for section in self.soup.select("#journal_info .wrap_info"):  # the Detail page's accordion
            heading = section.select_one(".accordion-title a")
            if heading is not None and _clean(heading.find(string=True, recursive=False)) in _ABSTRACT_HEADINGS:
                versions = [_paragraphs(p) for p in section.select(".wrap_part_body > p")]
                break
        if versions is None:  # the thesis-view.asp page's "초록 보기" section
            heading = next((h for h in self.soup.select("section > h4") if _clean(h.get_text()) == "초록 보기"), None)
            versions = [_paragraphs(pre) for pre in heading.parent.find_all("pre")] if heading else []
        versions = [v for v in versions if v]
        if not versions:
            return None
        english = ([v for v in versions if is_english(v)]
                   or [v for v in versions if not _HANGUL_CJK.search(v)]) if len(versions) > 1 else []
        return (english or versions)[0]
