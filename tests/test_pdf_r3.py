"""PDF links that were wrong all along on three sites (oxjob #2239, phase 2, class pdf-r3).

DOAJ record pages (doaj.org/article/<id>) print the record's full-text links as "Read online" buttons and nothing
else says which of them is a PDF: only the address does. The finder knew no "Read online" link, so a record whose
button goes straight to the publisher's PDF had no PDF link (68 of 508 labelled DOAJ pages; the other 440 buttons go
to landing pages and gold has no PDF link there).

A JSTOR book page lists one "Download" per chapter (/stable/pdf/<book>.<n>.pdf) and is the page JSTOR serves for
every chapter of the book ("?turn_away=true"). The finder took the first one, the front matter, whichever chapter the
page was stored for; the page doesn't say which, so it has no PDF link.

De Gruyter: a download link the page prints is returned as printed. It used to be moved to the degruyterbrill host
and lose its query (".../pdf?licenseType=free" came back as ".../pdf"). The link the reader builds for a page that
prints none is a different question (parked, oxjob #1632) and is not touched: one test here pins it as it was.

A usage-statistics link ("Full-text downloads" under /usage-metrics/) counts downloads; it is not the file.

Hand-cut markup from the labelled pages; no network.
"""
import pytest

from parseland_lib.parse import parse_page


def _pdf(html, namespace, resolved_url):
    out = parse_page(html, namespace, resolved_url)
    return next((u["url"] for u in out["urls"] if u["content_type"] == "pdf"), None)


# ---- DOAJ ----

DOAJ_URL = "https://doaj.org/article/d518857622504f56b349a4d69241a829"


def _doaj_page(*hrefs, og_url=DOAJ_URL):
    buttons = "\n".join(
        f'<a href="{href}" class="button button--primary" target="_blank" rel="noopener" role="button">Read online</a>'
        for href in hrefs)
    return f"""
    <html><head>
      <title>Kalbos ribos – DOAJ</title>
      <meta property="og:url" content="{og_url}">
      <meta name="citation_journal_title" content="Literatūra (Vilnius)">
    </head><body>
      <a href="/docs/public-data-dump/" class="dropdown__link" role="menuitem"> Public data dump </a>
      <a href="/toc/1648-1143">Literatūra (Vilnius)</a>
      <dl id="authors-affiliations"><dt>Jonas Jonaitis</dt></dl>
      <section class="col-md-8">
        <h2>Abstract</h2>
        <p>{buttons}</p>
        <p class="article-details__abstract">Straipsnyje nagrinėjama ...</p>
      </section>
      <a href="http://www.journals.vu.lt/literatura" target="_blank" rel="noopener">http://www.journals.vu.lt/literatura</a>
      <a href="/toc/1648-1143" class="button secondary-button">About the journal</a>
    </body></html>
    """


def _doaj_pdf(*hrefs, resolved_url=DOAJ_URL):
    return _pdf(_doaj_page(*hrefs), "pmh", resolved_url)


def test_doaj_read_online_pdf_is_the_pdf_link():
    href = "http://www.literatura.flf.vu.lt/wp-content/uploads/2014/03/55_3_50_711.pdf"
    assert _doaj_pdf(href) == href


def test_doaj_page_stored_with_no_url_is_known_by_its_og_url():
    href = "https://jfafu.journals.ekb.eg/article_210006_86dbc6e0d88fcedb16ccd6211c617cc3.pdf"
    assert _doaj_pdf(href, resolved_url=None) == href


@pytest.mark.parametrize("href", [
    "https://doi.org/10.1186/s12889-024-17651-6",
    "https://www.mdpi.com/1422-0067/21/24/9650",
    "https://revistas.usc.gal/index.php/rr/article/view/10048",
    "http://journal.frontiersin.org/article/10.3389/fmicb.2017.02353/full",
    "http://www.redalyc.org/articulo.oa?id=43238076007",
    "http://www.scielo.br/scielo.php?script=sci_arttext&amp;pid=S0103-84781994000300009&amp;lng=en&amp;tlng=en",
    "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8659340/?tool=EBI",
    "http://aammt.tmmu.edu.cn/Upload/rhtml/202101061.htm",
    # "file" inside a word, "pdf" inside a title: neither names a PDF
    "http://perfilesla.flacso.edu.mx/index.php/perfilesla/article/view/486",
    "https://example.org/articles/accessible-pdf-documents-in-libraries",
])
def test_doaj_read_online_landing_page_is_not_a_pdf_link(href):
    assert _doaj_pdf(href) is None


