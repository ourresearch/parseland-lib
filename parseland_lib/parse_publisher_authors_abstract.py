from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.repository.parsers.parser import RepositoryParser


def get_authors_and_abstract(soup, namespace):
    both_conditions_parsers = []
    authors_found_parsers = []

    def has_affs(parsed):
        if isinstance(parsed, list):
            if not parsed:
                return False
            return any(author.get('affiliations') for author in parsed)
        elif isinstance(parsed, dict):
            if not parsed.get('authors'):
                return False
            return any([author['affiliations'] if isinstance(author, dict)
                        else author.affiliations for author in parsed['authors']])
        return False

    if namespace == "doi":
        for cls in PublisherParser.__subclasses__():
            parser = cls(soup)
            try:
                if parser.authors_found():
                    parsed = parser.parse()
                    if parser.is_publisher_specific_parser():
                        both_conditions_parsers.append((parser, parsed))
                    else:
                        authors_found_parsers.append((parser, parsed))
            except Exception:
                continue
    elif namespace == "pmh":
        for cls in RepositoryParser.__subclasses__():
            parser = cls(soup)
            try:
                if parser.is_correct_parser() and parser.authors_found():
                    parsed = parser.parse()
                    authors_found_parsers.append((parser, parsed))
            except Exception:
                continue


    for parser, parsed in both_conditions_parsers:
        if has_affs(parsed):
            return parsed

    for parser, parsed in authors_found_parsers:
        if has_affs(parsed):
            return parsed

    generic_parser = GenericPublisherParser(soup)
    if generic_parser.authors_found():
        print(f"Authors found for generic parser")
        return generic_parser.parse()

    return None