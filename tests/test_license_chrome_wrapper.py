"""
Site chrome that holds the page is not chrome (oxjob #2239, phase 2).

page_potential_license_text() clears <footer>, <nav>, role=contentinfo and footer-named elements before the licence
regexes run, so a site footer cannot license a paywalled page (test_license_untrusted_hosts.py). Some pages wrap their
WHOLE content in an element those finders match, and the article's own licence went with it:

- arXiv abstract pages sit inside <div class="flex-wrap-footer"> (a sticky-footer layout wrapper);
- WordPress themes put footer options in <body class="... ast-footer-...">;
- DSpace JSPUI leaves a <div> open inside its header <nav>, so the HTML parser ignores </nav> and the nav swallows
  <main> and everything after it.

On a random sample of stored pages whose licence the re-parse dropped, 36 of 875 were these shapes (arXiv 32).
The rule: an element that holds the page's <main> (or role="main"), and <html>/<body> themselves, are never cleared
whole. The real footer and nav inside them still are, and how much of the page's text an element holds is never
evidence: a footer is most of the text on a short or paywalled page. Fragments mirror stored pages; no network.
"""
import pytest

from parseland_lib.legacy_parse_utils.version_and_license import page_potential_license_text
from parseland_lib.parse import parse_page

ARXIV_URL = "https://arxiv.org/abs/2603.25690"
TRUSTED_URL = "https://journals.example.org/article/1"

SITE_CC = ('The content of this site is licensed under a '
           '<a href="https://creativecommons.org/licenses/by/4.0/">Creative Commons Attribution 4.0 licence</a>.')
SITE_LINKS = "".join(f'<li><a href="/page/{i}">About the journal, policies and contact {i}</a></li>' for i in range(30))

ARXIV_LICENSE = ('<div class="abs-license"><a href="http://creativecommons.org/licenses/by-nc-sa/4.0/" '
                 'title="Rights to this article" class="has_license"><img alt="license icon" role="presentation" '
                 'src="https://arxiv.org/icons/licenses/by-nc-sa-4.0.png"/></a></div>')


def arxiv_page(license_block=ARXIV_LICENSE, footer_extra=""):
    """arXiv's abstract page, 2026: header, <main> and <footer> all inside div.flex-wrap-footer."""
    return f"""<html><head><title>[2603.25690] Fast inference for gravitational waves</title></head>
<body class="with-cu-identity">
<div class="flex-wrap-footer">
<header>
  <a href="#content" class="is-sr-only">Skip to main content</a>
  <div class="mobile-header"><div class="mobile-toggle-block toggle-target">
    <nav class="mobile-menu" aria-labelledby="mobilemenulabel"><h2 id="mobilemenulabel">quick links</h2>
      <ul><li><a href="https://arxiv.org/login">Login</a></li>
      <li><a href="https://info.arxiv.org/help">Help Pages</a></li></ul></nav>
  </div></div>
</header>
<main><div id="content"><div id="abs-outer">
  <div class="leftcolumn"><div id="content-inner"><div id="abs">
    <h1 class="title mathjax"><span class="descriptor">Title:</span>Fast inference for gravitational waves</h1>
    <div class="authors"><a href="/search/?searchtype=author&amp;query=Doe,+J">Jane Doe</a></div>
    <blockquote class="abstract mathjax"><span class="descriptor">Abstract:</span>We present a method.</blockquote>
  </div></div></div>
  <div class="extra-services"><div class="full-text"><ul>
    <li><a class="abs-button download-pdf" href="/pdf/2603.25690">View PDF</a></li></ul>
    {license_block}
  </div></div>
</div></div></main>
<footer style="clear: both;"><div class="columns is-desktop" role="navigation" aria-label="Secondary">
  <ul><li><a href="https://info.arxiv.org/about">About</a></li>
  <li><a href="https://info.arxiv.org/help/license/index.html">Copyright</a></li></ul>{footer_extra}
</div></footer>
</div>
</body></html>"""


# --- the bug: the article's licence inside a "chrome" element that holds the page

@pytest.mark.parametrize("namespace", ["pmh", "doi"])
def test_arxiv_wrapper_keeps_the_articles_licence(namespace):
    assert parse_page(arxiv_page(), namespace, ARXIV_URL)["license"] == "cc-by-nc-sa"


def test_arxiv_page_without_a_licence_block_has_no_licence():
    assert parse_page(arxiv_page(license_block=""), "pmh", ARXIV_URL)["license"] is None


def test_real_footer_inside_the_wrapper_is_still_cleared():
    # the wrapper stays, its <footer> does not: a site statement there must not license the preprint
    page = arxiv_page(license_block="", footer_extra=f"<p>{SITE_CC}</p>")
    assert parse_page(page, "pmh", ARXIV_URL)["license"] is None
    assert "creativecommons" not in page_potential_license_text(page)


