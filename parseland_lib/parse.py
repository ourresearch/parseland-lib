from urllib.parse import urlparse

from bs4 import BeautifulSoup

from parseland_lib.legacy_parse_utils.fulltext import parse_publisher_fulltext_location
from parseland_lib.legacy_parse_utils.fulltext import parse_repo_fulltext_location
from parseland_lib.parse_publisher_authors_abstract import get_authors_and_abstract


def _is_doi_router_url(url):
    """True for bare DOI router URLs (doi.org / dx.doi.org)."""
    if not url:
        return False
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return False
    return host in ("doi.org", "dx.doi.org", "www.doi.org")


def _sniff_publisher_url(soup):
    """Try to recover the actual publisher landing-page URL from the HTML.

    Looks at <link rel="canonical">, then <meta property="og:url">. Returns
    None if neither is present or both still point at doi.org (some publishers
    set canonical to the DOI link).
    """
    try:
        canonical = soup.find("link", attrs={"rel": "canonical"})
        if canonical and canonical.get("href"):
            href = canonical.get("href").strip()
            if href and not _is_doi_router_url(href):
                return href
    except Exception:
        pass
    try:
        og = soup.find("meta", attrs={"property": "og:url"})
        if og and og.get("content"):
            href = og.get("content").strip()
            if href and not _is_doi_router_url(href):
                return href
    except Exception:
        pass
    return None


def parse_page(lp_content, namespace, resolved_url=None):
    soup = BeautifulSoup(lp_content, parser='lxml', features='lxml')

    # If the caller passed a bare doi.org link, the relative-PDF-URL joiner
    # downstream produces broken hosts like https://doi.org/doi/pdf/... .
    # Sniff the HTML's canonical / og:url meta to recover the actual landing
    # URL. Falls through to the original resolved_url if neither is present.
    if namespace == "doi" and _is_doi_router_url(resolved_url):
        sniffed = _sniff_publisher_url(soup)
        if sniffed:
            resolved_url = sniffed

    raw_authors_and_abstract = get_authors_and_abstract(soup, namespace)
    if namespace == "doi":
        fulltext_location = parse_publisher_fulltext_location(soup, resolved_url)
    elif namespace == "pmh":
        fulltext_location = parse_repo_fulltext_location(soup, resolved_url)
    else:
        fulltext_location = None

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

def find_pdf_link(lp_content, namespace, resolved_url):
    soup = BeautifulSoup(lp_content, parser='lxml', features='lxml')
    if namespace == "doi":
        fulltext_location = parse_publisher_fulltext_location(soup, resolved_url)
    elif namespace == "pmh":
        fulltext_location = parse_repo_fulltext_location(soup, resolved_url)
    else:
        fulltext_location = None
    return fulltext_location.get("pdf_url") if fulltext_location else None
