"""Record pages keep the abstract they print (oxjob #2239, round 1 of the random-sample loop); publisher pages
too, with a main-article guard (round 4)."""
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


def test_publisher_page_reads_its_own_abstract_heading():
    # round 4: publisher pages use the heading reader too, with a main-article guard
    html = f"<html><body><h2>Abstract</h2><p>{ABSTRACT}</p></body></html>"
    assert parse_page(html.encode(), "doi", "https://example.org/x")["abstract"] == ABSTRACT


def test_publisher_page_drops_the_article_history_tail():
    html = (f"<html><body><h2>Abstract</h2><div><p>{ABSTRACT}</p><p>Received 15 February 2005</p>"
            f"<p>DOI: https://doi.org/10.1103/x ©2005 American Physical Society</p></div></body></html>")
    assert parse_page(html.encode(), "doi", "https://example.org/x")["abstract"] == ABSTRACT


def test_publisher_page_skips_other_works_abstracts():
    other = ABSTRACT.replace("cheese", "yoghurt")
    related = (f"<div class='related-articles'><h3>Abstract</h3><p>{other}</p></div>")
    assert parse_page(f"<html><body>{related}</body></html>".encode(), "doi", "https://example.org/x")["abstract"] is None
    aside = f"<aside><h3>Abstract</h3><p>{other}</p></aside>"
    assert parse_page(f"<html><body>{aside}</body></html>".encode(), "doi", "https://example.org/x")["abstract"] is None


def test_publisher_listing_with_two_abstracts_is_not_read():
    other = ABSTRACT.replace("cheese", "yoghurt")
    html = f"<html><body><h2>Abstract</h2><p>{ABSTRACT}</p><h2>Abstract</h2><p>{other}</p></body></html>"
    assert parse_page(html.encode(), "doi", "https://example.org/issue/3")["abstract"] is None


def test_peer_review_report_page_gets_no_abstract():
    # PLOS's review-report page carries the reviewed article's tags and abstract; its parser returns the byline only
    url = "https://journals.plos.org/plosone/peerReview?id=10.1371/journal.pone.0310173.r002"
    html = (f'<html><head><meta property="og:url" content="{url}"/><meta name="citation_abstract" content="{ABSTRACT}"/>'
            f'</head><body><div class="title-authors"><ul><li><a class="author-name">Ana Lima,</a></li></ul></div>'
            f'<h2>Abstract</h2><p>{ABSTRACT}</p></body></html>')
    assert parse_page(html.encode(), "doi", url)["abstract"] is None


def test_cut_preview_under_abstract_heading_is_not_read():
    html = f"<html><body><h2>Abstract</h2><p>{ABSTRACT[:150]}…</p></body></html>"
    assert parse_page(html.encode(), "doi", "https://example.org/x")["abstract"] is None


def test_authors_only_publisher_page_gets_its_citation_abstract():
    # PLOS's parser returns its byline only; the article-level tag fills the abstract
    html = (f'<html><head><meta property="og:url" content="https://journals.plos.org/plosone/article?id=1"/>'
            f'<meta name="citation_abstract" content="{ABSTRACT}"/></head><body><div class="title-authors"><ul>'
            f'<li><a class="author-name">Ana Lima,</a></li></ul></div></body></html>')
    out = parse_page(html.encode(), "doi", "https://journals.plos.org/plosone/article?id=1")
    assert out["abstract"] == ABSTRACT


def test_short_abstract_in_a_tag_named_for_one():
    short = "This paper makes progress on classifying closed orientable 3-manifolds that contain arithmetic knots."
    html = (f'<html><head><meta name="citation_title" content="Arithmetic knots"/>'
            f'<meta name="citation_abstract" content="{short}"/></head><body></body></html>')
    assert parse_page(html.encode(), "pmh", "https://hal.science/hal-1")["abstract"] == short
    same_as_title = (f'<html><head><meta name="citation_title" content="{short}"/>'
                     f'<meta name="citation_abstract" content="{short}"/></head><body></body></html>')
    assert parse_page(same_as_title.encode(), "pmh", "https://hal.science/hal-1")["abstract"] is None


def test_citation_lines_are_not_abstracts():
    from parseland_lib.not_abstract import is_not_abstract
    assert is_not_abstract("(1983). Incorporation of Mental Health Into Primary Health Care. International Journal of "
                           "Mental Health: Vol. 12, Mental Health Care in Developing Countries, pp. 1-15.")
    assert is_not_abstract("Generations on the Land: A Conservation Legacy. By Joe Nick Patoski. 2011. Sand County "
                           "Foundation, College Station, TX, USA. 136 p. US$25. hardcover. ISBN 978-1-60344-241-1.")


def test_review_report_doi_through_doi_org_gets_no_abstract():
    # the stored URL is the review's DOI; the page's og:url names the reviewed article
    html = (f'<html><head><meta property="og:url" content="https://journals.plos.org/plosglobalpublichealth/article?id=1"/>'
            f'<meta name="citation_abstract" content="{ABSTRACT}"/></head><body><div class="title-authors"><ul>'
            f'<li><a class="author-name">Ana Lima,</a></li></ul></div><h2>Abstract</h2><p>{ABSTRACT}</p></body></html>')
    assert parse_page(html.encode(), "doi", "https://doi.org/10.1371/journal.pgph.0000105.r005")["abstract"] is None


def test_no_abstract_notice_with_citation_is_not_an_abstract():
    from parseland_lib.not_abstract import is_not_abstract
    assert is_not_abstract("No hay resúmenes disponibles.\nInvestigaciones UCA, Año. 1, Vol. 1, 2019-2020: 48-52.")
    assert not is_not_abstract(ABSTRACT)