def test_doaj_several_buttons_the_pdf_one_wins_wherever_it_stands():
    html_first = ["http://www.scielo.br/scielo.php?script=sci_arttext&amp;pid=S1519-69842025000100463&amp;lng=en",
                  "http://www.scielo.br/pdf/bjb/v85/1519-6984-bjb-85-e297458.pdf"]
    assert _doaj_pdf(*html_first) == html_first[1]
    pdf_first = ["https://peerj.com/articles/6576.pdf", "https://peerj.com/articles/6576/"]
    assert _doaj_pdf(*pdf_first) == pdf_first[0]


def test_doaj_other_download_formats_are_not_the_pdf():
    hrefs = ["https://zookeys.pensoft.net/article/105446/download/xml/",
             "https://zookeys.pensoft.net/article/105446/download/pdf/",
             "https://zookeys.pensoft.net/article/105446/"]
    assert _doaj_pdf(*hrefs) == hrefs[1]
    assert _doaj_pdf(hrefs[0], hrefs[2]) is None
    assert _doaj_pdf("https://example.org/files/article-55.zip") is None


@pytest.mark.parametrize("href", [
    "http://europepmc.org/articles/PMC4374749?pdf=render",  # the query asks for the PDF
    "https://www.ncbi.nlm.nih.gov/pmc/articles/pmid/22701563/pdf/?tool=EBI",  # a path part named "pdf"
    "http://arxiv.org/pdf/1709.00829v1",
    "http://navus.sc.senac.br/index.php/navus/article/view/477/pdf",
    "https://www.jstage.jst.go.jp/article/jamdsm/7/4/7_608/_pdf/-char/en",
    "https://jcdr.net/articles/PDF/13837/44277_CE[Ra1]_F(SHU)_PF1(Su_AKA_KM)_PN(SL).pdf",
    "https://www.jvas.in/public_html/upload/article_file/article_file_r1kvfz.pdf?t=r1kvfz",
    # three routes that serve the article's file and never say "pdf"
    "https://hrcak.srce.hr/file/450777",
    "https://dergipark.org.tr/tr/download/article-file/4938331",
    "http://journals.rudn.ru/polylinguality/article/viewFile/2025/1498",
])
def test_doaj_addresses_that_name_a_pdf(href):
    assert _doaj_pdf(href) == href


@pytest.mark.parametrize("href", [
    "https://hrcak.srce.hr/clanak/450777",  # Hrčak's article page, not its file
    "https://dergipark.org.tr/en/pub/jsr/issue/90555/1513214",
    "http://journals.rudn.ru/polylinguality/article/view/2025",
    "http://journals.rudn.ru/polylinguality/article/view/2025/1498",  # OJS shows a galley in a web page here
])
def test_doaj_look_alike_routes_are_not_pdf_links(href):
    assert _doaj_pdf(href) is None


def test_read_online_on_another_site_is_left_as_it_was():
    # the rule reads DOAJ's own record template only: the same button on any other record page is not looked at
    html = _doaj_page("https://example.org/files/paper.pdf", og_url="https://repository.example.org/article/55")
    assert _pdf(html, "pmh", "https://repository.example.org/article/55") is None


# ---- JSTOR ----

def _jstor_book_page(book, chapters):
    entries = "\n".join(f"""
        <li><ul>
          <li><a href="/stable/{book}.{n}" aria-hidden="true" tabindex="-1"> {title} </a></li>
          <li><a href="/stable/pdf/{book}.{n}.pdf" aria-hidden="true" tabindex="-1">Download</a></li>
          <li><a href="/doi/xml/10.2307/{book}.{n}" aria-hidden="true" tabindex="-1">XML</a></li>
        </ul></li>""" for n, title in enumerate(chapters, 1))
    return f"""
    <html><head>
      <title>The Other Great Game: The Opening of Korea on JSTOR</title>
      <link rel="canonical" href="https://www.jstor.org/stable/{book}">
    </head><body>
      <main id="content" class="content">
        <div id="toc-mount-point"></div>
        <ul class="visuallyhidden">{entries}</ul>
      </main>
    </body></html>
    """


