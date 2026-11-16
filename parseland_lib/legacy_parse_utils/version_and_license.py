import re
from urllib.parse import unquote

from lxml import etree

from parseland_lib.legacy_parse_utils.pdf import get_pdf_in_meta, \
    trust_publisher_license, find_normalized_license, site_license_covers_articles
from parseland_lib.legacy_parse_utils.strings import normalized_strings_equal, \
    get_tree


# Site chrome, never the article's own licence statement: a site-wide "content of this site is licensed CC BY" footer
# turned paywalled pages into cc-by (scientific.net, crossref.org defunct-DOI page, 2026-09). Kept on SITE_LICENSE_HOSTS,
# whose footer licenses every article (pdf.py).
SITE_CHROME_FINDERS = [
    "//footer",
    "//nav",
    "//*[@role='contentinfo']",
    "//*[contains(concat(' ', normalize-space(@class), ' '), ' footer ')"
    " or contains(@class, 'footer-') or contains(@class, '-footer') or contains(@class, '_footer')"
    " or @id='footer' or starts-with(@id, 'footer') or contains(@id, '-footer') or contains(@id, '_footer')]",
]

# Where the page's own content is (#2239): HTML allows one <main> (or role="main") per page and never inside a
# <footer> or <nav>, so an element that holds it is not site chrome, whatever its tag or name says.
_MAIN_CONTENT = etree.XPath("//main | //*[@role='main'][not(self::nav or self::footer)]")


# A statement in site chrome that speaks of the page's article, not of the site (#2239, round 2): "This is an open
# access article distributed under ...", "This article is licensed under ...". Journals print it once, in the footer
# of every article page (4 dev pages, all labelled with that licence). The sentence is kept; the rest of the footer
# still goes. What stays chrome, on purpose:
# - "This work is licensed under ..." (the Creative Commons chooser's badge text, pasted into site footers, where "this
#   work" is the site): 26 dev pages whose label is no licence against 1 with one;
# - "All published work is licensed under ...", "<Journal> is licensed under ...", "content of this site ...": the
#   labels go both ways on the same wording (clausiuspress.com with a licence, an iMedPub journal without), so that
#   is a decision, not a rule.
# The licence must be named in the same sentence, so "Share this article" beside a site badge keeps nothing, and a
# condition ("if this article is published under ...") is not a statement.
_ARTICLE_STATEMENT = re.compile(
    r"\bthis\s+(?:is\s+an?\s+)?(?:open[\s\-]?access\s+)?article\s+"
    r"(?:(?:is\s+)?(?:licen[sc]ed|distributed|published|(?:made\s+)?available)\s+)?under"
    r"\b(?:[^.]|\.(?=\S)){0,300}", re.IGNORECASE)
_CONDITION_BEFORE = re.compile(r"\b(?:if|when|where|whether|unless)\s+$", re.IGNORECASE)


def _article_statements(section):
    """The sentences in a site-chrome element that license the page's article itself (_ARTICLE_STATEMENT)."""
    text = " ".join(section.itertext())
    if 'rticle' not in text and 'RTICLE' not in text:
        return []  # nearly every nav and footer: skip the whitespace pass
    text = re.sub(r"\s+", " ", text)
    return [m.group(0) for m in _ARTICLE_STATEMENT.finditer(text)
            if find_normalized_license(m.group(0))
            and not _CONDITION_BEFORE.search(text, max(0, m.start() - 12), m.start())]


def _clear_all_but_main(element, mains, holders):
    """Clear what a <nav> or <footer> holds beside the page's main content; True when anything went."""
    cleared = False
    for child in element.iterchildren(tag=etree.Element):
        if child in mains:
            continue
        if child in holders:
            cleared |= _clear_all_but_main(child, mains, holders)
        else:
            child.clear()
            cleared = True
    return cleared


# class="article-footer", "article__footer", "articleFooter": the article's footer by the page's own naming
_ARTICLE_OWN_FOOTER = re.compile(r"(?:^|\s)article[\w\-]*footer", re.IGNORECASE)


