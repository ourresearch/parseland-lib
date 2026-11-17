"""
Sites that state their licence once for everything they serve, and statements about some other item or version
(oxjob #2239, phase 2, round 3).

Round 2 left the footer statements alone because the labels went both ways on the same wording. Round 3 follows the
rule of SITE_LICENSE_HOSTS (#1792, 14 Nov 2026): on a whole-site open publisher the footer IS the item's licence.

- doi.nilu.no (EBAS datasets), clausiuspress.com and biographien.ac.at (OEBL biographies) join that list. OEBL pages
  are harvested with no stored URL, so their host is the one the page itself declares (DC.Identifier);
- aclanthology.org names two licences by year in its footer: the sentence for the paper's own year is read, and
  nothing when the page gives no year;
- a PubFactory (Brill) chapter page repeats the licence links of the book's OTHER chapters in its table of contents;
- Science's rights-retention line promises a licence for the accepted manuscript, not for the article on the page;
- a footer statement whose block names several different licences names none: an OJS theme's boilerplate ("This is
  an open-access article distributed under ... BY-NC-SA ... Licensed under <BY-SA badge> ... a <BY link>") was kept
  by round 2's article-statement rule and outranked the article's own License panel.

What must not change: a single journal's "<Journal> is licensed under ..." footer on a host that is not listed is
still not the article's licence (charter rule, 13 Nov 2026).

Fragments mirror stored pages; no network.
"""
import pytest

from parseland_lib.legacy_parse_utils.pdf import find_normalized_license
from parseland_lib.legacy_parse_utils.version_and_license import acl_anthology_license_text, license_search_text
from parseland_lib.parse import parse_page

OTHER_URL = "https://journals.example.org/article/1"


def searched_license(page, url):
    return find_normalized_license(license_search_text(page, url))


def page_of(body, head=""):
    return f"<html><head><title>t</title>{head}</head><body>{body}</body></html>"


# --- whole-site hosts: the footer is the item's licence

EBAS_FOOTER = """<footer class="footer mt-auto py-3"><div class="container"><div class="row">
<div class="col"> EBAS &copy; 2024 - All rights reserved </div>
<div class="col text-center"><a href="/privacy_policy">EBAS Privacy policy</a></div>
<div class="col text-end"> EBAS data is licensed under
<a href="https://creativecommons.org/licenses/by/4.0/deed.en">CC BY 4.0</a></div></div></div></footer>"""
EBAS_PAGE = page_of("<main><h4>Submission</h4><table><tr><th>Organization</th><td>Finnish Meteorological Institute"
                    "</td></tr></table></main>" + EBAS_FOOTER)

CLAUSIUS_FOOTER = """<div id="footer2"><p style="text-align: center;">All published work is licensed under a
<a href="https://creativecommons.org/licenses/by/4.0/legalcode" target="_blank">Creative Commons Attribution 4.0
International License</a>.</p><div>Copyright © 2016 - 2031 <b>Clausius Scientific Press Inc</b>. All Rights Reserved.
</div></div>"""
CLAUSIUS_PAGE = page_of("<div><h1>Media and Communication Research</h1><p>Abstract text.</p></div>" + CLAUSIUS_FOOTER)

OEBL_HEAD = """<meta name="DC.Title" content="Vika, Karel (H.)"><meta name="DC.Type" content="text">
<meta name="DC.Identifier" content="https://www.biographien.ac.at"><meta name="DC.Language" content="de">
<meta name="DC.Publisher" content="Verlag der Österreichischen Akademie der Wissenschaften">
<meta name="DC.Rights" content="Österreichische Akademie der Wissenschaften">"""
OEBL_FOOTER = """<div id="footer"><span class="fusszeile2">[ <a href="https://verlag.oeaw.ac.at" class="fzlink">Verlag
</a> ]</span><br><span id="rights" class="fusszeile1">[ <a rel="license" class="fzlink"
href="https://www.biographien.ac.at/oebl/oebl_div/Urheberrechtliche-Hinweise.html">Urheberrechtliche Hinweise</a> ]<br>
Text: <a class="fzlink" target="_blank" rel="license" href="http://creativecommons.org/licenses/by-nc-sa/3.0/at/">
Creative Commons BY-NC-SA 3.0 AT <img alt="Creative Commons Lizenzvertrag"
src="https://i.creativecommons.org/l/by-nc-sa/3.0/at/80x15.png"></a><br>
Medien/Abbildungen/Grafiken/Videos: Angaben zu Urheberrechten finden sich direkt bei den Medien<br></span></div>"""
OEBL_BODY = "<div id='view'><h1>Vika, Karel (H.)</h1><p>(1875–1941), Schriftsteller</p></div>" + OEBL_FOOTER
OEBL_PAGE = page_of(OEBL_BODY, OEBL_HEAD)


