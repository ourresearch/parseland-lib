import copy
import re
from urllib.parse import unquote

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash


class CAIRN(PublisherParser):
    parser_name = "cairn"

    # Both Cairn templates print the reference list the same way (oxjob #2268): one <li class="refbiblio" id="rbN">
    # per entry, numbered from rb1, in <section id="decoupe-bibliographie">.
    _REFERENCE_ITEMS = "section#decoupe-bibliographie li.refbiblio"
    _ENTRY_ID = re.compile(r"^rb(\d+)$")
    # the list's own title printed as its first entry ("BIBLIOGRAFÍA"): not a reference, and not a gap in the list
    _HEADING_ENTRY = re.compile(r"^(?:bibliograf[ií]a|bibliograph(?:ie|y)|r[ée]f[ée]rences(?: bibliographiques)?|"
                                r"works cited)\W*$", re.I)
    _MORE_MARKER = re.compile(r"\b(?:voir|afficher) (?:plus|la suite)\b|\b(?:show|load|view) (?:all|more)\b", re.I)

    def is_publisher_specific_parser(self):
        return self.domain_in_meta_og_url('cairn.info')

    def authors_found(self):
        # The old template's byline is div.auteur. The current one (shs. / stm. / droit.cairn.info) prints the byline
        # without markup: its pages are taken only for their reference list, the rest stays the generic parser's.
        return bool(self.soup.select('div.auteur')) or bool(
            self.is_publisher_specific_parser() and self.soup.select_one(self._REFERENCE_ITEMS))

    def parse_authors(self):
        author_tags = self.soup.select('div.auteur')
        authors = []
        for author_tag in author_tags:
            name = ' '.join([tag.text for tag in author_tag.select_one('.nompers').children if len(tag.text) > 2])
            affs = []
            aff_raw = ''
            if aff_raw_tag := author_tag.select_one('div.affiliation'):
                aff_raw = aff_raw_tag.text
                aff = aff_raw_tag.text.split('E-mail')[0]
                affs = [aff]
            authors.append({'name': name, 'affiliations': affs, 'is_corresponding': 'correspondant' in aff_raw})
        return authors

    def parse(self):
        if self.soup.select('div.auteur'):
            result = {'authors': self.parse_authors() or self.parse_author_meta_tags(),
                      'abstract': self.parse_abstract_meta_tags()}
        else:
            # current template: the same authors and abstract the generic parser gives these pages (citation_* tags)
            result = dict(GenericPublisherParser(self.soup).parse())
        if self.is_publisher_specific_parser():
            references, complete = self._references()
            if references:
                result.update(references=references, references_complete=complete)
        return result

    def _references(self):
        """(references, references_complete). Complete only when the entry ids run rb1..rbN with no gap, every list
        item in the section is an entry, and nothing in the section says there are more."""
        # imported here: back_matter imports this package, which imports every parser module
        from parseland_lib.back_matter import _clean_doi, _pick_doi, _printed_doi

        section = self.soup.select_one("section#decoupe-bibliographie")
        if section is None:
            return None, False
        refs, numbers, skipped = [], [], False
        for item in section.select("li.refbiblio"):
            found = self._ENTRY_ID.match(item.get("id") or "")
            numbers.append(int(found.group(1)) if found else None)
            item = copy.copy(item)
            for button in item.select("a.reference-vers-autre-contenu"):  # "En ligne": a link to Cairn's copy
                button.decompose()
            raw = squash(item.get_text())
            if self._HEADING_ENTRY.match(raw):
                continue
            if not raw:
                skipped = True
                continue
            link = item.find("a", href=re.compile(r"doi\.org/10\."))
            doi = _pick_doi(_clean_doi(unquote(link["href"])) if link is not None else None, _printed_doi(raw))
            refs.append({"position": len(refs) + 1, "raw": raw, "doi": doi})
        if not refs:
            return None, False
        whole = (not skipped and numbers == list(range(1, len(numbers) + 1))
                 and len(section.find_all("li")) == len(numbers)
                 and not section.find(string=self._MORE_MARKER))
        return refs, whole
