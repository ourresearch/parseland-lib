from bs4 import BeautifulSoup

from parseland_lib.legacy_parse_utils.fulltext import parse_publisher_fulltext_location
from parseland_lib.legacy_parse_utils.fulltext import parse_repo_fulltext_location
from parseland_lib.parse_publisher_authors_abstract import get_authors_and_abstract

def parse_page(lp_content, namespace, resolved_url=None):
    soup = BeautifulSoup(lp_content, parser='lxml', features='lxml')

    raw_authors_and_abstract = get_authors_and_abstract(soup, namespace)
    if namespace == "doi":
        fulltext_location = parse_publisher_fulltext_location(soup, resolved_url)
    elif namespace == "pmh":
        fulltext_location = parse_repo_fulltext_location(soup, resolved_url)

    if raw_authors_and_abstract is None:
        authors_and_abstract = {'authors': [], 'abstract': None}
    elif isinstance(raw_authors_and_abstract, list):
        authors_and_abstract = {'authors': raw_authors_and_abstract, 'abstract': None}
    else:
        authors_and_abstract = raw_authors_and_abstract

    if authors_and_abstract and authors_and_abstract.get('authors'):
        authors = []
        for author in authors_and_abstract['authors']:
            # handle both dict and object formats
            name = author.get("name", "") if isinstance(author, dict) else getattr(author, "name", "")
            affiliations = (
                [{"name": aff} for aff in author.get("affiliations", [])]
                if isinstance(author, dict)
                else [{"name": aff} for aff in getattr(author, "affiliations", [])]
            )
            is_corresponding = (
                author.get("is_corresponding", None)
                if isinstance(author, dict)
                else getattr(author, "is_corresponding", None)
            )
            authors.append({
                "name": name,
                "affiliations": affiliations,
                "is_corresponding": is_corresponding,
            })
        authors_and_abstract['authors'] = authors

    # Merge into a single response
    response = authors_and_abstract
    response.update(fulltext_location or {})

    urls = []
    if response.get("pdf_url"):
        urls.append({"url": response["pdf_url"], "content_type": "pdf"})
    if response.get("resolved_url"):
        urls.append({"url": response["resolved_url"], "content_type": "html"})

    # reorder the response
    ordered_response = {
        "authors": response.get("authors", []),
        "urls": urls,
        "license": response.get("license"),
        "version": response.get("version"),
        "abstract": response.get("abstract"),
    }

    return ordered_response

