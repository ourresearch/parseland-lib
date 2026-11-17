"""
Footer licences after the charter's ruling of 17 Nov 2026 08:20 (oxjob #2239, phase 2, round 7; landing-pages § 6):

1. On an Open Journal Systems page the footer speaks for the journal: a single-licence line with no subject counts
   ("Utgiven av <publisher> | Open Access enligt Creative Commons CC-BY 4.0"; "Excepto donde se indique explícitamente
   se publica bajo la siguiente licencia ..."; "Published by <publisher> under the terms of ..."; "Licensed under ..."),
   unless it licenses something else (the site, its metadata, a theme, a picture) or is a badge alone.
2. On any other site, a footer sentence counts when it names the journal, its articles or its materials ("This is an
   open access journal, is following CC-BY license"; "Материалы журнала доступны по лицензии ..."; "Czasopismo jest
   udostępnione ... (CC-BY-NC-ND)"; "<Journal> is licensed under ..."). The article's own licence wins.
3. Off OJS, "This work is licensed under ..." (the Creative Commons chooser's sentence), a line with no subject, or a
   badge still licenses nothing.
4. eve.gd and wals.info license every item they serve in their footer (SITE_LICENSE_HOSTS).

Two licences in the chrome still license nothing, on OJS or off it. Fragments mirror stored pages; no network.
"""
import pytest

from parseland_lib.legacy_parse_utils.version_and_license import license_search_text
from parseland_lib.parse import parse_page

URL = "https://journals.example.org/index.php/kp/article/view/31627"
OJS = '<meta name="generator" content="Open Journal Systems 3.3.0.19">'
KP = (OJS + '<meta name="DC.Source" content="Kulturella Perspektiv – Svensk etnologisk tidskrift">'
      '<meta name="DC.Source.URI" content="https://journals.example.org/index.php/kp">')
BODY = "<main><h1>An article</h1><p>Abstract text.</p>{panel}</main>"
BY = "https://creativecommons.org/licenses/by/4.0/"
BY_SA = "http://creativecommons.org/licenses/by-sa/4.0/"
BY_NC = "https://creativecommons.org/licenses/by-nc/4.0/"
BY_NC_SA = "https://creativecommons.org/licenses/by-nc-sa/4.0/"
BY_SA_NAME = f'<a rel="license" href="{BY_SA}">Creative Commons Attribution-ShareAlike 4.0 International License</a>'
BY_SA_BADGE = (f'<a rel="license" href="{BY_SA}"><img alt="Creative Commons License" '
               'src="https://i.creativecommons.org/l/by-sa/4.0/88x31.png" /></a>')
OJS_FOOTER = ('<div class="pkp_structure_footer_wrapper" role="contentinfo"><div class="pkp_footer_content">{}</div>'
              '</div>')


def page_of(footer, head=KP, panel="", wrapper=OJS_FOOTER, title="An article | Kulturella Perspektiv"):
    return (f"<html><head><title>{title}</title>{head}</head><body>{BODY.format(panel=panel)}"
            f"{wrapper.format(footer)}</body></html>")


def licenses(page, url=URL):
    """The licence on the publisher path and on the repository path."""
    return parse_page(page, "doi", url)["license"], parse_page(page, "pmh", url)["license"]


# --- 1. OJS: a licence line with no subject

# publicera.kb.se (Kulturella Perspektiv, Socialmedicinsk tidskrift): the masthead line, then the licence line
PUBLICERA = ('<p>Kulturella Perspektiv | ISSN 1102-7908 | ISSN (Online) 2004-0288</p><p>Utgiven av Föreningen '
             'Kulturella Perspektiv (org. nr. 894002-7843) | Open Access enligt <a href="{}" target="_blank" '
             'rel="noopener">Creative Commons CC-BY 4.0</a> </p>')
# bibliotecavirtual.unl.edu.ar: the portal's footer, on every journal's pages (here a login page)
PORTAL = ('<div style="clear: both;"><small>Excepto donde se indique explícitamente se publica bajo la siguiente '
          'licencia <a title="Creative Commons " href="{}" target="_blank" rel="noopener">Attribution-NonCommercial-'
          'ShareAlike 4.0 International (CC BY-NC-SA 4.0)</a>&nbsp;</small></div>')