def test_ebas_dataset_takes_the_footers_data_licence():
    assert parse_page(EBAS_PAGE, "pmh", "https://doi.nilu.no/doi/submission/KB4A-XBMN")["license"] == "cc-by"


def test_clausius_article_takes_the_footers_licence():
    assert parse_page(CLAUSIUS_PAGE, "doi", "https://www.clausiuspress.com/article/9711.html")["license"] == "cc-by"


@pytest.mark.parametrize("page", [EBAS_PAGE, CLAUSIUS_PAGE, page_of(OEBL_BODY)])
def test_the_same_footers_on_a_host_that_is_not_listed_license_nothing(page):
    # the look-alike: "All published work is licensed under ..." is labelled no licence on another publisher's page
    assert searched_license(page, "https://www.imedpub.com/articles/an-article.html") is None
    assert parse_page(page, "doi", "https://www.imedpub.com/articles/an-article.html")["license"] is None
    assert parse_page(page, "pmh", "https://data.example.org/record/1")["license"] is None


def test_oebl_biography_with_no_stored_url_is_known_by_its_own_identifier():
    # harvested from hw.oeaw.ac.at / epub.oeaw.ac.at with no resolved URL: DC.Identifier names the site
    assert parse_page(OEBL_PAGE, "pmh", None)["license"] == "cc-by-nc-sa"
    assert parse_page(OEBL_PAGE, "pmh",
                      "https://www.biographien.ac.at/oebl/oebl_V/Vika_Karel_1875_1941.xml")["license"] == "cc-by-nc-sa"


def test_oebl_footer_without_the_sites_identifier_licenses_nothing():
    # no URL and no identifier: nothing says whose footer this is
    assert parse_page(page_of(OEBL_BODY), "pmh", None)["license"] is None
    # a page stored under another host that only points at the lexicon
    assert parse_page(OEBL_PAGE, "pmh", "https://repository.example.org/record/7")["license"] is None


@pytest.mark.parametrize("sentence", [
    'Eltin by http://e-journal.stkipsiliwangi.ac.id/index.php/eltin is licensed under a <a rel="license" '
    'href="http://creativecommons.org/licenses/by-sa/4.0/">Creative Commons Attribution - Share Alike 4.0 '
    'Internasional License</a>.',
    # ("The work of the Journal is licensed under ..." stood here until round 7: a footer sentence that names the
    # journal counts, charter § 6, 17 Nov 2026 08:20; tests/test_licence_footer_r7.py)
    'WALS Online edited by Dryer, Matthew S. &amp; Haspelmath, Martin is licensed under a <a rel="license" '
    'href="https://creativecommons.org/licenses/by/4.0/">Creative Commons Attribution 4.0 International License</a>.',
])
def test_a_single_journals_footer_licence_is_still_not_the_articles(sentence):
    page = page_of(f"<main><h1>An article</h1><p>Text.</p></main><footer><p>{sentence}</p></footer>")
    assert parse_page(page, "doi", OTHER_URL)["license"] is None
    assert parse_page(page, "pmh", OTHER_URL)["license"] is None


# --- ACL Anthology: the footer names a licence per year of publication

