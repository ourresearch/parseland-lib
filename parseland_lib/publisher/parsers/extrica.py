import re

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

_SITE_URL = re.compile(r"^https?://(?:www\.)?(?:extrica|jvejournals)\.com/", re.I)
_CORRESPONDING_LINE = re.compile(r"^corresponding authors?\s*:?$", re.I)


def is_extrica_page(soup):
    """A page of Extrica, JVE International's platform (extrica.com; jvejournals.com before it): its citation_publisher
    tag says "JVE International Ltd." or "Extrica", or its og:url is on one of the two domains.

    Every parser's claim runs on every DOI page (oxjob #2239's per-page CPU budget), so only the small <head> is
    searched, where the site prints both tags."""
    head = soup.head
    if head is None:
        return False
    tag = head.find("meta", attrs={"name": "citation_publisher"})
    publisher = (tag.get("content") or "").strip().lower() if tag else ""
    if publisher.startswith("jve international") or publisher == "extrica":
        return True
    tag = head.find("meta", attrs={"property": "og:url"})
    return bool(tag and _SITE_URL.match(tag.get("content") or ""))


def _name_key(name):
    """A name's words as a set, so "Fangyu, Chen" (the tag) and "Chen Fangyu" (the byline) are one person."""
    return frozenset(re.findall(r"[^\W\d_]+", (name or "").lower()))


def _numbers(text):
    return {int(n) for n in re.findall(r"\d+", text or "")}


class Extrica(PublisherParser):
    """Extrica article pages (oxjob #2339): Journal of Vibroengineering, Journal of Measurements in Engineering,
    Mathematical Models in Engineering and JVE's other titles.

    The citation_author tags give the byline in page order, and the generic parser reads them and the abstract right;
    what it missed is who the corresponding author is:
      - older template: <h2 class="my-4"> holds <strong>name</strong><sup>n</sup> for each author, and a
        <p class="mb-0"> line "<sup>2</sup>Corresponding author" names the author by place;
      - current template: div.single-author bylines and a div.corresponding-author block whose value names one
        author or several ("Corresponding Authors: A, B"; the generic parser read only a block naming one).
    A mark is kept only when the byline and the tags agree on who stands at that place. Left as the generic parser
    reads them, each under #2339's floor of 1,000 works on this site: affiliations (the works have them from
    Crossref), and the current template's Acknowledgements block (14 of its 32 are the site's "The authors have not disclosed any
    funding."; the older template's is read by parse_page's headed back-matter reader). No reference list is read:
    the works have Crossref's.
    """
    parser_name = "extrica"

    def is_publisher_specific_parser(self):
        if not hasattr(self, "_claim"):  # authors_found() and the dispatcher both ask: work it out once
            self._claim = is_extrica_page(self.soup)
        return self._claim

    def _older_byline(self):
        return self.soup.find("h2", class_="my-4")

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(
            self._older_byline() or self.soup.find("div", class_="single-author"))

    def _byline_and_marks(self):
        """(byline names in page order, 0-based places of the corresponding authors), or ([], set())."""
        h2 = self._older_byline()
        if h2 is not None:
            names = [squash(strong.get_text()) for strong in h2.find_all("strong")]
            marked = set()
            for line in self.soup.find_all("p", class_="mb-0"):
                sup = line.find("sup")
                if sup is None:
                    continue
                if _CORRESPONDING_LINE.match(squash(line.get_text().replace(sup.get_text(), "", 1))):
                    marked |= {n - 1 for n in _numbers(sup.get_text()) if 0 < n <= len(names)}
            return names, marked
        names = []
        for div in self.soup.find_all("div", class_="single-author"):
            names.append(squash(" ".join(div.find_all(string=True, recursive=False))))  # not the <sup>, not ORCID
        block = self.soup.find("div", class_="corresponding-author")
        value = block.find("div", class_="value") if block else None
        label = block.find("div", class_="label") if block else None
        if not value or not label or not _CORRESPONDING_LINE.match(squash(label.get_text())):
            return names, set()
        keys = [_name_key(n) for n in names]
        marked = set()
        for named in squash(value.get_text(" ")).split(","):
            places = [i for i, key in enumerate(keys) if key and key == _name_key(named)]
            if len(places) == 1:
                marked.add(places[0])
        return names, marked

    def parse(self):
        result = dict(GenericPublisherParser(self.soup).parse())
        authors = [dict(author) for author in result.get("authors") or []]
        byline, marked = self._byline_and_marks()
        # the byline and the tags must name the same people in the same order, or a place points at no one
        if marked and len(byline) == len(authors) and all(
                _name_key(shown) == _name_key(author.get("name")) for shown, author in zip(byline, authors)):
            for i, author in enumerate(authors):
                author["is_corresponding"] = i in marked
        result["authors"] = authors
        return result
