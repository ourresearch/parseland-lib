import html
import json
import re

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

# Sciendo's article app (sciendo.com and the society sites it serves) takes every page's og:image from its own S3
# bucket ("sciendo-parsed", "sciendo-parsed-data-feed"), whichever host serves the page (oxjob #2289)
SCIENDO_IMAGE = 'sciendo-parsed'
# a reference's JATS id numbers the publisher's whole list: "j_czoto-2023-0003_ref_004", "j_fas-2016-0008_ref_001_w2aab..."
JATS_REF_NUMBER = re.compile(r'_ref_(\d+)(?:_|$)')
TAGGED_DOI = re.compile(r'<(?:[\w-]+:)?pub-id\b[^>]*\bpub-id-type="doi"[^>]*>([^<]+)<')
LINKED_DOI = re.compile(r'href="((?:https?://)?(?:dx\.)?doi\.org/10\.[^"]+)"')


class DeGruyterOpen(PublisherParser):
    parser_name = "de_gruyter_open"

    def is_publisher_specific_parser(self):
        return bool(self.soup.find(lambda
                                       tag: 'Sciendo is a De Gruyter company'.lower() in tag.text.lower()))

    def is_sciendo_page(self):
        """One <head> tag, before any whole-page search: production asks every parser on every DOI page (#2239)."""
        page = self.soup.find('html', recursive=False)
        head = page.find('head', recursive=False) if page else None
        image = head.find('meta', attrs={'property': 'og:image'}, recursive=False) if head else None
        return bool(image) and SCIENDO_IMAGE in (image.get('content') or '')

    def authors_found(self):
        return self.is_sciendo_page() and bool(self.soup.select('div[class*=author-popup]'))

    def parse_json(self):
        if json_tag := self.soup.select_one('script#__NEXT_DATA__'):
            return json.loads(json_tag.text)
        return {}

    @staticmethod
    def parse_authors(j):
        authors = []
        contrib_group = j['props']['pageProps']['product']['articleData'][
            'contribGroup']
        for author in contrib_group['contrib']:
            name = f'{author["name"]["given-names"]} {author["name"]["surname"]}'
            is_corresponding = 'y' in (author.get('corresp', '') or '')
            affs = []
            aff_id = author['xref']['rid']
            if isinstance(contrib_group['aff'], dict):
                contrib_group['aff'] = [contrib_group['aff']]
            for aff in contrib_group['aff']:
                if aff['id'] == aff_id:
                    if isinstance(aff['institution'], list):
                        desc = ''
                        for item in aff['institution']:
                            if isinstance(item, str):
                                desc += item + ', '
                            elif isinstance(item, dict):
                                desc += item.get('content', '') + ', '
                        affs.append(desc.strip(' ,'))
                    elif isinstance(aff['institution'], str):
                        affs.append(aff['institution'])
            authors.append({
                'name': name,
                'affiliations': affs,
                'is_corresponding': is_corresponding,
            })
        return authors

    @staticmethod
    def parse_references(j):
        """The References tab: `articleData.referenceList`, one entry per reference in page order (oxjob #2289).
        `citeString` is the entry's printed text; its DOI is a JATS pub-id, a doi.org link or printed in the text. The
        list is whole when the entries' JATS ids run 1..n (and any numbers typed into the text do too)."""
        from parseland_lib.back_matter import _clean_doi, _pick_doi, _printed_doi, _without_list_numbers
        article = ((j.get('props') or {}).get('pageProps') or {}).get('product') or {}
        refs = [r for r in (article.get('articleData') or {}).get('referenceList') or [] if isinstance(r, dict)]
        if not refs:
            return {}
        texts, tagged, linked = [], [], []
        for ref in refs:
            markup = ref.get('mixed-citation') or ''
            text = squash(ref.get('citeString'))
            doi = html.unescape(m.group(1)).strip() if (m := TAGGED_DOI.search(markup)) else None
            if doi and text.endswith(doi) and not text[:-len(doi)].endswith(' '):
                text = f'{text[:-len(doi)]} {doi}'  # the citeString glues the tagged DOI to the entry's last page
            texts.append(text)
            tagged.append(_clean_doi(doi))
            linked.append(_clean_doi(html.unescape(m.group(1))) if (m := LINKED_DOI.search(markup)) else None)
        texts, typed_whole = _without_list_numbers(texts)
        numbers = [int(m.group(1)) if (m := JATS_REF_NUMBER.search(r.get('refId') or '')) else None for r in refs]
        return {
            'references': [{'raw': text, 'doi': _pick_doi(t, li, _printed_doi(text))}
                           for text, t, li in zip(texts, tagged, linked)],
            'references_complete': typed_whole and numbers == list(range(1, len(refs) + 1)),
        }

    def parse(self):
        j = self.parse_json()
        return {'authors': self.parse_authors(j), 'abstract': self.parse_abstract_meta_tags(),
                **self.parse_references(j)}
