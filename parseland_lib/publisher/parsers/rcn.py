import re

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import email_matches_name, strip_suffix

_ACKNOWLEDGMENTS = re.compile(r"^\s*acknowledge?ments?\s*:?\s*$", re.I)
# the page's section (meta dcterms:subject) for a piece of opinion writing, which has no abstract (#2239)
_OPINION = re.compile(r"^(?:opinion|comment|commentary|viewpoint|editorial)s?$", re.I)


def _squash(text):
    return " ".join(text.split())


class RoyalCollegeOfNursing(PublisherParser):
    """RCNi's journals (journals.rcni.com): one template for every year, 1987 to 2026 (oxjob #2330).

    The byline block follows the <h1> (news items credit no one and have none); then one or two <abstract> elements,
    read together: a standfirst and the opening paragraph, both shown as the abstract.
    Research articles add <strong>-headed notes after the citation line (Correspondence, Acknowledgements).
    """
    parser_name = "royal_college_of_nursing"

    def is_publisher_specific_parser(self):
        # Cheap marker first (#2239: every parser's claim runs on every DOI page): a <head> meta tag naming rcni.com
        # (dcterms.identifier, twitter:url), never a whole-document search; a page with no <head> still gets one.
        # Cached: the dispatcher calls authors_found() and then this on the same instance.
        claim = self.__dict__.get("_claim")
        if claim is None:
            scope = self.soup.head or self.soup
            claim = self._claim = scope.select_one('meta[content*="rcni.com"]') is not None
        return claim

    def _byline(self):
        return self.soup.select_one('h1 + .mar-bot-15')

    def authors_found(self):
        # the byline, or on a news item that credits no one, its abstract
        return self.is_publisher_specific_parser() and bool(self._byline() or self.soup.find("abstract"))

    def parse_authors(self):
        byline = self._byline()
        if byline is None:
            return []
        corr_email = ''
        if corr_email_tag := self.soup.select_one('meta[name=correspondence]'):
            corr_email = corr_email_tag.get('content') or ''
        authors = []
        for author_tag in byline.find_all(recursive=False):
            name_tag = author_tag.find('strong')
            if name_tag is None:
                continue  # an empty row (<h6><br></h6>)
            name = _squash(strip_suffix(r'@\w+', name_tag.get_text().strip()))
            if not name:
                continue
            # the text beside the name, read without editing the page (the soup is shared with the other parsers)
            aff = _squash("".join(s for s in author_tag.find_all(string=True)
                                  if not any(p is name_tag for p in s.parents)))
            aff = aff.strip(" ,;")
            authors.append({'name': name, 'affiliations': [aff] if aff else [],
                            'is_corresponding': bool(corr_email) and email_matches_name(corr_email, name)})
        return authors

    def parse_abstract(self):
        blocks = []
        for tag in self.soup.find_all('abstract'):
            paras = [_squash(p.get_text()) for p in tag.find_all('p')] or [_squash(tag.get_text())]
            if (text := "\n".join(p for p in paras if p)) and text not in blocks:
                blocks.append(text)
        # Two blocks are a standfirst ("Simon Rippon and Malcolm Rae outline ...") and the opening paragraph; the page
        # shows both as the abstract and both blind labellers read both (#2330 fresh set: 5 of 6 such pages), so keep both.
        # An opinion piece has no abstract: its second block is the body's first paragraph cut off by the paywall
        # ("THE PEOPLE HAVE SPOKEN ... (Table 1)."), so only the standfirst is read (10.7748/nm.10.3.10.s10, #2239).
        if len(blocks) > 1 and self._is_opinion():
            blocks = blocks[:1]
        return "\n".join(blocks) or None

    def _is_opinion(self):
        tag = self.soup.find('meta', attrs={'name': 'dcterms:subject'})
        return tag is not None and _OPINION.match(_squash(tag.get('content') or '')) is not None

    def parse_acknowledgments(self):
        for label in self.soup.find_all('strong', string=_ACKNOWLEDGMENTS):
            if (note := label.find_next_sibling()) is not None and note.name == 'p':
                if text := _squash(note.get_text()):
                    return text
        return None

    def parse(self):
        return {'authors': self.parse_authors(),
                'abstract': self.parse_abstract(),
                'acknowledgments': self.parse_acknowledgments(),
                'funding_statement': None}
