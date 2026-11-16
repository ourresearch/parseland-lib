"""
An Open Journal Systems journal's own licence statement in its site footer (oxjob #2239, phase 2, round 5).

Charter § 6, 16 Nov 2026 09:30 (it replaces the line of 13 Nov, "an OJS journal's site-footer licence is not read as
the article's licence"): on OJS pages a footer statement that licenses the journal or its articles is the article's
licence. #2267 read all 17,118 OJS pages whose licence a re-parse dropped and found a journal-wide Creative Commons
statement in the footer of 94% of them, the only statement those articles have. Gold v1.4 labels it so.

The rule, on OJS pages only (is_ojs_page), in both namespaces: a statement in the cleared site chrome counts as the
article's licence when the statement itself names the work, the journal (in words, or by the title, short title or
address in the page's meta tags) or its articles, and the rest of the page names no licence. It does not count when it
is about the site, its pages or its metadata, credits an image, covers only some articles, sits in chrome that names
several different licences (statements or badges, in whichever blocks), or is a bare "Licensed under ..." or a badge.
An issue's table of contents takes the footer's licence like an article page.

Fragments mirror stored pages; no network.
"""
import pytest

from parseland_lib.legacy_parse_utils.pdf import find_normalized_license
from parseland_lib.legacy_parse_utils.version_and_license import license_search_text
from parseland_lib.parse import parse_page

URL = "https://journals.example.org/index.php/eje/article/view/12"
OJS = '<meta name="generator" content="Open Journal Systems 3.3.0.13">'
JOURNAL = (OJS + '<meta name="citation_journal_title" content="Economic Journal of Emerging Markets">'
           '<meta name="citation_journal_abbrev" content="EJEM">'
           '<meta name="DC.Source.URI" content="https://journals.example.org/index.php/eje">')
BODY = "<main><h1>An article</h1><p>Abstract text.</p>{panel}</main>"
BY = "https://creativecommons.org/licenses/by/4.0/"
BY_SA = "http://creativecommons.org/licenses/by-sa/4.0/"
BY_NC = "https://creativecommons.org/licenses/by-nc/4.0/"
BY_SA_NAME = f'<a rel="license" href="{BY_SA}">Creative Commons Attribution-ShareAlike 4.0 International License</a>'
BY_SA_BADGE = (f'<a rel="license" href="{BY_SA}"><img alt="Creative Commons License" '
               'src="https://i.creativecommons.org/l/by-sa/4.0/88x31.png" /></a>')


def page_of(footer, head=JOURNAL, panel="", wrapper="<footer><div>{}</div></footer>"):
    return (f"<html><head><title>t</title>{head}</head><body>{BODY.format(panel=panel)}{wrapper.format(footer)}"
            "</body></html>")


def licenses(page, url=URL):
    """The licence on the publisher path and on the repository path."""
    return parse_page(page, "doi", url)["license"], parse_page(page, "pmh", url)["license"]


# --- what counts: the statement names the work, the journal or its articles

