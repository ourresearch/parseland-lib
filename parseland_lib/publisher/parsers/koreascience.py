import re

from bs4 import NavigableString

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser

# KoreaScience (koreascience.or.kr, KISTI): the DOIs of hundreds of Korean society journals resolve to its one article
# page (oxjob #2289). Its only author tag is a single citation_author with every name joined by ';', so the generic
# parser read one "author" made of all of them and no affiliation. The page prints the byline twice under the title,
# in English and then in Korean, each name linked to its doi.or.kr person record (10.PSN) and followed by
# "(affiliation)"; and its reference list as an <ol> of li#ref-N under a "References" box.
_TITLE_MARK = "| Korea Science"  # every page of the platform: "<article title> -<journal> | Korea Science"
_PERSON = re.compile(r"/10\.PSN/")
_REF_HEADINGS = {"References", "참고문헌"}
_REF_ID = re.compile(r"^ref-(\d+)$")
_DOI = re.compile(r"doi\.org/(10\.\d{4,9}/\S+)$", re.I)
_MORE = re.compile(r"\b(?:show|load|view)\s+(?:more|all)\b|더보기", re.I)


def _squash(text):
    return " ".join(text.split())


def _texts(tag, skip=None):
    """The tag's text pieces (no comments), leaving out those inside `skip`."""
    return [s for s in tag.find_all(string=True)
            if type(s) is NavigableString and not (skip is not None and s.find_parent(skip.name) is skip)]


def _split_affiliation(text):
    """'Name (Aff (X))' -> ('Name', 'Aff (X)'); the last bracketed group closing the text is the affiliation."""
    text = _squash(text).rstrip(";").strip()
    if not text.endswith(")"):
        return text, None
    depth = 0
    for i in range(len(text) - 1, -1, -1):
        depth += {")": 1, "(": -1}.get(text[i], 0)
        if depth == 0:
            return text[:i].strip(), text[i + 1:-1].strip() or None
    return text, None


class KoreaScience(PublisherParser):
    parser_name = "koreascience"
    # the printed byline splits the names the one citation_author tag runs together
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        # Every parser's claim runs on every DOI page (oxjob #2239's per-page CPU rule): the page's first <title>
        # (in its <head>, found at once) before any whole-page search.
        claim = self.__dict__.get("_ks_claim")
        if claim is None:
            title = self.soup.title
            claim = bool(title is not None and _squash(title.get_text()).endswith(_TITLE_MARK)
                         and self.soup.find(id="article-view") is not None)
            self._ks_claim = claim
        return claim

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._authors())

    def parse(self):
        # the abstract stays the generic reader's (the English paragraph in the description tag)
        out = {"authors": self._authors(), "abstract": GenericPublisherParser(self.soup).parse().get("abstract")}
        refs, whole = self._references()
        if refs:
            out["references"] = refs
            out["references_complete"] = whole
        return out

    # ---- byline
    def _bylines(self):
        """The printed bylines in page order (English first, then Korean), each a list of (name, affiliation, person)."""
        title = self.soup.select_one("#article-view h1.article-title")
        title_row = title.find_parent("div", class_="row") if title else None
        row = title_row.find_next_sibling("div", class_="row") if title_row else None
        if row is None:
            return []
        bylines = []
        for ul in row.select("ul.list-inline.g-color-gray-dark-v2"):
            entries = [e for li in ul.find_all("li", recursive=False) if (e := self._entry(li))[0]]
            if entries:
                bylines.append(entries)
        return bylines

    @staticmethod
    def _entry(li):
        link = li.find("a", href=_PERSON)
        rest = " ".join(_texts(li, skip=link))
        name, aff = _split_affiliation(rest)  # with a person link, the rest is only "(affiliation)"
        if link is None:
            return name, aff, None
        return _squash(link.get_text()), aff, link["href"].rsplit("/", 1)[-1]

    def _authors(self):
        cached = self.__dict__.get("_ks_authors")
        if cached is not None:
            return cached
        bylines = self._bylines()
        authors = []
        if bylines:
            main, others = bylines[0], bylines[1:]
            for i, (name, aff, person) in enumerate(main):
                if not aff:  # the English byline leaves it out: the Korean one prints it for the same person
                    for other in others:
                        twin = next((o for o in other if person and o[2] == person), None) or (
                            other[i] if len(other) == len(main) and not (person and other[i][2]) else None)
                        if twin and twin[1]:
                            aff = twin[1]
                            break
                authors.append({"name": name, "affiliations": [aff] if aff else [], "is_corresponding": None})
        self._ks_authors = authors
        return authors

    # ---- references
    def _references(self):
        box = next((h.parent for h in self.soup.select("div.article-box > h4")
                    if _squash(h.get_text()) in _REF_HEADINGS), None)
        if box is None:
            return [], False
        lists = box.find_all("ol")
        refs, numbers = [], []
        for li in [li for ol in lists for li in ol.find_all("li", recursive=False)]:
            link = li.select_one("a.doi-link")
            text = li.select_one("span.ref-text") or li
            raw = _squash("".join(_texts(text, skip=link)))
            if not raw:
                continue
            doi = _DOI.search(link.get("href", "")) if link else None
            number = _REF_ID.match(li.get("id") or "")
            numbers.append(int(number.group(1)) if number else None)
            refs.append({"position": len(refs) + 1, "raw": raw, "doi": doi.group(1) if doi else None})
        # whole: one list, numbered ref-1..ref-n with no gap, no "show more", and no reference text outside its items
        outside = _squash("".join(s for s in _texts(box) if not s.find_parent("ol") and not s.find_parent("h4")))
        whole = (len(lists) == 1 and (lists[0].get("start") or "1").strip() == "1"
                 and numbers == list(range(1, len(refs) + 1))
                 and not outside and not _MORE.search(box.get_text(" ")))
        return refs, whole