@pytest.mark.parametrize("footer, expected", [
    (PUBLICERA.format(BY), "cc-by"),
    (PORTAL.format(BY_NC_SA), "cc-by-nc-sa"),
    # round 5's subjectless lines (tests/test_ojs_footer_licence_r5.py pinned them as none until this ruling)
    (f'<p>Licensed under a {BY_SA_NAME}.</p>', "cc-by-sa"),
    (f'<p>Distributed under a {BY_SA_NAME}.</p>', "cc-by-sa"),
    (f'<p>Published by the Example Scientific Publication under the terms of the <a href="{BY}">Creative Commons '
     'CC-BY 4.0</a> license.</p>', "cc-by"),
    (f'<p>Kulturella Perspektiv</p><p>is licensed under <a href="{BY_SA}">CC BY-SA 4.0</a></p>', "cc-by-sa"),
    # the badge beside the line, naming the same licence
    (f'<p>{BY_SA_BADGE}<br/>Licensed under a {BY_SA_NAME}.</p>', "cc-by-sa"),
    # the licence named by its short name only, with no link
    ('<p>Copyright (c) 2024 the authors. Published under CC BY-NC 4.0.</p>', "cc-by-nc"),
])
def test_an_ojs_licence_line_with_no_subject_is_the_journals_licence(footer, expected):
    assert licenses(page_of(footer)) == (expected, expected)


def test_the_portals_line_on_a_login_page_is_the_journals_licence():
    # 6b0f2beb: the stored page of the work is the journal's login form; the portal's footer is the journal's licence
    login = page_of(PORTAL.format(BY_NC_SA), OJS, title="Entrar | Natura Neotropicalis").replace(
        "<h1>An article</h1><p>Abstract text.</p>", "<h1>Entrar</h1><form><input name='username'/></form>")
    assert licenses(login, URL.replace("article/view/31627", "login")) == ("cc-by-nc-sa", "cc-by-nc-sa")


@pytest.mark.parametrize("footer", [
    # a badge alone, with or without a word: the licence is named only by a picture or an address
    f'<p>{BY_SA_BADGE}</p>',
    f'<p>Licensed under {BY_SA_BADGE}</p>',
    f'<p><a href="{BY_SA}">Creative Commons 4.0 International License</a>.</p>',
    f'<p>Creative Commons «Attribution» 4.0 <a href="{BY}">WorldWide</a>.</p>',
    # a line with a subject of its own, that is not the journal: a picture's credit, another journal, a site
    f'<p>Sabine\'s Gull by Andy Reago &amp; Chrissy McClarren is licensed under <a href="{BY}">CC BY 4.0</a></p>',
    f'<p>Jurnal Transparansi Hukum is licensed under a {BY_SA_NAME}.</p>',
    f'<p>Agronomia Costarricense is edited in the Universidad de Costa Rica under a license {BY_SA_NAME}.</p>',
    f'<p>Except where otherwise noted, content on this site is licensed under a {BY_SA_NAME}.</p>',
    f'<p>Official Website of eJournal System<br>All content is licensed under a {BY_SA_NAME}</p>',
    # a line that licenses the site, its metadata, the theme, the software, a picture, an icon
    f'<p>Website licensed under a {BY_SA_NAME}.</p>',
    f'<p>Metadata published under a {BY_SA_NAME}.</p>',
    f'<p>Theme by Example Studio, licensed under a {BY_SA_NAME}.</p>',
    f'<p>Header image: licensed under <a href="{BY}">CC BY 4.0</a>.</p>',
    f'<p>Icons by Example Icons, distributed under <a href="{BY}">CC BY 4.0</a>.</p>',
    # a condition, a date range
    f'<p>If published under a {BY_SA_NAME}, the work may be shared.</p>',
    f'<p>Published since 2019 under a {BY_SA_NAME}.</p>',
    # a line that is no licence's: the theme's credit with no licensing word
    '<p>U.S. Department of Agriculture, Grass Fed Beef - Ryan Thompson - USDAgov, <a href="https://creativecommons.org/'
    'licenses/by/2.0/legalcode">CC BY 2.0</a></p>',
    # the licence's name beside a picture is a badge too: "Licença" names the licence, it licenses nothing
    # (estacio.periodicoscientificos.com.br, found by the sizing)
    '<p><img src="/public/site/images/aricco/mceclip0.png" />: <a href="https://creativecommons.org/licenses/by-nc-nd/'
    '4.0/">Licença Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International</a></p>',
    f'<p>{BY_SA_BADGE}<br/>Licencia {BY_SA_NAME}</p>',
    # a subject cut off by an abbreviation's full stop (journalspress.uk, found by the sizing)
    '<p>Corporate Research Patents Pending. Copyrights © by Journals Press Hybrid Access Journals by Journal Press Inc. '
    'is licensed under a Creative Commons Attribution 4.0 International License.</p>',
])
def test_a_badge_a_line_about_something_else_or_a_condition_licenses_nothing(footer):
    assert licenses(page_of(footer)) == (None, None)


