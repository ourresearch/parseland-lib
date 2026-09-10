"""
Scraped licences must come from the article, not from site chrome.

Two guards, both offline:
1. trust_publisher_license(): hosts whose licence text is site-wide (footer, shell page,
   aggregator) are ignored in BOTH the publisher (doi) and repository (pmh) paths.
2. page_potential_license_text(): <footer>, <nav>, role=contentinfo and footer-named
   containers are stripped before the licence regexes run, so a site footer on an
   otherwise-trusted host cannot license a paywalled page.
"""
import pytest

from parseland_lib.legacy_parse_utils.pdf import trust_publisher_license
from parseland_lib.legacy_parse_utils.version_and_license import page_potential_license_text
from parseland_lib.parse import parse_page


CC_LINK = '<a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>'

BODY_LICENSED = f"""<html><head><title>t</title></head><body>
<article><p>This article is distributed under the terms of the {CC_LINK}.</p></article>
</body></html>"""

FOOTER_ONLY = f"""<html><head><title>t</title></head><body>
<article><p>Purchase this article.</p></article>
<footer>The content of this site is licensed under a {CC_LINK}.</footer>
</body></html>"""


@pytest.mark.parametrize("url", [
    "https://www.scientific.net/AMM.719-720.580",
    "https://www.schwabeonline.ch/schwabe-xaveropp/elibrary/start.xav?id=doi%3A10.24894%2FX",
    "https://indianjournals.com/article/ijphrd-10-11-899",
    "https://www.indianjournals.com/ijor.aspx?target=ijor:ijphrd",
    "https://www.crossref.org:443/deleted_DOI.html",
    "https://chooser.crossref.org/?doi=10.1215%2F9780822377450-079",
    "https://doaj.org/article/c87843854b2c4926a2e5fa83f5262983",
])
def test_site_licence_hosts_are_untrusted(url):
    assert trust_publisher_license(url) is False


@pytest.mark.parametrize("url", [
    "https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0000001",
    "https://www.frontiersin.org/articles/10.3389/fpsyg.2019.00001/full",
    "https://notscientific.net/x",       # suffix match must be on a dot boundary
    "https://doaj.org.example.com/x",
    None, "",
])
def test_ordinary_hosts_are_trusted(url):
    assert trust_publisher_license(url) is True


def test_untrusted_host_licence_dropped_on_publisher_path():
    assert parse_page(BODY_LICENSED, "doi", "https://www.scientific.net/AMM.1.1")["license"] is None


def test_untrusted_host_licence_dropped_on_repo_path():
    assert parse_page(BODY_LICENSED, "pmh", "https://doaj.org/article/abc")["license"] is None


def test_trusted_host_body_licence_kept():
    assert parse_page(BODY_LICENSED, "doi", "https://journals.plos.org/x")["license"] == "cc-by"
    assert parse_page(BODY_LICENSED, "pmh", "https://repo.example.edu/x")["license"] == "cc-by"


def test_footer_licence_is_not_the_article_licence():
    assert parse_page(FOOTER_ONLY, "doi", "https://journals.plos.org/x")["license"] is None


@pytest.mark.parametrize("wrapper", [
    '<footer>{}</footer>',
    '<nav>{}</nav>',
    '<div role="contentinfo">{}</div>',
    '<div class="sc-footer">{}</div>',
    '<div class="footer-fluid">{}</div>',
    '<div id="footer">{}</div>',
    '<div id="site_footer">{}</div>',
])
def test_chrome_containers_are_stripped(wrapper):
    html = f"<html><body><main>body</main>{wrapper.format(CC_LINK)}</body></html>"
    assert "creativecommons" not in page_potential_license_text(html)


def test_article_body_is_not_stripped():
    html = f'<html><body><div class="article-footnotes">{CC_LINK}</div></body></html>'
    assert "creativecommons" in page_potential_license_text(html)


# --- shorthand "cc by" must be a token in the original text, not a substring of stripped text

@pytest.mark.parametrize("text,expected", [
    ("This work is licensed CC BY 4.0", "cc-by"),
    ("Licence: CC-BY-NC-ND", "cc-by-nc-nd"),
    ("cc by-nc-sa", "cc-by-nc-sa"),
    ("(CC BY-SA 4.0)", "cc-by-sa"),
    ("https://creativecommons.org/licenses/by-nc/4.0/", "cc-by-nc"),
    # base64 of "...sheep rearers..." contains "ccbyzwfy" once whitespace is stripped
    ("PGk+dGhlIGNhc2Ugb2Ygc2hlZXAgcmVhcmVyc2luIHNlbWk=", None),
    ("cmfyesbtawdyyxrpb24gdg8gtwl0awdhdgugrm9kzgvyifnjyxjjaxr5oibuagugy2fzzsbvzibzagvlccbyzwfyzxjz", None),
    ("accbyx", None),
    ("occupancy by night", None),  # "cc by" split across words with a space is a token: 'occupan-cc by' is not
])
def test_cc_shorthand_requires_token_boundaries(text, expected):
    from parseland_lib.legacy_parse_utils.pdf import find_normalized_license
    assert find_normalized_license(text) == expected