CHAPTERS = ["Front Matter", "Table of Contents", "INTRODUCTION", "ONE Korea's Pivotal Victory"]


def test_jstor_book_page_has_no_pdf_link():
    # stored for chapter 10.2307/jj.2840677.25: the page is the book's, the first "Download" is the front matter
    html = _jstor_book_page("jj.2840677", CHAPTERS)
    assert _pdf(html, "doi", "https://www.jstor.org/stable/jj.2840677?turn_away=true") is None
    assert _pdf(html, "doi", "https://www.jstor.org/stable/jj.2840677") is None
    assert _pdf(html, "doi", "https://doi.org/10.2307/jj.2840677.25") is None


def test_jstor_book_page_with_doi_shaped_ids_has_no_pdf_link():
    html = _jstor_book_page("10.5325/jj.6914780", CHAPTERS)
    assert _pdf(html, "doi", "https://www.jstor.org/stable/10.5325/jj.6914780?turn_away=true") is None


def test_jstor_book_page_reached_from_a_repository_record_has_no_pdf_link():
    html = _jstor_book_page("j.ctt13wzwh1", CHAPTERS)
    assert _pdf(html, "pmh", "https://www.jstor.org/stable/j.ctt13wzwh1") is None


def test_jstor_page_with_one_item_pdf_keeps_it():
    # one item, one PDF: the page's own (a single-entry list is not a table of contents)
    html = _jstor_book_page("j.ctt13wzwh1", ["Cool: How Air Conditioning Changed Everything"])
    assert _pdf(html, "doi", "https://www.jstor.org/stable/j.ctt13wzwh1.1") == \
        "https://www.jstor.org/stable/pdf/j.ctt13wzwh1.1.pdf"


def test_a_list_of_downloads_on_another_site_is_left_as_it_was():
    html = """
    <html><head><link rel="canonical" href="https://press.example.org/books/55"></head><body>
      <ul><li><a href="/files/55/chapter-1.pdf">Download</a></li>
          <li><a href="/files/55/chapter-2.pdf">Download</a></li></ul>
    </body></html>
    """
    assert _pdf(html, "doi", "https://press.example.org/books/55") == "https://press.example.org/files/55/chapter-1.pdf"


# ---- De Gruyter ----

def _de_gruyter_page(doi, host="www.degruyterbrill.com", restricted=True, download_href=None, preview=None,
                     meta_pdf=None):
    link = (f'<a href="{download_href}" data-doi="{doi}" class="ga_download_button_pdf_chapter '
            f'downloadCompletePdfChapter downloadPdf vgwort-click btn-download-dgb"><span>Download chapter (PDF)</span>'
            f'</a>') if download_href else ""
    viewer = f'<div class="pdf-container" data-url="{preview}" lang="en"></div>' if preview else ""
    meta = f'<meta name="citation_pdf_url" content="{meta_pdf}"/>' if meta_pdf else ""
    return f"""
    <html><head>
      <meta property="og:url" content="https://{host}/document/doi/{doi}/html"/>
      {meta}
    </head><body>
      <span class="contributor">Example Author</span>
      {link}
      <div id="documentContent" data-doi='{doi}' data-accessrestricted="{str(restricted).lower()}">
        <div class="dgb-accordion-item pdfView">{viewer}</div>
      </div>
    </body></html>
    """


def test_de_gruyter_page_that_prints_no_link_keeps_its_built_link():
    # parked (#1632): whether a page that shows no PDF link should get a built one is not decided here; unchanged
    doi = "10.1515/sug-2024-2011"
    built = f"https://www.degruyterbrill.com/document/doi/{doi}/pdf"
    html = _de_gruyter_page(doi, preview=f"/document/doi/{doi}/pdf/firstPage")
    assert _pdf(html, "doi", f"https://www.degruyterbrill.com/document/doi/{doi}/html") == built
    html = _de_gruyter_page(doi, host="www.degruyter.com")
    assert _pdf(html, "doi", f"https://www.degruyter.com/document/doi/{doi}/html") == built


