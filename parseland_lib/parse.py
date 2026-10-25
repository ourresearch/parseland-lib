from urllib.parse import urlparse

from bs4 import BeautifulSoup

from parseland_lib.legacy_parse_utils.fulltext import parse_publisher_fulltext_location
from parseland_lib.legacy_parse_utils.fulltext import parse_repo_fulltext_location
from parseland_lib.not_abstract import clean_abstract, is_not_abstract
from parseland_lib.parse_publisher_authors_abstract import get_authors_and_abstract
from parseland_lib.publisher.parsers.frontiers import frontiers_corresponding_names
from parseland_lib.publisher.parsers.parser import frontmatter_abstract, silverchair_abstract, \
    silverchair_corresponding_names
from parseland_lib.publisher.parsers.utils import same_person


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


def _mark_corresponding_by_name(authors, names):
    """Fill the corresponding flag from a byline's marks when the winning parser marked no one (#1805).

    For bylines the winning parser can't read marks from: Silverchair (ACS and RSC moved there and no publisher
    parser claims the pages, so the meta-tag parser wins) and old-template Frontiers (the '*' sits outside <sup>).
    Each marked name sets the flag on the one parsed author with that name; a name that matches no author, or more
    than one, is skipped.
    """
    if not authors or any(a["is_corresponding"] for a in authors):
        return
    for name in names:
        matches = [a for a in authors if same_person(a["name"], name)]
        if len(matches) == 1:
            matches[0]["is_corresponding"] = True
    if any(a["is_corresponding"] for a in authors):
        for a in authors:
            if a["is_corresponding"] is None:
                a["is_corresponding"] = False


def _has(content, marker):
    """Cheap raw-bytes check before a whole-tree search (lp_content may be bytes or str)."""
    return (marker.encode() if isinstance(content, (bytes, bytearray)) else marker) in content


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

    # Atypon's front-matter block holds the publisher's full abstract; whichever parser won the page may only
    # have its cut meta tag (RSNA, Neurology: first 200 characters or first section), so a clearly longer
    # front-matter abstract wins (#1800). "Clearly": the block's get_text adds spaces inside inline markup, so a
    # parser's own, equally complete text is a few characters shorter and must stay.
    if (front := frontmatter_abstract(soup)) and not is_not_abstract(front):
        chosen = authors_and_abstract.get('abstract')
        if not chosen or is_not_abstract(chosen) or len(chosen) < 0.8 * len(front):
            authors_and_abstract['abstract'] = front

    # Silverchair's abstract section fills a page the winning parser left without one (pubs.aip.org) (#1800).
    if not authors_and_abstract.get('abstract') or is_not_abstract(authors_and_abstract['abstract']):
        if (silver := silverchair_abstract(soup)) and not is_not_abstract(silver):
            authors_and_abstract['abstract'] = silver

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
        if authors and not any(a["is_corresponding"] for a in authors):
            if _has(lp_content, "al-author-name"):
                _mark_corresponding_by_name(authors, silverchair_corresponding_names(soup))
            elif _has(lp_content, '<div class="authors"') and _has(lp_content, "/10.3389/"):
                _mark_corresponding_by_name(authors, frontiers_corresponding_names(soup))

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
        # one check for every parser: placeholders, site blurbs and SEO templates are not abstracts (#1800)
        "abstract": clean_abstract(response.get("abstract")),
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