def test_footer_licence_does_not_beat_the_articles_licence_inside_the_wrapper():
    page = arxiv_page(footer_extra=f"<p>{SITE_CC}</p>")   # article: by-nc-sa, footer: by
    assert parse_page(page, "pmh", ARXIV_URL)["license"] == "cc-by-nc-sa"


def test_arxiv_mobile_menu_nav_left_open_does_not_hide_the_licence():
    # no </nav> and no closing tags after it: the parser extends the mobile-menu nav over <main> and the footer
    closers = "</ul></nav>\n  </div></div>\n</header>"
    assert closers in arxiv_page()
    page = arxiv_page(footer_extra=f"<p>{SITE_CC}</p>").replace(closers, "</ul>")   # article: by-nc-sa, footer: by
    assert parse_page(page, "pmh", ARXIV_URL)["license"] == "cc-by-nc-sa"
    menu_licence = '<li><a href="https://creativecommons.org/licenses/by/4.0/">Licence</a></li></ul>'
    page = arxiv_page(license_block="").replace(closers, menu_licence)
    assert parse_page(page, "pmh", ARXIV_URL)["license"] is None


# DSpace JSPUI (bdm.unb.br, PUCRS's meriva.pucrs.br): <div class="nav navbar-nav navbar-right"> is never closed, so the
# parser ignores </nav>, </div> and </header>, and the header <nav> swallows <main> and the page footer.
DSPACE_ITEM_LICENSE = ('<p class="submitFormHelp alert alert-info">Este item está licenciado na '
                       '<a href="http://creativecommons.org/licenses/by-nc-nd/3.0/">Licença Creative Commons</a></p>')


def dspace_page(item_license=DSPACE_ITEM_LICENSE, menu_extra="", footer_extra=""):
    return f"""<html><head><title>BDM: Um estudo</title></head><body class="undernavigation">
<a class="sr-only" href="#content">Skip navigation</a>
<header class="navbar navbar-inverse navbar-fixed-top"><div class="container">
  <nav class="collapse navbar-collapse bs-navbar-collapse" role="navigation">
    <ul class="nav navbar-nav"><li><a href="/">Página inicial</a></li>{menu_extra}</ul>
    <div class="nav navbar-nav navbar-right">
      <ul class="nav navbar-nav navbar-right"><li><a href="/mydspace">Entrar</a></li></ul>
  </nav>
</div></header>
<main id="content" role="main"><div class="container">
  <table class="table itemDisplayTable"><tr><td class="metadataFieldLabel">Título:</td>
  <td class="metadataFieldValue">Um estudo</td></tr></table>
  {item_license}
</div></main>
<footer class="navbar navbar-inverse navbar-bottom"><div id="footer_feedback" class="pull-left">
  <p class="text-muted">Biblioteca Digital{footer_extra}</p></div></footer>
</body></html>"""


def test_nav_extended_over_the_content_does_not_hide_the_licence():
    assert parse_page(dspace_page(), "pmh", "https://bdm.unb.br/handle/10483/4029")["license"] == "cc-by-nc-nd"


def test_nav_extended_over_the_content_still_loses_its_own_menu_and_the_footer():
    # the nav's own items and the page footer are chrome even when the parser put <main> inside the nav
    for where in ("menu_extra", "footer_extra"):
        extra = '<li><a href="https://creativecommons.org/licenses/by/4.0/">Licença do site: CC BY</a></li>'
        page = dspace_page(item_license="", **{where: extra})
        assert parse_page(page, "pmh", "https://bdm.unb.br/handle/10483/4029")["license"] is None, where


WORDPRESS_URL = "https://ayaeditora.com.br/livros/L1/"
WORDPRESS_LICENSE = '<h2><a href="https://creativecommons.org/licenses/by/4.0/deed.pt_BR">Creative Commons (CC-BY 4.0)</a></h2>'


def wordpress_page(book_license="", footer_text="Editora"):
    """WordPress with Astra or Avada: footer options sit in the <body> class, so <body> matched the footer finder."""
    return f"""<html><head><title>Livro</title></head>
<body class="wp-singular post-template single ast-footer-overlay elementor-default">
<div id="page" class="hfeed site"><div id="content" class="site-content">
  <h1 class="entry-title">Um livro</h1>
  {book_license}
</div>
<footer class="elementor-location-footer"><p>{footer_text}</p></footer></div>
</body></html>"""


def test_body_with_a_footer_named_class_is_not_chrome():
    assert parse_page(wordpress_page(WORDPRESS_LICENSE), "doi", WORDPRESS_URL)["license"] == "cc-by"


def test_footer_of_a_body_with_a_footer_named_class_is_still_chrome():
    assert parse_page(wordpress_page(footer_text=SITE_CC), "doi", WORDPRESS_URL)["license"] is None


# --- the rule this must not weaken: a site footer never licenses the page

