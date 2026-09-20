"""Reference / footnote containers must never supply the article PDF. Oxjob #786.

The generic finder sorts every .pdf-shaped href to the front of the candidate
list, so a third-party report cited in a reference list, footnote or reader
comment used to beat the page's own (non-.pdf-shaped) download link, or win
outright when the page offers no PDF. Four publisher templates had containers
the bad-section list did not know: Science eLetters, Annual Reviews' reference
list, ACM's DPUB-ARIA footnotes/bibliography, PLOS's <ol class="references">.

Hand-crafted HTML that mirrors the real ancestor chains of the stored pages
(10.1126/science.add2734, 10.1146/annurev-polisci-040723-013245, 10.1145/3746132,
10.1371/journal.pone.0316527) — no network.
"""
from parseland_lib.parse import parse_page

CITED_PDF = "https://www.un.org/sites/un2.un.org/files/governing_ai_for_humanity_final_report_en.pdf"


def _pdf_urls(html, resolved_url):
    out = parse_page(html, "doi", resolved_url)
    return [u["url"] for u in out["urls"] if u["content_type"] == "pdf"]


def _page(body):
    return f"<html><head><title>x</title></head><body>{body}</body></html>"


def test_science_eletter_pdf_is_dropped_and_own_pdf_kept():
    html = _page(f"""
      <div class="article-container"><div class="after-credits"><div class="core-container">
        <a href="/doi/pdf/10.1126/science.add2734">Download PDF</a>
      </div></div></div>
      <div class="related-do__items"><div class="eletters-comment mb-1_5x">
        <div class="eletters-comment__description serif">
          <p><u>References and notes</u></p>
          <ol><li><a href="{CITED_PDF}">{CITED_PDF}</a></li></ol>
        </div></div></div>
    """)
    assert _pdf_urls(html, "https://www.science.org/doi/10.1126/science.add2734") == [
        "https://www.science.org/doi/pdf/10.1126/science.add2734"
    ]


def test_annual_reviews_reference_list_pdf_is_dropped():
    html = _page(f"""
      <ol id="articlereference" class="articlereference-vancouver">
        <li id="ref-B79" class="refbody"><div class="citation"><div class="ref-content">
          <span class="reference-bold"><a target="xrefwindow" href="{CITED_PDF}">{CITED_PDF}</a></span>
        </div></div></li>
      </ol>
    """)
    assert _pdf_urls(html, "https://www.annualreviews.org/content/journals/10.1146/annurev-polisci-040723-013245") == []


def test_acm_footnotes_and_bibliography_pdfs_are_dropped():
    html = _page(f"""
      <section id="backmatter"><div class="core-container">
        <section id="footnotes"><div role="doc-footnote"><div id="fn1" role="paragraph">
          <a href="{CITED_PDF}">{CITED_PDF}</a>
        </div></div></section>
        <section id="bibliography" role="doc-bibliography"><div role="list"><div role="listitem">
          <div class="citations"><div class="citation"><div class="citation-content">
            <a href="https://www.nber.org/system/files/working_papers/w11986/w11986.pdf">w11986.pdf</a>
          </div></div></div>
        </div></div></section>
      </div></section>
    """)
    assert _pdf_urls(html, "https://dl.acm.org/doi/10.1145/3746132") == []


def test_plos_reference_list_loses_to_own_printable_link():
    html = _page(f"""
      <aside class="article-aside"><div class="dload-menu"><div class="dload-pdf">
        <a href="/plosone/article/file?id=10.1371/journal.pone.0316527&amp;type=printable">Download PDF</a>
      </div></div></aside>
      <div class="article-text" id="artText"><div class="toc-section">
        <ol class="references"><li id="ref36">
          <a href="https://www.who.int/nmh/publications/essential_ncd_interventions_lr_settings.pdf">WHO report</a>
        </li></ol>
      </div></div>
    """)
    assert _pdf_urls(html, "https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0316527") == [
        "https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0316527&type=printable"
    ]


def test_dpub_aria_containers_are_generic():
    # A page on any host: the same markup without the wrapper still surfaces the link,
    # so the exclusion (not some other filter) is what drops it.
    resolved = "https://example-press.org/article/1"
    wrapped = _page(f'<div role="doc-endnotes"><p><a href="{CITED_PDF}">{CITED_PDF}</a></p></div>')
    bare = _page(f'<a href="{CITED_PDF}">{CITED_PDF}</a>')
    assert _pdf_urls(wrapped, resolved) == []
    assert _pdf_urls(bare, resolved) == [CITED_PDF]
