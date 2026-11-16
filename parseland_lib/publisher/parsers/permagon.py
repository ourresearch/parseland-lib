from parseland_lib.publisher.parsers.parser import PublisherParser, silverchair_corresponding_cards
from parseland_lib.publisher.parsers.utils import names_match


class PermagonPress(PublisherParser):
    parser_name = "permagon_press"

    def is_publisher_specific_parser(self):
        if publisher_meta := self.soup.select_one('meta[name=citation_publisher]'):
            return 'iwa publishing' in publisher_meta['content'].lower()
        return self.domain_in_canonical_link('iwaponline.com')

    def authors_found(self):
        return bool(self.soup.select('.al-author-name'))

    def parse_authors(self):
        authors = self.parse_author_meta_tags()
        author_tags = self.soup.select('.al-author-name')
        corresponding_tags = {id(tag) for tag in silverchair_corresponding_cards(author_tags)}
        for author_tag in author_tags:
            name = author_tag.select_one('.info-card-name').text.strip('\r\n *')
            is_corresponding = id(author_tag) in corresponding_tags
            for author in authors:
                if names_match(author['name'], name):
                    author['is_corresponding'] = is_corresponding
        return authors

    def parse(self):
        return {'authors': self.parse_authors(),
                'abstract': self.parse_abstract_meta_tags()}
