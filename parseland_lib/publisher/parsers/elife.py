"""eLife reviewed preprints: the corresponding authors their byline marks (oxjob #2268, template "elife").

eLife's reviewed-preprint pages come from its Next.js "enhanced preprints" app (route /reviewed-preprints/[...path]).
The full-text tab prints the byline as `ol.author-list`; each corresponding author's entry carries a "For
correspondence:" e-mail line. The citation_author tags the generic parser reads carry no such flag, and the generic
parser's byline star is eLife's "Lead contact" note, not a correspondence mark.

Scope, on purpose (#2268 sizing, 24 pages weighted by works):
- Corresponding flags only. Every eLife work with authors already has affiliations, so affiliations stay empty here
  (the generic parser reads none either) and the works keep theirs.
- The Peer review tab prints no byline and is not claimed: its DOIs are review sub-articles, and the citation tags it
  carries are the reviewed preprint's.
- eLife's journal (version-of-record) template, `ol.author_list` on /articles/ pages, is not read: most sample DOIs that
  land on those pages are review sub-articles (decision letters, author responses) that land on the article's own page,
  and from the HTML alone the parser can't tell them from the article.
"""
import re

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser

_RP_ROUTE = '"page":"/reviewed-preprints/[...path]"'
_CORRESPONDENCE = re.compile(r"^\s*for\s+correspondence\b", re.I)


class ELifeReviewedPreprint(PublisherParser):
    parser_name = "elife_reviewed_preprint"
    # the byline's correspondence lines beat the citation tags' unflagged names
    prefer_publisher_authors_over_generic = True

    def _citation_publisher_is_elife(self):
        # Cheap marker first (#2239: every parser's claim runs on every page): read citation_publisher from <head>
        # only, never the whole tree. On every stored page whose head has one, it is the document's first one, the
        # one substr_in_citation_publisher reads; a page with no <head> still gets the whole-document search.
        scope = self.soup.head or self.soup
        if tag := scope.select_one('meta[name="citation_publisher"]'):
            return "elife" in tag.get("content").lower()
        return False

    def is_publisher_specific_parser(self):
        # cached: the dispatcher calls authors_found() and then this on the same instance
        claim = self.__dict__.get("_claim")
        if claim is None:
            claim = False
            if self._citation_publisher_is_elife():
                data = self.soup.find("script", id="__NEXT_DATA__")
                claim = bool(data and data.string and _RP_ROUTE in data.string)
            self._claim = claim
        return claim

    def _byline(self):
        byline = self.__dict__.get("_byline_items")
        if byline is None:
            byline = self._byline_items = self.soup.select("ol.author-list > li.author-list__author")
        return byline

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._byline())

    def parse_authors(self):
        authors = []
        for item in self._byline():
            name_tag = item.find(class_="author-list__author_name")
            if not name_tag:
                continue
            name = " ".join(s.strip() for s in name_tag.find_all(string=True, recursive=False) if s.strip())
            name = name or name_tag.get_text(" ", strip=True).rstrip("*").strip()
            if not name:
                continue
            corresponding = any(_CORRESPONDENCE.match(h.get_text(" ", strip=True))
                                for h in item.select(".author-list__email--heading"))
            authors.append({"name": name, "affiliations": [], "is_corresponding": corresponding})
        return authors

    def parse(self):
        return {"authors": self.parse_authors(),
                "abstract": GenericPublisherParser(self.soup).parse().get("abstract")}
