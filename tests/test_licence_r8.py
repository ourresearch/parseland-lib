"""
Licence readers, round 8 (oxjob #2239, phase 2; check1's confirmed-worse licence pages). Policy choice: follows
charter § 6 2026-11-17 08:20 (landing-pages): on OJS a single-licence footer line counts; off OJS a footer sentence
that names the journal, its articles or its materials counts; "This work is licensed under ...", subjectless lines and
badges stay none off OJS; two licences in the chrome license nothing; the article's own statement wins.

What round 8 reads that round 7 missed (each a mechanism, not a site):
- footer statements whose words the patterns did not know: Ukrainian "Цей твір ліцензовано" (the pattern wanted "Це"),
  Persian "این نشریه" (this journal, Sinaweb), "Articles are published under ...", "All <conference> proceedings are
  licenced under ...", a journal's title in words with no meta tags ("The <...> Review is published under ..."),
  Italian "è distribuita con Licenza ..." (a subjectless OJS line);
- a statement whose licence is named only in another language's words ("Licença Creative Commons Atribuição 4.0"),
  read from the one licence its block links to when the words spell that licence's terms;
- a statement cut in two by markup ("... is licensed under a</p><p><a>Creative Commons ...</a>");
- the article's own block in a short form ("Licencia Creative Commons BY-NC-ND 4.0") agrees with the footer;
- a page wrapper named "not-footer" is the page, not its footer;
and what it stops reading: a "Public Domain" subject term in a script's taxonomy, a photo credit's "- CC BY-SA", and on
eScholarship the licences of other issues in the page's data. Fragments mirror stored pages; no network.
"""
import pytest

from parseland_lib.legacy_parse_utils.version_and_license import license_search_text
from parseland_lib.legacy_parse_utils.pdf import find_normalized_license
from parseland_lib.parse import parse_page

OJS = '<meta name="generator" content="Open Journal Systems 3.3.0.7">'
OJS_FOOTER = ('<div class="pkp_structure_footer_wrapper" role="contentinfo"><div class="pkp_structure_footer">'
              '<div class="pkp_footer_content">{}</div></div></div>')
BODY = "<main><h1>An article</h1><p>Abstract text.</p>{panel}</main>"
BY = "https://creativecommons.org/licenses/by/4.0/"
BY_NC = "http://creativecommons.org/licenses/by-nc/4.0/"
BY_ND = "http://creativecommons.org/licenses/by-nd/4.0/"
BY_NC_ND = "https://creativecommons.org/licenses/by-nc-nd/4.0/deed.es"
BY_NC_SA = "http://creativecommons.org/licenses/by-nc-sa/3.0/"


def page_of(footer, head=OJS, panel="", wrapper=OJS_FOOTER, title="An article | A Journal"):
    return (f"<html><head><title>{title}</title>{head}</head><body>{BODY.format(panel=panel)}"
            f"{wrapper.format(footer)}</body></html>")


def licence(page, url="https://journal.example.org/index.php/j/article/view/1", ns="doi"):
    return parse_page(page, ns, url)["license"]


# --- OJS footers (rule 1)

# ojs.nusta.edu.ua: "This work is licensed under ..." in Ukrainian ("Цей твір", masculine; the pattern only knew "Це")
NUSTA = (f'<p><a href="{BY_NC}" rel="license"><img src="https://i.creativecommons.org/l/by-nc/4.0/88x31.png" '
         f'alt="Ліцензія Creative Commons"></a><br>Цей твір ліцензовано на умовах <a href="{BY_NC}" rel="license">'
         'Ліцензії Creative Commons Із Зазначенням Авторства — Некомерційна 4.0 Міжнародна</a>..</p>')


def test_ukrainian_this_work_on_ojs():
    assert licence(page_of(NUSTA)) == "cc-by-nc"


# ppg.revistas.uema.br: the licence is named in Portuguese words only; the badge link before the sentence and the
# address after "visite:" name the one licence the words spell
UEMA = (f'<p><a href="https://creativecommons.org/licenses/by/4.0/deed.pt_BR"><img src="/public/by.png" alt="" /></a> '
        '<br />Este trabalho está licenciado sob uma Licença Creative Commons Atribuição 4.0 Internacional. Para ver '
        'uma cópia desta licença, visite: <a href="https://creativecommons.org/licenses/by/4.0/deed.pt_BR">'
        'https://creativecommons.org/licenses/by/4.0/deed.pt_BR</a>. Direitos para esta edição foram cedidos pelos '
        'autores.</p>')


