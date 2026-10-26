import re

from lxml import etree

from parseland_lib.legacy_parse_utils.pdf import get_pdf_in_meta, \
    trust_publisher_license, find_normalized_license
from parseland_lib.legacy_parse_utils.strings import normalized_strings_equal, \
    get_tree


def page_potential_license_text(page):
    tree = get_tree(page)

    if tree is None:
        return page

    section_removed = False

    bad_section_finders = [
        "//div[contains(@class, 'view-pnas-featured')]",  # https://www.pnas.org/content/114/38/10035
        "//meta[contains(@name, 'citation_reference')]",  # https://www.thieme-connect.de/products/ebooks/lookinside/10.1055/sos-SD-226-00098
        # Site chrome, never the article's own licence statement: a site-wide
        # "content of this site is licensed CC BY" footer turned paywalled pages into cc-by
        # (scientific.net, crossref.org defunct-DOI page, 2026-09).
        "//footer",
        "//nav",
        "//*[@role='contentinfo']",
        "//*[contains(concat(' ', normalize-space(@class), ' '), ' footer ')"
        " or contains(@class, 'footer-') or contains(@class, '-footer') or contains(@class, '_footer')"
        " or @id='footer' or starts-with(@id, 'footer') or contains(@id, '-footer') or contains(@id, '_footer')]",
        # Page-template code that looks for a CC badge is not a licence statement: SAGE's older template ships
        # `if ($('.creative-commons-badge.cc-by').length){ console.debug('... CC-BY type of article.') ...}` on every
        # article page, paywalled or not, which read as cc-by (oxjob #1794: 755 closed works turned hybrid).
        "//script[contains(., 'creative-commons-badge')]",
        # IOP's Accepted Manuscript notice for a subscription article states a future licence for the manuscript,
        # not the article's licence: "During the embargo period ... the Accepted Manuscript is fully protected by
        # copyright ... As the Version of Record of this article is going to be / has been published on a
        # subscription basis, this Accepted Manuscript will be available for reuse under a CC BY-NC-ND 4.0 licence
        # after the 12 month embargo period", with a cc-by-nc-nd.png badge in the same block. Read as the article's
        # licence it turned paywalled IOP articles into hybrid OA (oxjob #1860: 249 of 250 sampled cc-by-nc-nd IOP
        # pages). Only the subscription notice goes; the gold-OA notice ("published on a gold open access basis
        # under a CC BY 4.0 licence") and the published article's own licence block stay.
        "//div[contains(@class, 'media') or contains(@class, 'license')]"
        "[contains(normalize-space(.), 'subscription basis')]"
        "[contains(., 'Accepted Manuscript')][contains(., 'embargo')]",
    ]

    for section_finder in bad_section_finders:
        for bad_section in tree.xpath(section_finder):
            bad_section.clear()
            section_removed = True

    if not section_removed:
        return page

    try:
        return etree.tostring(tree, encoding=str)
    except Exception:
        return page


# ScienceDirect states the article's own licence in its page state, once per page:
#   "access":{"openAccess":<bool>,"openArchive":<bool>[,"license":"<url>"]}
# The same state also holds licences that are not the article's: the journal's self-archiving policy
# ("sa-user-license": the licence an author's accepted manuscript may carry after an embargo, CC BY-NC-ND on most
# journals) and open-research agreements ("or-agreement-license"). Read anywhere on the page, those turned
# paywalled articles into cc-by-nc-nd (oxjob #1794: 12 of 12 such dev pages).
_SD_ACCESS = re.compile(r'"access":\{([^{}]*"openAccess":\s*(?:true|false)[^{}]*)\}')
_SD_ACCESS_LICENSE = re.compile(r'"license":\s*"([^"]*)"')