@pytest.mark.parametrize("footer, expected", [
    # the Creative Commons chooser's sentence, with its badge (the most common footer of all)
    (f'<p>{BY_SA_BADGE}<br />This work is licensed under a {BY_SA_NAME}.</p>', "cc-by-sa"),
    # ... after the journal's address lines, in the same block (jurnalanestesiobstetri-indonesia.id)
    (f'<p>Jurnal Anestesi Obstetri Indonesia e-ISSN: 2615-370X Published by Collegium of Obstetric Anesthesia<br>'
     f'This work is licensed under a {BY_SA_NAME}</p>', "cc-by-sa"),
    # the licence only in the link: the text gives the family name (ijstm.inarah.co.id) or no name at all
    (f'<p>This work is licensed under a <a href="{BY_SA}">Creative Commons Attribution License</a></p>', "cc-by-sa"),
    (f'<p>The publication is licensed under a <a href="{BY_NC}">Creative Commons License</a>.</p>', "cc-by-nc"),
    (f'<div>This work is licensed under a <a href="{BY_SA}deed.id">{BY_SA}deed.id</a></div>', "cc-by-sa"),
    # the journal, in words
    (f'<p>This Journal is licensed under a {BY_SA_NAME}.</p>', "cc-by-sa"),
    ('<p>This is an open-access journal distributed under the terms of the Creative Commons Attribution-NonCommercial '
     f'4.0 International <a href="{BY_NC}">(CC BY-NC 4.0)</a>.</p>', "cc-by-nc"),
    (f'<p>The journal content is authorized under the <a href="{BY_NC}">Creative Commons Attribution-NonCommercial '
     '4.0 International License</a></p>', "cc-by-nc"),
    # its articles
    ('<p>All articles published in this journal are licensed under a <a href="https://creativecommons.org/licenses/'
     'by-nc/4.0/">Creative Commons Attribution-NonCommercial 4.0 International License</a></p>', "cc-by-nc"),
    ('<p>Website copyright © 2024 JOSAET | Articles published in JOSAET are distributed under Creative Commons '
     'Attribution-ShareAlike 4.0 International License (CC-BY-SA)</p>', "cc-by-sa"),
    # the PKP default notice, when a theme prints it in the footer
    ('<p>Authors retain copyright and grant the journal right of first publication with the work simultaneously '
     f'licensed under a <a href="{BY}">Creative Commons Attribution License</a>.</p>', "cc-by"),
])
def test_footer_statement_about_the_work_the_journal_or_its_articles_is_the_articles_licence(footer, expected):
    assert licenses(page_of(footer)) == (expected, expected)


@pytest.mark.parametrize("footer, expected", [
    # Indonesian: the chooser's sentence, its machine translation back to English, and "this journal"
    (f'<p>Ciptaan disebarluaskan di bawah <a href="{BY}">Lisensi Creative Commons Atribusi 4.0 Internasional</a>.</p>',
     "cc-by"),
    (f'<p>Work is distributed below <a href="{BY_SA}">Lisensi Creative Commons Atribusi-BerbagiSerupa 4.0 '
     'Internasional</a>.</p>', "cc-by-sa"),
    (f'<p>Jurnal ini dibawah lisensi <a href="{BY}">Lisensi Creative Commons Atribusi 4.0 Internasional</a>.</p>',
     "cc-by"),
    (f'<p>Artikel dalam jurnal ini memiliki lisensi {BY_SA_NAME}</p>', "cc-by-sa"),
    # Spanish and Portuguese
    (f'<p>Esta obra está bajo una <a href="{BY_NC}deed.es">Licencia Creative Commons Atribución-NoComercial 4.0 '
     'Internacional</a>.</p>', "cc-by-nc"),
    (f'<p>Este obra está licenciado com uma Licença <a href="{BY_NC}">Creative Commons Atribuição-NãoComercial 4.0 '
     'Internacional</a>.</p>', "cc-by-nc"),
    ('<p>Todos los artículos están licenciados bajo <a href="https://creativecommons.org/licenses/by-nc-nd/3.0/">'
     'Creative Commons Attribution-NonCommercial-NoDerivs 3.0 Unported License</a>.</p>', "cc-by-nc-nd"),
    (f'<p>Todo conteúdo do periódico, exceto onde está identificado, está licenciado sob uma <a href="{BY}deed.pt">'
     'Licença Creative Commons</a>.</p>', "cc-by"),
    # Arabic (spu.sharjah.ac.ae) and Turkish (tisej.com)
    (f'<p>هذا العمل مُرخص بموجب <a href="{BY}">رخصة المشاع الإبداعي نَسب المُصنَّف 4.0</a> (CC-BY 4.0).</p>', "cc-by"),
    (f'<p>Dergimizde yayımlanan makaleler, <a href="{BY_NC}">Creative Commons Atıf-Ticari Olmayan 4.0 (CC BY-NC 4.0)'
     '</a> ile lisanslanmıştır.</p>', "cc-by-nc"),
])
def test_the_same_statements_in_other_languages(footer, expected):
    assert licenses(page_of(footer)) == (expected, expected)


