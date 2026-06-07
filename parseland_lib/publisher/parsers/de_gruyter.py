import re

from parseland_lib.publisher.parsers.parser import PublisherParser


class DeGruyter(PublisherParser):
    parser_name = "de_gruyter"

    def is_publisher_specific_parser(self):
        return self.domain_in_meta_og_url('degruyter.com')

    def authors_found(self):
        return bool(self.soup.select('span.contributor'))

    def parse_authors(self):
        author_tags = self.soup.select('span.contributor')
        authors = []
        for author_tag in author_tags:
            name = author_tag.text.strip('\n ')
            if cont_popdown := author_tag.select_one('contributor-popdown'):
                is_corresponding = bool(cont_popdown.get('email', ''))
                affiliations = [aff for aff in cont_popdown.get('affiliations', '').split(';') if aff]
            else:
                is_corresponding = '@' in author_tag.get('title', '')
                affiliations = [aff for aff in author_tag.get('title', '').split(';') if '@' not in aff and aff]

            authors.append({
                'name': name,
                'is_corresponding': is_corresponding,
                'affiliations': affiliations
            })
        return authors

    def parse_abstract(self):
        paragraphs = self.soup.select('section[id*=_abs_] p')
        if paragraphs:
            text = self.clean_abstract_text(
                ' '.join([p.get_text(' ', strip=True) for p in paragraphs])
            )
            if text:
                return text

        if text := self.parse_abstract_meta_tags():
            return self.clean_abstract_text(text)

        if abstract_tag := self.soup.select_one('div.abstract'):
            text = self.clean_abstract_text(abstract_tag.get_text(' ', strip=True))
            if text:
                return text

        if text_container := self.soup.select_one('div#text-container'):
            raw_text = text_container.get_text(' ', strip=True)
            if re.match(
                    r'^(showing a limited preview of this publication:\s*)?'
                    r'(abstract|zusammenfassung)\b',
                    raw_text,
                    flags=re.I,
            ):
                text = self.clean_abstract_text(raw_text)
                if text and len(text) < 5000:
                    return text

        return None

    @staticmethod
    def clean_abstract_text(text):
        text = re.sub(r'\s+', ' ', text or '').strip()
        text = re.sub(
            r'^showing a limited preview of this publication:\s*',
            '',
            text,
            flags=re.I,
        )
        text = re.sub(
            r'^(abstract|zusammenfassung)\s*[:.]?\s*',
            '',
            text,
            flags=re.I,
        )
        return text or None

    def parse(self):
        return {'authors': self.parse_authors(),
                'abstract': self.parse_abstract()}