@pytest.mark.parametrize("footer", [
    # two licences in the chrome: the line and a badge of another licence, or two lines
    f'<p><img src="https://i.creativecommons.org/l/by-nc/4.0/88x31.png" alt=""/></p><p>Licensed under a {BY_SA_NAME}.</p>',
    PORTAL.format(BY_NC_SA) + f'<p>Licensed under a {BY_SA_NAME}.</p>',
    # the line names one licence in its words and another in its link
    f'<p>Licensed under a <a href="{BY_NC}">Creative Commons Attribution-ShareAlike 4.0 International License</a>.</p>',
])
def test_a_line_beside_another_licence_licenses_nothing(footer):
    assert licenses(page_of(footer)) == (None, None)


def test_the_articles_own_licence_wins_over_the_line():
    panel = ('<div class="item copyright"><p>This work is licensed under a <a rel="license" href="https://'
             'creativecommons.org/licenses/by-nc-nd/4.0/">Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 '
             'International License</a>.</p></div>')
    assert licenses(page_of(PUBLICERA.format(BY), panel=panel)) == ("cc-by-nc-nd", "cc-by-nc-nd")


def test_the_line_is_read_on_ojs_pages_only():
    head = KP.replace(OJS, "")
    assert licenses(page_of(PUBLICERA.format(BY), head, wrapper="<footer>{}</footer>")) == (None, None)
    assert licenses(page_of(PORTAL.format(BY_NC_SA), head, wrapper="<footer>{}</footer>")) == (None, None)
    assert licenses(page_of(f'<p>Licensed under a {BY_SA_NAME}.</p>', head, wrapper="<footer>{}</footer>")) == (
        None, None)


@pytest.mark.parametrize("generator", ["Open Monograph Press 3.3.0.8", "Open Preprint Systems 3.4.0.5"])
def test_a_presss_or_a_preprint_servers_line_is_not_a_journals(generator):
    page = page_of(f'<p>Licensed under a {BY_SA_NAME}.</p>', f'<meta name="generator" content="{generator}">')
    assert licenses(page) == (None, None)


# --- 2. any other site: a footer sentence that names the journal, its articles or its materials

OTHER_URL = "https://journal.example.edu/Abstract?AId=1201&DId=2590"
NOT_OJS = ('<meta name="citation_journal_title" content="Journal of Mahani Mathematical Research">'
           '<meta name="citation_journal_abbrev" content="JMMR">')


def site_page(footer, head=NOT_OJS, panel=""):
    return page_of(footer, head, panel, wrapper="<footer>{}</footer>", title="An article")


@pytest.mark.parametrize("footer, expected", [
    # journals.unite.edu.mk, natural-sciences.ru, pjph.eu
    ('<p>OPEN ACCESS JOURNAL</p><br><p>This is an open access journal, is following <a href="https://creativecommons.'
     'org/licenses/by/3.0/">CC-BY license</a> . </p>', "cc-by"),
    (f'<div><a href="{BY}" rel="license"><img src="https://i.creativecommons.org/l/by/4.0/88x31.png" alt="Лицензия '
     f'Creative Commons"></a><br/>Материалы журнала доступны по <a href="{BY}" rel="license">лицензии Creative '
     'Commons «Attribution» («Атрибуция») 4.0 Всемирная</a>. <br>Сайт работает на универсальной издательской '
     'платформе</div>', "cc-by"),
    ('<div id="footer">© 2013 Uniwersytet Medyczny w Lublinie. <br/>Czasopismo jest udostępnione w systemie Open Access '
     'na podstawie licencji otwartej Creative Commons (CC-BY-NC-ND).<br/>ISSN: 0044-2011</div>', "cc-by-nc-nd"),
    # the journal by its title in the page's tags (Sinaweb), and its articles
    (f'<p>{BY_SA_BADGE}<br/>Journal of Mahani Mathematical Research is licensed under a {BY_SA_NAME}.</p>', "cc-by-sa"),
    (f'<p>All articles published in this journal are licensed under a {BY_SA_NAME}</p>', "cc-by-sa"),
    (f'<p>Todos los artículos están licenciados bajo <a href="{BY}">Creative Commons Attribution 4.0 License</a>.</p>',
     "cc-by"),
    (f'<p>The work of the Journal is licensed under open access policy found via <a href="{BY_NC_SA}">Creative Commons '
     'Attribution-NonCommercial-ShareAlike 4.0 International License</a></p>', "cc-by-nc-sa"),
    # the content of the journals of a site of several journals (round 6's sentence, now off OJS too)
    (f'<p>El contenido de las Revistas de este sitio, están bajo una Licencia de <br/><a href="{BY_NC_SA}deed.es_ES">'
     'Creative Commons Reconocimiento-NoComercial-CompartirIgual 4.0 Internacional.</a></p>', "cc-by-nc-sa"),
])
def test_a_site_footer_that_names_the_journal_its_articles_or_its_materials(footer, expected):
    assert licenses(site_page(footer), OTHER_URL) == (expected, expected)


