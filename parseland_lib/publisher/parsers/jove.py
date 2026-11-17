"""JoVE app pages (app.jove.com; DOI prefix 10.3791), oxjob #2338.

JoVE serves its articles and videos from a Next.js app (app.jove.com) besides its older WordPress pages (www.jove.com).
No parser claimed the app's pages, so the generic parser read only their citation_* tags, and only journal articles
(/t/) carry those. What an app page shows:

- A byline: each author is an <a rel="author"> holding <span data-atm="author-name"> and <sup> numbers into the
  institution list (<span data-atm="institution-name"> after its own <sup>). An envelope <span title="Corresponding
  author"> (the e-mail in a pop-up) follows the corresponding authors' links; a "*" after a name marks equal
  contribution, not correspondence. Author Spotlight videos (/v/) print this byline and no citation_* tags.
- The item's own data in <script id="__NEXT_DATA__">: the "fetchArticleByDomainId" query whose domain.id is the
  canonical URL's id holds overviewContent (an article's abstract; on Encyclopedia of Experiments videos a "Source:
  <the JoVE article it comes from>" line, then the video's summary). Other queries hold other items (a related
  video, an older version), never read.
- On journal articles, a reference list: one <ol> under <h2 id="references">. On a page the reader can't open, the
  list is cut to two entries and an overlay follows it ("Access restricted. Please log in ..."): that list is never
  called whole. Their "Acknowledgements" section is left to parse_page's headed back-matter reader, which already
  reads it (no work gains one from this parser: PLAYBOOK v1.5, a field under 1,000 works is not shipped).

Journal articles keep the citation_author tags' names and affiliations (what the generic parser read); the envelope
marks are added when the byline lists the same authors. WordPress pages are left to the generic parser: their tags
hold the byline and abstract, and they print no corresponding mark.
"""
import json
import re

from bs4 import BeautifulSoup, Tag

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import same_person, squash

_APP = "https://app.jove.com/"
_ITEM_ID = re.compile(r"^https://app\.jove\.com/(?:[a-z-]+/){1,2}(\d+)(?:[/?#]|$)")
_SOURCE = re.compile(r"^\s*source\s*:", re.I)
# the "Source:" citation where a tag runs it into the summary: "Source: Lo, B. C., et al. Title. J. Vis. Exp. (2019)The
# video demonstrates ..."
_SOURCE_CITATION = re.compile(r"^\s*source\s*:.{0,400}?J\.\s*Vis\.\s*Exp\.\s*\(\d{4}\)\s*\.?\s*", re.I | re.S)
_ABSTRACT_FLOOR = 50  # characters: the shortest Encyclopedia summary in the sample is ~400
_CORRESPONDING = "Corresponding author"
_DOI = re.compile(r"\b10\.\d{4,9}/[^\s\"<>]+")


def _paragraphs(html):
    """The text of each innermost <p> of an embedded HTML value (the whole text when it has none)."""
    if not isinstance(html, str) or not html.strip():
        return []
    frag = BeautifulSoup(html, "lxml")
    blocks = frag.find_all(lambda t: t.name == "p" and t.find("p") is None) or [frag]
    return [text for text in (squash(b.get_text()) for b in blocks) if text]


def _without_source(paragraphs):
    """The text without the leading "Source: <JoVE article>" citation of an Encyclopedia video (both labellers leave it
    out of the abstract)."""
    if paragraphs and _SOURCE.match(paragraphs[0]):
        rest = _SOURCE_CITATION.sub("", paragraphs[0], count=1)
        paragraphs = ([rest] if rest != paragraphs[0] and len(rest) >= _ABSTRACT_FLOOR else []) + paragraphs[1:]
    return "\n".join(paragraphs).strip() or None


def _doi(li):
    for text in [li.get_text()] + [a.get("href") or "" for a in li.find_all("a")]:
        if m := _DOI.search(text):
            return m.group(0).rstrip(".,;)")
    return None


def _cut_short(ol, block):
    """True when anything follows the list inside its section block: the overlay a page the reader can't open puts
    after its two-entry preview."""
    node = ol
    while node is not None and node is not block:
        if any(isinstance(sib, Tag) for sib in node.next_siblings):
            return True
        node = node.parent
    return False


