import re
from urllib.parse import urlparse

from parseland_lib.legacy_parse_utils.resolved_url import get_base_url_from_soup
from parseland_lib.legacy_parse_utils.pdf import trust_publisher_license, \
    find_normalized_license, DuckLink, get_link_target, clean_pdf_url, \
    find_repo_version, find_pdf_link, discard_pdf_url, find_doc_download_link, \
    try_pdf_link_as_doc, find_bhl_view_link
from parseland_lib.legacy_parse_utils.version_and_license import \
    page_potential_license_text, detect_sd_author_manuscript, detect_bronze, \
    detect_hybrid
from parseland_lib.legacy_parse_utils.strings import cleanup_soup


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

    pdf_url = get_link_target(pdf_link.href, resolved_url) if pdf_link is not None else None
    _, pdf_link = clean_pdf_url(pdf_url, pdf_link) if pdf_url else (None, None)

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
    if pdf_download_link:
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