@pytest.mark.parametrize("footer", [
    # 3. the Creative Commons chooser's sentence (omjournal.org, Sinaweb): the site is "this work"
    f'<p>{BY_SA_BADGE}<br/>This work is licensed under a {BY_SA_NAME}.</p>',
    f'<p>Esta obra está bajo una <a href="{BY_NC}">Licencia Creative Commons Atribución-NoComercial 4.0</a>.</p>',
    f'<p>Ciptaan disebarluaskan di bawah <a href="{BY}">Lisensi Creative Commons Atribusi 4.0 Internasional</a>.</p>',
    f'<p>The publication is licensed under a <a href="{BY_NC}">Creative Commons License</a>.</p>',
    # a line with no subject, a badge, the journal's title beside a badge only
    f'<p>Licensed under a {BY_SA_NAME}.</p>',
    f'<p>Published by the Example Scientific Publication under the terms of the <a href="{BY}">CC-BY 4.0</a> '
    'license.</p>',
    f'<p>{BY_SA_BADGE}</p>',
    f'<p>Journal of Mahani Mathematical Research: {BY_SA_BADGE}</p>',
    f'<p>Journal of Mahani Mathematical Research is licensed under a <a href="{BY_SA}">licence</a>.</p>',
    # the site and its content, as on OJS
    f'<p>Except where otherwise noted, all material on this site is licensed under a {BY_SA_NAME}.</p>',
    f'<p>The website of this journal is licensed under a {BY_SA_NAME}.</p>',
    f'<p>All published work is licensed under a {BY_SA_NAME}</p>',
    # another journal's name, and only some of the articles
    f'<p>Journal of Examples is licensed under a {BY_SA_NAME}.</p>',
    f'<p>All articles published before 2016 are licensed under a {BY_SA_NAME}.</p>',
])
def test_off_ojs_this_work_a_bare_line_or_a_badge_still_licenses_nothing(footer):
    assert licenses(site_page(footer), OTHER_URL) == (None, None)


PERSIAN = ('<meta name="citation_journal_title" content="متن پژوهی ادبی" />'
           '<meta name="DC.Source" content="متن پژوهی ادبی" />')


@pytest.mark.parametrize("footer, expected", [
    # Sinaweb: the tags name the journal in Persian, the footer in English
    (f'<p><a href="{BY_NC}" rel="license"><img src="https://i.creativecommons.org/l/by-nc/4.0/88x31.png" '
     f'alt="Creative Commons License" /></a><br />Literary Text Research is licensed under a <a href="{BY_NC}" '
     'rel="license">Creative Commons Attribution-NonCommercial 4.0 International License</a>.</p>', "cc-by-nc"),
    ('<p>Amirkabir Journal of Civil Engineering&nbsp;is licensed under a<br /><a href="https://creativecommons.org/'
     'licenses/by-nc/2.0/">Creative Commons Attribution-NonCommercial 2.0 Generic (CC BY-NC 2.0)</a></p>', "cc-by-nc"),
    # the look-alikes: "This work", an author's credit, a single word, a picture
    (f'<p>This work is licensed under a {BY_SA_NAME}.</p>', None),
    (f'<p>Sabine\'s Gull by Andy Reago is licensed under a {BY_SA_NAME}.</p>', None),
    (f'<p>Sinaweb is licensed under a {BY_SA_NAME}.</p>', None),
    (f'<p>Cover Image is licensed under a {BY_SA_NAME}.</p>', None),
])
def test_a_journal_tagged_only_in_another_script_names_itself_in_latin_letters(footer, expected):
    assert licenses(site_page(footer, PERSIAN), OTHER_URL) == (expected, expected)


