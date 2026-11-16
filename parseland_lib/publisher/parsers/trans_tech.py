import copy
import re
from urllib.parse import unquote

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import remove_parents, squash

_LABEL = re.compile(r"^\[(\d+)\]$")  # scientific.net numbers each entry "[n]" in a span
# the old selector meta[name=citation_publisher] matched with soupsieve's ^...$ (a trailing newline passes); kept exact
_PUBLISHER_TAG = re.compile(r"^citation_publisher$")


class TransTechPub(PublisherParser):
    parser_name = "trans_tech_publications"
    # Scientific.Net pages carry citation_reference meta tags; one naming Elsevier ("Elsevier, Amsterdam") also
    # satisfies Elsevier's meta-tag claim, and Elsevier's parser, earlier in line, won the page and dropped the
    # starred corresponding author (oxjob #2268: 2 of 76 sample pages). The byline here is the page's own.
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        # Every parser is asked authors_found() on every DOI page, so the claim goes first and stays cheap (#2239's
        # per-page CPU rule): the page's first citation_publisher tag, looked for in the small <head>, and in the rest
        # of the page only when the head has none (lxml moves a broken head's tags into the body: 1 page in 300 from
        # other templates). The answer is kept: authors_found(), parse() and the caller all ask (oxjob #2268).
        if getattr(self, '_claimed', None) is None:
            head = self.soup.head
            meta = head.find('meta', attrs={'name': _PUBLISHER_TAG}) if head is not None else None
            if meta is None:
                meta = self.soup.find('meta', attrs={'name': _PUBLISHER_TAG})
            self._claimed = meta is not None and 'Trans Tech' in meta['content']
        return self._claimed

    def authors_found(self):
        # The claim first: on a page with no "Authors" this search reads .text on every tag (2.8 ms a page). A page
        # this parser does not claim never takes its byline, which has no affiliations (oxjob #2268).
        return self.is_publisher_specific_parser() and bool(self.soup.find(
            lambda tag: 'Authors' in tag.text))

    def parse_authors(self):
        authors = []
        if authors_headings := remove_parents(self.soup.find_all(
            lambda tag: 'Authors' in tag.text)):
            authors_heading = authors_headings[0]
            authors_tags = authors_heading.parent.parent.find_next_sibling().find_all('a')
            for tag in authors_tags:
                if 'author-papers' not in tag['href']:
                    continue
                name = tag.text
                is_corresponding = '*' in tag.next_sibling.text
                authors.append({'name': name, 'affiliations': [], 'is_corresponding': is_corresponding})
        return authors

    def parse_abstract(self):
        return self.soup.select_one('.abstract-block-description p').text

    def parse_references(self):
        """The page's reference list (div.references-block, one div.reference-text per entry): (references, complete).
        Whole only when every entry is numbered and the numbers run 1..n, and the page's citation_reference tags, when
        it has them, count the same entries (oxjob #2268)."""
        # imported here: back_matter imports this package's utils, which imports every parser
        from parseland_lib.back_matter import _clean_doi, _pick_doi, _printed_doi
        refs, numbers = [], []
        for position, entry in enumerate(self.soup.select('.references-block .reference-text'), start=1):
            first = entry.find('p')
            if first is None:
                numbers.append(None)
                continue
            first = copy.copy(first)  # the other parsers still read this soup
            label = first.find('span')
            number = _LABEL.match(label.get_text(strip=True)) if label else None
            numbers.append(int(number.group(1)) if number else None)
            if number:
                label.decompose()
            raw = squash(first.get_text())
            if not raw:
                continue
            link = next((a for a in entry.find_all('a', href=True)
                         if 'doi.org/10.' in a['href'] and 'scholar' not in a['href']), None)
            linked = _clean_doi(unquote(link['href'])) if link is not None else None
            refs.append({'position': position, 'raw': raw, 'doi': _pick_doi(linked, _printed_doi(raw))})
        if not refs:
            return None, False
        tags = len(self.soup.find_all('meta', attrs={'name': 'citation_reference'}))
        complete = (len(refs) == len(numbers) and numbers == list(range(1, len(numbers) + 1))
                    and tags in (0, len(numbers)))
        return refs, complete

    def parse(self):
        result = {'authors': self.parse_authors(), 'abstract': self.parse_abstract()}
        if not self.is_publisher_specific_parser():
            return result  # the dispatcher runs parse() on most pages; only a claimed page's list is ours
        references, complete = self.parse_references()
        if references:
            result['references'] = references
            result['references_complete'] = complete
        return result