@pytest.mark.parametrize("footer, expected", [
    (f'<p>{BY_SA_BADGE}<br />Economic Journal of Emerging Markets is licensed under a {BY_SA_NAME}.</p>', "cc-by-sa"),
    # with the Creative Commons chooser's attribution, a year, an ISSN
    ('<p>Economic Journal of Emerging Markets © 2025 by Center of Economic Studies is licensed under '
     f'<a href="{BY_NC}?ref=chooser-v1">CC BY-NC 4.0</a></p>', "cc-by-nc"),
    (f'<p>Economic Journal of Emerging Markets (e-ISSN: 2988-2982) is licensed under {BY_SA_NAME}.</p>', "cc-by-sa"),
    # the short title, and the last part of the journal's address
    (f'<p>Online ISSN : 2146-4405 EJEM is licensed under a {BY_SA_NAME}.</p>', "cc-by-sa"),
    (f'<p>EJE at http://journals.example.org/EJE/ is licensed under a <a href="{BY}">Creative Commons Attribution 4.0 '
     'International License</a>.</p>', "cc-by"),
    # the journal's own address
    (f'<p>Emerging Markets by http://journals.example.org/index.php/eje is licensed under a {BY_SA_NAME}.</p>',
     "cc-by-sa"),
    # other verbs
    ('<p>Economic Journal of Emerging Markets is edited in the Universidad de Costa Rica under a license <a '
     f'href="{BY_NC}">Creative Commons Attribution-NonCommercial 4.0 International</a>.</p>', "cc-by-nc"),
    # the link's text ends the sentence: its address still belongs to the statement (KOVALEN, 65 pages)
    (f'<p>{BY_SA_BADGE}<strong>Economic Journal of Emerging Markets</strong> is licensed under a <a href="{BY_SA}">'
     'Creative Commons Attribution-4.0 Internasional License.</a></p>', "cc-by-sa"),
    # a badge in a block that names the journal and nothing else
    (f'<p>Economic Journal of Emerging Markets: {BY_SA_BADGE}</p>', "cc-by-sa"),
])
def test_footer_statement_that_names_the_journal_by_its_own_name(footer, expected):
    assert licenses(page_of(footer)) == (expected, expected)


def test_a_title_with_a_short_name_is_known_by_the_short_name():
    head = OJS + '<meta name="citation_journal_title" content="KOVALEN: Jurnal Riset Kimia">'
    assert licenses(page_of(f"<p>KOVALEN is licensed under a {BY_SA_NAME}.</p>", head)) == ("cc-by-sa", "cc-by-sa")
    head = OJS + '<meta name="DC.Source" content="KONSTAN (Jurnal Fisika dan Pendidikan Fisika)">'
    assert licenses(page_of(f"<p>Jurnal KONSTAN is licensed under a {BY_SA_NAME}.</p>", head)) == ("cc-by-sa", "cc-by-sa")


def test_a_name_that_holds_a_full_stop_is_still_one_subject():
    head = OJS + '<meta name="citation_journal_title" content="Rilce. Revista de Filología Hispánica">'
    footer = ('<p>Rilce. Revista de Filología Hispánica se publica bajo una licencia <a href="https://creativecommons.'
              'org/licenses/by-nc-nd/4.0/">Creative Commons Reconocimiento-NoComercial-SinObraDerivada 4.0</a>.</p>')
    assert licenses(page_of(footer, head)) == ("cc-by-nc-nd", "cc-by-nc-nd")


def test_an_issue_page_knows_its_journal_by_the_pages_title():
    # no citation or Dublin Core tags there: OJS titles its pages "<issue or article> | <journal>"
    footer = f"<p>Nusantara Journal of Islamic Studies is published under a {BY_SA_NAME}.</p>"
    page = page_of(footer, OJS).replace("<title>t</title>", "<title>Vol. 2 No. 1 (2021) | Nusantara Journal of "
                                                              "Islamic Studies</title>")
    assert licenses(page) == ("cc-by-sa", "cc-by-sa")
    assert licenses(page_of(footer, OJS)) == (None, None)  # the look-alike: the page names no journal


