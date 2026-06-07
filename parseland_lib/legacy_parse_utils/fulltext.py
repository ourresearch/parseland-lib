import html
import re
from urllib.parse import urlparse, urlsplit, urlunsplit

from parseland_lib.legacy_parse_utils.resolved_url import get_base_url_from_soup
from parseland_lib.legacy_parse_utils.pdf import trust_publisher_license, \
    find_normalized_license, DuckLink, get_link_target, clean_pdf_url, \
    find_repo_version, find_pdf_link, discard_pdf_url, find_doc_download_link, \
    try_pdf_link_as_doc, find_bhl_view_link
from parseland_lib.legacy_parse_utils.version_and_license import \
    page_potential_license_text, detect_sd_author_manuscript, detect_bronze, \
    detect_hybrid
from parseland_lib.legacy_parse_utils.strings import cleanup_soup


# Lippincott / Wolters Kluwer (journals.lww.com) embeds the article PDF as a
# downloadpdf.aspx link in the page markup but emits no citation_pdf_url meta
# tag, so the generic find_pdf_link misses it entirely. The an= (article
# number) query param identifies the resource; trckng_src_pg is a tracking
# param. We take the first downloadpdf.aspx URL in the markup.
_LWW_PDF_RE = re.compile(
    r'https://journals\.lww\.com/[^\s"\'<>]*?/oaks\.journals/downloadpdf\.aspx\?[^\s"\'<>]*',
    re.I,
)


def find_lww_pdf_link(page_with_scripts):
    """Return the LWW downloadpdf.aspx URL from page markup, or None."""
    match = _LWW_PDF_RE.search(page_with_scripts or '')
    if not match:
        return None
    # The URL is HTML-escaped in markup (&amp; -> &). Unescape, then trim any
    # trailing escaped-entity / delimiter junk the greedy class may capture.
    url = html.unescape(match.group(0))
    url = re.split(r'["\'<>\\]|&quot;', url)[0]
    return url


# Cambridge University Press (cambridge.org) journal pages expose the PDF via a
# citation_pdf_url meta tag (handled by find_pdf_link), but Cambridge eBook
# (cbo*) chapter pages have no such meta and no PDF anchor — the
# aop-cambridge-core/content/view/<hash>/<file>.pdf link only appears inside a
# script/JSON blob. Pull it from the markup and resolve to the canonical host.
_CUP_PDF_RE = re.compile(
    r'/core/services/aop-cambridge-core/content/view/[^\s"\'<>\\)]+\.pdf',
    re.I,
)

_DE_GRUYTER_DOCUMENT_RE = re.compile(
    r"^https?://(?:www\.)?degruyter(?:brill)?\.com"
    r"(?P<path>/document/doi/10\.[^\s\"'<>?#]+/html)/?(?:[?#].*)?$",
    re.I,
)

_DE_GRUYTER_PDF_PATH_RE = re.compile(
    r"(?P<prefix>/document/doi/10\.[^\s\"'<>?#]+/pdf)(?:/(?:firstPage))?/?$",
    re.I,
)


def find_cup_pdf_link(page_with_scripts):
    """Return the Cambridge Core aop PDF URL from page markup, or None."""
    match = _CUP_PDF_RE.search(page_with_scripts or '')
    if not match:
        return None
    return 'https://www.cambridge.org' + html.unescape(match.group(0))


def normalize_de_gruyter_pdf_url(url):
    """Return De Gruyter document PDFs on the stable degruyterbrill host."""
    if not url:
        return url
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    host = parts.netloc.lower().removeprefix("www.")
    if host not in {"degruyter.com", "degruyterbrill.com"}:
        return url
    path = _DE_GRUYTER_PDF_PATH_RE.sub(r"\g<prefix>", parts.path)
    if path == parts.path and not re.search(r"/document/doi/10\..*/pdf/?$", path, re.I):
        return url
    return urlunsplit(("https", "www.degruyterbrill.com", path.rstrip("/"), "", ""))