def test_licence_in_portuguese_words_takes_the_blocks_one_link():
    assert licence(page_of(UEMA)) == "cc-by"


def test_portuguese_words_that_spell_other_terms_than_the_link_stay_none():
    # the words say Atribuição-NãoComercial, the links say by: which one is meant is not said
    other = UEMA.replace("Atribuição 4.0", "Atribuição-NãoComercial 4.0")
    assert licence(page_of(other)) is None


def test_portuguese_words_with_two_licences_linked_stay_none():
    two = UEMA.replace('visite: <a href="https://creativecommons.org/licenses/by/4.0/deed.pt_BR">',
                       'visite: <a href="https://creativecommons.org/licenses/by-sa/4.0/">')
    assert licence(page_of(two)) is None


# ojs.unica.it (Rhesis): the journal named in one sentence, "È edita da ... ed è distribuita con Licenza ..." the next
RHESIS = ('<p><em>Rhesis. International Journal of Linguistics</em> è una rivista del Dipartimento di Lettere '
          'dell’Università di Cagliari. È edita da <a href="https://unicapress.example.it/">UNICApress</a>,&nbsp;casa '
          f'editrice dell’Università ed è distribuita con Licenza&nbsp;<a href="{BY_ND}">Creative Commons '
          'Attribuzione - Non opere derivate 4.0 Internazionale</a></p>')


def test_italian_distributed_under_on_ojs():
    assert licence(page_of(RHESIS), ns="pmh") == "cc-by-nd"


def test_italian_line_that_licenses_the_site_stays_none():
    site = RHESIS.replace("ed è distribuita", "e il sito web è distribuito")
    assert licence(page_of(site), ns="pmh") is None


# ejournal.uin-suka.ac.id (INKLUSI): the statement cut into three paragraphs by the theme's table cell
INKLUSI_HEAD = OJS + '<meta name="citation_journal_title" content="INKLUSI">'
INKLUSI = ('<table><tr><td><p>ISSN 2355-8954</p></td><td>'
           f'<p><a href="{BY_NC}" rel="license"><img src="https://i.creativecommons.org/l/by-nc/4.0/88x31.png" '
           'alt="Creative Commons License" /></a></p><p>All publications</p>'
           '<p>by <em>INKLUSI: Journal of Disability Studies </em>is licensed under a</p>'
           f'<p><a href="{BY_NC}" rel="license">Creative Commons Attribution-NonCommercial 4.0 International License</a>'
           '</p></td></tr></table>')
FOOTER_TAG = '<footer class="footer" role="contentinfo">{}</footer>'


def test_statement_cut_by_paragraphs_is_read_whole():
    assert licence(page_of(INKLUSI, head=INKLUSI_HEAD, wrapper=FOOTER_TAG)) == "cc-by-nc"


def test_cut_statement_off_ojs_still_needs_the_journal():
    # "This work is licensed under a" / <p>licence</p> on a site that is not OJS: rule 3, none
    cut = ('<p>This work is licensed under a</p>'
           f'<p><a href="{BY_NC}" rel="license">Creative Commons Attribution-NonCommercial 4.0 International License</a>'
           '</p>')
    assert licence(page_of(cut, head="", wrapper=FOOTER_TAG)) is None


# --- Other journal sites (rule 2)

def off_ojs(footer, head="", wrapper=FOOTER_TAG, title="An article"):
    return page_of(footer, head=head, wrapper=wrapper, title=title)


# cejiss.org (Joomla)
CEJISS = ('<p>© 2007 - 2021 CEJISS. eISSN 1805-482X. Articles are published under the '
          '<a href="https://creativecommons.org/licenses/by-nc/4.0/">CC BY-NC 4.0</a> licence.</p>')


def test_articles_are_published_under():
    assert licence(off_ojs(CEJISS)) == "cc-by-nc"


def test_site_content_is_published_under_stays_none():
    site = CEJISS.replace("Articles are published under", "Site content is published under")
    assert licence(off_ojs(site)) is None


# jhistory.um.ac.ir (Sinaweb): "this journal is under the international licence ..." in Persian
SINAWEB = (f'<p><a href="{BY}"><img src="/images/cc.png" alt="" /></a></p>'
           f'<p>این نشریه تحت مجوز بین المللی <a href="{BY}">Creative Commons Attribution 4.0</a> می باشد.</p>')


def test_persian_this_journal():
    assert licence(off_ojs(SINAWEB)) == "cc-by"


def test_persian_this_work_off_ojs_stays_none():
    # "این اثر" (this work) off OJS: rule 3
    assert licence(off_ojs(SINAWEB.replace("این نشریه", "این اثر"))) is None