ACL_URL = "https://aclanthology.org/W17-0808"
ACL_FOOTER = """<footer class="bg-gradient-light py-2"><div class=container><p class="text-muted small px-1">
<span class="float-right mt-2 ml-2"><a rel=license href=http://creativecommons.org/licenses/by/4.0/><img
alt="Creative Commons License" src=https://i.creativecommons.org/l/by/4.0/88x31.png></a></span>
ACL materials are Copyright ©&nbsp;1963&ndash;2025 ACL; other materials are copyrighted by their respective copyright
holders. Materials prior to 2016 here are licensed under the <a
href=https://creativecommons.org/licenses/by-nc-sa/3.0/>Creative Commons Attribution-NonCommercial-ShareAlike 3.0
International License</a>. Permission is granted to make copies for the purposes of teaching and research. Materials
published in or after 2016 are licensed on a <a href=https://creativecommons.org/licenses/by/4.0/>Creative Commons
Attribution 4.0 International License</a>.</p><p class="text-muted small px-1">The ACL Anthology is managed and built
by the <a href=/info/credits/>ACL Anthology team</a> of volunteers.</p></div></footer>"""


def acl_page(date='2017/4', footer=ACL_FOOTER, abstract="We survey annotation tools.", canonical=""):
    date_meta = f'<meta content="{date}" name=citation_publication_date>' if date is not None else ""
    head = ('<meta content="A paper" name=citation_title>' + date_meta
            + '<meta property="og:site_name" content="ACL Anthology">' + canonical)
    return page_of(f'<section id=main><h2 id=title>A paper</h2><div class="acl-abstract"><span>{abstract}</span></div>'
                   f'</section>{footer}', head)


@pytest.mark.parametrize("date, expected", [
    ("2017/4", "cc-by"), ("2016", "cc-by"), ("2015/12", "cc-by-nc-sa"),
])
def test_acl_paper_takes_the_footer_sentence_for_its_year(date, expected):
    assert parse_page(acl_page(date), "doi", ACL_URL)["license"] == expected
    assert find_normalized_license(acl_anthology_license_text(acl_page(date), ACL_URL)) == expected


def test_acl_paper_with_no_stored_url_is_known_by_its_canonical_link():
    page = acl_page(canonical="<link rel=canonical href=https://aclanthology.org/W17-0808>")
    assert parse_page(page, "doi", None)["license"] == "cc-by"


@pytest.mark.parametrize("date", [None, "", "April"])
def test_acl_paper_whose_year_cannot_be_read_gets_no_licence(date):
    assert acl_anthology_license_text(acl_page(date), ACL_URL) == ""
    assert parse_page(acl_page(date), "doi", ACL_URL)["license"] is None


def test_acl_footer_without_a_sentence_for_the_year_licenses_nothing():
    one_licence = ('<footer><p>Materials published in or after 2016 are licensed on a <a '
                   'href=https://creativecommons.org/licenses/by/4.0/>Creative Commons Attribution 4.0 International '
                   'License</a>.</p></footer>')
    assert parse_page(acl_page("2010/7", footer=one_licence), "doi", ACL_URL)["license"] is None
    assert parse_page(acl_page("2020/7", footer=one_licence), "doi", ACL_URL)["license"] == "cc-by"
    plain = "<footer><p>The ACL Anthology is managed and built by volunteers.</p></footer>"
    assert parse_page(acl_page("2020/7", footer=plain), "doi", ACL_URL)["license"] is None


def test_acl_abstract_naming_a_dataset_licence_is_not_the_papers():
    page = acl_page("2020/7", abstract="We release the corpus under a Creative Commons Attribution-ShareAlike license.")
    assert parse_page(page, "doi", ACL_URL)["license"] == "cc-by"
    assert parse_page(acl_page(None, abstract="The corpus is CC BY-NC-ND."), "doi", ACL_URL)["license"] is None


def test_the_acl_footer_on_another_host_is_site_chrome():
    assert acl_anthology_license_text(acl_page(), OTHER_URL) is None
    assert acl_anthology_license_text(acl_page(), None) is None
    assert parse_page(acl_page(), "doi", OTHER_URL)["license"] is None


# --- PubFactory (Brill): the table of contents lists the book's other chapters, each with its own licence link

PF_LICENCE_BADGE = ('<div title="Open Access" class="accessIcon ico-access ico-access-open has-license"><span>Open '
                    'Access</span><div class="license-link license-link-open license-cc licence-cc-by"><a '
                    'rel="license" target="_blank" href="https://creativecommons.org/licenses/by/4.0/"><span></span>'
                    '</a></div></div>')