def find_de_gruyter_pdf_link(soup):
    """Construct De Gruyter's DOI-scoped PDF URL from document page metadata.

    Many De Gruyter/Brill pages expose the article/chapter as
    /document/doi/<doi>/html and render the PDF viewer from scripts or a
    non-anchor .pdf-container, so the generic anchor scanner has no link to
    pick. The PDF route is the same DOI-scoped document path with /pdf.
    """
    for tag in (
        soup.select_one('link[rel="canonical"]'),
        soup.select_one('meta[property="og:url"]'),
        soup.select_one('meta[name="og:url"]'),
    ):
        if not tag:
            continue
        raw = (tag.get("href") if tag.name == "link" else tag.get("content")) or ""
        match = _DE_GRUYTER_DOCUMENT_RE.match(raw.strip())
        if match:
            return normalize_de_gruyter_pdf_url(
                "https://www.degruyterbrill.com"
                + match.group("path")[:-len("/html")]
                + "/pdf"
            )

    container = soup.select_one(".pdf-container[data-url]")
    if container and (data_url := container.get("data-url")):
        return normalize_de_gruyter_pdf_url(
            "https://www.degruyterbrill.com" + data_url.split("?", 1)[0]
        )
    return None


def _doi_router_relative_pdf_base(pdf_href, resolved_url):
    """Recover publisher hosts for relative DOI PDF links.

    When eval callers only know the DOI-router URL, relative links such as
    /doi/pdf/10.1080/... otherwise join against doi.org and become
    https://doi.org/doi/pdf/... . Only adjust links already selected as PDFs.
    """
    if not pdf_href or not resolved_url:
        return resolved_url
    if urlparse(pdf_href).scheme or not pdf_href.startswith('/doi/'):
        return resolved_url
    host = urlparse(resolved_url).hostname or ''
    if host not in {'doi.org', 'dx.doi.org', 'www.doi.org'}:
        return resolved_url

    href_lower = pdf_href.lower()
    doi_match = re.search(r'/doi/(?:pdfdirect|pdf|epdf)/(10\.[^?&#]+)', href_lower)
    doi = doi_match.group(1) if doi_match else ''

    if '/doi/pdfdirect/' in href_lower or doi.startswith(('10.1002/', '10.1111/')):
        return 'https://onlinelibrary.wiley.com'
    if doi.startswith(('10.1080/', '10.3109/', '10.4324/', '10.1201/', '10.1517/')):
        return 'https://www.tandfonline.com'
    if doi.startswith('10.1177/'):
        return 'https://journals.sagepub.com'
    if doi.startswith('10.1021/'):
        return 'https://pubs.acs.org'

    return resolved_url