def test_a_line_break_parts_the_statement_from_the_line_before_it():
    footer = (f"<p>Jl. Jendral Sudirman No. 30, Kota Serang, Banten 42118<br>This work is licensed under a "
              f"{BY_SA_NAME}</p>")
    assert licenses(page_of(footer)) == ("cc-by-sa", "cc-by-sa")


def test_the_footer_of_the_default_theme_is_read_like_any_other():
    wrapper = ('<div class="pkp_structure_footer_wrapper" role="contentinfo"><div class="pkp_structure_footer">'
               '<div class="pkp_footer_content">{}</div><div class="pkp_brand_footer" role="complementary">'
               '<a href="/about/aboutThisPublishingSystem"><img alt="More information about the publishing system, '
               'Platform and Workflow by OJS/PKP." src="/templates/images/ojs_brand.png"></a></div></div></div>')
    page = page_of(f"<p>{BY_SA_BADGE}</p><p>This work is licensed under a {BY_SA_NAME}.</p>", wrapper=wrapper)
    assert licenses(page) == ("cc-by-sa", "cc-by-sa")
    # these classes alone make the page an OJS page (is_ojs_page), with no generator tag
    assert licenses(page_of(f"<p>This work is licensed under a {BY_SA_NAME}.</p>", head="", wrapper=wrapper)) == (
        "cc-by-sa", "cc-by-sa")


# --- what does not count

@pytest.mark.parametrize("footer", [
    f'<p>{BY_SA_BADGE}<br />This work is licensed under a {BY_SA_NAME}.</p>',
    f'<p>Economic Journal of Emerging Markets is licensed under a {BY_SA_NAME}.</p>',
    f'<p>All articles published in this journal are licensed under a {BY_SA_NAME}</p>',
    f'<p>Ciptaan disebarluaskan di bawah <a href="{BY}">Lisensi Creative Commons Atribusi 4.0 Internasional</a>.</p>',
])
def test_the_same_footer_on_a_page_that_is_not_an_ojs_page_licenses_nothing(footer):
    head = JOURNAL.replace(OJS, "")
    assert licenses(page_of(footer, head)) == (None, None)
    assert licenses(page_of(footer, head + '<meta name="generator" content="WordPress 6.4">')) == (None, None)


@pytest.mark.parametrize("generator", ["Open Monograph Press 3.3.0.8", "Open Preprint Systems 3.4.0.5"])
def test_a_presss_or_a_preprint_servers_footer_is_not_a_journals(generator):
    footer = f'<p>This work is licensed under a {BY_SA_NAME}.</p>'
    wrapper = '<div class="pkp_structure_footer_wrapper" role="contentinfo">{}</div>'
    page = page_of(footer, f'<meta name="generator" content="{generator}">', wrapper=wrapper)
    assert licenses(page) == (None, None)