PF_TOC = ('<h6 class="c-List__subheader"><button><span> Table of Contents </span></button></h6><div '
          'class="container-item"><div class="component component-content-item component-table-of-contents '
          'chapter-toc"><div class="content-box"><ul>'
          f'<li class="type-chapter"><a href="/display/book/9789004522756/BP000012.xml">Chapter 1</a>{PF_LICENCE_BADGE}'
          '</li><li class="type-chapter"><a href="/display/book/9789004522756/BP000014.xml">Chapter 3</a></li>'
          f'<li class="type-chapter"><a href="/display/book/9789004522756/BP000019.xml">Chapter 8</a>{PF_LICENCE_BADGE}'
          '</li></ul></div></div></div>')


def pf_chapter(is_open):
    header = ('<div class="component component-content-item component-content-summary"><h1>Chapter 3 The Hair Relics'
              f'</h1>{PF_LICENCE_BADGE if is_open else "<p>Purchase instant access (PDF download):</p>"}</div>')
    body_class = "content-license-open-access" if is_open else "content-license-ccc"
    return (f'<html><head><title>t</title></head><body class="content-page type-chapter {body_class} site-brill '
            f'pf-skin-pf2"><div id="mainContent">{header}{PF_TOC}</div></body></html>')


BRILL_URL = "https://brill.com/display/book/9789004522756/BP000014.xml"


def test_sold_chapter_does_not_take_the_licence_of_open_chapters_in_the_table_of_contents():
    assert searched_license(pf_chapter(False), BRILL_URL) is None
    assert parse_page(pf_chapter(False), "doi", BRILL_URL)["license"] is None


def test_open_chapter_keeps_the_licence_in_its_own_header():
    assert parse_page(pf_chapter(True), "doi", BRILL_URL)["license"] == "cc-by"


def test_a_licence_under_a_table_of_contents_heading_elsewhere_stays():
    # the look-alike: an article page with a "Table of Contents" box and its own licence after it
    page = page_of('<main><div class="toc"><h2>Table of Contents</h2><ul><li>1 Introduction</li></ul></div><p>This '
                   'article is licensed under a <a href="https://creativecommons.org/licenses/by-nc/4.0/">CC BY-NC 4.0'
                   '</a> licence.</p></main>')
    assert parse_page(page, "doi", OTHER_URL)["license"] == "cc-by-nc"


# --- Science: the rights-retention line licenses the accepted manuscript, not the article on the page

SCIENCE_URL = "https://www.science.org/doi/10.1126/science.adh8967"
DEFAULT_LICENSE = ('<section class="core-copyright"><div role="paragraph">Copyright © 2024 The Authors, some rights '
                   'reserved; exclusive licensee American Association for the Advancement of Science.</div><div '
                   'role="paragraph">This is an article distributed under the terms of the <a '
                   'href="https://www.science.org/content/page/science-licenses-journal-article-reuse">Science Journals '
                   'Default License</a>.</div></section>')


def science_page(promise, own_licence=DEFAULT_LICENSE):
    return page_of('<div data-article-access="no" class="meta-panel"><span class="sr-only">No access</span></div>'
                   f'<main><h1>Cellular architecture shapes the naïve T cell response</h1>{own_licence}<section '
                   f'id="acknowledgments"><div role="paragraph">{promise}</div></section></main>')


AAM_PROMISE = ("This research was funded in whole or in part by the Swiss National Science Foundation (PP00P3_163961), "
               "a cOAlition S organization. The author will make the Author Accepted Manuscript (AAM) version "
               "available under a CC BY public copyright license.")


@pytest.mark.parametrize("promise", [
    AAM_PROMISE,
    "The authors will make the accepted manuscript available under a Creative Commons Attribution licence.",
    # the licence as a link: the link goes with the promise
    'The author will make the Author Accepted Manuscript (AAM) version available under a <a '
    'href="https://creativecommons.org/licenses/by/4.0/">CC BY</a> public copyright license.',
])
def test_a_promise_to_license_the_accepted_manuscript_is_not_the_articles_licence(promise):
    assert searched_license(science_page(promise), SCIENCE_URL) is None
    assert parse_page(science_page(promise), "doi", SCIENCE_URL)["license"] is None