# lrec.elra.info
LREC = ('<div>All LREC proceedings (including proceedings from workshops) are licenced under CC-BY-NC-4.0, the '
        '<a href="https://creativecommons.org/licenses/by-nc/4.0/">Creative Commons Attribution-NonCommercial 4.0 '
        'International License</a>.</div>')


def test_all_proceedings_are_licensed_under():
    assert licence(off_ojs(LREC, wrapper='<footer class="border-t">{}</footer>')) == "cc-by-nc"


# timreview.ca and gsconlinepress.com (Drupal): the journal named by its title in words, no journal meta tags
TIM = ('<p>Copyright © Talent First Network 2007–2023 ISSN: 1927-0321 Formerly the Open Source Business Resource '
       'The Technology Innovation Management Review is published under a <a href="http://creativecommons.org/licenses/'
       'by/3.0/">Creative Commons Attribution 3.0 Unported License</a>. Authors retain full copyright.</p>')
GSC = ('<p>GSC Advanced Research and Reviews (GSCARR) is licensed under a <a rel="license" href="' + BY_NC_SA + '">'
       'Creative Commons Attribution-Non Commercial-Share Alike 3.0 Unported License</a>. Based on a work at '
       'www.gsconlinepress.com.</p>')


@pytest.mark.parametrize("footer, expected", [(TIM, "cc-by"), (GSC, "cc-by-nc-sa")])
def test_journal_title_in_words(footer, expected):
    assert licence(off_ojs(footer, wrapper='<footer class="footer container">{}</footer>')) == expected


@pytest.mark.parametrize("subject", [
    "The Example Research Centre",  # no journal word: a site or an organisation
    "Journal Theme by ThemeForest",  # a theme's credit (and "by ...": someone else's)
    "The Journal of Web Semantics website",  # the website
])
def test_titles_that_name_no_journal_stay_none(subject):
    footer = TIM.replace("The Technology Innovation Management Review", subject)
    assert licence(off_ojs(footer, wrapper='<footer class="footer container">{}</footer>')) is None


# --- The article's own statement

# revistas.cef.udima.es: the article's "Licencia" block in short form, and the OJS footer's statement of the same licence
UDIMA_PANEL = ('<div class="item copyright"><a rel="license" href="/licencia" class="copyright">Derechos de autor '
               '2003 - Todos los derechos reservados durante un año desde la fecha de publicación y Licencia Creative '
               'Commons BY-NC-ND 4.0 pasado el primer año de la fecha de publicación.</a></div>')
UDIMA = (f'<p>Esta obra está bajo una <a href="{BY_NC_ND}">Licencia creative commons CC BY-NC-ND 4.0</a></p>')


def test_article_block_in_short_form_is_read():
    assert licence(page_of(UDIMA, panel=UDIMA_PANEL)) == "cc-by-nc-nd"
    # the footer under an embargo says nothing; the article's own block still does
    embargo = '<p>Esta revista se encuentra bajo un periodo de embargo de 12 meses tras el cual es de acceso ' \
              f'gratuito mediante una <a href="{BY_NC_ND}">Licencia creative commons CC BY-NC-ND 4.0</a></p>'
    assert licence(page_of(embargo, panel=UDIMA_PANEL)) == "cc-by-nc-nd"


def test_article_block_in_short_form_that_disagrees_wins():
    other = UDIMA_PANEL.replace("BY-NC-ND", "BY-NC-SA")
    assert licence(page_of(UDIMA, panel=other)) == "cc-by-nc-sa"


@pytest.mark.parametrize("text, expected", [
    ("Licencia Creative Commons BY-NC-ND 4.0", "cc-by-nc-nd"),
    ("Creative Commons BY-SA 4.0", "cc-by-sa"),
    ("Creative Commons BY-NC 3.0", "cc-by-nc"),
    ("shared under Creative Commons by the authors", None),  # one term: plain English, not read
    ('<img src="/files/2015/05/creative-commons-by-nc-nd-300x104.png" />', None),  # a picture's file name
])
def test_family_name_with_short_form(text, expected):
    assert find_normalized_license(text) == expected


# wlv.openrepository.com (Atmire Open Repository, via hdl.handle.net): <div id="not-footer"> wraps the whole page
NOT_FOOTER = ('<html><head><title>Item</title></head><body><div id="not-footer"><header><nav>Menu</nav></header>'
              '<div class="row"><div class="col-sm-3"><a rel="license" href="https://creativecommons.org/licenses/by/'
              '4.0/"><img src="/themes/OR/images/creativecommons/cc-by.png" alt="" /></a></div><div class="col-sm-8">'
              "<span>Except where otherwise noted, this item's license is described as "
              'https://creativecommons.org/licenses/by/4.0/</span></div></div></div>'
              '<footer><p>Site footer</p></footer></body></html>')


