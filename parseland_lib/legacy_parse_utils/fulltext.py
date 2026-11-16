import html
import re
from urllib.parse import parse_qsl, urlparse, urlsplit, urlunsplit

from parseland_lib.legacy_parse_utils.resolved_url import get_base_url_from_soup
from parseland_lib.legacy_parse_utils.pdf import trust_publisher_license, \
    find_normalized_license, DuckLink, get_link_target, clean_pdf_url, \
    find_repo_version, find_pdf_link, discard_pdf_url, find_doc_download_link, \
    try_pdf_link_as_doc, find_bhl_view_link, has_bad_href_word
from parseland_lib.legacy_parse_utils.version_and_license import \
    detect_sd_author_manuscript, detect_bronze, detect_hybrid, license_search_text
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

_TANDFONLINE_DOI_PATH_RE = re.compile(
    r"^/doi/(?:full|abs|epdf)/(10\.[^?#]+)$",
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


def find_tandfonline_pdf_link(soup):
    """Construct TandF's stable article PDF URL from canonical metadata.

    Some TandF article pages expose no PDF anchor or citation_pdf_url in the
    cached HTML, but their canonical / og URL is the DOI article route:
    /doi/full/<doi> or /doi/abs/<doi>. The PDF route is the same DOI at
    /doi/pdf/<doi>. Keep this host- and path-scoped so non-TandF pages and
    TaylorFrancis book/product pages are not affected.
    """
    for tag in (
        soup.select_one('link[rel="canonical"]'),
        soup.select_one('meta[property="og:url"]'),
        soup.select_one('meta[name="og:url"]'),
    ):
        if not tag:
            continue
        raw = (tag.get("href") if tag.name == "link" else tag.get("content")) or ""
        try:
            parts = urlsplit(raw.strip())
        except ValueError:
            continue
        host = parts.netloc.lower().removeprefix("www.")
        if host != "tandfonline.com":
            continue
        match = _TANDFONLINE_DOI_PATH_RE.match(parts.path)
        if not match:
            continue
        return urlunsplit(("https", "www.tandfonline.com", f"/doi/pdf/{match.group(1)}", "", ""))
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



# OpenEdition (books.openedition.org, journals.openedition.org): a page's own PDF, when it has
# one, lives on the same host (books.openedition.org/<site>/pdf/<id>,
# journals.openedition.org/<site>/pdf/<id> or .../<id>?file=N). Every .pdf-shaped anchor on
# another host is a footnote citing a third-party document, or on Books the "ePub / PDF" buy
# button (7switch). The generic finder took those: 2,111 works under 10.4000 ended up with
# someone else's PDF as best_oa_location.pdf_url and in the Content API store. Oxjob #786.
_OPENEDITION_HOST_RE = re.compile(r'^(?:[a-z0-9-]+\.)*openedition\.org$', re.I)


def _openedition_host(resolved_host, page_markup):
    """The openedition.org host a page belongs to (by resolved host, else og:url / canonical), or None."""
    host = (resolved_host or '').lower()
    if _OPENEDITION_HOST_RE.match(host):
        return host
    for pat in (r'<(?:meta|link)[^>]+(?:property="og:url"|rel="canonical")[^>]+(?:content|href)="([^"]+)"',
                r'<(?:meta|link)[^>]+(?:content|href)="([^"]+)"[^>]+(?:property="og:url"|rel="canonical")'):
        m = re.search(pat, page_markup or '', re.I)
        if m:
            h = (urlparse(m.group(1)).hostname or '').lower()
            if _OPENEDITION_HOST_RE.match(h):
                return h
    return None


def is_openedition_page(resolved_host, page_markup):
    return _openedition_host(resolved_host, page_markup) is not None


def is_openedition_own_pdf(href, resolved_host, page_markup):
    """True only when the pdf link sits on the same openedition.org host as the page."""
    page_host = _openedition_host(resolved_host, page_markup)
    link_host = (urlparse(href or '').hostname or '').lower()
    return bool(page_host) and link_host == page_host


# JSTOR's page for a book lists one "Download" per chapter (/stable/pdf/<book>.<n>.pdf), and it is the page JSTOR
# serves for every chapter of the book ("/stable/<book>?turn_away=true"): the HTML is the same whichever chapter it
# was stored for. The finder took the first "Download", the book's front matter, so a page stored for chapter 25
# gave chapter 1's PDF (#2239: 63 of 88 sampled book pages, right once). A page that offers several items' PDFs
# doesn't say which is this work's: it has no PDF link. A journal item's page lists no such link, or its own one.
_JSTOR_ITEM_PDF_RE = re.compile(r'/stable/pdf/[^\s"\'<>?#]+\.pdf', re.I)


def is_jstor_contents_pdf(href, page_markup):
    """True when the link is one of several items' PDFs that a JSTOR page lists (a book's table of contents)."""
    if not href or '/stable/pdf/' not in href:
        return False
    try:
        parts = urlsplit(href)
    except ValueError:
        return False
    # relative, or on JSTOR's host (a library proxy's "www.jstor.org.<proxy>" included)
    if (parts.netloc and 'jstor.org' not in parts.netloc.lower()) or not parts.path.startswith('/stable/pdf/'):
        return False
    return len(set(_JSTOR_ITEM_PDF_RE.findall(page_markup or ''))) > 1


# DOAJ article records (doaj.org/article/<id>) print the record's full-text links as "Read online" buttons, and
# nothing on the page says which of them is a PDF: only the address does. The finder knows no "Read online" link,
# so a record whose button goes straight to the publisher's PDF had no PDF link (#2239: 68 of 508 labelled DOAJ
# pages; the other 440 go to a landing page, and have none).
_DOAJ_RECORD_RE = re.compile(r'^https?://(?:www\.)?doaj\.org/article/', re.I)
# Routes that serve an article's file and never say "pdf" (4 of the 68): Hrčak's /file/<n>, DergiPark's
# /download/article-file/<n>, Open Journal Systems' /article/viewFile/<article>/<galley>.
_ARTICLE_FILE_ROUTE_RE = re.compile(
    r'^(?:hrcak\.srce\.hr/file/\d+|dergipark\.org\.tr/(?:[a-z]{2}/)?download/article-file/\d+|'
    r'[^/]+/(?:.*/)?article/viewFile/\d+/\d+)/?$', re.I)


def address_names_pdf(href):
    """True when a link's address itself says it serves a PDF: the path ends in .pdf or has a part named "pdf"
    (/download/pdf/, /article/view/477/pdf, J-STAGE's /_pdf/), the query asks for one (Europe PMC's ?pdf=render),
    or it is a known article-file route. A word that only contains "pdf" or "file" doesn't count."""
    try:
        parts = urlsplit(href or '')
    except ValueError:
        return False
    path = parts.path.lower()
    if path.endswith('.pdf') or any(part in ('pdf', '_pdf') for part in path.split('/')):
        return True
    if any('pdf' in (key.lower(), value.lower()) for key, value in parse_qsl(parts.query, keep_blank_values=True)):
        return True
    return bool(_ARTICLE_FILE_ROUTE_RE.match(parts.netloc.lower().removeprefix('www.') + parts.path))


def find_doaj_pdf_link(soup, resolved_url):
    """The first "Read online" button of a DOAJ article record whose address names a PDF, or None."""
    og_url = soup.find('meta', {'property': 'og:url', 'content': True})
    if not any(_DOAJ_RECORD_RE.match(url or '') for url in (resolved_url, og_url['content'] if og_url else None)):
        return None
    for button in soup.select('a.button[href]'):
        href = button['href'].strip()
        if button.get_text(strip=True).lower() == 'read online' and address_names_pdf(href) \
                and not has_bad_href_word(href):
            return href
    return None


def parse_publisher_fulltext_location(soup, resolved_url, ojs_page=False):
    # cleanup_soup() extracts <script> in place, so anything read from `soup` after it has
    # no JSON payloads. The licence search needs them: Next.js pages (eLife reviewed
    # preprints) carry the article's licence only in __NEXT_DATA__ once site chrome is
    # stripped. Snapshot before cleanup, for the licence search only.
    license_page = str(soup)
    cleaned_soup = cleanup_soup(soup)
    detected_resolved_url = get_base_url_from_soup(soup)
    if not resolved_url:
        resolved_url = detected_resolved_url
    resolved_host = urlparse(resolved_url).hostname or ''
    soup_str = str(soup)
    # ScienceDirect: only the article's own licence statement counts, never the self-archiving or
    # open-research licences in the same page state (oxjob #1794).
    license_search_substr = license_search_text(license_page, resolved_url, ojs_page)
    version = 'publishedVersion'
    open_version_source_string, oa_status = None, None
    # untrusted host -> None, never False: a False licence leaks downstream as the string 'False'
    license = find_normalized_license(license_search_substr) if trust_publisher_license(resolved_url) else None
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

    # *.openedition.org: only a PDF on the page's own host counts. Oxjob #786.
    if pdf_link is not None and is_openedition_page(resolved_host, soup_str) \
            and not is_openedition_own_pdf(pdf_link.href, resolved_host, soup_str):
        pdf_link = None

    # a JSTOR book page's "Download" links are its chapters', none of them this page's own (#2239)
    if pdf_link is not None and is_jstor_contents_pdf(pdf_link.href, soup_str):
        pdf_link = None

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
        elif resolved_host.endswith('tandfonline.com') and (
                tandfonline_pdf := find_tandfonline_pdf_link(soup)):
            pdf_link = DuckLink(tandfonline_pdf, 'Taylor & Francis DOI PDF')

    if pdf_link is not None:
        pdf_base_url = _doi_router_relative_pdf_base(pdf_link.href, resolved_url)
        pdf_url = get_link_target(pdf_link.href, pdf_base_url)
    else:
        pdf_url = None
    pdf_url, pdf_link = clean_pdf_url(pdf_url, pdf_link) if pdf_url else (None, None)
    # A De Gruyter link the page prints (its "Download chapter (PDF)" link, its citation_pdf_url tag) is returned as
    # printed (#2239). It used to be moved to the degruyterbrill host and lose its query here, so
    # ".../pdf?licenseType=free" came back as ".../pdf" and a www.degruyter.com page's link on another host: 12 of
    # the 16 labelled pages that print one. The link built above for a page that prints none is already in that
    # form (find_de_gruyter_pdf_link) and is not touched: whether such a page should get one is parked (#1632).

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


def parse_repo_fulltext_location(soup, resolved_url, ojs_page=False):
    soup_str = str(soup)
    if not resolved_url:
        resolved_url = get_base_url_from_soup(soup)

    # license (a repository record can resolve to a ScienceDirect page: same rule as the publisher path, #1794)
    license_search_substr = license_search_text(soup_str, resolved_url, ojs_page)
    license = find_normalized_license(license_search_substr) if trust_publisher_license(resolved_url) else None

    # version
    version = find_repo_version(soup_str)
    # An OJS article page is the publisher's own copy, not a repository deposit.
    if soup.find('meta', attrs={'name': 'generator',
                                'content': re.compile(r'^Open Journal Systems')}):
        version = 'publishedVersion'

    # fulltext url
    pdf_url = None
    doc_url = None
    pdf_download_link = find_pdf_link(resolved_url, soup, page_with_scripts=soup_str)
    # a JSTOR book page's "Download" links are its chapters', none of them this page's own (#2239)
    if pdf_download_link is not None and is_jstor_contents_pdf(getattr(pdf_download_link, 'href', None), soup_str):
        pdf_download_link = None
    # a DOAJ record's "Read online" button that goes straight to a PDF (#2239)
    if pdf_download_link is None and 'doaj.org/article/' in soup_str and (
            doaj_pdf := find_doaj_pdf_link(soup, resolved_url)):
        pdf_download_link = DuckLink(doaj_pdf, 'Read online')
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
