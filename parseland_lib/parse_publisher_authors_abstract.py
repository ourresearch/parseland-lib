import re

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.repository.parsers.parser import RepositoryParser


def _authors_of(parsed):
    return parsed if isinstance(parsed, list) else parsed.get('authors')


def _one_clean_name(author):
    name = author.get('name') if isinstance(author, dict) else getattr(author, 'name', None)
    return bool(name) and not re.search(r"[\d*]", name) and name.count(",") <= 1


def get_authors_and_abstract(soup, namespace):
    both_conditions_parsers = []
    authors_found_parsers = []

    def has_affs(parsed):
        def author_affiliations(author):
            if isinstance(author, dict):
                return author.get('affiliations')
            return getattr(author, 'affiliations', None)

        if isinstance(parsed, list):
            if not parsed:
                return False
            return any(author_affiliations(author) for author in parsed)
        elif isinstance(parsed, dict):
            if not parsed.get('authors'):
                return False
            return any(author_affiliations(author) for author in parsed['authors'])
        return False

    def has_content(parsed):
        if isinstance(parsed, list):
            return bool(parsed)
        if isinstance(parsed, dict):
            return bool(parsed.get('authors') or parsed.get('abstract'))
        return False

    def has_authors(parsed):
        if isinstance(parsed, list):
            return bool(parsed)
        if isinstance(parsed, dict):
            return bool(parsed.get('authors'))
        return False

    if namespace == "doi":
        for cls in PublisherParser.__subclasses__():
            parser = cls(soup)
            try:
                if parser.authors_found():
                    parsed = parser.parse()
                    if parser.is_publisher_specific_parser():
                        both_conditions_parsers.append((parser, parsed))
                        # The first publisher-specific parser with affiliations is the one returned below, so the
                        # parsers after it can't change the answer. Stop here: running them roughly doubled the
                        # time per page, and 2-7 MB open-access ScienceDirect pages ran past the service's worker
                        # timeout (oxjob #1794).
                        if has_affs(parsed):
                            break
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

    for parser, parsed in both_conditions_parsers:
        if (
            getattr(parser, "prefer_publisher_authors_over_generic", False)
            and has_authors(parsed)
        ):
            return parsed

    for parser, parsed in authors_found_parsers:
        if has_affs(parsed):
            return parsed

    for parser, parsed in both_conditions_parsers:
        if has_content(parsed):
            return parsed

    # A record page's own repository parser that found authors but no affiliations (Zenodo's JSON-LD creators) was
    # passed over above for the generic parser, and when that found no one the page lost its authors (#2239 round 8b)
    # Only names that read as one person each: "V.Viswanath1*, T.Niranjan Reddy1" (marks, several people in one
    # creator field) is no author list.
    repository = next((parsed for _, parsed in authors_found_parsers if has_authors(parsed) and all(
        _one_clean_name(author) for author in _authors_of(parsed))), None) if namespace == "pmh" else None

    generic_parser = GenericPublisherParser(soup)
    if generic_parser.authors_found():
        print(f"Authors found for generic parser")
        parsed = generic_parser.parse()
        if repository is not None and not has_authors(parsed):
            if isinstance(parsed, dict):
                return {**parsed, "authors": _authors_of(repository)}
            return repository
        return parsed

    return repository
