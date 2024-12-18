import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from parseland_lib.legacy_parse_utils.resolved_url import get_base_url_from_soup
from parseland_lib.legacy_parse_utils.pdf import trust_publisher_license, \
    find_normalized_license, DuckLink, get_link_target, clean_pdf_url, \
    find_version, find_pdf_link, discard_pdf_url, find_doc_download_link, \
    try_pdf_link_as_doc, find_bhl_view_link
from parseland_lib.legacy_parse_utils.version_and_license import \
    page_potential_license_text, detect_sd_author_manuscript, detect_bronze, \
    detect_hybrid
from parseland_lib.legacy_parse_utils.strings import cleanup_soup


def parse_publisher_fulltext_location(lp_content, resolved_url):
    soup = BeautifulSoup(lp_content, parser='lxml', features='lxml')
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


def parse_repo_fulltext_locations(soup, cleaned_soup, resolved_url):
    soup_str = str(soup)
    license_search_substr = page_potential_license_text(soup_str)
    version = find_version(resolved_url, soup_str)
    license = trust_publisher_license(
        resolved_url) and find_normalized_license(license_search_substr)

    location_candidates = []

    page = str(cleaned_soup)

    pdf_download_link = None
    # special exception for citeseer because we want the pdf link where
    # the copy is on the third party repo, not the cached link, if we can get it
    if "citeseerx.ist.psu.edu/" in resolved_url:
        matches = re.findall('<h3>Download Links</h3>.*?href="(.*?)"', page,
                             re.DOTALL)
        if matches:
            pdf_download_link = DuckLink(matches[0], "download")

    # osf doesn't have their download link in their pages
    # so look at the page contents to see if it is osf-hosted
    # if so, compute the url.  example:  http://osf.io/tyhqm
    elif page and "osf-cookie" in page:
        pdf_download_link = DuckLink("{}/download".format(resolved_url), "download")
        pdf_download_link.href = re.sub('//download$', '/download',
                                        pdf_download_link.href)

    # otherwise look for it the normal way
    else:
        pdf_download_link = find_pdf_link(resolved_url, cleaned_soup, page_with_scripts=soup_str)

    if pdf_download_link is None:
        if re.search(
                r'https?://cdm21054\.contentdm\.oclc\.org/digital/collection/IR/id/(\d+)',
                resolved_url):
            pdf_download_link = DuckLink(
                '/digital/api/collection/IR/id/{}/download'.format(
                    re.search(
                        r'https?://cdm21054\.contentdm\.oclc\.org/digital/collection/IR/id/(\d+)',
                        resolved_url
                    ).group(1)
                ),
                'download'
            )

    pdf_url = get_link_target(pdf_download_link.href, resolved_url)
    if pdf_download_link.anchor and 'accepted version' in pdf_download_link.anchor.lower():
        version = 'acceptedVersion'

    if not discard_pdf_url(pdf_url, resolved_url):
        location_candidates.append({'url': pdf_url,
                                    'version': version,
                                    'license': license})

    doc_link = find_doc_download_link(page)
    if doc_link is None and try_pdf_link_as_doc(resolved_url):
        doc_link = pdf_download_link

    if doc_link:
        absolute_doc_url = get_link_target(doc_link.href, resolved_url)
        location_candidates.append({'url': absolute_doc_url,
                                    'version': version,
                                    'license': license})

    bhl_link = find_bhl_view_link(resolved_url, page)
    if bhl_link:
        location_candidates.append({'url': bhl_link.href,
                                    'version': version,
                                    'license': license})

    return location_candidates