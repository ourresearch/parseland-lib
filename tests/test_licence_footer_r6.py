"""
An Open Journal Systems journal's footer licence, the wordings round 5 did not read (oxjob #2239, phase 2, round 6).

Charter § 6, 16 Nov 2026 09:30: on an OJS page a footer statement that licenses the journal or its articles is the
article's licence; a badge alone, a footer naming two different licences and a statement about the site or its
metadata only are not; every non-OJS site footer still is not. Round 5 (tests/test_ojs_footer_licence_r5.py) built the
rule. Here, from the loop's dev pages:

- "El contenido de las Revistas de este sitio, están bajo una Licencia ..." (a site of several journals): the content
  of the journals, not of the site;
- an OJS 2 issue page, which has no citation tags and no journal in its title, knows its journal by the feed links
  OJS writes in its head;
- the journal's name written without its accents ("Agronomia Mesoamericana" for "Agronomía Mesoamericana");
- "Attribution-NonCommercial-NonDerivative" is BY-NC-ND;
- the article's own copyright block may say the same licence in words ("the attribution, non-commercial and
  no-derivative license from Creative Commons"): then the footer's statement stands.

Statements that name no journal, work or articles stay out and are pinned here as they are on the pages, so nobody
reads them by accident: they wait for a decision. Fragments mirror stored pages; no network.
"""
import pytest

from parseland_lib.legacy_parse_utils.pdf import find_normalized_license
from parseland_lib.parse import parse_page

URL = "https://revistas.example.org/index.php/agromeso/article/view/4911"
OJS = '<meta name="generator" content="Open Journal Systems 3.3.0.8">'
JOURNAL = (OJS + '<meta name="citation_journal_title" content="Agronomía Mesoamericana">'
           '<meta name="citation_journal_abbrev" content="Agron. Mesoam.">'
           '<meta name="DC.Source.URI" content="https://revistas.example.org/index.php/agromeso">')
BODY = "<main><h1>An article</h1><p>Abstract text.</p>{panel}</main>"
BY = "https://creativecommons.org/licenses/by/4.0/"
BY_NC ="https://creativecommons.org/licenses/by-nc/4.0/"
BY_NC_SA = "https://creativecommons.org/licenses/by-nc-sa/4.0/"
BY_NC_ND = "https://creativecommons.org/licenses/by-nc-nd/4.0/"
OJS_FOOTER = ('<div class="pkp_structure_footer_wrapper" role="contentinfo"><div class="pkp_footer_content">{}</div>'
              '</div>')


def page_of(footer, head=JOURNAL, panel="", wrapper=OJS_FOOTER, title="An article | Agronomía Mesoamericana"):
    return (f"<html><head><title>{title}</title>{head}</head><body>{BODY.format(panel=panel)}"
            f"{wrapper.format(footer)}</body></html>")


def licenses(page, url=URL):
    """The licence on the publisher path and on the repository path."""
    return parse_page(page, "doi", url)["license"], parse_page(page, "pmh", url)["license"]


# --- the content of the site's journals (universidadverdad.uazuay.edu.ec)

SITE_JOURNALS = ('<p>Editor responsable: Universidad del Azuay.<br/>Av. 24 de Mayo 7-77 y Hernán Malo, Cuenca – '
                 'Ecuador.<br/>Correo electrónico: <strong>agromeso@example.org</strong><br/>El contenido de las '
                 f'Revistas de este sitio, están bajo una Licencia de <br/><a href="{BY_NC_SA}deed.es_ES" '
                 'target="_blank" rel="noopener">Creative Commons Reconocimiento-NoComercial-CompartirIgual 4.0 '
                 'Internacional.</a></p>')


@pytest.mark.parametrize("footer, expected", [
    (SITE_JOURNALS, "cc-by-nc-sa"),
    (f'<p>Los contenidos de las revistas de este portal están bajo una <a href="{BY}">Licencia Creative Commons '
     'Atribución 4.0 Internacional</a>.</p>', "cc-by"),
    # Portuguese
    (f'<p>O conteúdo das revistas deste portal está licenciado sob uma <a href="{BY_NC}">Licença Creative Commons '
     'Atribuição-NãoComercial 4.0 Internacional</a>.</p>', "cc-by-nc"),
    # one journal, as before
    (f'<p>El contenido de la revista está bajo una <a href="{BY_NC}">licencia Creative Commons</a>.</p>', "cc-by-nc"),
])
def test_the_content_of_the_sites_journals_is_the_journals_content(footer, expected):
    assert licenses(page_of(footer)) == (expected, expected)