def parse_publisher_fulltext_location(soup, resolved_url):
    cleaned_soup = cleanup_soup(soup)
    detected_resolved_url = get_base_url_from_soup(soup)
    if not resolved_url:
        resolved_url = detected_resolved_url
    resolved_host = urlparse(resolved_url).hostname or ''
    soup_str = str(soup)
    license_search_substr = page_potential_license_text(soup_str)
    version = 'publishedVersion'
    open_version_source_string, oa_status, license = None, None, trust_publisher_license(
        resolved_url) and find_normalized_license(license_search_substr)
    def is_ojs_full_index(soup):
        ojs_meta = soup.find('meta', {'name': 'generator',
                                      'content': re.compile(
                                          r'^Open Journal Systems')})
        if ojs_meta is not None:
            main_article_elements = soup.select(
                'div[role="main"] li a[id^="article-"]')
            return len(main_article_elements) > 1

    if is_ojs_full_index(cleaned_soup):
        return None

    pdf_link = None

    if am_ovs := detect_sd_author_manuscript(soup):
        open_version_source_string = am_ovs
        version = 'acceptedVersion'
        pdf_link = DuckLink(re.sub(
            r'/article/(?:abs/)?pii/', '/article/am/pii/', resolved_url),
            'download')

    pdf_link = find_pdf_link(resolved_url, soup=cleaned_soup,
                             page_with_scripts=soup_str) if not pdf_link else pdf_link

    if pdf_link is None:
        if resolved_host.endswith('ieeexplore.ieee.org') and (
        ieee_pdf := re.search(r'"pdfPath":\s*"(/ielx?7/[\d/]*\.pdf)"',
                              str(soup))):
            pdf_link = DuckLink(
                ieee_pdf.group(1).replace('iel7', 'ielx7'), 'download')
        elif any(resolved_host.endswith(x) for x in
                 ['osf.io', 'psyarxiv.com']):
            pdf_link = DuckLink(get_link_target('download', resolved_url),
                                'download')
        elif am_ovs := detect_sd_author_manuscript(soup):
            open_version_source_string = am_ovs
            version = 'acceptedVersion'
            pdf_link = DuckLink(resolved_url.replace(
                '/article/pii/', '/article/am/pii/'), 'download')
        elif resolved_host.endswith('journals.lww.com') and (
                lww_pdf := find_lww_pdf_link(soup_str)):
            pdf_link = DuckLink(lww_pdf, 'download')
        elif resolved_host.endswith('cambridge.org') and (
                cup_pdf := find_cup_pdf_link(soup_str)):
            pdf_link = DuckLink(cup_pdf, 'download')
        elif resolved_host.endswith(('degruyter.com', 'degruyterbrill.com')) and (
                de_gruyter_pdf := find_de_gruyter_pdf_link(soup)):
            pdf_link = DuckLink(de_gruyter_pdf, 'De Gruyter document PDF')

    if pdf_link is not None:
        pdf_base_url = _doi_router_relative_pdf_base(pdf_link.href, resolved_url)
        pdf_url = get_link_target(pdf_link.href, pdf_base_url)
    else:
        pdf_url = None
    _, pdf_link = clean_pdf_url(pdf_url, pdf_link) if pdf_url else (None, None)
    pdf_url = normalize_de_gruyter_pdf_url(pdf_url)

    if bronze_ovs := detect_bronze(soup, resolved_url):
        open_version_source_string = bronze_ovs
        oa_status = 'bronze'

    if (hybrid_parse := detect_hybrid(soup, license_search_substr, resolved_url)) and \
            hybrid_parse[0] is not None and open_version_source_string is None:
        open_version_source_string, license = hybrid_parse
        oa_status = 'hybrid'

    # ensure pdf_url starts with http
    if pdf_url and not pdf_url.startswith('http'):
        pdf_url = None

    return {'pdf_url': pdf_url,
             'open_version_source_string': open_version_source_string,
             'license': license,
             'oa_status': oa_status,
             'version': version
             }


def parse_repo_fulltext_location(soup, resolved_url):
    soup_str = str(soup)
    if not resolved_url:
        resolved_url = get_base_url_from_soup(soup)

    # license
    license_search_substr = page_potential_license_text(soup_str)
    license = find_normalized_license(license_search_substr)

    # version
    version = find_repo_version(soup_str)

    # fulltext url
    pdf_url = None
    doc_url = None
    pdf_download_link = find_pdf_link(resolved_url, soup, page_with_scripts=soup_str)
    if pdf_download_link is not None:
        pdf_url = get_link_target(pdf_download_link.href, resolved_url) if hasattr(pdf_download_link, 'href') else None

    doc_link = find_doc_download_link(soup_str)
    if doc_link is None and try_pdf_link_as_doc(resolved_url):
        doc_link = pdf_download_link

        if doc_link:
            doc_url = get_link_target(doc_link.href, resolved_url)

    bhl_link = find_bhl_view_link(resolved_url, soup)
    if bhl_link:
        doc_url = bhl_link.href

    pdf_url = pdf_url or doc_url
    return {
        'pdf_url': pdf_url,
        'license': license,
        'version': version
    }