class JoVE(PublisherParser):
    parser_name = "jove_app"

    def __init__(self, soup):
        super().__init__(soup)
        self._canon = False  # not looked up yet
        self._result = None

    def _canonical(self):
        """The canonical URL when it is an app.jove.com one, else None. Every parser's claim runs on every DOI page
        (#2239: under 0.5 ms a page it does not claim), so <head> is reached through direct children and only its
        own <link> children are read; nothing walks the page until this passes."""
        if self._canon is False:
            self._canon = None
            html = self.soup.find("html", recursive=False)
            head = (html or self.soup).find("head", recursive=False)
            for link in head.find_all("link", recursive=False) if head is not None else []:
                if "canonical" in (link.get("rel") or []):
                    href = link.get("href") or ""
                    self._canon = href if href.startswith(_APP) else None
                    break
        return self._canon

    def is_publisher_specific_parser(self):
        return self._canonical() is not None

    def authors_found(self):
        if not self.is_publisher_specific_parser():
            return False
        out = self.parse()
        return bool(out["authors"] or out["abstract"])

    def _domain(self):
        """The page's own item in the embedded Next.js data, or {}."""
        m = _ITEM_ID.match(self._canonical() or "")
        script = self.soup.find("script", id="__NEXT_DATA__")
        if not m or script is None:
            return {}
        try:
            queries = json.loads(script.string or "")["props"]["pageProps"]["dehydratedState"]["queries"]
        except (ValueError, KeyError, TypeError):
            return {}
        for query in queries if isinstance(queries, list) else []:
            data = (query.get("state") or {}).get("data") if isinstance(query, dict) else None
            domain = data.get("domain") if isinstance(data, dict) else None
            if isinstance(domain, dict) and str(domain.get("id")) == m.group(1):
                return domain
        return {}

    def _byline(self):
        """[(name, [affiliation], corresponding)] from the printed byline."""
        institutions = {}
        for span in self.soup.find_all(attrs={"data-atm": "institution-name"}):
            sup = span.find_previous_sibling("sup")
            text = squash(span.get_text()).rstrip(",").strip()
            if sup is not None and text:
                institutions.setdefault(squash(sup.get_text()), text)
        byline = []
        for name_el in self.soup.find_all(attrs={"data-atm": "author-name"}):
            link = name_el.find_parent("a")
            if link is None or "author" not in (link.get("rel") or []) or not (name := squash(name_el.get_text())):
                continue
            affs = []
            for sup in link.find_all("sup"):
                aff = institutions.get(squash(sup.get_text()))
                if aff and aff not in affs:
                    affs.append(aff)
            byline.append((name, affs, self._enveloped(link)))
        return byline

    @staticmethod
    def _enveloped(link):
        """True when the envelope follows this author's link, before the next author's."""
        for sib in link.next_siblings:
            if not isinstance(sib, Tag):
                continue
            if sib.name == "a" and "author" in (sib.get("rel") or []):
                return False
            if sib.get("title") == _CORRESPONDING or sib.find(attrs={"title": _CORRESPONDING}) is not None:
                return True
        return False

    def _authors(self):
        byline = self._byline()
        tagged = self.parse_author_meta_tags()
        if not tagged:
            return [{"name": n, "affiliations": affs, "is_corresponding": c} for n, affs, c in byline]
        if (len(byline) == len(tagged) and any(c for _, _, c in byline)
                and all(same_person(a["name"], n) for a, (n, _, _) in zip(tagged, byline))):
            for author, (_, _, corresponding) in zip(tagged, byline):
                author["is_corresponding"] = corresponding
        return tagged

    def _abstract(self, domain):
        # an article's citation_abstract tag first, as the generic parser read it; the item's own data otherwise
        tag = self.parse_abstract_meta_tags(include_seo_tags=False)
        text = _without_source([tag.strip()]) if tag else None
        if not text:
            text = _without_source(_paragraphs(domain.get("overviewContent")))
        return text if text and len(text) >= _ABSTRACT_FLOOR else None

    def _references(self):
        head = self.soup.find("h2", id="references")
        lists = head.parent.find_all("ol") if head is not None and head.parent is not None else []
        if len(lists) != 1:
            return None, False
        items = lists[0].find_all("li", recursive=False)
        refs = []
        for li in items:
            if raw := squash(li.get_text()):
                refs.append({"position": len(refs) + 1, "raw": raw, "doi": _doi(li)})
        start = lists[0].get("start") or "1"
        whole = (bool(refs) and len(refs) == len(items) and start.strip() in ("", "0", "1")
                 and not _cut_short(lists[0], head.parent))
        return refs or None, whole

    def parse(self):
        if self._result is None:
            domain = self._domain()
            refs, whole = self._references()
            self._result = {
                "authors": self._authors(),
                "abstract": self._abstract(domain),
                "acknowledgments": None,  # parse_page's back-matter reader reads the printed section
                "funding_statement": None,  # JoVE prints its funding inside the acknowledgments
                "references": refs,
                "references_complete": whole,
            }
        return self._result
