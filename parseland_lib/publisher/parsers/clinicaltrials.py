"""ClinicalTrials.gov study records, the classic "Full Text View" (clinicaltrials.gov/ct2/show/NCT...) (oxjob #2338).

DOI prefix 10.31525 registers trial records; ~25K of its works resolve to these pages, which no parser claimed: the
generic one read nothing, because the record's summary sits under a label div ("Brief Summary:") rather than an
"Abstract" heading or a meta tag. Both blind labellers (label-v1) give the Brief Summary as the work's abstract, never
the longer "Detailed Description". The record credits no authors: its sponsor, responsible party and principal
investigator are not a byline, so this parser returns none.

Left alone: the "Publications:" entries (unnumbered, no stated count, so never provably a whole list; "Publications
automatically indexed" are works that cite the trial), and the new site's JavaScript pages (/study/NCT...), which the
store holds as empty shells.
"""
import copy

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

_RECORD_URL = "clinicaltrials.gov/ct2/show/"
_PARAGRAPH = " "  # a mark for <br> and block ends while the summary's text is read


def _og_url_in_head(soup):
    """The og:url meta tag among <head>'s direct children. Every parser's claim runs on every DOI page (#2239: under
    0.5 ms a page it does not claim), so nothing below <head>'s own children is searched."""
    html = soup.find("html", recursive=False)
    head = (html or soup).find("head", recursive=False)
    if head is None:
        return None
    meta = head.find("meta", attrs={"property": "og:url"}, recursive=False)
    return meta.get("content") if meta is not None else None


def _block_lines(block):
    """The summary's text, one line per paragraph (<p>, <li>, <div> or <br>), whitespace inside a line squashed."""
    block = copy.copy(block)  # the other parsers still read this soup
    for br in block.find_all("br"):
        br.replace_with(_PARAGRAPH)
    for tag in block.find_all(["p", "li", "div"]):
        tag.append(_PARAGRAPH)
    lines = [squash(line) for line in block.get_text().split(_PARAGRAPH)]
    return "\n".join(line for line in lines if line) or None


class ClinicalTrialsGov(PublisherParser):
    parser_name = "clinicaltrials_gov"

    def is_publisher_specific_parser(self):
        # asked by authors_found(), parse() and the caller: the answer is kept
        if getattr(self, "_claimed", None) is None:
            self._claimed = _RECORD_URL in (_og_url_in_head(self.soup) or "")
        return self._claimed

    def _summary_block(self):
        """The div after the "Brief Summary:" label, found once."""
        if not hasattr(self, "_summary"):
            self._summary = None
            for label in self.soup.find_all("div", class_="ct-body3"):
                if squash(label.get_text()) == "Brief Summary:":
                    block = label.find_next_sibling("div")
                    if block is not None and "ct-body3" in (block.get("class") or []):
                        self._summary = block
                    break
        return self._summary

    def authors_found(self):
        # the claim first: the label search walks the page, so it runs only on this site's records
        return self.is_publisher_specific_parser() and self._summary_block() is not None

    def parse(self):
        block = self._summary_block()
        return {"authors": [], "abstract": _block_lines(block) if block is not None else None}
