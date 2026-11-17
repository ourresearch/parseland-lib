import re

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import is_h_tag

# A standard reprinted in a symposium volume prints the standard's own preamble where a paper prints its abstract
# ("This Standard of the American Society for Testing and Materials is issued under the fixed designation D 1159; ...").
_STANDARD_PREAMBLE = re.compile(r"\bis issued under the fixed designation\b", re.I)


class ASMInternational(PublisherParser):
    parser_name = "asm_international"

    def __init__(self, soup):
        super().__init__(soup)
        self._claimed = None

    def is_publisher_specific_parser(self):
        # Every DOI page asks every parser's authors_found() (#2239: under 0.5 ms a page it does not claim), so the
        # claim is the og:url tag looked for in <head> alone, reached through direct children; nothing walks the
        # whole page before it passes. The answer is kept: authors_found(), parse() and the caller all ask (#2330).
        if self._claimed is None:
            html = self.soup.find("html", recursive=False)
            head = (html or self.soup).find("head", recursive=False)
            meta = None
            if head is not None:
                meta = head.find("meta", property="og:url") or head.find("meta", attrs={"name": "og:url"})
            url = (meta.get("content") or "") if meta is not None else ""
            self._claimed = "astm.org" in url or "asme.org" in url
        return self._claimed

    def authors_found(self):
        # The claim first: the searches below read every tag of the page (oxjob #2330).
        return bool(self.is_publisher_specific_parser() and (
            self._author_heading() or self.soup.select('.al-author-name')))

    def _author_heading(self):
        return self.soup.find(lambda tag: is_h_tag(tag) and 'Author Information' in tag.text)

    def parse_authors(self, author_heading=None):
        author_heading = author_heading or self._author_heading()
        authors = []
        for author_tag in author_heading.find_next_siblings('div'):
            author = {'name': None, 'affiliations': [], 'is_corresponding': None}
            for i, child in enumerate(author_tag.children):
                if len(child.text.strip()) < 3:
                    continue
                if author['name'] is None:
                    author['name'] = child.text
                else:
                    author['affiliations'].append(child.text.strip())
            authors.append(author)
        return authors

    def parse_abstract(self):
        if abs_heading := self.soup.find(lambda tag: is_h_tag(tag) and 'Abstract' in tag.text):
            abs_tag = abs_heading.find_next_sibling('div')
            return abs_tag.find('p').text
        return None

    @staticmethod
    def parse_lead_abstract(author_heading):
        """A symposia paper's or book chapter's abstract: astm.org prints it with no heading, in the lead block between
        the title and "Author Information" (journal articles head theirs "Abstract") (oxjob #2330)."""
        block = author_heading.parent.find_previous_sibling('div') if author_heading is not None else None
        classes = (block.get('class') or []) if block is not None else []
        if 'astm-type-body--lead' not in classes or 'border-top' not in classes:
            return None
        paragraphs = [' '.join(p.get_text().split()) for p in block.find_all('p')] or [' '.join(block.get_text().split())]
        text = '\n'.join(p for p in paragraphs if p)
        if not text or _STANDARD_PREAMBLE.search(text):
            return None
        return text

    def get_asme_corresponding_author(self):
        for author_tag in self.soup.select('.al-author-name'):
            if 'Corresponding author' in author_tag.text:
                return author_tag.find('a').text.strip()
        return None

    def parse(self):
        if self.domain_in_meta_og_url('asme.org'):
            authors = self.parse_author_meta_tags()
            if corr_author := self.get_asme_corresponding_author():
                split = [part.strip() for part in re.split(r'\W', corr_author)]
                for author in authors:
                    if all([part.lower() in author['name'].lower() for part in split]):
                        author['is_corresponding'] = True
            return {'authors': authors, 'abstract': self.parse_abstract_meta_tags()}
        author_heading = self._author_heading()
        return {'authors': self.parse_authors(author_heading),
                'abstract': self.parse_abstract() or self.parse_lead_abstract(author_heading)}