@pytest.mark.parametrize("footer", [
    # Jurnal Tabarru' (262 pages of #2267's set), with the journal's name twice before it
    "<p>Economic Journal of Emerging Markets &nbsp;The&nbsp;Economic Journal of Emerging Markets site and its metadata "
    "are licensed under CC BY-SA</p>",
    f'<p>This OJS site and its metadata are licensed under a <a href="{BY}">Creative Commons Attribution 4.0 '
    'International License</a></p>',
    # the DOI Foundation's own page footer
    f'<p>Copyright © 2023 DOI Foundation. The content of this site is licensed under a <a href="{BY}">Creative Commons '
    'Attribution 4.0 International License</a>.</p>',
    f'<p>This webpage is published under the terms of the <a href="{BY}">Creative Commons Attribution 4.0 '
    'International (CC BY 4.0) license</a></p>',
    # ("El contenido de las Revistas de este sitio, están bajo una Licencia ..." stood here until round 6: it licenses
    # the content of the site's journals, so it counts; tests/test_licence_footer_r6.py, with the site's own content
    # as its look-alike)
    f'<p>El contenido de este sitio está bajo una <a href="{BY_NC}">Licencia de Creative Commons '
    'Reconocimiento-NoComercial 4.0 Internacional</a>.</p>',
    f'<p>The website of this journal and all its pages are licensed under a {BY_SA_NAME}.</p>',
    # "all content": the site's or the journal's, the statement does not say
    f'<p>Official Website of eJournal System<br>All content is licensed under a {BY_SA_NAME}</p>',
])
def test_a_statement_about_the_site_its_pages_or_its_metadata_licenses_nothing(footer):
    assert licenses(page_of(footer)) == (None, None)


@pytest.mark.parametrize("footer", [
    # journal.westernfieldornithologists.org and bovine-ojs-tamu.tdl.org: the credit of the footer's picture
    f'<p>Sabine\'s Gull by Andy Reago &amp; Chrissy McClarren is licensed under <a href="{BY}">CC BY 4.0</a> / '
    'Expanded from original</p>',
    '<p>U.S. Department of Agriculture, Grass Fed Beef - Ryan Thompson - USDAgov, <a href="https://creativecommons.org/'
    'licenses/by/2.0/legalcode">CC BY 2.0</a></p>',
    f'<p>The cover image of Economic Journal of Emerging Markets is licensed under <a href="{BY}">CC BY 4.0</a></p>',
    f'<p>Economic Journal of Emerging Markets theme by Example Studio, <a href="{BY}">CC BY 4.0</a></p>',
    # another journal's footer, copied with the site's template (integral.upstegal.ac.id, ojs.unik-kediri.ac.id)
    f'<p>Jurnal Transparansi Hukum is licensed under a {BY_SA_NAME}.</p>',
    # the journal's name in a link to its visitor counter, beside a badge
    f'<p><a href="https://statcounter.com/p1/">View Economic Journal of Emerging Markets Stats</a> {BY_SA_BADGE}</p>',
    # the journal's name, an address, and then someone else's statement
    '<p><strong>Economic Journal of Emerging Markets (EJEM)</strong><br>Pusat Penelitian dan Pengabdian kepada '
    'Masyarakat, Politeknik Kesehatan Kementerian Kesehatan Mataram<br>Address: Kampus A Poltekkes Kemenkes Mataram '
    f'Jalan Prabu Rangkasari Dasan Cermen Sandubaya Mataram<br>{BY_SA_BADGE}<br><strong>Indonesian Health Issue'
    f'</strong> is licensed under a {BY_SA_NAME}</p>',
])
def test_a_statement_about_something_else_licenses_nothing(footer):
    assert licenses(page_of(footer)) == (None, None)


@pytest.mark.parametrize("footer", [
    f'<p>Licensed under a {BY_SA_NAME}.</p>',
    f'<p>Distributed under a {BY_SA_NAME}.</p>',
    f'<p>{BY_SA_BADGE}</p>',
    f'<p><a href="{BY_SA}">Creative Commons 4.0 International License</a>.</p>',
    f'<p>Creative Commons «Attribution» 4.0 <a href="{BY}">WorldWide</a>.</p>',
    f'<p>Published by the Example Scientific Publication under the terms of the <a href="{BY}">Creative Commons CC-BY '
    '4.0</a> license.</p>',
    # the subject and the licence are in different blocks, or different sentences
    f'<p>Economic Journal of Emerging Markets</p><p>is licensed under <a href="{BY_SA}">CC BY-SA 4.0</a></p>',
    f'<p>Contact the editors of this journal. {BY_SA_BADGE}</p>',
])
def test_a_bare_statement_or_a_badge_names_nothing(footer):
    assert licenses(page_of(footer)) == (None, None)