@pytest.mark.parametrize("footer", [
    # the look-alikes: the site's own content, its metadata, its pages
    f'<p>El contenido de este sitio está bajo una <a href="{BY_NC_SA}">Licencia de Creative Commons '
    'Reconocimiento-NoComercial-CompartirIgual 4.0 Internacional</a>.</p>',
    f'<p>O conteúdo deste site está licenciado sob uma <a href="{BY}">Licença Creative Commons Atribuição 4.0 '
    'Internacional</a>.</p>',
    f'<p>El contenido de las revistas y los metadatos de este sitio están bajo una <a href="{BY}">Licencia Creative '
    'Commons Atribución 4.0 Internacional</a>.</p>',
    f'<p>Los metadatos de las revistas de este sitio están bajo una <a href="{BY}">Licencia Creative Commons '
    'Atribución 4.0 Internacional</a>.</p>',
    f'<p>El contenido del sitio web de las revistas está bajo una <a href="{BY}">Licencia Creative Commons Atribución '
    '4.0 Internacional</a>.</p>',
    f'<p>El contenido de las revistas de este sitio y sus páginas están bajo una <a href="{BY}">Licencia Creative '
    'Commons Atribución 4.0 Internacional</a>.</p>',
])
def test_the_content_of_the_site_itself_still_licenses_nothing(footer):
    assert licenses(page_of(footer)) == (None, None)


def test_the_same_sentence_on_a_page_that_is_not_an_ojs_page_licenses_nothing():
    page = page_of(SITE_JOURNALS, JOURNAL.replace(OJS, ""), wrapper="<footer>{}</footer>")
    assert licenses(page) == (None, None)


# --- an OJS 2 issue page names its journal in its feed links only (e-journal.stkipsiliwangi.ac.id, Eltin)

ISSUE_URL = "http://e-journal.example.ac.id/index.php/eltin/issue/view/48"
OJS2 = '<meta name="generator" content="Open Journal Systems 2.4.8.0" />'
FEEDS = ('<link rel="alternate" type="application/atom+xml" title="Eltin Journal : Journal of English Language '
         'Teaching in Indonesia (atom+xml)" href="http://e-journal.example.ac.id/index.php/eltin/gateway/plugin/'
         'WebFeedGatewayPlugin/atom" /><link rel="alternate" type="application/rss+xml" title="Eltin Journal : '
         'Journal of English Language Teaching in Indonesia (rss+xml)" href="http://e-journal.example.ac.id/index.php/'
         'eltin/gateway/plugin/WebFeedGatewayPlugin/rss2" />')
OJS2_FOOTER = '<div id="footer"><div id="footerContent"><div id="pageFooter">{}</div></div></div>'
ELTIN = ('<p><strong>Eltin </strong>is published by STKIP Siliwangi, Indonesia</p><p> <br />Eltin by '
         'http://e-journal.example.ac.id/index.php/eltin is licensed under a Creative Commons Attribution - Share '
         'Alike 4.0 Internasional License.</p><p>p-ISSN: 2339-1561</p>')


def issue_page(footer, head=OJS2 + FEEDS):
    return page_of(footer, head, wrapper=OJS2_FOOTER, title="Vol 5, No 1 (2017)")


@pytest.mark.parametrize("footer", [
    ELTIN,  # the last part of the journal's address
    '<p>Eltin Journal is licensed under a Creative Commons Attribution-ShareAlike 4.0 International License.</p>',
])
def test_an_ojs_2_issue_page_knows_its_journal_by_its_feed_links(footer):
    assert licenses(issue_page(footer), ISSUE_URL) == ("cc-by-sa", "cc-by-sa")


@pytest.mark.parametrize("head", [
    OJS2,  # the page names no journal
    # some other feed, with a title: not the journal's own
    OJS2 + '<link rel="alternate" type="application/rss+xml" title="Eltin" href="http://e-journal.example.ac.id/feed/"'
           ' />',
    # the feed of a site of several journals names no journal
    OJS2 + '<link rel="alternate" type="application/atom+xml" href="http://e-journal.example.ac.id/index.php/index/'
           'gateway/plugin/WebFeedGatewayPlugin/atom" />',
])
def test_without_the_journals_own_feed_the_page_names_no_journal(head):
    assert licenses(issue_page(ELTIN, head), ISSUE_URL) == (None, None)


