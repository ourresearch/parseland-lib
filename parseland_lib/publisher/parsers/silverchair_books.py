import re
from functools import cached_property

from parseland_lib.publisher.parsers.oxford import Oxford
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

# Name suffixes that belong to the name, and bare initials ("J.", "J.R."): a "Family, Given" name, never credentials
_NAME_SUFFIX = re.compile(r"^(?:jr\.?|sr\.?|i{2,3}|iv)$", re.I)
_INITIALS = re.compile(r"^(?:[A-Z]\.)+$")


def _is_credential(token):
    """A degree, honour or year after a card name: four digits, a period or bracket (Ph.D., BSc(Tech)), or two capitals
    (PhD, MD, FAAP, CEng). A given name ("John") has none of these."""
    return bool(re.fullmatch(r"\d{4}", token) or any(c in ".()" for c in token)
                or (re.fullmatch(r"[A-Za-z&/-]+", token) and sum(c.isupper() for c in token) >= 2))


class SilverchairBooks(PublisherParser):
    """Book chapter and book pages on Silverchair's books platform (oxjob #2221).

    Duke, MIT Press, Emerald, RSC, Karger, AAP, GSA, Bristol, Elgar and other presses serve book chapters from one
    Silverchair template. Its byline is not in the meta tags (``citation_author`` is empty) but in widgets:

    - ``div.widget-ChapterTopInfo`` holds the chapter's own byline (edited volumes);
    - the left rail's ``div.book-info__authors`` holds the book's byline, as ``.al-authors-list.authors`` (a
      monograph: the book's authors wrote every chapter) or ``.al-authors-list.editors`` (an edited volume: never
      the chapter's authors);
    - on a book's own page, ``div.widget-BookToc`` with the book's byline at the top.

    Each name has an info card; ``.info-card-affilitation .aff`` (Silverchair's spelling) holds its affiliations.
    Cards on monographs often hold a biography instead (``.info-card-note``): not an affiliation (label-v1).
    No parser read these bylines, so on gold v1.3's dev pages Parseland read authors on 6 of 11 Silverchair chapter
    pages and affiliations on 0 of 6. The chapter's abstract is ``section.abstract`` in the chapter's text widget;
    the ``section.abstract`` in the left rail is the book's description, never the chapter's.

    Oxford Academic runs the same template and has its own parser (it reads its chapters): those pages are left to it.
    """

    parser_name = "silverchair_books"

    @cached_property
    def _chapter_top(self):
        return self.soup.select_one("div.widget-ChapterTopInfo")

    @cached_property
    def _claim(self):
        # one pass over the document for the template's widgets: this runs on every page Parseland parses
        if self.soup.find("div", class_=["widget-ChapterTopInfo", "widget-BookToc"]) is None:
            return False
        if self.soup.select_one(".al-author-name") is None:
            return False
        og = self.soup.find("meta", property="og:url") or self.soup.select_one('meta[name="og:url"]')
        canonical = self.soup.find("link", {"rel": "canonical"})
        urls = " ".join(filter(None, [og and og.get("content"), canonical and canonical.get("href")]))
        return not any(d in urls for d in Oxford.oxford_domains)

    def is_publisher_specific_parser(self):
        return self._claim

    @cached_property
    def _byline(self):
        """The ``.al-authors-list`` that credits this work's authors, or None."""
        def credits(lst):
            return lst is not None and lst.select_one(".al-author-name") is not None

        if self._chapter_top is not None:
            own = [lst for lst in self._chapter_top.select(".al-authors-list:not(.editors)") if credits(lst)]
            if own:
                return own[0]
            book = self.soup.select_one(".book-info__authors")
        else:
            book = self.soup.select_one("div.widget-BookBasicInfo .book-info__authors")
        # the book's byline counts only when it credits authors: an editors-only list credits nobody for a chapter,
        # and a book page credited to editors is left to the other parsers
        lst = book.select_one(".al-authors-list.authors") if book is not None else None
        return lst if credits(lst) else None

    def authors_found(self):
        return self._claim and self._byline is not None

    @staticmethod
    def _clean(text):
        return squash(text).strip(" ,;")

    def _name(self, text):
        """The card name without credentials or a year ("G. J. Bignold, BSc, PhD", "Maya Bunik, MD, MPH, FAAP",
        "Horace Bushnell, 1853": ICE and AMPP books); label-v1 drops them. A "Family, Given" name stays whole."""
        name = self._clean(text).strip(" *")
        head, sep, rest = name.partition(",")
        head = head.strip()
        tokens = rest.replace(",", " ").split()
        if sep and " " in head and tokens and all(_is_credential(t) for t in tokens) \
                and not any(_NAME_SUFFIX.match(t) or _INITIALS.match(t) for t in tokens):
            return head
        return name

    def _affiliations(self, card):
        affs = []
        for aff in card.select(".info-card-affilitation .aff"):
            for junk in aff.select("span.label, a[href*='email-protection'], a[href^='mailto:'], .__cf_email__"):
                junk.decompose()
            text = re.sub(r"\s+,", ",", self._clean(aff.get_text(" ")))
            if text and text not in affs:
                affs.append(text)
        return affs

    def _authors(self):
        if self._byline is None:
            return []
        authors = []
        for tag in self._byline.select(".al-author-name"):
            name_tag = tag.select_one(".info-card-name") or tag.select_one("a.linked-name")
            name = self._name(name_tag.get_text(" ", strip=True)) if name_tag is not None else ""
            if not name:
                continue
            corresponding = tag.select_one("a.xref-corresp, .info-author-correspondence") is not None
            authors.append({"name": name, "affiliations": self._affiliations(tag), "is_corresponding": corresponding})
        if not any(a["is_corresponding"] for a in authors):
            for a in authors:
                a["is_corresponding"] = None  # nobody marked: unknown, as the other parsers leave it
        return authors

    def _abstract(self):
        selector = ("div.widget-BookSectionsText section.abstract" if self._chapter_top is not None
                    else "div.widget-BookBasicInfo .book-info__abstract section.abstract")
        section = self.soup.select_one(selector)
        if section is None:
            return None
        paras = [p for p in (self._clean(p.get_text(" ", strip=True)) for p in section.find_all("p")) if p]
        text = "\n".join(paras) if paras else self._clean(section.get_text(" ", strip=True))
        return re.sub(r"^abstract[:.]?\s*", "", text, flags=re.I) or None

    def parse(self):
        # #2215's three new fields: stored chapter pages show no acknowledgments, funding statement or reference list
        # (0 of 76 sampled non-OUP chapter pages from #2214's census; paywalled chapters show the abstract only)
        return {
            "authors": self._authors(),
            "abstract": self._abstract(),
            "acknowledgments": None,
            "funding_statement": None,
            "references": None,
            "references_complete": False,
        }
