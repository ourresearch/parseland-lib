from parseland_lib.legacy_parse_utils.fulltext import parse_publisher_fulltext_location
from parseland_lib.parse_publisher_authors_abstract import get_authors_and_abstract

def parse_page(lp_content, resolved_url):
    authors_and_abstract = get_authors_and_abstract(lp_content)
    fulltext_location = parse_publisher_fulltext_location(lp_content, resolved_url)

    # Ensure authors are consistently processed
    if authors_and_abstract and 'authors' in authors_and_abstract:
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
    else:
        authors_and_abstract = {'authors': [], 'abstract': None}

    # Merge into a single response
    response = authors_and_abstract
    response.update(fulltext_location)

    urls = []
    if response.get("pdf_url"):
        urls.append({"url": response["pdf_url"], "content_type": "pdf"})
    if response.get("resolved_url"):
        urls.append({"url": response["resolved_url"], "content_type": "html"})

    # reorder the response
    ordered_response = {
        "authors": response["authors"],
        "urls": urls,
        "license": response["license"],
        "version": response["version"],
        "abstract": response["abstract"],
    }

    return ordered_response