def test_another_journals_statement_on_the_issue_page_licenses_nothing():
    footer = '<p>Jurnal Transparansi Hukum is licensed under a Creative Commons Attribution-ShareAlike 4.0 License.</p>'
    assert licenses(issue_page(footer), ISSUE_URL) == (None, None)


# --- the journal's name without its accents, and "NonDerivative" (revistas.ucr.ac.cr, Agronomía Mesoamericana)

UCR = (f'<p><a href="{BY_NC_ND}"><img src="//revistas.example.org/public/site/images/nanleon/by-nc-nd.png" alt="" '
       'width="215" height="74"/></a> Agronomia Mesoamericana is edited in the Universidad de Costa Rica under a '
       'license Creative Commons Attribution-NonCommercial-NonDerivative 4.0 International. For more information '
       'write to pccmca@example.org</p>')


def test_the_journal_named_without_its_accents_is_the_journal():
    assert licenses(page_of(UCR)) == ("cc-by-nc-nd", "cc-by-nc-nd")
    # no link at all: the words alone name the licence
    assert licenses(page_of(UCR.replace(f'<a href="{BY_NC_ND}">', "<a>"))) == ("cc-by-nc-nd", "cc-by-nc-nd")


@pytest.mark.parametrize("footer", [
    # the look-alikes: another journal's name; the words and the link name different licences
    UCR.replace("Agronomia Mesoamericana", "Agronomia Costarricense"),
    UCR.replace("Agronomia Mesoamericana", "Agronomias Mesoamericanas"),
    UCR.replace(BY_NC_ND, BY_NC),
])
def test_another_name_or_another_licence_beside_it_licenses_nothing(footer):
    assert licenses(page_of(footer)) == (None, None)


@pytest.mark.parametrize("text, expected", [
    ("Creative Commons Attribution-NonCommercial-NonDerivative 4.0 International", "cc-by-nc-nd"),
    ("Creative Commons Attribution-NonCommercial-Non-Derivatives 4.0 International Licence", "cc-by-nc-nd"),
    ("Creative Commons Attribution Non Derivatives 4.0", "cc-by-nd"),
    # the look-alikes
    ("Creative Commons Attribution-NonCommercial 4.0 International", "cc-by-nc"),
    ("We study non-derivative instruments. Licensed under a Creative Commons Attribution License.", "cc-by"),
    ("a common derivation of the non-derivative case", None),
])
def test_non_derivative_is_no_derivatives(text, expected):
    assert find_normalized_license(text) == expected


# --- the article's own block says the same licence in words

IN_WORDS = ('<div class="item copyright"><h2 class="label">License</h2><p><br/>a. Authors retain the copyright and '
            'assign to the journal the right to the first publication, with the work registered under the attribution, '
            'non-commercial and no-derivative license from Creative Commons, which allows third parties to use what '
            'has been published as long as they mention the authorship of the work and upon first publication in '
            'this journal, the work may not be used for commercial purposes and the publications may not be used to '
            'remix, transform or create another work.</p></div>')
# the Spanish text of PKP's default copyright notice
IN_SPANISH = ('<div class="item copyright"><p>Los autores/as conservan los derechos de autor y ceden a la revista el '
              'derecho de la primera publicación, con el trabajo registrado con la licencia de atribución de Creative '
              'Commons, que permite a terceros utilizar lo publicado siempre que mencionen la autoría del trabajo y a '
              'la primera publicación en esta revista.</p></div>')
ESTA_OBRA = '<p>Esta obra está bajo una <a href="{}" rel="license">Licencia Creative Commons</a>.</p>'


def test_the_articles_own_block_may_say_the_footers_licence_in_words():
    assert licenses(page_of(UCR, panel=IN_WORDS)) == ("cc-by-nc-nd", "cc-by-nc-nd")
    assert licenses(page_of(ESTA_OBRA.format(BY), panel=IN_SPANISH)) == ("cc-by", "cc-by")