@pytest.mark.parametrize("footer", [
    # revistas.itm.edu.co, on a 2013 article's page
    f'<p>The articles published in this journal after June 2018 are licensed under a <a href="{BY_NC}deed.en">'
    'Attribution-Non-Commercial 4.0 (CC BY-NC)</a></p>',
    f'<p>All articles published before 2016 are licensed under a {BY_SA_NAME}.</p>',
    # revistas.cef.udima.es
    '<p>Esta revista se encuentra bajo un periodo de embargo de 12 meses tras el cual es de acceso gratuito mediante '
    f'una <a href="{BY_NC}deed.es">Licencia creative commons BY-NC 4.0</a></p>',
    f'<p>If this work is licensed under a {BY_SA_NAME}, you may share it.</p>',
    # not a Creative Commons licence
    '<p>This work is in the <a href="https://creativecommons.org/publicdomain/mark/1.0/">public domain</a>.</p>',
])
def test_a_statement_that_covers_only_some_articles_or_is_no_cc_licence_licenses_nothing(footer):
    assert licenses(page_of(footer)) == (None, None)


# openjournaltheme.com's boilerplate (round 3): one block, three licences
THEME_FOOTER = f"""<div class="copy-right">© 2021 IGNITED MINDS JOURNALS, ALL RIGHTS RESERVED. Licensed under <img
src="https://i.creativecommons.org/l/by-sa/4.0/80x15.png" alt="" /> This work is licensed under a {BY_SA_NAME}. a <a
href="https://creativecommons.org/licenses/by/4.0/">Creative Commons Attribution 4.0 International License</a>.</div>"""


@pytest.mark.parametrize("footer", [
    THEME_FOOTER,
    # the text names one licence and the link another (revistas.pucsp.br, innovareacademics.in)
    '<p>Os artigos são disponibilizados sob os termos da licença <a href="https://creativecommons.org/licenses/'
    'by-nc-nd/4.0/deed.fr">Creative Commons Attribution 4.0 International</a></p>',
    # two licences in two blocks: a badge and a statement (jurnal-umbuton.ac.id), a statement and the theme's line
    f'<p><a href="{BY_NC}" rel="license"><img src="https://i.creativecommons.org/l/by-nc/4.0/88x31.png" alt="Creative '
    f'Commons License" /></a></p><p>Economic Journal of Emerging Markets is licensed under a {BY_SA_NAME}</p>',
    f'<div><span>This work is licensed under a {BY_SA_NAME}</span></div><div class="copy-right">Licensed under a <a '
    f'href="{BY}">Creative Commons Attribution 4.0 International License</a>.</div>',
    # two statements that disagree (riviste.unimi.it's Italiano LinguaDue)
    f'<p>Economic Journal of Emerging Markets by Promoitals is licensed under a {BY_SA_NAME}.</p><p>Economic Journal '
    'of Emerging Markets by Promoitals is licensed under a <a href="http://creativecommons.org/licenses/by-nc-nd/2.5/'
    'it/">Creative Commons Attribuzione-Non commerciale-Non opere derivate 2.5 Italia License</a>.</p>',
])
def test_a_footer_that_names_several_licences_licenses_nothing(footer):
    assert licenses(page_of(footer)) == (None, None)


def test_a_footer_that_names_one_licence_in_several_blocks_still_counts():
    footer = (f'<p>{BY_SA_BADGE}</p><p>This work is licensed under a {BY_SA_NAME}.</p><div class="copy-right">Licensed '
              f'under <a href="{BY_SA}">CC BY-SA 4.0</a></div>')
    assert licenses(page_of(footer)) == ("cc-by-sa", "cc-by-sa")


def test_a_host_whose_licences_are_not_trusted_takes_none():
    page = page_of(f'<p>This work is licensed under a {BY_SA_NAME}.</p>')
    assert licenses(page, "https://journals.eco-vector.com/1681-3456/article/view/1") == (None, None)


# --- the article's own statement wins

