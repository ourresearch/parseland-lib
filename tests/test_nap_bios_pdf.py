"""National Academies project pages: the committee bios file is not the report's PDF. Oxjob #1152 (Zendesk 28305).

A study's publication page under www.nationalacademies.org/projects/<code>/publication/<record> links "Download all bios"
(projects/<code>/download-bios, an 8-page PDF of the committee members' biographies) before the report's own "Read
Online" and "Download PDF" links. The PDF finder took the bios file, and 160 NAP reports served it as their PDF.

Hand-crafted HTML modelled on https://www.nationalacademies.org/projects/HMD-FNB-23-06/publication/28582 (doi
10.17226/28582, Wayback 2026-09-24), no network.
"""
from bs4 import BeautifulSoup

from parseland_lib.legacy_parse_utils.pdf import find_pdf_link, has_bad_href_word

URL = "https://www.nationalacademies.org/projects/HMD-FNB-23-06/publication/28582"
BIOS = "https://www.nationalacademies.org/projects/HMD-FNB-23-06/download-bios"
REPORT = "https://www.nationalacademies.org/publications/28582/download"


def _page(with_report=True):
    report = f"""
      <a href="https://www.nationalacademies.org/read/28582">Read Online</a>
      <a class="btn" href="{REPORT}">Download PDF</a>
    """ if with_report else ""
    return f"""
    <html><head><title>Review of Evidence on Alcohol and Health</title></head><body>
      <nav><a href="https://www.nationalacademies.org/projects/HMD-FNB-23-06/resources">Publications/Resources</a></nav>
      <section class="committee">
        <h2>Committee</h2>
        <a href="{BIOS}">Download all bios</a>
      </section>
      <section class="publication">
        <h1>Review of Evidence on Alcohol and Health</h1>
        {report}
      </section>
    </body></html>
    """


def _find(html):
    link = find_pdf_link(URL, BeautifulSoup(html, parser="lxml", features="lxml"))
    return link.href if link is not None else None


def test_bios_href_is_bad():
    assert has_bad_href_word(BIOS)
    assert has_bad_href_word(BIOS + "?x=1")
    assert has_bad_href_word("https://nationalacademies.org/projects/DBASSE-BOSE-23-01/download-bios")


def test_other_nap_files_are_not_bad():
    assert not has_bad_href_word("https://nap.nationalacademies.org/resource/29391/9780309604475_508.pdf")
    assert not has_bad_href_word(REPORT)
    assert not has_bad_href_word("https://www.nationalacademies.org/projects/HMD-FNB-23-06/download-bios-guide.pdf")


def test_bios_file_is_never_the_pdf():
    assert _find(_page()) != BIOS
    assert _find(_page(with_report=False)) != BIOS