PAYWALLED_MAIN = "<main><h1>A paywalled article</h1><p>Purchase this article.</p></main>"


@pytest.mark.parametrize("footer", [
    f"<footer>{SITE_CC}</footer>",
    f'<div class="page-footer"><a href="https://creativecommons.org/licenses/by/4.0/">'
    f'<img alt="CC BY" src="/img/cc-by.png"/></a></div>',
    f'<div id="footer"><div id="contenu_footer"><div id="creativecommons">'
    f'<a href="http://creativecommons.org/licenses/by-nc-nd/2.0/fr/"><img alt="Creative Commons" src="/cc.png"/></a>'
    f'</div></div></div>',
    f'<div class="pkp_structure_footer_wrapper"><div class="pkp_structure_footer">{SITE_CC}</div></div>',
    f'<div role="contentinfo">{SITE_CC}</div>',
    f'<nav class="site-nav"><ul><li>{SITE_CC}</li></ul></nav>',
])
@pytest.mark.parametrize("layout", [
    "<body>{main}{footer}</body>",
    '<body><div class="flex-wrap-footer">{main}{footer}</div></body>',          # nested in a wrapper named *-footer
    '<body class="has-footer-widgets"><div id="page">{main}{footer}</div></body>',
])
def test_site_footer_licence_is_never_the_articles(footer, layout):
    page = "<html><head><title>t</title></head>" + layout.format(main=PAYWALLED_MAIN, footer=footer) + "</html>"
    assert parse_page(page, "doi", TRUSTED_URL)["license"] is None
    assert "creativecommons" not in page_potential_license_text(page)


@pytest.mark.parametrize("footer", [
    # most of the page's text, and the furniture a text or heading test would take for content
    f"<footer><h1>Journal of Examples</h1><ul>{SITE_LINKS}</ul><p>{SITE_CC}</p></footer>",
    f'<div class="site-footer"><h1>Journal of Examples</h1><ul>{SITE_LINKS}</ul><p>{SITE_CC}</p></div>',
    f'<footer><article><h2>Latest news</h2><ul>{SITE_LINKS}</ul></article><p>{SITE_CC}</p></footer>',
    f'<div id="footer"><div id="content-footer"><ul>{SITE_LINKS}</ul><p>{SITE_CC}</p></div></div>',
])
@pytest.mark.parametrize("body", [
    "<main><p>Purchase this article.</p></main>",     # short body: the footer is nearly all the text
    "<div id=\"root\"></div>",                           # app shell: the footer is all the text
    "<div><p>Purchase this article.</p></div>",
])
def test_footer_that_is_most_of_the_text_is_still_a_footer(footer, body):
    page = f"<html><head><title>t</title></head><body>{body}{footer}</body></html>"
    assert parse_page(page, "doi", TRUSTED_URL)["license"] is None
    assert "creativecommons" not in page_potential_license_text(page)


# --- the helper itself

def test_wrapper_text_is_kept_and_its_nested_chrome_is_not():
    page = ('<html><body><div class="sticky-footer-wrap"><main><p>ARTICLE <a href="https://creativecommons.org/'
            'licenses/by-nc/4.0/">CC BY-NC</a></p></main><footer>FOOTERTEXT</footer>'
            '<div class="site-footer">SITEFOOTER</div></div></body></html>')
    text = page_potential_license_text(page)
    assert "creativecommons.org/licenses/by-nc/4.0" in text and "ARTICLE" in text
    assert "FOOTERTEXT" not in text and "SITEFOOTER" not in text


def test_role_main_counts_as_main():
    page = ('<html><body><div id="wrap-footer"><div role="main"><a href="https://creativecommons.org/licenses/by/4.0/">'
            'CC BY</a></div><div class="footer">FOOTERTEXT</div></div></body></html>')
    text = page_potential_license_text(page)
    assert "creativecommons" in text and "FOOTERTEXT" not in text


def test_page_without_chrome_is_returned_untouched():
    page = "<html><body><main><p>text</p></main></body></html>"
    assert page_potential_license_text(page) is page


def test_main_element_with_a_footer_like_name_is_content():
    page = ('<html><body><main class="content has-sticky-footer"><a href="https://creativecommons.org/licenses/by/4.0/">'
            'CC BY</a></main><footer>FOOTERTEXT</footer></body></html>')
    text = page_potential_license_text(page)
    assert "creativecommons" in text and "FOOTERTEXT" not in text


@pytest.mark.parametrize("chrome", [
    f'<nav role="main"><ul><li>{SITE_CC}</li></ul></nav>',
    f'<footer role="main">{SITE_CC}</footer>',
])
def test_nav_or_footer_calling_itself_main_is_still_chrome(chrome):
    page = f"<html><body><div><p>Purchase this article.</p></div>{chrome}</body></html>"
    assert "creativecommons" not in page_potential_license_text(page)
