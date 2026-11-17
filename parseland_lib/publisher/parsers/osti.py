import re

from parseland_lib.not_abstract import is_not_abstract
from parseland_lib.publisher.parsers.parser import PublisherParser


def _text(tag, sep=""):
    return re.sub(r"\s+", " ", tag.get_text(sep)).strip()


class OSTIBiblio(PublisherParser):
    """OSTI.GOV record pages (www.osti.gov/biblio/<id>): DOE technical reports and other DOE-funded works (#2210).

    The citation_* meta tags carry the byline and affiliations as shown, so they are read as the generic parser reads
    them. The abstract comes from the visible description block: its meta copy escapes '&' twice and the meta reader
    skips abstracts of 200 characters or less. No funding statement: the record's "Sponsoring Org." and "DOE Contract
    Number" rows are the record's metadata, not a statement the work prints (#2239 round 7: the gold says none).
    """
    parser_name = "osti_biblio"

    def is_publisher_specific_parser(self):
        return bool(self.domain_in_canonical_link("osti.gov/biblio/")
                    and self.soup.select_one("div.biblio-page[data-ostiid]"))

    def authors_found(self):
        return self.is_publisher_specific_parser()

    def parse(self):
        authors = self.parse_author_meta_tags()
        for author in authors:
            author["is_corresponding"] = False  # the pages never mark a corresponding author
        return {
            "authors": authors,
            "abstract": self.parse_abstract(),
            "acknowledgments": None,
            "funding_statement": None,
            "references": None,
            "references_complete": False,
        }

    def parse_abstract(self):
        tag = self.soup.find(id="citation-abstract")
        if tag is None:
            return self.parse_abstract_meta_tags(include_seo_tags=False)
        text = _text(tag)
        # OSTI cuts some long abstracts itself and ends them with "..."; like the meta reader, leave those out
        if not text or text.endswith(("...", "…")) or is_not_abstract(text):
            return None
        if len(text) > 200:
            return text
        # The submitter fills this slot with whatever they had: short entries are often a label ("presentation
        # slides", "Final Technical Report", "Invited talk at ...") or the title again. A short one is kept only
        # when it reads as a sentence.
        title = self.soup.find("meta", attrs={"name": "citation_title"})
        if title and title.get("content", "").strip().lower() == text.lower():
            return None
        if len(text.split()) < 8 or not text.endswith((".", "!", "?")):
            return None
        return text