PANEL = ('<div class="item copyright"><h2 class="label">License</h2><p>This work is licensed under a <a rel="license" '
         f'href="{BY}">Creative Commons Attribution 4.0 International License</a>.</p></div>')


@pytest.mark.parametrize("footer", [
    # by rank the footer's licence would come first
    '<p>Economic Journal of Emerging Markets is licensed under a <a href="https://creativecommons.org/licenses/'
    'by-nc-sa/4.0/">Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License</a>.</p>',
    f'<p>This work is licensed under a {BY_SA_NAME}.</p>',
])
def test_the_articles_own_licence_panel_is_read_not_the_journals_footer(footer):
    assert licenses(page_of(footer, panel=PANEL)) == ("cc-by", "cc-by")


def test_an_articles_own_statement_that_cannot_be_read_still_keeps_the_footer_out():
    # revistascientificas.filo.uba.ar (labelled by-nc-sa): the copyright block names the licence in Spanish over a dead
    # link, and the footer says Attribution-ShareAlike
    panel = ('<div class="item copyright"><p>Los/as autores/as conservan los derechos de autor/a y ceden a la revista '
             'el derecho de la primera publicación, con el trabajo registrado con <a href="about:blank">Licencia '
             'Creative Commons Atribución-NoComercial-CompartirIgual 4.0 Internacional</a>.</p></div>')
    footer = (f'<div class="pie">{BY_SA_BADGE}<br>Esta obra está bajo una <a href="{BY_SA}" rel="license">Licencia '
              'Creative Commons Atribución-CompartirIgual 4.0 Internacional</a>.</div>')
    assert licenses(page_of(footer, panel=panel)) == (None, None)
    assert licenses(page_of(footer)) == ("cc-by-sa", "cc-by-sa")


@pytest.mark.parametrize("panel", [
    # the look-alikes: Creative Commons in an address or an alt text only (a sidebar's link to the licence chooser,
    # a visitor counter's picture) is not a statement of the article's
    '<div class="pkp_block"><h4><a href="https://chooser-beta.creativecommons.org/">Journal License</a></h4></div>',
    '<div class="pkp_block"><a href="https://statcounter.com/"><img src="/public/site/images/Logo_Stats_Counter.png" '
    'alt="Creative Commons License"/></a></div>',
])
def test_creative_commons_in_an_address_or_an_alt_text_does_not_keep_the_footer_out(panel):
    assert licenses(page_of(f'<p>This work is licensed under a {BY_SA_NAME}.</p>', panel=panel)) == (
        "cc-by-sa", "cc-by-sa")


def test_a_statement_about_the_article_and_one_about_the_journal_must_agree():
    # round 2's rule and this one in two footers of one page
    article = ('<div id="footer-info"><p>This is an open access article distributed under the terms of the <a href="{}">'
               'Creative Commons Attribution-{} 4.0 License</a>.</p></div></body>')
    page = page_of(f'<p>This work is licensed under a {BY_SA_NAME}.</p>')
    assert licenses(page.replace("</body>", article.format(BY_SA, "ShareAlike"))) == ("cc-by-sa", "cc-by-sa")
    assert licenses(page.replace("</body>", article.format(BY_NC, "NonCommercial"))) == (None, None)


def test_the_statement_is_kept_without_the_rest_of_the_footer():
    footer = (f'<p>This work is licensed under a {BY_SA_NAME}.</p><p>Hosted by Example Press, whose own journals are '
              'sold under the Elsevier user license elsevier.com/open-access/userlicense</p>')
    page = page_of(footer)
    text = license_search_text(page, URL, ojs_page=True)
    assert "This work is licensed under a" in text and "Example Press" not in text
    assert find_normalized_license(text) == "cc-by-sa"
    assert "This work is licensed" not in license_search_text(page, URL)


# --- chrome that names different licences, in whichever blocks, with or without a subject (gold v1.4)

