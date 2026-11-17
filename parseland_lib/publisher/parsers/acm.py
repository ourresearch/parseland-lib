"""ACM Digital Library (dl.acm.org): Atypon Literatum's older item template, the one with a `loa__author-info` card per
author (oxjob #2289). The 2022 "core" template (`div[property=author]`) has no such card and stays with the shared
Literatum readers.

What this template prints, from 76 stored pages (#2289's sample, 17 Nov 2026):
- each author's card: the name, then a `loa_author_inst` span per affiliation. Old proceedings and journals print the
  span EMPTY when ACM holds no affiliation (1966, 1993, 1998 pages; Zendesk ticket 2685's 35-author SIGMOD Record
  report): no affiliation, never an empty one;
- the abstract in `.abstractInFull`, one <p> per paragraph (7 of 55 abstracts have two or three);
- the reference list in `div.article__references > ol.references__list`, every entry in the HTML (the section's
  "show-more-items" class only folds the list on screen), as `li.references__item` with ids ref-00001.. or Bib0001..
  The page's other `references__list`s are its footnotes and its "Cited By" list: not references.
"""
import copy
import re

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

_ENTRY_ID = re.compile(r"^(?:ref-|Bib)0*(\d+)$")
_NUMBER_LABEL = re.compile(r"^\[?\d{1,4}[.\]]?$")
_PLACEHOLDER_DOI = "10.5555/"  # ACM's own catalogue number for an item with no DOI: no registered DOI


class AssociationForComputingMachinery(PublisherParser):
    parser_name = "association_for_computing_machineinery"

    def is_publisher_specific_parser(self):
        # Every DOI page is offered to this parser, so the claim reads one meta tag in the small <head> (#2239's
        # per-page CPU rule), and the answer is kept: authors_found() and the caller both ask.
        if getattr(self, "_claimed", None) is None:
            head = self.soup.head
            scope = head if head is not None else self.soup
            og_url = scope.find("meta", property="og:url") or scope.find("meta", attrs={"name": "og:url"})
            self._claimed = bool(og_url and "acm.org" in (og_url.get("content") or ""))
        return self._claimed

    def _author_tags(self):
        return self.soup.select('span[class*="author-info"]')

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._author_tags())

    def parse_authors(self):
        authors = []
        for author_tag in self._author_tags():
            if name_tag := author_tag.select_one('[class*="author-name"]'):
                name = name_tag.text.strip()
            else:
                continue
            # an empty institution span is the page saying nothing (ticket 2685), not an affiliation
            affs = [aff for tag in author_tag.select('[class*="author_inst"]') if (aff := tag.text).strip()]
            authors.append({
                'name': name,
                'affiliations': affs,
                'is_corresponding': None,
            })

        return authors

    def parse_abstract(self):
        # every paragraph, not only the first (the outer block holds a nested copy's <p>s once)
        for block in self.soup.select('.abstractInFull'):
            if paragraphs := block.select('p'):
                return "\n".join(p.text for p in paragraphs)
        return None

    def parse_references(self):
        """(entries, whole): whole when the entries' ids number them 1..n with no gap."""
        ol = self.soup.select_one('div.article__references > ol.references__list')
        refs, numbers = [], []
        for entry in ol.select('li.references__item') if ol else []:
            note = entry.select_one('.references__note')
            if note is None:
                return refs, False
            note = copy.copy(note)  # the soup is read again after this parser
            for tag in note.select('.references__suffix, .references__pub-id'):
                tag.decompose()
            label = note.select_one('.label')
            if label is not None and _NUMBER_LABEL.match(squash(label.get_text())):
                label.decompose()  # a list number; an author-year label ("Wirth 1968") is part of the entry
            raw = squash(note.get_text())
            if not raw:
                return refs, False
            refs.append({"raw": raw, "doi": self._entry_doi(entry, raw)})
            numbers.append(int(m.group(1)) if (m := _ENTRY_ID.match(entry.get("id") or "")) else None)
        starts_at_one = (ol.get("start") or "1").strip() == "1" if ol else False
        return refs, bool(refs) and starts_at_one and numbers == list(range(1, len(refs) + 1))

    @staticmethod
    def _entry_doi(entry, raw):
        # imported here: back_matter imports this package, which imports every parser module (as cairn.py does)
        from parseland_lib.back_matter import _clean_doi, _linked_doi, _pick_doi, _printed_doi
        pub_id = entry.select_one('.references__pub-id.doi')
        given = _clean_doi(" ".join(pub_id.get("class", []))) if pub_id is not None else None
        doi = _pick_doi(given, _linked_doi(entry), _printed_doi(raw))
        return None if not doi or doi.startswith(_PLACEHOLDER_DOI) else doi

    def parse(self):
        refs, whole = self.parse_references()
        return {'authors': self.parse_authors(),
                'abstract': self.parse_abstract(),
                'acknowledgments': None,
                'funding_statement': None,
                'references': refs or None,
                'references_complete': whole}
