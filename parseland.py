from bs4 import BeautifulSoup

from exceptions import ParserNotFoundError
from parsers.generic import GenericPublisherParser
from parsers.parser import PublisherParser
from s3 import get_landing_page


def _best_parser_msg(soup: BeautifulSoup) -> (PublisherParser, dict):
    both_conditions_parsers = []
    authors_found_parsers = []

    def has_affs(parsed):
        if not parsed['authors']:
            return False
        return any([author['affiliations'] if isinstance(parsed['authors'][0],
                                                         dict) else author.affiliations for author in parsed['authors']])

    for cls in PublisherParser.__subclasses__():
        parser = cls(soup)
        if parser.authors_found():
            if parser.is_publisher_specific_parser():
                both_conditions_parsers.append(parser)
            else:
                authors_found_parsers.append(parser)

    for parser in both_conditions_parsers:
        try:
            parsed = parser.parse()
            if has_affs(parsed):
                return parser, parsed
        except Exception as e:
            continue

    for parser in authors_found_parsers:
        try:
            parsed = parser.parse()
            if has_affs(parsed):
                return parser, parsed
        except Exception as e:
            continue

    generic_parser = GenericPublisherParser(soup)
    if generic_parser.authors_found():
        return generic_parser, generic_parser.parse()

    raise ParserNotFoundError(f"Parser not found")

def parse_landing_page(lp_content):
    soup = BeautifulSoup(lp_content, parser='lxml', features='lxml')
    return _best_parser_msg(soup)


def parse_doi(doi, s3=None):
    lp_content = get_landing_page(doi, s3)
    return parse_landing_page(lp_content)



if __name__ == '__main__':
    lp = get_landing_page('10.1016/0003-2697(76)90527-3')
    print(parse_landing_page(lp))