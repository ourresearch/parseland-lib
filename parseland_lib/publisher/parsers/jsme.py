import re

from parseland_lib.publisher.parsers.parser import PublisherParser

# A reference's own number at the start of its text: "(1) ", "1) ", "1. ", "[1] ". Stripped only when it equals
# the entry's position, so a year or a volume number at the start of a reference is never taken for one.
_LEADING_NUMBER = re.compile(r'^\s*(?:\((\d{1,4})\)|\[(\d{1,4})\]|(\d{1,4})\s*[.)])\s*')
_DOI = re.compile(r'\b(10\.\d{4,9}/[^\s"<>]+)')
_STATED_COUNT = re.compile(r'\((\d{1,5})\)\s*$')


class JSME(PublisherParser):
    """J-STAGE (www.jstage.jst.go.jp) article pages, every society on the platform."""
    parser_name = "japan_society_of_mechanical_engineers"

    def is_publisher_specific_parser(self):
        return self.domain_in_meta_og_url('www.jstage')

    def authors_found(self):
        return bool(self.soup.select('.global-authors-name-tags a'))

    def parse_abstract(self):
        p_tags = self.soup.select('#article-overiew-abstract-wrap p')
        for tag in p_tags:
            if len(tag.text) > 3:
                return tag.text
        return None

    def stated_reference_count(self):
        """The length J-STAGE states for the list: the article menu's 'References (9)' / '引用文献 (9)' link, or the
        (hidden) heading of the references section."""
        for tag in (self.soup.select('a[href="#article-overiew-references-wrap"]')
                    + self.soup.select('#article-overiew-references-wrap .section-title-18')):
            m = _STATED_COUNT.search(tag.get_text(' ', strip=True))
            if m:
                return int(m.group(1))
        return None

    def parse_references(self):
        """(references, references_complete), oxjob #2223 under #2215's contract. J-STAGE prints the list only in
        citation_reference meta tags (the page's own list is filled in by script). Complete only when the count the
        page states equals the tags read."""
        raws = [m.get('content', '').strip() for m in self.soup.select('meta[name="citation_reference"]')]
        raws = [r for r in raws if r]
        if not raws:
            return None, False
        references, numbers = [], []
        for position, raw in enumerate(raws, start=1):
            m = _LEADING_NUMBER.match(raw)
            number = int(next(g for g in m.groups() if g)) if m else None
            numbers.append(number)
            if number == position:
                raw = raw[m.end():].strip()
            doi = _DOI.search(raw)
            references.append({'position': position, 'raw': raw,
                               'doi': doi.group(1).rstrip('.,;)]') if doi else None})
        # Whole only on positive evidence: the stated count equals the tags, and the entries' own numbers, when they
        # carry any, run 1..n. Gaps (a paper's notes numbered with its references) or one reference split over two
        # tags ('2)' at position 3) mean the tags are not one entry per reference: not provably whole.
        numbered_in_order = all(n is None for n in numbers) or numbers == list(range(1, len(numbers) + 1))
        return references, self.stated_reference_count() == len(references) and numbered_in_order

    def parse(self):
        authors = self.parse_author_meta_tags()
        author_tags = self.soup.select('.global-authors-name-tags a')
        for author_tag in author_tags:
            if '*' in author_tag.text:
                for author in authors:
                    if author['name'] in author_tag.text:
                        author['is_corresponding'] = True
        references, references_complete = self.parse_references()
        return {'authors': authors, 'abstract': self.parse_abstract(),
                'acknowledgments': None, 'funding_statement': None,
                'references': references, 'references_complete': references_complete}