def sciencedirect_article_license_text(page):
    """The ScienceDirect article's own licence statement: its licence URL, or '' when it states none.

    None when the page carries no ScienceDirect article state, so other pages keep the whole-page search.
    """
    if not page:
        return None
    access = _SD_ACCESS.search(page) if '"openAccess"' in page else None
    if access is None and '\\"openAccess\\"' in page:
        # some pages (peer-review reports, year-book articles) hold the state as an escaped JSON string:
        # \"access\":{\"openAccess\":false,...}; read it the same way, or the self-archiving licence leaks again
        access = _SD_ACCESS.search(page.replace('\\"', '"'))
    if access is None:
        return None
    license_url = _SD_ACCESS_LICENSE.search(access.group(1))
    return license_url.group(1) if license_url else ''


def license_search_text(page):
    """The text the licence regexes run over, on both the publisher and the repository path.

    A ScienceDirect page counts only its article's own licence statement (repository records such as Zenodo
    deposits often resolve to the ScienceDirect page, so the repository path needs the same rule); any other
    page is searched whole, minus site chrome.
    """
    sd_license_text = sciencedirect_article_license_text(page)
    if sd_license_text is not None:
        return sd_license_text
    tf_license_text = taylorfrancis_product_license_text(page)
    if tf_license_text is not None:
        return tf_license_text
    return page_potential_license_text(page)


# Taylor & Francis book pages (taylorfrancis.com) keep the product in Angular TransferState JSON, `"` escaped as `&q;`,
# and state the product's own licence once there:
#   &q;license&q;:{&q;type&q;:&q;open-access&q;,&q;description&q;:...,&q;location&q;:&q;http://creativecommons.org/licenses/by-nc-nd/4.0&q;}
# or &q;license&q;:null. The same JSON holds the chapter's subject keywords and text, so the whole-page search read a
# keyword ("Creative Commons Attribution ShareAlike") or a sentence ("... into the public domain") as the licence
# (oxjob #1809 pilot: 3 of 3,016 pages; the 37 right licences there all came from the object). Pages that hold several
# objects repeat the same one (8 of 372 sampled).
_TF_LICENSE = re.compile(r'&q;license&q;:(null|\{[^{}]*\})')


def taylorfrancis_product_license_text(page):
    """The T&F product's own licence statement (its licence object, quotes decoded), or '' when it is null.

    None when the page is not a T&F page carrying that object, so other pages keep the whole-page search.
    """
    if not page or '&q;license&q;:' not in page or 'taylorfrancis.com' not in page:
        return None
    m = _TF_LICENSE.search(page)
    if m is None:
        return None
    return '' if m.group(1) == 'null' else m.group(1).replace('&q;', '"')