def _clear_site_chrome(tree):
    """Clear the page's site chrome (SITE_CHROME_FINDERS), except chrome that holds the page; True when anything went.

    Site chrome that holds the page is not chrome (#2239, phase 2). The finders also match elements that wrap the
    WHOLE page, and the article's own licence went with them: arXiv's abstract pages sit in
    <div class="flex-wrap-footer"> (a sticky-footer layout), WordPress themes put footer options in the <body> class,
    and DSpace JSPUI leaves a <div> open in its header <nav>, so the parser ignores </nav> and the nav swallows <main>
    and all that follows (36 of 875 sampled pages whose stored licence the re-parse dropped; arXiv 32). So <html>,
    <body> and any element that holds the page's <main> are never cleared whole:
    - a wrapper that only has a footer-like name stays, and the real <footer>, <nav> and footer-named elements inside
      it still go, because the same finders match them on their own;
    - a real <nav>, <footer> or role=contentinfo that swallowed <main> loses everything but <main>: its own menu
      items are still chrome.
    Only structure counts. The share of the page's text an element holds, an <h1> or an <article> in it are not
    evidence of content: on short and paywalled pages the site footer is most of the text (sampled pages: an OJS
    footer with 70% of the page's visible text, another repository's with 85%, DOAJ's with 40%, OpenGrey's with
    40-60% once its inline scripts count), and site navs and footers carry <h1> logos and <article> teasers (PLOS,
    APS, Frontiers, Erudit). Sparing those would bring back the site-footer licences this rule exists to keep out.

    Round 2 (#2239), the same structure read the other way, and one wording rule:
    - a footer-named element the page itself names as the ARTICLE's, inside an <article>, is that article's own
      (<article class="article-body">...<footer class="article-footer"> with its licence line): it stays. Both are
      needed. Where it sits is not enough: doi.org's pages and some OJS themes put the SITE footer inside <main>,
      doi.org's "not found" page even inside <main><article> (5 gold pages took the site's licence when position
      alone counted);
    - a cleared element keeps the sentences that license the page's article itself (_ARTICLE_STATEMENT), as plain text.
    """
    mains = set(_MAIN_CONTENT(tree))
    holders = {ancestor for main in mains for ancestor in main.iterancestors()}
    cleared = False
    for section_finder in SITE_CHROME_FINDERS:
        for section in tree.xpath(section_finder):
            if section in mains or section.tag in ('html', 'body'):
                continue  # <main class="has-footer">, <body class="ast-footer-overlay">: the content itself
            if _ARTICLE_OWN_FOOTER.search(section.get('class') or '') \
                    and next(section.iterancestors('article'), None) is not None:
                continue  # <article> ... <footer class="article-footer">: the article's own footer
            if section not in holders:
                if section.getroottree().getroot() is not tree:
                    continue  # already gone with an enclosing element cleared earlier in this pass
                statements = _article_statements(section)
                section.clear()
                for statement in statements:
                    etree.SubElement(section, 'p').text = statement
                cleared = True
            elif section.tag in ('nav', 'footer') or section.get('role') == 'contentinfo':
                cleared |= _clear_all_but_main(section, mains, holders)
    return cleared


# A RightsLink permissions link names the licence of ONE article, the one in its contentID (#2239, round 2):
#   /servlet/linkout?type=rightslinkReprints&url=...%26contentID%3D10.1080%252F13530194.2021.1916154...%26oa%3DCC-BY-NC-ND...
# On older Taylor & Francis pages it is the only place the article's licence is named (beside an "Open access" badge),
# and its doubly URL-encoded "oa%3DCC-BY-NC-ND" stopped reading as a licence when the CC shorthands began to need
# token boundaries. On a Wiley issue page each listed article has its own link, and one open article licensed the
# issue. So the link is replaced by what it states: its decoded oa= value when its contentID is the page's own DOI,
# nothing otherwise (never the whole decoded link: its title= parameter is the article's title, which may name a
# licence). A page that names no DOI trusts none.
_RIGHTSLINK_OA = re.compile(r"(?<![A-Za-z])oa=[A-Za-z0-9\-+ ]+")
_RIGHTSLINK_CONTENT_ID = re.compile(r"contentID=(10\.\d{4,9}/[^&\s]+)", re.IGNORECASE)
_DOI_META_NAMES = {"citation_doi", "dc.identifier", "dc.identifier.doi", "prism.doi", "doi"}
_DOI_VALUE = re.compile(r"^(?:doi:\s*|https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/\S+)$", re.IGNORECASE)


def _page_dois(tree):
    dois = set()
    for meta in tree.iter('meta'):
        if (meta.get('name') or meta.get('property') or '').lower() in _DOI_META_NAMES:
            doi = _DOI_VALUE.match((meta.get('content') or '').strip())
            if doi:
                dois.add(doi.group(1).lower())
    return dois


def _keep_own_rightslink_licence(tree):
    """Rewrite RightsLink links so only the page's own article can state a licence; True when any link changed."""
    changed, dois = False, None
    for link in tree.xpath("//a[contains(@href, 'rightslink')]"):
        href = unquote(unquote(link.get('href')))
        oa = _RIGHTSLINK_OA.search(href)
        if not oa:
            continue
        if dois is None:  # read once, and only on a page whose links name a licence
            dois = _page_dois(tree)
        content_id = _RIGHTSLINK_CONTENT_ID.search(href)
        own = content_id and content_id.group(1).lower() in dois
        link.set('href', 'rightslink ' + oa.group(0).replace('+', ' ') if own else 'rightslink')
        changed = True
    return changed