def test_a_latin_title_is_not_the_journals_when_the_tags_name_it_in_latin_letters():
    footer = f'<p>Literary Text Research is licensed under a {BY_SA_NAME}.</p>'
    assert licenses(site_page(footer), OTHER_URL) == (None, None)  # the tags: Journal of Mahani Mathematical Research
    assert licenses(site_page(footer, ""), OTHER_URL) == (None, None)  # no tags: nothing says it is a journal's page


def test_off_ojs_the_journals_name_is_its_title_in_the_tags_not_the_sites_title():
    footer = f'<p>Example Blog is licensed under a {BY_SA_NAME}.</p>'
    assert licenses(page_of(footer, "", wrapper="<footer>{}</footer>", title="A post | Example Blog"), OTHER_URL) == (
        None, None)


def test_off_ojs_the_articles_own_licence_wins_and_two_licences_license_nothing():
    statement = f'<p>All articles published in this journal are licensed under a {BY_SA_NAME}</p>'
    panel = (f'<div class="license"><p>This article is distributed under a <a href="{BY_NC}">CC BY-NC 4.0</a> '
             'licence.</p></div>')
    assert licenses(site_page(statement, panel=panel), OTHER_URL) == ("cc-by-nc", "cc-by-nc")
    badge = '<p><img src="https://i.creativecommons.org/l/by-nc/4.0/88x31.png" alt=""/></p>'
    assert licenses(site_page(badge + statement), OTHER_URL) == (None, None)
    # an article whose own text speaks of Creative Commons, in a way this reader cannot read, keeps the footer out
    words = '<p>Reuse of this article: see the Creative Commons notice of the society.</p>'
    assert licenses(site_page(statement, panel=words), OTHER_URL) == (None, None)


def test_the_footer_statement_is_read_on_the_parsers_paths_only():
    # the bare search text (fulltext.py's check that an OJS issue page's licence is the footer's) reads no footer
    page = site_page(f'<p>All articles published in this journal are licensed under a {BY_SA_NAME}</p>')
    assert "All articles published" not in license_search_text(page, OTHER_URL)
    assert "All articles published" in license_search_text(page, OTHER_URL, journal_footer=True)


# --- 4. two more whole-site hosts

@pytest.mark.parametrize("url, footer, expected", [
    ("https://eve.gd/2011/03/15/unreasonable-fees-by-which-metric/",
     '<footer><span>© 2023 Martin Paul Eve. Unless otherwise noted, all material on this site is licensed under a <a '
     'href="http://creativecommons.org/licenses/by/4.0/deed.en_US">Creative Commons Attribution 4.0 License</a>. '
     '<a href="http://thenounproject.com/term/student/63368/">Favicon by Joseph Wilson under a CC BY 3.0 license</a>.'
     '</span></footer>', "cc-by"),
    ("https://wals.info/languoid/lect/wals_code_uma",
     f'<footer><div class="span6"><a rel="license" href="{BY}"><img alt="License" src="https://wals.info/clld-static/'
     'images/cc-by.png" /></a><br /><span class="Dataset" property="dct:title">WALS Online</span> edited by <span '
     'property="cc:attributionName">Dryer, Matthew S. &amp; Haspelmath, Martin</span><br />is licensed under a <a '
     f'rel="license" href="{BY}">Creative Commons Attribution 4.0 International License</a>.</div></footer>', "cc-by"),
])
def test_eve_gd_and_wals_info_license_every_item_in_their_footer(url, footer, expected):
    page = f"<html><head><title>t</title></head><body><main><p>A post.</p></main>{footer}</body></html>"
    assert licenses(page, url) == (expected, expected)
    # the same footer on another host licenses nothing
    assert licenses(page, "https://blog.example.org/2011/03/15/post/") == (None, None)


def test_wals_infos_reference_database_is_not_licensed_by_its_footer():
    # a record of someone else's publication ("Redden et al. 1963"), found by the sizing
    footer = (f'<footer><a rel="license" href="{BY}"><img alt="License" src="https://wals.info/clld-static/images/'
              'cc-by.png" /></a><br /><span class="Dataset" property="dct:title">WALS Online</span> edited by Dryer, '
              f'Matthew S. &amp; Haspelmath, Martin<br />is licensed under a <a rel="license" href="{BY}">Creative '
              'Commons Attribution 4.0 International License</a>.</footer>')
    page = f"<html><head><title>t</title></head><body><main><p>Reference.</p></main>{footer}</body></html>"
    assert licenses(page, "https://wals.info/refdb/record/Redden-et-al-1963") == (None, None)
    assert licenses(page, "https://wals.info/chapter/1") == ("cc-by", "cc-by")
