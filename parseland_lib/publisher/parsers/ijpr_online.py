"""International Journal of Pharmaceutical Research (IJPR, ijpronline.com, Advanced Scientific Research; DOI prefix
10.31838/ijpr) article pages (oxjob #2339; the swarm's census filed the 10.31838 prefix under antennajournal.com).

The site is an ASP.NET app with no meta tags. An article page's <title> is "ViewArticleDetail" (special issues:
"ViewSpecialArticleDetail"), and one GridView row (ContentPlaceHolder1_gvArticle / _gvSpecialArticle) prints the
byline as one comma-separated span (lblAuthor_0; the first author in <FONT COLOR="GREEN">, which the page never
explains), the abstract in lblAbstract_0 and the DOI link in lblDOI_0. Pages show no affiliations,
corresponding-author marks, acknowledgments, funding statements or reference lists. Before this parser only the
generic one read these pages: the abstract under its "Abstract:" label, no authors.
"""
import re

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import cleanup_raw_name

_TITLES = ("ViewArticleDetail", "ViewSpecialArticleDetail")
_FIELD_ID = "ContentPlaceHolder1_{grid}_lbl{field}_0"
_GRIDS = ("gvArticle", "gvSpecialArticle")
_SITE_MARKS = re.compile(r"ijprlogo|10\.31838/ijpr", re.I)
_TITLE_PREFIX = re.compile(r"^(?:dr|prof)(?:\.\s*|\s+)(?=[A-Za-z])", re.I)  # "DR.HANAN", "DR. ARCHANA", not "DRAVID"
_TRAILING_MARKS = re.compile(r"[\d*†]+$")  # "SAYYED HUSSAIN1*": a footnote number and star the page never explains


def _squash(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _has_article_title(soup):
    """The page's <title> is the article view's: the cheap first test of the claim. Every parser's claim runs on every
    page (#2239: under 0.5 ms a page it does not claim), so <title> is reached through direct children only and
    nothing walks the whole tree until this passes."""
    html = soup.find("html", recursive=False)
    head = (html or soup).find("head", recursive=False)
    title = head.find("title", recursive=False) if head is not None else None
    return title is not None and title.get_text().strip() in _TITLES


class IJPROnline(PublisherParser):
    parser_name = "ijpr_online"
    # the pages show no affiliations; another parser's guesses must not win over this byline
    prefer_publisher_authors_over_generic = True

    def _span(self, field):
        for grid in _GRIDS:
            if span := self.soup.find("span", id=_FIELD_ID.format(grid=grid, field=field)):
                return span
        return None

    def is_publisher_specific_parser(self):
        if not _has_article_title(self.soup) or self._span("Author") is None:
            return False
        doi = self._span("DOI")
        return bool((doi is not None and doi.find("a", href=_SITE_MARKS))
                    or self.soup.find("img", src=_SITE_MARKS))

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self.parse_authors())

    def parse_authors(self):
        span = self._span("Author")
        authors = []
        for raw in _squash(span.get_text(" ")).split(","):
            name = cleanup_raw_name(_TRAILING_MARKS.sub("", _TITLE_PREFIX.sub("", raw.strip())))
            if name:
                authors.append({"name": name, "affiliations": [], "is_corresponding": False})
        return authors

    def parse_abstract(self):
        span = self._span("Abstract")
        text = _squash(span.get_text(" ")) if span is not None else ""
        return text if len(text) > 1 else None  # an empty row prints "-"

    def parse(self):
        return {"authors": self.parse_authors(), "abstract": self.parse_abstract()}