@pytest.mark.parametrize("footer, panel", [
    # the look-alikes. The block's words name another licence than the footer
    (UCR.replace("NonDerivative", "ShareAlike").replace(BY_NC_ND, BY_NC_SA), IN_WORDS),
    (ESTA_OBRA.format(BY_NC_SA), IN_SPANISH),
    (UCR, IN_WORDS.replace("non-commercial and no-derivative", "share-alike")),
    # ... both no-derivatives and share-alike, or none of the licence's terms at all
    (UCR, IN_WORDS.replace("no-derivative license", "no-derivative or share-alike license")),
    (UCR, '<div class="item copyright"><p>Articles are published under a Creative Commons license.</p></div>'),
    # ... or it agrees in one sentence and not in another
    (UCR, IN_WORDS + '<div class="pkp_block"><p>Data sets: Creative Commons, share-alike.</p></div>'),
])
def test_a_block_that_does_not_say_the_footers_licence_keeps_the_footer_out(footer, panel):
    assert licenses(page_of(footer, panel=panel)) == (None, None)


def test_the_words_alone_license_nothing():
    # no statement in the footer (a badge names nothing): the block's words are not read on their own
    badge = (f'<p><a href="{BY_NC_ND}"><img src="https://i.creativecommons.org/l/by-nc-nd/4.0/88x31.png" alt=""/></a>'
             '</p>')
    assert licenses(page_of(badge, panel=IN_WORDS)) == (None, None)
    assert licenses(page_of("<p>Universidad de Costa Rica</p>", panel=IN_WORDS)) == (None, None)


# --- statements that name no journal, work or articles: out, until someone decides (RESULT.json, needs_decision)

KP = (OJS + '<meta name="citation_journal_title" content="Kulturella Perspektiv – Svensk etnologisk tidskrift">'
      '<meta name="citation_journal_abbrev" content="KP">'
      '<meta name="DC.Source.URI" content="https://publicera.example.se/kp">')
SMT = (OJS + '<meta name="citation_journal_title" content="Socialmedicinsk tidskrift">'
       '<meta name="citation_journal_abbrev" content="SMT">'
       '<meta name="DC.Source.URI" content="https://publicera.example.se/smt">')


@pytest.mark.parametrize("footer, head", [
    # publicera.kb.se: "Published by <the publisher> | Open Access according to CC-BY 4.0". The publisher's name holds
    # the journal's, and it is still the publisher that is named
    (f'<p>Utgiven av Föreningen Kulturella Perspektiv (org. nr. 894002-7843) | Open Access enligt <a href="{BY}" '
     'target="_blank" rel="noopener">Creative Commons CC-BY 4.0</a> </p>', KP),
    (f'<p>Utgiven av Stiftelsen Socialmedicinskt tidskrift | Open Access enligt <a href="{BY}" target="_blank" '
     'rel="noopener">Creative Commons CC-BY 4.0</a> </p>', SMT),
    # bibliotecavirtual.unl.edu.ar: "Except where explicitly indicated, published under the following licence"
    ('<div style="clear: both;"><small>Excepto donde se indique explícitamente se publica bajo la siguiente licencia '
     f'<a title="Creative Commons " href="{BY_NC_SA}" target="_blank" rel="noopener">Attribution-NonCommercial-'
     'ShareAlike 4.0 International (CC BY-NC-SA 4.0)</a> </small></div>', JOURNAL),
])
def test_a_statement_with_no_subject_still_names_nothing(footer, head):
    assert licenses(page_of(footer, head)) == (None, None)


@pytest.mark.parametrize("footer", [
    # journals.unite.edu.mk, pjph.eu, natural-sciences.ru: the journal named in the footer of a site that is not OJS
    f'<p>This is an open access journal, is following <a href="{BY}">CC-BY license</a> .</p>',
    '<div id="footer">© 2013 Uniwersytet Medyczny w Lublinie. <br/>Czasopismo jest udostępnione w systemie Open Access '
    'na podstawie licencji otwartej Creative Commons (CC-BY-NC-ND).<br/>ISSN: 0044-2011</div>',
    f'<div>Материалы журнала доступны по <a rel="license" href="{BY}">лицензии Creative Commons «Attribution» '
    '(«Атрибуция») 4.0 Всемирная</a>.</div>',
    UCR,
])
def test_a_site_footer_that_is_not_an_ojs_journals_still_licenses_nothing(footer):
    page = page_of(footer, JOURNAL.replace(OJS, ""), wrapper="<footer>{}</footer>")
    assert licenses(page) == (None, None)
