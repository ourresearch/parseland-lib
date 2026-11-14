import re

from parseland_lib.not_abstract import is_not_abstract
from parseland_lib.publisher.parsers.parser import PublisherParser

# The record's funding rows: OSTI prints the DOE office that paid for the work and the contract under these labels.
# "Research Organization" (the lab that did the work) is not funding.
_FUNDING_LABEL = re.compile(r"^(Sponsoring Org(anization|\.)|(DOE |Other Award/)?Contract Number)\s*:", re.I)


def _text(tag, sep=""):
    return re.sub(r"\s+", " ", tag.get_text(sep)).strip()


class OSTIBiblio(PublisherParser):
    """OSTI.GOV record pages (www.osti.gov/biblio/<id>): DOE technical reports and other DOE-funded works (#2210).

    The citation_* meta tags carry the byline and affiliations as shown, so they are read as the generic parser reads
    them. The abstract comes from the visible description block: its meta copy escapes '&' twice and the meta reader
    skips abstracts of 200 characters or less. The funding statement is the record's labelled funding rows.
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
            "funding_statement": self.parse_funding_statement(),
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

    def parse_funding_statement(self):
        rows = []
        for dt in self.soup.select("#section-metadata dt, #biblio-full dt"):
            label = _text(dt, " ")
            dd = dt.find_next_sibling("dd")
            if _FUNDING_LABEL.match(label) and dd and (value := _text(dd, " ")):
                row = f"{label} {value}"
                if row not in rows:
                    rows.append(row)
        return "\n".join(rows) or None