def detect_bronze(soup, resolved_url):
    from parseland_lib.publisher.parsers.nejm import NewEnglandJournalOfMedicine
    from parseland_lib.publisher.parsers.elsevier_bv import ElsevierBV
    page = str(soup)
    open_version_string = None
    bronze_url_snippet_patterns = [
        ('sciencedirect.com/',
         '<div class="OpenAccessLabel">open archive</div>'),
        ('sciencedirect.com/',
         r'<span[^>]*class="[^"]*pdf-download-label[^"]*"[^>]*>Download PDF</span>'),
        ('sciencedirect.com/',
         r'<span class="primary-cta-button-text|link-button-text">View\s*<strong>PDF</strong></span>'),
        ('onlinelibrary.wiley.com',
         '<div[^>]*class="doi-access"[^>]*>Free Access</div>'),
        ('openedition.org', r'<span[^>]*id="img-freemium"[^>]*></span>'),
        ('openedition.org', r'<span[^>]*id="img-openaccess"[^>]*></span>'),
        # landing page html is invalid: <span class="accesstext"></span>Free</span>
        ('microbiologyresearch.org',
         r'<span class="accesstext">(?:</span>)?Free'),
        ('journals.lww.com',
         r'<li[^>]*id="[^"]*-article-indicators-free"[^>]*>'),
        ('ashpublications.org', r'<i[^>]*class="[^"]*icon-availability_free'),
        ('academic.oup.com', r'<i[^>]*class="[^"]*icon-availability_free'),
        ('publications.aap.org', r'<i[^>]*class="[^"]*icon-availability_free'),
        ('degruyter.com/', '<span>Free Access</span>'),
        ('degruyter.com/', 'data-accessrestricted="false"'),
        (
        'practicalactionpublishing.com', r'<img [^>]*class="open-access-icon"'),
        ("iucnredlist.org", r'<title>'),
    ]

    for (url_snippet, pattern) in bronze_url_snippet_patterns:
        if url_snippet in resolved_url.lower() and re.findall(pattern,
                                                                   page,
                                                                   re.IGNORECASE | re.DOTALL):
            open_version_string = "open (via free article)"

    bronze_publisher_patterns = [
        (NewEnglandJournalOfMedicine(soup).is_publisher_specific_parser,
         '<meta content="yes" name="evt-free"'),
        (lambda: soup.find('meta', {'name': 'dc.Publisher', 'content': lambda x: 'university of chicago press' in x.lower()}),
         r'<img[^>]*class="[^"]*accessIconLocation'),
        (ElsevierBV(soup).is_publisher_specific_parser,
         r'<span[^>]*class="[^"]*article-header__access[^"]*"[^>]*>Open Archive</span>'),
    ]

    for (publisher_func, pattern) in bronze_publisher_patterns:
        if publisher_func() and re.findall(pattern, page, re.IGNORECASE | re.DOTALL):
            open_version_string = "open (via free article)"

    # bronze_journal_patterns = [
    #     ('1352-2310', r'<span[^>]*>Download PDF</span>'),
    # ]

    # for (issn_l, pattern) in bronze_journal_patterns:
    #     if self.issn_l == issn_l and re.findall(pattern, page,
    #                                             re.IGNORECASE | re.DOTALL):
    #         self.scraped_open_metadata_url = metadata_url
    #         self.open_version_source_string = "open (via free article)"

    bronze_citation_pdf_patterns = [
        r'^https?://www\.sciencedirect\.com/science/article/pii/S[0-9X]+/pdf(?:ft)?\?md5=[0-9a-f]+.*[0-9x]+-main.pdf$'
    ]

    citation_pdf_link = get_pdf_in_meta(page)

    if citation_pdf_link and citation_pdf_link.href:
        for pattern in bronze_citation_pdf_patterns:
            if re.findall(pattern, citation_pdf_link.href,
                          re.IGNORECASE | re.DOTALL):
                open_version_string = "open (via free article)"

    return open_version_string