# Text that names a licence without stating the work's (#2239, round 2), dropped from the search text:
# - a JSON schema's "enum": the list of values a field MAY take. AgEcon Search (TIND) record pages define their file
#   table's licence column with every licence on offer, and each record read as cc-by-nc-nd;
# - a map's attribution ("Map data (c) OpenStreetMap contributors CC-BY-SA", in UNT Digital Library record pages);
# - an image credit: "Image by CSTAR via Wikipedia licensed under CC-BY-SA 3.0" (a schema.org image caption),
#   "Featured image by <a ...>Katherine Lynn</a> under a CC-BY-NC-ND license" (a blog post and its description),
#   "Image by Rob Palmer via iNaturalist (CC BY-NC-SA 4.0)" (an alt text). The credit ends at the next sentence,
#   and is not one when it reaches a word for the work itself before its licence.
# A map attribution or image credit runs over text and its own <a> links only (raw or escaped, as in a script once the
# tree is serialised), so on a one-line page it cannot swallow a statement in the next element.
_LICENSE_OPTIONS = re.compile(r'"enum"\s*:\s*\[[^\[\]]*\]')
_MAP_ATTRIBUTION = re.compile(
    r"OpenStreetMap(?:\s*(?:</a>|&lt;/a&gt;))?\s*contributors"
    r"(?:</?a\b[^>]*>|&lt;/?a\b(?:(?!&gt;)[^\n])*&gt;|[^\"<>\n]){0,200}")
# cheap gate for _IMAGE_CREDIT, which would otherwise scan every page: the usual casings only
_IMAGE_CREDIT_HINTS = ("mage by", "hoto by", "icture by", "mage credit", "hoto credit")
_IMAGE_CREDIT = re.compile(
    r"\b(?:image|photo|picture)\s+(?:by|credit)\b"
    r"(?:(?!\b(?:article|paper|work|post|text|content)\b)(?:[^\"<>]|</?a\b[^>]*>)){0,80}?(?:\bunder\b|\(\s*CC\b)"
    r"(?:[^\"<>.]|\.(?!\s+[A-Z])){0,120}", re.IGNORECASE)
# anchored on the newline before the comment (the caller prepends one): a fixed first character keeps the scan fast
_LICENSE_IN_CODE_COMMENT = re.compile(
    r"\n[ \t]*//[^\r\n]*(?:public\s*domain|creative\s*commons)[^\r\n]*", re.IGNORECASE)


def _drop_code_comments_naming_a_license(tree):
    """Drop the comment lines of code scripts that name a licence ("// Appends the Public Domain image", on every
    ROSAP and CDC Stacks record page); True when any went."""
    changed = False
    for script in tree.iter('script'):
        if 'json' in (script.get('type') or '').lower():
            continue  # data, not code
        text = script.text
        if text and ('ommons' in text or 'omain' in text):
            without, dropped = _LICENSE_IN_CODE_COMMENT.subn('\n', '\n' + text)
            if dropped:
                script.text = without[1:]
                changed = True
    return changed


def _drop_non_statements(text):
    """The search text without option lists, map attributions and image credits; the same object when it has none."""
    text = _LICENSE_OPTIONS.sub('', text)
    text = _MAP_ATTRIBUTION.sub('', text)
    if any(hint in text for hint in _IMAGE_CREDIT_HINTS):
        text = _IMAGE_CREDIT.sub('', text)
    return text


def page_potential_license_text(page, keep_site_chrome=False):
    tree = get_tree(page)

    if tree is None:
        return _drop_non_statements(page)

    section_removed = False if keep_site_chrome else _clear_site_chrome(tree)
    if 'rightslink' in page:
        section_removed |= _keep_own_rightslink_licence(tree)
    section_removed |= _drop_code_comments_naming_a_license(tree)

    bad_section_finders = [
        "//div[contains(@class, 'view-pnas-featured')]",  # https://www.pnas.org/content/114/38/10035
        "//meta[contains(@name, 'citation_reference')]",  # https://www.thieme-connect.de/products/ebooks/lookinside/10.1055/sos-SD-226-00098
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

    if section_removed:
        try:
            page = etree.tostring(tree, encoding=str)
        except Exception:
            pass
    return _drop_non_statements(page)


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


def license_search_text(page, resolved_url=None):
    """The text the licence regexes run over, on both the publisher and the repository path.

    A ScienceDirect page counts only its article's own licence statement (repository records such as Zenodo
    deposits often resolve to the ScienceDirect page, so the repository path needs the same rule); any other
    page is searched whole, minus site chrome (kept on hosts whose footer licenses every article).
    """
    sd_license_text = sciencedirect_article_license_text(page)
    if sd_license_text is not None:
        return sd_license_text
    tf_license_text = taylorfrancis_product_license_text(page)
    if tf_license_text is not None:
        return tf_license_text
    return page_potential_license_text(page, keep_site_chrome=site_license_covers_articles(resolved_url))


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
