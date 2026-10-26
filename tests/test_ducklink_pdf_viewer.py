"""find_pdf_link must not error on a DuckLink that reaches its element checks (Sentry PARSELAND-4, oxjob #1809).

OJS 3.3 PDF-viewer pages put the download link in <div class="pdf-download-button">. get_useful_links adds that
link twice: once as the lxml <a> element and once as a DuckLink (the pdf-download container rule). With a
non-English label ("Скачать", "Herunterladen") neither copy matches the anchor checks, so the DuckLink reached
`link.findall(".//img")` and `link.attrib["title"]` and raised AttributeError, which errored the whole page
(~550 pages a day, e.g. taxicab 4fe914f0-1092-4915-9596-3f6a62e2d132 on med-alyans.ru).

Shape copied from that stored page; hand-crafted, no Taxicab, no network.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from parseland_lib.legacy_parse_utils.fulltext import parse_publisher_fulltext_location
from parseland_lib.legacy_parse_utils.pdf import DuckLink, find_pdf_link

RESOLVED = "https://med-alyans.ru/index.php/Hahn/article/view/1115/1292"

OJS_VIEWER = """<!DOCTYPE html>
<html lang="ru-RU"><head><meta charset="utf-8">
<title>Просмотр «Роль бронхоскопического исследования» | Медицинский Альянс</title>
<meta name="generator" content="Open Journal Systems 3.3.0.8"></head>
<body class="page-view-pdf">
  <div class="pdf-header">
    <div class="pdf-return-article">
      <a href="https://med-alyans.ru/index.php/Hahn/article/view/1115" class="btn btn-text">
        <span class="sr-only">Вернуться к Подробностям о статье</span>Роль бронхоскопического исследования</a>
    </div>
    <div class="pdf-download-button">
      <a href="https://med-alyans.ru/index.php/Hahn/article/download/1115/1292/4078" class="btn" download>
        <span class="label">{label}</span>
      </a>
    </div>
  </div>
  <div id="pdfCanvasContainer" class="pdf-frame">
    <iframe src="https://med-alyans.ru/plugins/generic/pdfJsViewer/pdf.js/web/viewer.html?file=x"></iframe>
  </div>
</body></html>"""


def test_ducklink_answers_element_questions():
    link = DuckLink(href="https://example.org/a.pdf", anchor="x")
    assert link.findall(".//img") == []
    assert link.attrib == {}


def test_ojs_viewer_non_english_label_does_not_error():
    for label in ("Скачать", "Herunterladen"):
        soup = BeautifulSoup(OJS_VIEWER.format(label=label), "lxml")
        # Before the fix this raised AttributeError: 'DuckLink' object has no attribute 'findall'.
        find_pdf_link(RESOLVED, soup=soup)
        parse_publisher_fulltext_location(soup, RESOLVED)


def test_ojs_viewer_english_label_unchanged():
    # The English label already returned the <a> element at the "download" anchor check; still does.
    soup = BeautifulSoup(OJS_VIEWER.format(label="Download"), "lxml")
    link = find_pdf_link(RESOLVED, soup=soup)
    assert link is not None
    assert link.href == "https://med-alyans.ru/index.php/Hahn/article/download/1115/1292/4078"