def test_not_footer_wrapper_is_the_page():
    assert licence(NOT_FOOTER, url="https://wlv.openrepository.example/handle/2436/625343", ns="pmh") == "cc-by"


def test_real_footer_inside_a_not_footer_wrapper_still_goes():
    page = ('<html><head><title>Item</title></head><body><div id="not-footer"><header><nav>Menu</nav></header>'
            '<div class="row"><p>An item.</p></div><footer class="site"><p>Content on this site is licensed under '
            '<a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA</a></p></footer></div></body></html>')
    assert licence(page, url="https://wlv.openrepository.example/handle/2436/1", ns="pmh") is None


# --- What is not a licence statement

# sk.sagepub.com: the encyclopedia's subject taxonomy, in a script, has a term "Public Domain"
SAGE = ("<html><head><title>Entry</title><script>var terms = [{ 'type': 'NV', 'name': ' Federal Sentencing "
        "Guidelines', 'position': '613' },{ 'type': 'NV', 'name': ' Public Domain', 'position': '614' }];</script>"
        "</head><body><main><p>Sign in to access this content</p></main></body></html>")


def test_public_domain_subject_term_is_not_a_licence():
    assert licence(SAGE, url="https://sk.example.com/reference/ethics/n250") is None


def test_public_domain_statement_still_counts():
    page = SAGE.replace("<p>Sign in", "<p>This work is in the public domain.</p><p>Sign in")
    assert licence(page, url="https://sk.example.com/reference/ethics/n250") == "public-domain"


# joi.ito.com: a photo credit "Photo by <name> via Flickr - CC BY-SA" in the post's description
CREDIT = ('<html><head><title>Post</title><meta name="description" content="Photo by wp paarz via Flickr - CC BY-SA '
          'The term society-in-the-loop machine learning ..."></head><body><main><p>Text.</p></main></body></html>')


def test_photo_credit_with_a_dash_is_not_the_works_licence():
    assert licence(CREDIT, url="https://blog.example.com/2016/06/29/post.html") is None


def test_dash_cc_without_a_photo_credit_still_counts():
    page = CREDIT.replace("Photo by wp paarz via Flickr - CC BY-SA", "Licence - CC BY-SA")
    assert licence(page, url="https://blog.example.com/2016/06/29/post.html") == "cc-by-sa"


# escholarship.org: the item's own "rights" in the page data, never the journal's other issues' in the navigation data
ESCHOL = ('<html><head><title>Item</title></head><body><div id="main"></div><script>window.jscholApp_initialPageData = '
          '{"unit":{"id":"ucm_mwp_ucmurj"},"article":{"genre":"article","id":"53f3s8gg","index_digest":"pfeb==",'
          '"last_indexed":"2019-02-02 20:30:05 +0000","oa_policy":null,"ordering_in_sect":10006,'
          '"pdf_url":"/content/qt53f3s8gg/qt53f3s8gg.pdf","preview_key":null,"published":"2017","rights":{rights},'
          '"sidebar":[]},"header":{"nav":[{"issue_id":2568,"volume":"13","attrs":{"rights":'
          '"https://creativecommons.org/licenses/by-nc-nd/4.0/","description":""}}]}};</script></body></html>')
ESCHOL_URL = "https://escholarship.org/uc/item/53f3s8gg"


def test_escholarship_item_without_rights_takes_no_issue_licence():
    page = ESCHOL.replace("{rights}", "null")
    assert licence(page, url=ESCHOL_URL) is None


def test_escholarship_item_rights_is_its_licence():
    page = ESCHOL.replace("{rights}", '"https://creativecommons.org/licenses/by/4.0/"')
    assert licence(page, url=ESCHOL_URL) == "cc-by"
    assert find_normalized_license(license_search_text(page, ESCHOL_URL)) == "cc-by"


def test_title_in_words_only_where_no_tag_names_the_journal():
    footer = TIM.replace("The Technology Innovation Management Review", "Journal of Examples")
    wrapper = '<footer class="footer container">{}</footer>'
    assert licence(off_ojs(footer, wrapper=wrapper)) == "cc-by"
    # the page's tags name its journal: "Journal of Examples" is another one
    tagged = '<meta name="citation_journal_title" content="Kulturella Perspektiv">'
    assert licence(off_ojs(footer, head=tagged, wrapper=wrapper)) is None
