"""DBpia and earticle (Korea) article pages (oxjob #2268, template "DBpia / KISS / KCI (Korea)").

Both platforms give citation_author tags with names only, so the generic parser read every author and no
affiliation. Their own bylines carry them:

- DBpia (www.dbpia.co.kr) prints "Name (Affiliation)" in one of three page skins: a `thesisDetail__author` author list
  (name, then a `authorList__agency` span), an `#authorWrap` line (`authorName`, `authorAffiliation`), or an older
  `thesisInfoArea` paragraph of links whose text is "Name (Affiliation)". A hidden author dialog repeats the list.
  The page shows a login-walled preview of the reference list (3-5 of n entries), never the whole list.
- earticle (www.earticle.net) lists "Name [ Romanized name | Affiliation ]" under the heading 저자 (authors), with a
  role tag naming the corresponding author (교신저자).

Neither marks a corresponding author otherwise. Both run their Korean and English abstracts together while
citation_abstract holds the Korean one; this parser leaves the abstract as the generic parser reads it. KISS
(kiss.kstudy.com), the template's third site, prints names only and stays with the generic parser.
"""
import re

from bs4 import Comment

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser

WS = re.compile(r"\s+")
NAME_AFF = re.compile(r"^(?P<name>[^()]+?)\s*\((?P<aff>.*)\)$")  # "Name (Affiliation)", "Name ((주)Company)"
NAME_BRACKET = re.compile(r"^(?P<name>[^\[\]]+?)\s*\[(?P<inner>.*)\]$")  # "Name [ Romanized | Affiliation ]"
DOI = re.compile(r"\b(10\.\d{4,9}/\S+)")

DBPIA_LIST = "section.thesisDetail__author ul.authorList > li.authorList__item"
DBPIA_WRAP = ".thesisDetail__authorList #authorWrap > span.author"
DBPIA_LINKS = "div.thesisInfoArea div.author-wrap > p.author"
DBPIA_DIALOG = "dialog#authorLayer ul.authorList > li.authorList__item"


def _clean(text):
    return WS.sub(" ", text or "").strip()


def _text(node, skip=None):
    """The node's text without HTML comments (DBpia keeps an old copy of the byline in one) or `skip`'s text."""
    return _clean(" ".join(s for s in node.find_all(string=True)
                           if not isinstance(s, Comment) and (skip is None or skip not in s.parents)))


def _unwrap(text):
    text = _clean(text)
    return text[1:-1].strip() if text.startswith("(") and text.endswith(")") else text


def _split_outside_parens(text):
    parts, depth, cur = [], 0, []
    for ch in text:
        depth += ch in "(（"
        depth = max(0, depth - (ch in ")）"))
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def _author(name, aff=None, corresponding=None):
    return {"name": name, "affiliations": [aff] if aff else [], "is_corresponding": corresponding}


def _name_aff(entry):
    entry = _clean(entry)
    if m := NAME_AFF.match(entry):
        return _author(m.group("name").strip(), m.group("aff").strip())
    return _author(entry)


def _parse(soup, authors, references=None):
    # the abstract stays the generic parser's (citation_abstract, the Korean version): no sampled work lacked one
    # the page shows, so changing it is out of #2268's scope
    return {"authors": authors, "abstract": GenericPublisherParser(soup).parse()["abstract"],
            "acknowledgments": None, "funding_statement": None,
            "references": references or None, "references_complete": False}  # DBpia shows a preview at most


class DBpia(PublisherParser):
    parser_name = "dbpia"
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        return bool(self.soup.select_one(f"{DBPIA_LIST}, {DBPIA_WRAP}, {DBPIA_LINKS}"))

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._authors())

    def parse(self):
        return _parse(self.soup, self._authors(), self._references())

    def _authors(self):
        if getattr(self, "_cache", None) is None:
            byline = ([self._list_item(li) for li in self.soup.select(DBPIA_LIST)]
                      or [self._wrap_item(span) for span in self.soup.select(DBPIA_WRAP)]
                      or [a for p in self.soup.select(DBPIA_LINKS)[:1] for a in self._linked_byline(p)])
            dialog = [self._list_item(li) for li in self.soup.select(DBPIA_DIALOG)]
            self._cache = [a for a in (dialog if len(dialog) > len(byline) else byline) if a["name"]]
        return self._cache

    @staticmethod
    def _list_item(li):
        agency = li.select_one(".authorList__agency")
        name_tag = li.select_one(".authorList__author")
        name = _text(name_tag) if name_tag else _text(li, skip=agency)
        return _author(name, _unwrap(_text(agency)) if agency else None)

    @staticmethod
    def _wrap_item(span):
        name, aff = span.select_one(".authorName"), span.select_one(".authorAffiliation")
        if name is None:
            return _name_aff(_text(span))
        return _author(_text(name), _text(aff) if aff else None)

    @staticmethod
    def _linked_byline(p):
        return [_name_aff(entry) for entry in _split_outside_parens(_text(p))]

    def _references(self):
        section = self.soup.select_one("section.thesisDetail__reference")
        refs = []
        for link in section.select(".referList a.referenceLink") if section else []:
            if raw := _text(link):
                doi = m.group(1).rstrip(".,;)]") if (m := DOI.search(raw)) else None
                refs.append({"position": len(refs) + 1, "raw": raw, "doi": doi})
        return refs


class Earticle(PublisherParser):
    parser_name = "earticle"
    prefer_publisher_authors_over_generic = True

    def _author_section(self):
        for section in self.soup.select("div.art-detail div.otherInfo div.detail-info div.section"):
            heading = section.find("h4")
            if heading and _clean(heading.get_text()) == "저자" and section.select_one("ul.authors"):
                return section
        return None

    def is_publisher_specific_parser(self):
        return self._author_section() is not None

    def authors_found(self):
        return bool(self._authors())

    def parse(self):
        return _parse(self.soup, self._authors())

    def _authors(self):
        if getattr(self, "_cache", None) is None:
            section = self._author_section()
            authors, roles = [], []
            for li in section.select("ul.authors > li") if section else []:
                role = li.select_one(".write_type")
                text = _text(li, skip=role)
                if m := NAME_BRACKET.match(text):
                    inner = m.group("inner").split("|", 1)
                    author = _author(_clean(m.group("name")), _clean(inner[1]) if len(inner) > 1 else None)
                else:
                    author = _author(text)
                if author["name"]:
                    authors.append(author)
                    roles.append("교신" in _text(role) if role else False)
            if any(roles):
                for author, corresponding in zip(authors, roles):
                    author["is_corresponding"] = corresponding
            self._cache = authors
        return self._cache