def test_an_open_article_with_the_promise_keeps_its_own_licence():
    own = ('<div role="paragraph">This is an open-access article distributed under the terms of the <a '
           'href="https://creativecommons.org/licenses/by-nc/4.0/">Creative Commons Attribution-NonCommercial license'
           '</a>.</div>')
    page = science_page(AAM_PROMISE, own)
    assert parse_page(page, "doi", SCIENCE_URL)["license"] == "cc-by-nc"


@pytest.mark.parametrize("statement, expected", [
    # the look-alikes that are statements about the item on the page: a repository's accepted manuscript ...
    ("© 2019. This accepted manuscript version is made available under the CC-BY-NC-ND 4.0 license "
     "https://creativecommons.org/licenses/by-nc-nd/4.0/", "cc-by-nc-nd"),
    ("Accepted author manuscript, 1.3 MB. Licence: CC BY", "cc-by"),
    # ... and the funders' standard rights-retention sentence, which this round leaves as it is
    ("For the purpose of open access, the author has applied a CC BY public copyright licence to any Author Accepted "
     "Manuscript version arising from this submission.", "cc-by"),
])
def test_other_statements_about_an_accepted_manuscript_are_unchanged(statement, expected):
    page = page_of(f"<main><h1>A record</h1><p>{statement}</p></main>")
    assert parse_page(page, "pmh", "https://repository.example.org/record/7")["license"] == expected


# --- a footer statement whose block names several different licences names none

# openjournaltheme.com OJS themes print this boilerplate on every page of every journal that uses them
THEME_FOOTER_THREE = """<footer class="site-footer"><div class="row copright-container"><div class="copyright-wrapper">
<div class="copy-right">© 2021 IGNITED MINDS JOURNALS, ALL RIGHTS RESERVED, This site is Powered by i-Publisher. This
is an open-access article distributed under the terms of the Creative Commons Attribution-NonCommercial-ShareAlike 4.0
International License. Licensed under <img src="https://i.creativecommons.org/l/by-sa/4.0/80x15.png" alt="" /> This
work is licensed under a <a href="http://creativecommons.org/licenses/by-sa/4.0/" rel="license">Creative Commons
Attribution-ShareAlike 4.0 International License</a>. a <a href="https://creativecommons.org/licenses/by/4.0/">Creative
Commons Attribution 4.0 International License</a>.</div></div></div></footer>"""
# another theme of the same maker: no full stop between the two names, and the second licence only as a link and badge
THEME_FOOTER_TWO = """<footer><div class="copyright-wrapper"><div class="copy-right">© Diksa, All rights reserved. This
is an open-access article distributed under the terms of the Creative Commons Attribution-NonCommercial-ShareAlike 4.0
International License <br />Licensed under <a href="https://creativecommons.org/licenses/by/4.0/" rel="license"><img
src="https://licensebuttons.net/l/by-sa/3.0/80x15.png" alt="Creative Commons License" /></a> a <a
href="https://creativecommons.org/licenses/by/4.0/">Creative Commons Attribution 4.0 International License</a>.
</div></div></footer>"""
THEME_FOOTER_LINK_ONLY = """<footer><div class="copyright">This is an open-access article distributed under the terms
of the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License. <a
href="https://creativecommons.org/licenses/by/4.0/" rel="license"><img alt="Licence" /></a></div></footer>"""
ARTICLE = "<main><article><h1>An article</h1><p>Abstract text.</p>{panel}</article></main>"


@pytest.mark.parametrize("footer", [THEME_FOOTER_THREE, THEME_FOOTER_TWO, THEME_FOOTER_LINK_ONLY])
def test_a_footer_that_names_conflicting_licences_licenses_nothing(footer):
    page = page_of(ARTICLE.format(panel="") + footer)
    assert searched_license(page, OTHER_URL) is None
    assert parse_page(page, "pmh", OTHER_URL)["license"] is None
    assert parse_page(page, "doi", OTHER_URL)["license"] is None


