import re

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import strip_suffix

_OWN_LABEL = re.compile(r"\bcorresponding\s+authors?\b", re.I)
_EMAIL = 'a[property=email], a[href*="email-protection"], a[href^="mailto:"]'


class AmericanSocietyOfCivilEngineers(PublisherParser):
    parser_name = "american_society_of_civil_engineers"

    def is_publisher_specific_parser(self):
        return self.domain_in_meta_og_url('ascelibrary.org')

    def authors_found(self):
        return bool(self.soup.select('.author-block')) or bool(self.core_author_blocks())

    def core_author_blocks(self):
        """The 2022 Literatum "core" template's author blocks (oxjob #2288)."""
        return self.soup.select('div[property=author]:has(span)')

    def parse_authors(self):
        author_tags = self.soup.select('.author-block')
        authors = []
        for author_tag in author_tags:
            name = author_tag.select_one('.authorName').text
            is_corresponding = 'corresponding author' in author_tag.text.lower()
            affs_tag = author_tag.select_one('.authorAffiliation')
            for email_tag in affs_tag.select('a[href*=email-protection]'):
                email_tag.decompose()
            affs = [strip_suffix('\W', aff.split('Email')[0].replace('(corresponding author)', '')) for aff in affs_tag.text.split(';')]
            affs = [aff.strip('(). ').replace(' . ', '. ') for aff in affs if len(aff) > 3]
            author = {'name': name, 'affiliations': affs, 'is_corresponding': is_corresponding}
            authors.append(author)
        return authors

    def parse_core_authors(self):
        """Authors on the core template (oxjob #2288). No ASCE reader claimed it, so the AAAS parser won these pages and
        took the <sup> in every block, the affiliation's number, for a mark: every author came out corresponding.
        Names and affiliations are read as the AAAS parser read them; the flag is what the page marks (#1791 label-v1):
        the "(corresponding author)" label, else an e-mail tied to some authors only. An e-mail on every one of two or
        more authors (most conference papers) marks no one."""
        blocks = self.core_author_blocks()
        labelled = [bool(_OWN_LABEL.search(tag.get_text(" "))) for tag in blocks]
        if any(labelled):
            marked = labelled  # a label on every author marks them all
        else:
            emailed = [bool(tag.select_one(_EMAIL)) or 'Email:' in tag.get_text() for tag in blocks]
            marked = emailed if len(blocks) == 1 or not all(emailed) else [False] * len(blocks)
        return [{'name': f"{tag.select_one('span[property=givenName]').text} "
                         f"{tag.select_one('span[property=familyName]').text}",
                 'affiliations': [aff_tag.text for aff_tag in tag.select('div[property=affiliation]')],
                 'is_corresponding': is_marked}
                for tag, is_marked in zip(blocks, marked)]

    def parse_abstract(self):
        if abs_tag := self.soup.select_one('div[class*=Abstract] p'):
            return abs_tag.text
        return None

    def parse(self):
        if self.soup.select('.author-block'):
            return {'authors': self.parse_authors(), 'abstract': self.parse_abstract()}
        # the core template's abstract block, as the AAAS parser read it (oxjob #2288)
        abs_tag = self.soup.select_one('section#abstract div')
        return {'authors': self.parse_core_authors(), 'abstract': abs_tag.text if abs_tag else None}