LEARNING_GATE_FOOTER = """<div class="col-3"><div class="item-contact"><br /><span style="font-size: 0.875rem;">This is an
open-access article distributed under the terms of the Creative Commons Attribution-NonCommercial-ShareAlike 4.0
International License</span></div></div><div class="copyright-wrapper"><div class="copy-right">Licensed under <a
href="https://creativecommons.org/licenses/by/4.0/" rel="license"><img
src="https://licensebuttons.net/l/by/4.0/80x15.png" alt="Creative Commons License" /></a> a <a
href="https://creativecommons.org/licenses/by/4.0/">Creative Commons Attribution 4.0 International License</a>.
</div></div>"""


@pytest.mark.parametrize("footer", [
    LEARNING_GATE_FOOTER,  # gate dev page cd5537c2
    # a statement, and a badge whose picture is another licence's (no link, no words)
    f'<p>This work is licensed under a {BY_SA_NAME}.</p><p><img src="https://i.creativecommons.org/l/by-nc/4.0/88x31.png" '
    'alt="Creative Commons License" /></p>',
    # a statement in the footer, another licence in the site's menu
    f'<p>This work is licensed under a {BY_SA_NAME}.</p></div></footer><nav><ul><li><a href="{BY_NC}">Licence</a></li>'
    '</ul></nav><footer><div>',
])
def test_chrome_that_names_different_licences_licenses_nothing(footer):
    wrapper = '<div class="pkp_structure_footer_wrapper" role="contentinfo">{}</div>'
    assert licenses(page_of(footer)) == (None, None)
    assert licenses(page_of(footer, wrapper=wrapper)) == (None, None)


def test_the_articles_own_statement_still_wins_over_chrome_that_names_different_licences():
    assert licenses(page_of(LEARNING_GATE_FOOTER, panel=PANEL)) == ("cc-by", "cc-by")


# --- an issue's table of contents (gold v1.4: gate dev pages 3b730d31, 7aaaa83e, ead7c4cd)

ISSUE = ('<div role="main"><h1>Vol. 19 No. 24 (2023)</h1><ul class="cmp_article_list articles">'
         '<li><a id="article-101" href="/index.php/eje/article/view/101">A first article</a>{extra}</li>'
         '<li><a id="article-102" href="/index.php/eje/article/view/102">A second article</a></li></ul></div>')


def issue_page(footer, extra=""):
    return (f"<html><head><title>Vol. 19 No. 24 (2023) | Economic Journal of Emerging Markets</title>{OJS}</head><body>"
            f"{ISSUE.format(extra=extra)}<footer><div>{footer}</div></footer></body></html>")


@pytest.mark.parametrize("footer, expected", [
    (f'<p>Este obra está bajo una <a href="{BY}">licencia de Creative Commons Reconocimiento 4.0 Internacional</a>.</p>',
     "cc-by"),
    (f'<p>All the published articles are licensed under a <a href="{BY}">Creative Commons Attribution 4.0 International '
     'License</a></p>', "cc-by"),
    (f'<p>Economic Journal of Emerging Markets is licensed under a {BY_SA_NAME}.</p>', "cc-by-sa"),
])
def test_an_issue_page_takes_the_journals_footer_licence_and_nothing_else(footer, expected):
    out = parse_page(issue_page(footer), "doi", URL.replace("article/view/12", "issue/view/5"))
    assert out["license"] == expected
    assert out["version"] is None and out["urls"] == []


def test_an_issue_page_takes_no_licence_from_its_list_of_articles():
    # one listed article's own licence link is not the issue's, with or without a footer statement (as before)
    extra = f' <a href="{BY_NC}">CC BY-NC</a>'
    url = URL.replace("article/view/12", "issue/view/5")
    assert parse_page(issue_page("<p>Example University Press</p>", extra), "doi", url)["license"] is None
    assert parse_page(issue_page(f'<p>This work is licensed under a {BY_SA_NAME}.</p>', extra), "doi", url)[
        "license"] is None
    assert parse_page(issue_page("<p>Example University Press</p>"), "doi", url)["license"] is None
