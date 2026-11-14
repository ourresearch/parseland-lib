import re

from parseland_lib.publisher.parsers.oxford import Oxford
from parseland_lib.publisher.parsers.parser import PublisherParser


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
    Stored chapter pages show no acknowledgments, funding statement or reference list (0 of 76 sampled pages from
    #2214's census), so the three new fields are always empty here.
    """

    parser_name = "silverchair_books"

    def _is_oxford(self):
        return any(self.domain_in_meta_og_url(d) or self.domain_in_canonical_link(d) for d in Oxford.oxford_domains)

    def is_publisher_specific_parser(self):
        return bool(self.soup.select_one("div.widget-ChapterTopInfo, div.widget-BookToc")
                    and self.soup.select_one(".al-author-name")) and not self._is_oxford()

    def _is_chapter(self):
        return self.soup.select_one("div.widget-ChapterTopInfo") is not None

    def _byline(self):
        """The ``.al-authors-list`` that credits this work's authors, or None."""
        if self._is_chapter():
            top = self.soup.select_one("div.widget-ChapterTopInfo")
            for lst in top.select(".al-authors-list"):
                if lst.select_one(".al-author-name") and "editors" not in (lst.get("class") or []):
                    return lst
            book = self.soup.select_one(".book-info__authors")
        else:
            book = self.soup.select_one("div.widget-BookBasicInfo .book-info__authors")
        if book is None:
            return None
        # the book's byline counts only when it credits authors: an editors-only list credits nobody for a chapter,
        # and a book page credited to editors is left to the other parsers
        lst = book.select_one(".al-authors-list.authors")
        return lst if lst is not None and lst.select_one(".al-author-name") else None

    def authors_found(self):
        return self.is_publisher_specific_parser() and self._byline() is not None

    @staticmethod
    def _clean(text):
        return re.sub(r"\s+", " ", text or "").strip(" ,;")

    def _affiliations(self, card):
        affs = []
        for aff in card.select(".info-card-affilitation .aff"):
            for junk in aff.select("span.label, a[href*='email-protection'], a[href^='mailto:'], .__cf_email__"):
                junk.decompose()
            text = self._clean(aff.get_text(" ", strip=True))
            text = re.sub(r"\s+,", ",", text)
            if text and text not in affs:
                affs.append(text)
        return affs

    def _authors(self):
        byline = self._byline()
        if byline is None:
            return []
        authors = []
        for tag in byline.select(".al-author-name"):
            name_tag = tag.select_one(".info-card-name") or tag.select_one("a.linked-name")
            if name_tag is None:
                continue
            name = self._clean(name_tag.get_text(" ", strip=True)).strip(" *")
            if not name:
                continue
            corresponding = bool(tag.select_one("a.xref-corresp") or tag.select_one(".info-author-correspondence"))
            authors.append({"name": name, "affiliations": self._affiliations(tag), "is_corresponding": corresponding})
        if not any(a["is_corresponding"] for a in authors):
            for a in authors:
                a["is_corresponding"] = None
        return authors

    def _abstract(self):
        if self._is_chapter():
            section = self.soup.select_one("div.widget-BookSectionsText section.abstract")
        else:
            section = self.soup.select_one("div.widget-BookBasicInfo .book-info__abstract section.abstract")
        if section is None:
            return None
        paras = [p.get_text(" ", strip=True) for p in section.find_all("p")]
        paras = [self._clean(p) for p in paras if p and p.strip()]
        text = "\n".join(paras) if paras else self._clean(section.get_text(" ", strip=True))
        text = re.sub(r"^abstract[:.]?\s*", "", text, flags=re.I)
        return text or None

    def parse(self):
        return {
            "authors": self._authors(),
            "abstract": self._abstract(),
            "acknowledgments": None,
            "funding_statement": None,
            "references": None,
            "references_complete": False,
        }
