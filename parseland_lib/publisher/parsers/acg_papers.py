"""Australian Centre for Geomechanics paper pages (papers.acg.uwa.edu.au, The University of Western Australia;
oxjob #2339).

The site runs its own template: citation_* meta tags (a plural citation_authors list the meta-tag reader skips), an
"Authors:" byline with no affiliations or corresponding mark, the abstract in citation_abstract, and a "References:"
block of <div class="refline"> lines. It also hosts other publishers' proceedings (Gecamin, University of Chile) in the
same template, so pages are claimed by the host in og:url, not by citation_publisher.

This parser adds the reference list only. Authors and abstract are the generic parser's, unchanged: the works on this
site already carry their authors from Crossref, and the pages show no affiliations or corresponding marks (#2339
step 2: no field but the reference list reaches 1,000 works the page could give).

The site printed some references across several lines, one <div class="refline"> each ("..., vol. 28, no. 1," then
"pp. 303-319,"; a URL's tail; a link alone). A line that cannot open a reference joins the one before it, and the
list is called whole only when every entry then reads as one: a letter first, a year (or n.d.), in the alphabetical
order an author-date list keeps.
"""
import re
import unicodedata

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

_HOSTS = ("https://papers.acg.uwa.edu.au/", "http://papers.acg.uwa.edu.au/")
_YEAR = re.compile(r"\b(?:1[5-9]|20)\d{2}[a-z]?\b|\bn\.\s?d\.", re.I)  # "2006a": a second work of one author and year
_LETTER = re.compile(r"[^\W\d_]")
_MORE = re.compile(r"\b(?:show|load|view|see) (?:more|all)\b", re.I)
_CLOSERS = (".", ")", "]", "'", "’", '"', "”")
# a printed address ends the entry: "... viewed 10 March 2019, www.gardguide.com", "...sikarapid-700-l.pdf"
_URL_END = re.compile(r"(?:https?:|www\.)\S*$|\S/\S*\.\w{2,4}$")


def _sort_letter(text):
    letter = _LETTER.search(text)
    return unicodedata.normalize("NFKD", letter.group(0))[0].casefold() if letter else ""


def _closed(entry):
    """The entry ends as a reference does: a full stop or closing mark, its link icon, or a printed address."""
    text = entry["text"]
    return text.endswith(_CLOSERS) or bool(_URL_END.search(text)) or entry["lines"][-1].find("a", href=True) is not None


def _continues(text, entry):
    """True when a refline cannot open a reference, so it is the rest of the entry before it: no text (a link alone),
    a first character that is no letter ("pp. 303-319,", "(eds), Proceedings ..."), or no year and either a
    lowercase start (a URL's tail) or an entry before it that stops mid-sentence ("... (2000) Strategic")."""
    if not text or not text[0].isalpha():
        return True
    if _YEAR.search(text):
        return False
    return text[0].islower() or not _closed(entry)


class ACGPapers(PublisherParser):
    parser_name = "acg_papers"

    def _is_acg(self):
        """og:url on the site's host; read from <head>'s own children, so a page of any other site costs a few
        comparisons, never a whole-tree search (#2239: every parser's claim runs on every DOI page)."""
        if "_acg" not in self.__dict__:
            head = self.soup.head
            tag = head.find("meta", attrs={"property": "og:url"}, recursive=False) if head else None
            self._acg = bool(tag) and (tag.get("content") or "").startswith(_HOSTS)
        return self._acg

    def _lines(self):
        if "_reflines" not in self.__dict__:
            self._reflines = self.soup.select("div.refline") if self._is_acg() else []
        return self._reflines

    def is_publisher_specific_parser(self):
        return self._is_acg()

    def authors_found(self):
        return bool(self._lines())

    def parse(self):
        # the generic parser's authors and abstract, as the page got them before this parser (see the module note)
        parsed = dict(GenericPublisherParser(self.soup).parse())
        references, complete = self.parse_references()
        parsed.update(references=references, references_complete=complete)
        return parsed

    def parse_references(self):
        # imported here: back_matter imports parsers.utils, whose package imports every parser, this one included
        from parseland_lib.back_matter import _linked_doi, _pick_doi, _printed_doi

        lines = self._lines()
        entries = []
        for line in lines:
            text = squash(line.get_text()).lstrip("\ufeff\u200b ")  # a byte-order mark opens some pasted lines
            if entries and _continues(text, entries[-1]):
                entries[-1]["text"] = squash(f'{entries[-1]["text"]} {text}')
                entries[-1]["lines"].append(line)
            elif text:
                entries.append({"text": text, "lines": [line]})
            # else: a blank line before any entry
        references = []
        for entry in entries:
            linked = next((doi for doi in map(_linked_doi, entry["lines"]) if doi), None)  # the doi.org link icon
            references.append({"position": len(references) + 1, "raw": entry["text"],
                               "doi": _pick_doi(linked, _printed_doi(entry["text"]))})
        if not references:
            return None, False
        letters = [_sort_letter(e["text"]) for e in entries]
        complete = (
            len({id(line.parent) for line in lines}) == 1  # one block under "References:"
            and not _MORE.search(lines[0].parent.get_text(" "))
            # each entry a whole reference: a letter first, a year, closed, no control characters (the PDF's
            # running header pasted in: "56\x19Paste\x192006,\x19Limerick")
            and all(e["text"][0].isalpha() and _YEAR.search(e["text"]) and _closed(e)
                    and not any(unicodedata.category(c) == "Cc" for c in e["text"]) for e in entries)
            and letters == sorted(letters)  # an author-date list sorts by name; a line out of order is a broken entry
        )
        return references, complete
