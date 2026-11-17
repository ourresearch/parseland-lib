"""ACTA Press paper pages (actapress.com PaperInfo.aspx: IASTED proceedings and journals, DOI prefix 10.2316),
oxjob #2339.

One ASP.NET template: <head> carries citation_* meta tags with citation_publisher "ACTA Press", and div#content prints
span#lblTitle, span#lblAuthors, span#lblKeywords and span#lblAbstract. The generic parser reads the citation_author
names and, on some pages, the one-sentence `description` meta tag as the abstract; it never reads span#lblAbstract,
which holds the whole abstract. This parser reads that span and keeps the meta-tag names.

The byline prints names only. Its asterisks ("Abd El-Aal∗", "Zhaohui Chen,∗ ... Yanjian Peng∗∗∗∗") point to footnotes
the page never shows, so nobody is marked corresponding (label-v1). The page shows no affiliations, acknowledgments,
funding statement or reference list (span#lblReferences is always empty). "Proceeding not found / withdrawn" pages
carry the same <head> title but no citation tags and no span#lblAbstract, and are not read.
"""
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash


def _head(soup):
    html = soup.find("html", recursive=False)
    return (html or soup).find("head", recursive=False)


class ActaPress(PublisherParser):
    parser_name = "acta_press"

    def is_publisher_specific_parser(self):
        # Every DOI page asks every parser (oxjob #2239's per-page CPU rule): only the small <head>, reached through
        # direct children, is searched for the publisher's meta tag, and the answer is kept.
        claim = self.__dict__.get("_actapress_claim")
        if claim is None:
            head = _head(self.soup)
            tag = head.find("meta", attrs={"name": "citation_publisher"}) if head is not None else None
            claim = tag is not None and squash(tag.get("content")).lower() == "acta press"
            self._actapress_claim = claim
        return claim

    def _abstract_span(self):
        return self.soup.find("span", id="lblAbstract")

    def authors_found(self):
        return self.is_publisher_specific_parser() and self._abstract_span() is not None

    def parse(self):
        authors = self.parse_author_meta_tags()
        for author in authors:
            author["is_corresponding"] = False
        span = self._abstract_span()
        abstract = squash(span.get_text()) if span is not None else ""
        return {
            "authors": authors,
            "abstract": abstract or None,
            "acknowledgments": None,
            "funding_statement": None,
            "references": [],
            "references_complete": False,
        }
