"""RCIN record pages (rcin.org.pl, the Digital Repository of Scientific Institutes of the Polish Academy of Sciences'
institutes; a dLibra repository; DOI prefixes 10.4098, 10.18318, 10.7163 ...), oxjob #2339.

A DOI resolves to the record's metadata page (h3.object__subheader + p.object__desc per field) or to its content
viewer (span.details__header + p.details__text). Both carry citation_author and DC.description meta tags, which the
generic parser already reads: the byline (names only: the record shows no affiliations and no corresponding author)
and the "Description" field, the abstract on the journals that fill it. This parser keeps exactly the generic parser's
authors and abstract and adds the one thing nothing read: the record's "References:" field, the work's reference list,
one entry per <br>-separated line (a <span>, or a metadata-search link on the IGiPZ journals), each optionally followed
by a DOI icon link. A DOI printed on its own line ("http://dx.doi.org/... -") belongs to the entry before it.

The list is called whole only when every entry carries its number and they run 1..n: APA-style lists print none, and
some records split the list under sub-headings ("Bibliografia podmiotowa" / "przedmiotowa") that restart at 1.
"Financing" and "Projects co-financed by" name the funding of the digitisation, not of the work: not read.
"""
import re

from bs4 import NavigableString, Tag

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

_RCIN_URL = re.compile(r"^https?://(?:www\.)?rcin\.org\.pl(?:[/:?#]|$)", re.I)
_REFERENCES_LABEL = {"references", "bibliografia"}
_NUMBERED = re.compile(r"^(\d{1,3})\.\s")
_LINK_LINE = re.compile(r"^(?:https?://|www\.|doi:)", re.I)
_DOI = re.compile(r"\b10\.\d{4,9}/[^\s\"<>]+")


def _head(soup):
    html = soup.find("html", recursive=False)
    return (html or soup).find("head", recursive=False)


def _doi_in(text):
    match = _DOI.search(text or "")
    return match.group(0).rstrip(".,;)]") if match else None


def _is_doi_icon(tag):
    return tag.name == "a" and "doi.org/" in (tag.get("href") or "") and tag.find("img") is not None


class RCIN(PublisherParser):
    parser_name = "rcin"
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        # Every DOI page asks every parser (oxjob #2239's per-page CPU rule): only the small <head>, reached through
        # direct children, is searched for the og:url tag, and the answer is kept.
        claim = self.__dict__.get("_rcin_claim")
        if claim is None:
            head = _head(self.soup)
            tag = head.find("meta", attrs={"property": "og:url"}) if head is not None else None
            claim = tag is not None and bool(_RCIN_URL.match((tag.get("content") or "").strip()))
            self._rcin_claim = claim
        return claim

    def _generic(self):
        if "_rcin_generic" not in self.__dict__:
            self._rcin_generic = GenericPublisherParser(self.soup)
        return self._rcin_generic

    def authors_found(self):
        # the pages the generic parser reads (a byline or an abstract); a record with neither is left to it
        return self.is_publisher_specific_parser() and bool(self._generic().authors_found())

    def _references_block(self):
        for header in self.soup.find_all(["h3", "span"], class_=["object__subheader", "details__header"]):
            if squash(header.get_text(" ")).rstrip(":").strip().lower() in _REFERENCES_LABEL:
                block = header.find_next_sibling()
                if block is not None and block.name == "p":
                    return block
        return None

    @staticmethod
    def _lines(block):
        """(text, icon DOI, unexpected markup) per <br>-separated line of the field."""
        lines, text, doi, odd = [], [], None, False
        for child in block.children:
            if isinstance(child, Tag) and child.name == "br":
                lines.append((squash(" ".join(text)), doi))
                text, doi = [], None
            elif isinstance(child, Tag) and _is_doi_icon(child):
                doi = doi or child["href"]
            elif isinstance(child, Tag):
                odd = odd or child.name not in ("span", "a")
                text.append(child.get_text(" "))
            elif isinstance(child, NavigableString):
                text.append(str(child))
        lines.append((squash(" ".join(text)), doi))
        return lines, odd

    def parse_references(self):
        block = self._references_block()
        if block is None:
            return [], False
        lines, odd = self._lines(block)
        lines = [(t, d) for t, d in lines if any(map(str.isalpha, t)) or d]  # empty lines and a bare "-"
        numbered = any(_NUMBERED.match(t) for t, _ in lines)
        entries, numbers, dropped = [], [], False
        for text, icon_doi in lines:
            if (not text or _LINK_LINE.match(text)) and entries:
                # a DOI or URL on its own line ("http://dx.doi.org/10.7163/GPol.2011.2.1 -"): the entry before's
                entries[-1]["raw"] = squash(entries[-1]["raw"] + " " + text.rstrip(" -"))
                entries[-1]["doi"] = entries[-1]["doi"] or _doi_in(text) or _doi_in(icon_doi)
                continue
            number = _NUMBERED.match(text)
            if numbered and not number:
                dropped = True  # a sub-heading inside a numbered list ("Bibliografia przedmiotowa")
                continue
            # the DOI printed in the entry's own text first: an icon link now and then carries the next entry's
            entries.append({"raw": text, "doi": _doi_in(text) or _doi_in(icon_doi)})
            numbers.append(int(number.group(1)) if number else None)
        refs = [{"position": i + 1, **entry} for i, entry in enumerate(entries)]
        whole = (bool(refs) and numbered and not dropped and not odd
                 and numbers == list(range(1, len(numbers) + 1)))
        return refs, whole

    def parse(self):
        result = dict(self._generic().parse())
        refs, whole = self.parse_references()
        result.update({
            "acknowledgments": None,
            "funding_statement": None,
            "references": refs,
            "references_complete": whole,
        })
        return result
