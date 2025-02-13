from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser


def get_authors_and_abstract(soup):
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
                return parsed
        except Exception as e:
            continue

    for parser in authors_found_parsers:
        try:
            parsed = parser.parse()
            if has_affs(parsed):
                return parsed
        except Exception as e:
            continue

    generic_parser = GenericPublisherParser(soup)
    if generic_parser.authors_found():
        return generic_parser.parse()

    return None