def test_de_gruyter_download_link_is_returned_as_the_page_prints_it():
    doi = "10.1515/9780228000129-001"
    html = _de_gruyter_page(doi, restricted=False, download_href=f"/document/doi/{doi}/pdf?licenseType=free",
                            preview=f"/document/doi/{doi}/pdf?stream=true")
    assert _pdf(html, "doi", f"https://www.degruyterbrill.com/document/doi/{doi}/html") == \
        f"https://www.degruyterbrill.com/document/doi/{doi}/pdf?licenseType=free"


def test_de_gruyter_download_link_stays_on_the_pages_own_host():
    doi = "10.1515/9781782384465-001"
    html = _de_gruyter_page(doi, host="www.degruyter.com", restricted=False, download_href=f"/document/doi/{doi}/pdf",
                            preview=f"/document/doi/{doi}/pdf?stream=true")
    expected = f"https://www.degruyter.com/document/doi/{doi}/pdf"
    assert _pdf(html, "doi", f"https://www.degruyter.com/document/doi/{doi}/html") == expected
    # stored under doi.org: resolved against the page's own og:url
    assert _pdf(html, "doi", f"https://doi.org/{doi}") == expected


def test_de_gruyter_pdf_meta_tag_is_returned_as_it_is():
    doi = "10.1515/9783110841015-007"
    meta_pdf = f"https://www.degruyter.com/document/doi/{doi}/pdf"
    html = _de_gruyter_page(doi, host="www.degruyter.com", preview=f"/document/doi/{doi}/pdf/firstPage",
                            meta_pdf=meta_pdf)
    assert _pdf(html, "doi", f"https://doi.org/{doi}") == meta_pdf


# ---- usage statistics ----

def _record_page(*links):
    anchors = "\n".join(f'<a href="{href}">{text}</a>' for href, text in links)
    return f"""
    <html><head><title>Goal Setting for On-Demand Learning</title></head><body>
      <a href="/ir/Record/1783.1-136951">Goal Setting for On-Demand Learning: A Field Experiment</a>
      <h3>Usage Metrics</h3>
      {anchors}
    </body></html>
    """


RECORD_URL = "https://repository.hkust.edu.hk/ir/Record/1783.1-136951"
METRICS = [("/ir/usage-metrics/pageviews/1783.1-136951", "Page views"),
           ("/ir/usage-metrics/download/1783.1-136951", "Full-text downloads")]


def test_usage_metrics_link_is_not_the_pdf():
    assert _pdf(_record_page(*METRICS), "pmh", RECORD_URL) is None


@pytest.mark.parametrize("href", [
    "/repo/usage-statistics/item/55", "/usage_stats/55?type=download", "/download-statistics/55", "/usagemetrics/55",
])
def test_other_usage_statistics_routes_are_not_the_pdf(href):
    assert _pdf(_record_page((href, "Full-text downloads")), "pmh", RECORD_URL) is None


def test_the_records_own_file_wins_over_the_usage_metrics_link():
    own = ("/ir/bitstream/1783.1-136951/1/paper.pdf", "Download")
    assert _pdf(_record_page(*METRICS, own), "pmh", RECORD_URL) == \
        "https://repository.hkust.edu.hk/ir/bitstream/1783.1-136951/1/paper.pdf"


@pytest.mark.parametrize("href", [
    # a file whose own name says usage, metrics or statistics is still the file
    "/bitstream/10251/56150/1/Study%20on%20the%20non-linear%20metrics%20contribution.pdf",
    "/files/usage-statistics-of-academic-libraries.pdf",
    "/record/55/files/usage-metrics.pdf",
    "/statistics/article/download/55/60",
])
def test_a_file_named_for_usage_or_metrics_is_still_the_pdf(href):
    assert _pdf(_record_page((href, "Download")), "pmh", RECORD_URL) == "https://repository.hkust.edu.hk" + href