def detect_hybrid(soup, license_search_substr, resolved_url):
    from parseland_lib.publisher.parsers.cup import CUP
    from parseland_lib.publisher.parsers.ieee import IEEE
    from parseland_lib.publisher.parsers.oxford import Oxford
    from parseland_lib.publisher.parsers.rsc import RSC
    from parseland_lib.publisher.parsers.wiley import Wiley

    page = str(soup)
    open_version_string, license = None, None
    hybrid_url_snippet_patterns = [
        ('projecteuclid.org/', '<strong>Full-text: Open access</strong>'),
        (
        'sciencedirect.com/', '<div class="OpenAccessLabel">open access</div>'),
        ('journals.ametsoc.org/',
         r'src="/templates/jsp/_style2/_ams/images/access_free\.gif"'),
        ('apsjournals.apsnet.org',
         r'src="/products/aps/releasedAssets/images/open-access-icon\.png"'),
        ('psychiatriapolska.pl', 'is an Open Access journal:'),
        ('journals.lww.com', '<span class="[^>]*ejp-indicator--free'),
        ('journals.lww.com',
         r'<img[^>]*src="[^"]*/icon-access-open\.gif"[^>]*>'),
        ('iospress.com',
         r'<img[^>]*src="[^"]*/img/openaccess_icon.png[^"]*"[^>]*>'),
        ('rti.org/', r'</svg>[^<]*Open Access[^<]*</span>'),
        ('cambridge.org/',
         r'<span[^>]*class="open-access"[^>]*>Open access</span>'),
    ]

    for (url_snippet, pattern) in hybrid_url_snippet_patterns:
        if url_snippet in resolved_url.lower() and re.findall(pattern,
                                                                   page,
                                                                   re.IGNORECASE | re.DOTALL):
            open_version_string = "open (via page says Open Access)"
            license = "unspecified-oa"

    backup_hybrid_url_snippet_patterns = [
        ('degruyter.com/', '<span>Open Access</span>'),
    ]

    # should probably defer to scraped license for all publishers, but don't want to rock the boat yet
    if not license:
        for (url_snippet, pattern) in backup_hybrid_url_snippet_patterns:
            if url_snippet in resolved_url.lower() and re.findall(pattern,
                                                                       page,
                                                                       re.IGNORECASE | re.DOTALL):
                open_version_string = "open (via page says Open Access)"
                license = "unspecified-oa"

    # # try the license tab on T&F pages
    # # https://www.tandfonline.com/doi/full/10.1080/03057240.2018.1471391
    # # https://www.tandfonline.com/action/showCopyRight?doi=10.1080%2F03057240.2018.1471391
    # if not self.scraped_license:
    #     if url_match := re.match(
    #             r'^https?://(?:www\.)?tandfonline\.com/doi/full/(10\..+)',
    #             self.resolved_url, re.IGNORECASE):
    #         license_tab_url = 'https://www.tandfonline.com/action/showCopyRight?doi={doi}'.format(
    #             doi=url_match.group(1))
    #         logger.info(
    #             f'looking for license tab {license_tab_url} on T&F landing page {self.resolved_url}')
    #         license_tab_response = http_get(
    #             license_tab_url, stream=True, publisher=self.publisher,
    #             session_id=self.session_id, ask_slowly=self.ask_slowly,
    #             cookies=self.r.cookies
    #         )
    #
    #         if license_tab_response.status_code == 200:
    #             license_tab_text = license_tab_response.text_small()
    #             if license_tab_license := find_normalized_license(
    #                     page_potential_license_text(license_tab_text)):
    #                 self.scraped_license = license_tab_license
    #                 logger.info(
    #                     f'found license {self.scraped_license} on license tab')

    hybrid_publisher_patterns = [
        # Informa UK Limited? Always returning true for now
        (lambda: True, "/accessOA.png"),
        (Oxford(soup).is_publisher_specific_parser, "<i class='icon-availability_open'"),
        (IEEE(soup).is_publisher_specific_parser,
         r'"isOpenAccess":true'),
        (IEEE(soup).is_publisher_specific_parser,
         r'"openAccessFlag":"yes"'),
        (RSC(soup).is_publisher_specific_parser, "/open_access_blue.png"),
        (CUP(soup).is_publisher_specific_parser,
         '<span class="icon access open-access cursorDefault">'),
        (Wiley(soup).is_publisher_specific_parser, r'<div[^>]*class="doi-access"[^>]*>Open Access</div>'),
    ]

    for (publisher_func, pattern) in hybrid_publisher_patterns:
        if publisher_func() and re.findall(pattern, page,
                                                            re.IGNORECASE | re.DOTALL):
            open_version_string = "open (via page says Open Access)"
            license = "unspecified-oa"

    # Look for more license-like patterns that make this a hybrid location.
    # Extract the specific license if present.

    license_patterns = [
        r"(creativecommons.org/licenses/[a-z\-]+)",
        "distributed under the terms (.*) which permits",
        "This is an open access article under the terms (.*) which permits",
        "This is an open-access article distributed under the terms (.*), where it is permissible",
        "This is an open access article published under (.*) which permits",
        '<div class="openAccess-articleHeaderContainer(.*?)</div>',
        r'this article is published under the creative commons (.*) licence',
        r'This work is licensed under a Creative Commons (.*), which permits ',
    ]


    if trust_publisher_license(resolved_url):
        for pattern in license_patterns:
            matches = re.findall(pattern, license_search_substr, re.IGNORECASE)
            if matches:
                normalized_license = find_normalized_license(matches[0])
                license = normalized_license or 'unspecified-oa'
                if normalized_license:
                    open_version_string = 'open (via page says license)'
                else:
                    open_version_string = 'open (via page says Open Access)'

    return open_version_string, license

def detect_sd_author_manuscript(soup):
    if bool(soup.find(lambda tag: tag.text == 'View Open Manuscript')):
        return 'open (author manuscript)'

    return None
