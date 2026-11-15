"""Figshare item pages (oxjob #2239 round 3): creators are DataCite.contributor; 'Download' is a PDF only for PDFs."""
from parseland_lib.parse import parse_page

HEAD = """<meta property="og:site_name" content="figshare"/><meta name="DataCite.contributor" content="Yu, Shi"/>
<meta name="DataCite.contributor" content="Zheng, Xu"/><meta name="DC.type" content="figure"/>"""


def page(mime):
    return (f'<html><head>{HEAD}</head><body><a role="tab" href="https://figshare.com/ndownloader/files/43111881">'
            f'Download (2 MB)</a><script>window.__s={{"files":[{{"mimeType":"{mime}"}}]}}</script></body></html>').encode()


def test_figshare_creators_are_the_authors():
    out = parse_page(page("image\\u002Ftiff"), "pmh", "https://figshare.com/articles/figure/x/1")
    assert [a["name"] for a in out["authors"]] == ["Yu, Shi", "Zheng, Xu"]


def test_download_link_of_a_figure_is_not_a_pdf():
    out = parse_page(page("image\\u002Ftiff"), "pmh", "https://figshare.com/articles/figure/x/1")
    assert not [u for u in out["urls"] if u["content_type"] == "pdf"]
