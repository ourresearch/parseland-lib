"""Record pages keep the abstract they print (oxjob #2239, round 1 of the random-sample loop)."""
from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from bs4 import BeautifulSoup

ABSTRACT = ("The interest in plant-based cheese alternatives is rapidly increasing due to health, environmental and "
            "ethical concerns. This review examines the flavour and textural problems these products face and the "
            "processing routes that address them.")


def test_doaj_record_abstract_under_its_heading_is_read():
    # DOAJ's parser returns authors only, and its description tag is cut short
    html = f"""<html><head><meta property="og:url" content="https://doaj.org/article/3c1ae66e"/>
    <meta name="description" content="{ABSTRACT[:120]}..."/></head><body>
    <dl id="authors-affiliations"><dt>Ali Tekin</dt><dd>Inonu University</dd></dl>
    <section class="col-md-8"><h2>Abstract</h2><p>{ABSTRACT}</p><h2>Keywords</h2><p>cheese</p></section>
    </body></html>"""
    assert parse_page(html.encode(), "pmh", "https://doaj.org/article/3c1ae66e")["abstract"] == ABSTRACT


def test_dcterms_abstract_is_article_level_metadata():
    html = f'<html><head><meta name="DCTERMS.abstract" content="{ABSTRACT}"/></head><body></body></html>'
    assert GenericPublisherParser(BeautifulSoup(html, "lxml")).parse_abstract_meta_tags(include_seo_tags=False) == ABSTRACT


def test_label_with_empty_value_does_not_read_the_next_field():
    html = ("<html><body><table><tr><td class='head'>Abstract</td><td class='odd'></td></tr>"
            "<tr><td class='head'>Keywords</td><td>" + "a long list of keywords and notes, " * 6 + "</td></tr>"
            "</table></body></html>")
    assert GenericPublisherParser(BeautifulSoup(html, "lxml")).parse_headed_abstract_section() is None


def test_abstract_tab_label_is_not_a_heading():
    html = (f"<html><body><ul class='nav-tabs'><li>Abstract</li><li>{ABSTRACT}</li></ul></body></html>")
    assert GenericPublisherParser(BeautifulSoup(html, "lxml")).parse_headed_abstract_section() is None


def test_publisher_pages_do_not_use_the_heading_reader():
    html = f"<html><body><h2>Abstract</h2><p>{ABSTRACT}</p></body></html>"
    assert parse_page(html.encode(), "doi", "https://example.org/x")["abstract"] is None