@pytest.mark.parametrize("panel, expected", [
    # the panel's text says only "Attribution"; its link is the licence
    ('<div class="item copyright"><h2 class="label">License</h2><p>This work is licensed under a <a rel="license" '
     'href="https://creativecommons.org/licenses/by-sa/4.0/">Creative Commons Attribution License</a>.</p></div>',
     "cc-by-sa"),
    ('<div class="item copyright"><h2 class="label">License</h2><p>This work is licensed under a <a rel="license" '
     'href="https://creativecommons.org/licenses/by/4.0/">Creative Commons Attribution 4.0 International License</a>.'
     '</p></div>', "cc-by"),
])
@pytest.mark.parametrize("footer", [THEME_FOOTER_THREE, THEME_FOOTER_TWO])
def test_the_articles_own_licence_panel_is_read_not_the_conflicting_footer(footer, panel, expected):
    page = page_of(ARTICLE.format(panel=panel) + footer)
    assert parse_page(page, "pmh", OTHER_URL)["license"] == expected
    assert parse_page(page, "doi", OTHER_URL)["license"] == expected


@pytest.mark.parametrize("footer", [
    # the look-alikes: one licence, named again by its short name, its link or its badge (round 2 keeps these)
    '<footer><p>This is an open access article distributed under the terms of the Creative Commons '
    'Attribution-NonCommercial 4.0 International License (CC BY-NC 4.0).</p></footer>',
    '<footer><p>© 2024 The Journal. This is an open access article distributed under the <a rel="license" '
    'href="https://creativecommons.org/licenses/by-nc/4.0/">Creative Commons Attribution-NonCommercial 4.0 '
    'International License</a>. <a href="http://creativecommons.org/licenses/by-nc/3.0/">Earlier version</a></p>'
    '</footer>',
])
def test_a_footer_statement_that_names_one_licence_still_licenses_the_article(footer):
    page = page_of(ARTICLE.format(panel="") + footer)
    assert parse_page(page, "doi", OTHER_URL)["license"] == "cc-by-nc"


def test_a_statement_in_one_block_and_another_licence_in_another_block_license_nothing():
    # learning-gate.com, gate dev page cd5537c2: the article statement stands alone in the contact block, the site's
    # "Licensed under" badge in the copyright block. Gold v1.3 gave the statement's licence and round 3 judged a
    # statement by its own block; gold v1.4 says none (charter § 6, 16 Nov 2026: chrome that names different licences
    # licenses nothing, whichever block each sits in), and round 5 judges the page's chrome as a whole.
    footer = """<div class="pkp_structure_footer_wrapper" role="contentinfo"><div class="col-3"><div
    class="item-contact"><br /><span style="font-size: 0.875rem;">This is an open-access article distributed under the
    terms of the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License</span></div></div>
    <div class="copyright-wrapper"><div class="copy-right">Licensed under <a
    href="https://creativecommons.org/licenses/by/4.0/" rel="license"><img
    src="https://licensebuttons.net/l/by/4.0/80x15.png" alt="Creative Commons License" /></a> a <a
    href="https://creativecommons.org/licenses/by/4.0/">Creative Commons Attribution 4.0 International License</a>.
    </div></div></div>"""
    page = page_of(ARTICLE.format(panel="") + footer)
    assert parse_page(page, "doi", OTHER_URL)["license"] is None
    assert parse_page(page, "pmh", OTHER_URL)["license"] is None
    # the look-alike: the second block names the statement's own licence again
    same = footer.replace("licenses/by/4.0", "licenses/by-nc-sa/4.0").replace("/l/by/4.0", "/l/by-nc-sa/4.0").replace(
        "Creative Commons Attribution 4.0 International", "Creative Commons Attribution-NonCommercial-ShareAlike 4.0")
    assert parse_page(page_of(ARTICLE.format(panel="") + same), "doi", OTHER_URL)["license"] == "cc-by-nc-sa"


def test_a_statement_and_another_licence_in_the_next_paragraph_license_nothing():
    footer = ('<footer><p>This is an <b>open-access</b> article distributed under the terms of the Creative Commons '
              'Attribution-NonCommercial-ShareAlike 4.0 International License.</p><p>Licensed under a <a '
              'href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a> licence.</p></footer>')
    assert parse_page(page_of(ARTICLE.format(panel="") + footer), "doi", OTHER_URL)["license"] is None
