from parseland_lib.legacy_parse_utils.fulltext import parse_publisher_fulltext_location
from parseland_lib.parse_publisher_authors_abstract import get_authors_and_abstract

def parse_page(lp_content):
    authors_and_abstract = get_authors_and_abstract(lp_content)
    fulltext_location = parse_publisher_fulltext_location(lp_content)

    # reformat
    if authors_and_abstract and 'authors' in authors_and_abstract:
        authors_and_abstract['authors'] = [
            {
                'name': author.name,
                'affiliations': [{'name': aff} for aff in author.affiliations],
                'is_corresponding': author.is_corresponding
            }
            for author in authors_and_abstract['authors']
        ]
    else:
        authors_and_abstract = {'authors': [], 'abstract': None}

    # merge into a single response
    response = authors_and_abstract
    response.update(fulltext_location)

    return response
