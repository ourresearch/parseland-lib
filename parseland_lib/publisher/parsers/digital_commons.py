"""Digital Commons (bepress, now Elsevier) item pages: university repositories and the journals they host (oxjob #2268).

Every item page prints its fields as <div class="element" id="..."> blocks inside div#alpha and carries
bepress_citation_* meta tags. The generic parser already reads what the page shows of the byline, affiliations,
corresponding-author block and abstract (#2239's printed-description reader at 274e37e closed the abstracts 9c1dc07
lost), so this parser returns exactly the generic parser's authors and abstract and adds what no reader took: the
"References" field some journals fill in (div#references). Its acknowledgments element is read by parse.py's
headed_back_matter already.

Claimed by the bepress_citation_* tags together with the Digital Commons page frame (div#alpha's field elements, or the
Digital Commons Network link): Drupal journals print bepress_citation_* tags too, without either.
"""
import copy
import re
from urllib.parse import unquote

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

_BEPRESS_TAG = re.compile(r"^bepress_citation_")
_HEADING = re.compile(r"^h[1-6]$")
_LINE_BREAK = "\u2028"  # a <br> or a line of a pasted list, before splitting into entries
_DOI_LINK = re.compile(r"doi\.org/10\.")


class DigitalCommons(PublisherParser):
    parser_name = "digital_commons"

    def __init__(self, soup):
        super().__init__(soup)
        self._parsed = None
        self._claimed = None

    def is_publisher_specific_parser(self):
        # Every DOI page asks every parser (oxjob #2268, #2239's CPU rule), so the claim is computed once and starts
        # with the cheapest test: a scan of the page's <meta> tags (bs4's name-only fast path), anywhere in the page,
        # so a bepress tag that lxml moved out of <head> still counts. Only a page with one goes on to the frame.
        if self._claimed is None:
            self._claimed = (any(_BEPRESS_TAG.match(meta.get("name") or "") for meta in self.soup.find_all("meta"))
                             and bool(self.soup.select_one("div#alpha div.element[id]")
                                      or self.soup.select_one('a[href*="network.bepress.com"]')))
        return self._claimed

    def authors_found(self):
        # A page this parser does not claim: the generic parser, which every page runs and which sits before this one
        # in PublisherParser.__subclasses__(), returns the same authors and abstract, so answering False there changes
        # no output and skips a whole generic parse per page.
        if not self.is_publisher_specific_parser():
            return False
        parsed = self.parse()
        return bool(parsed.get("authors") or parsed.get("abstract") or parsed.get("references"))

    def parse(self):
        if self._parsed is None:
            parsed = dict(GenericPublisherParser(self.soup).parse())
            references, complete = self.parse_references()
            parsed.update(references=references or None, references_complete=complete)
            self._parsed = parsed
        return self._parsed

    def _entries(self, block):
        """[(text, element or None)] in page order: one per <li> or <p>, and per line of a <p> that holds the whole
        list (a pasted list, one reference per line). Several <p>s: each is one entry, as the browser shows it."""
        items = block.find_all("li") or block.find_all("p") or [block]
        entries = []
        for item in items:
            item = copy.copy(item)
            for br in item.find_all("br"):
                br.replace_with(_LINE_BREAK)
            text = item.get_text()
            if len(items) == 1:
                text = text.replace("\n", _LINE_BREAK)
            lines = [line for part in text.split(_LINE_BREAK) if (line := squash(part))]
            entries.extend((line, item if len(lines) == 1 else None) for line in lines)
        return entries

    def parse_references(self):
        """(references, complete). Complete only when every entry carries a typed number and they run 1..n: the field
        is free text a journal pastes in, so an unnumbered list gives no positive sign that it is whole."""
        block = self.soup.select_one("div#references.element")
        if block is None:
            return [], False
        # imported here: back_matter imports parsers.utils, whose package imports every parser, this one included
        from parseland_lib.back_matter import (_TYPED_NUMBER, _clean_doi, _has_broken_entry, _numbering_whole,
                                               _pick_doi, _printed_doi)
        block = copy.copy(block)
        for heading in block.find_all(_HEADING):
            heading.decompose()
        entries = self._entries(block)
        if not entries:
            return [], False
        numbers = [m.group(1) if (m := _TYPED_NUMBER.match(text)) else None for text, _ in entries]
        numbered = None not in numbers and _numbering_whole(numbers)
        refs = []
        for (text, item), number in zip(entries, numbers):
            raw = _TYPED_NUMBER.sub("", text, count=1) if number is not None else text
            link = item.find("a", href=_DOI_LINK) if item is not None else None
            doi = _pick_doi(_clean_doi(unquote(link["href"])) if link is not None else None, _printed_doi(raw))
            refs.append({"position": len(refs) + 1, "raw": raw, "doi": doi})
        complete = numbered and not _has_broken_entry([r["raw"] for r in refs])
        return refs, complete
