import copy
import re

from bs4 import Comment

from parseland_lib.publisher.parsers.parser import PublisherParser


class ActaHorticulturae(PublisherParser):
    """Acta Horticulturae (actahort.org, ISHS) article records (oxjob #2210).

    The pages carry no citation meta tags, og:url or canonical link. The article record (/books/NNNN/NNNN_NN.htm) and
    the members login page that repeats it (/members/showpdf?booknrarnr=) share one table: an "ISHS Acta
    Horticulturae NNNN:" series line, a bold "Authors:" (or "Author:") row, a "DOI:" row and an "Abstract:" cell.
    The pages show no affiliations, corresponding author, acknowledgments, funding or reference list (references sit
    behind a separate members link), so those are not returned.
    """
    parser_name = "acta_horticulturae"
    # no other parser reads these pages correctly; a generic author list with affiliations must not win over ours
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        # all three: the series line, the record's own Acta Horticulturae DOI, and the site's own links or search form
        # (a page elsewhere that cites an Acta Horticulturae DOI has neither of the others)
        own = re.compile(r"^https?://www\.actahort\.org/")
        return bool(
            self.soup.find("b", string=re.compile(r"^\s*ISHS Acta Horticulturae\s+\d+\s*:"))
            and self.soup.find("a", href=re.compile(r"^https?://(dx\.)?doi\.org/10\.17660/ActaHortic\.", re.I))
            and (self.soup.find("a", href=own) or self.soup.find("form", action=own)))

    def _row_value(self, *labels):
        """The cell after a bold row label such as "Authors:" in the record table, or None."""
        for b in self.soup.find_all("b"):
            if b.get_text(strip=True) in labels:
                td = b.find_parent("td")
                if td is not None and (value := td.find_next_sibling("td")) is not None:
                    return value
        return None

    def _authors_cell(self):
        return self._row_value("Authors:", "Author:")

    def authors_found(self):
        return self.is_publisher_specific_parser() and self._authors_cell() is not None

    def parse_authors(self):
        cell = self._authors_cell()
        if cell is None:
            return []
        names = [re.sub(r"\s+", " ", n).strip() for n in cell.get_text("").split(",")]
        return [{"name": n, "affiliations": [], "is_corresponding": False} for n in names if n]

    def parse_abstract(self):
        label = self.soup.find("b", string=re.compile(r"^\s*Abstract:\s*$"))
        td = label.find_parent("td") if label is not None else None
        if td is None:
            return None
        td = copy.copy(td)  # never edit the page other parsers read
        td.find("b", string=re.compile(r"^\s*Abstract:\s*$")).decompose()
        for comment in td.find_all(string=lambda s: isinstance(s, Comment)):
            comment.extract()
        # inline markup (<i>, <sup>) joins without spaces: "h<sup>-1</sup>" stays "h-1"
        text = re.sub(r"\s+", " ", td.get_text("")).strip()
        return text or None

    def parse(self):
        return {"authors": self.parse_authors(), "abstract": self.parse_abstract()}
