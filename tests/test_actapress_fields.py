"""ACTA Press paper pages (actapress.com PaperInfo.aspx; IASTED proceedings and journals, DOI prefix 10.2316), oxjob #2339.

Markup is cut down from stored pages: one ASP.NET template whose <head> carries citation_* meta tags with
citation_publisher "ACTA Press", and whose div#content prints span#lblTitle, span#lblAuthors (names only, sometimes
with bare asterisks the page never explains), span#lblKeywords and span#lblAbstract. The generic parser reads the
meta-tag names and, on some pages, the one-sentence `description` meta tag as the abstract; it never reads
span#lblAbstract. The page shows no affiliations, corresponding author, acknowledgments, funding or reference list.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.actapress import ActaPress

URL = "https://doi.org/10.2316/Journal.201.2004.3.201-1195"
ABSTRACT = ("This article investigates the problems of stochastic stabilization and\r\ncontrol for a class of linear "
            "time-delay systems with Markovian\r\njump parameters via output feedback. The jumping parameters are\r\n"
            "modelled as continuous-time, discrete-state Markov process. The\r\ndelay factor is unknown and "
            "time-varying with a known bound.")
ABSTRACT_FLAT = " ".join(ABSTRACT.split())
NAMES = ["A. Ismail", "M.S. Mahmoud", "P. Shi"]


def _page(abstract=ABSTRACT, publisher="ACTA Press", byline="A. Ismail, M.S. Mahmoud, and P. Shi", names=NAMES,
          description="This article investigates the problems of stochastic stabilization."):
    metas = "".join(f'<meta name="citation_author" content="{n}" />' for n in names)
    pub = f'<meta name="citation_publisher" content="{publisher}" />' if publisher else ""
    abstract_span = f'<span id="lblAbstract">{abstract}</span>' if abstract is not None else ""
    return f"""<!DOCTYPE html><html><head><title>[Abstract] Output Feedback Stabilization</title>
<meta http-equiv="content-type" content="text/html;charset=utf-8"/>
<meta name="description" content="{description}" />
<meta name="citation_title" content="Output Feedback Stabilization" />{pub}{metas}
<meta name="citation_pdf_url" content="http://actapress.com/pdfviewer.aspx?paperID=20521" />
<meta name="citation_doi" content="10.2316/Journal.201.2004.3.201-1195" /></head>
<body><div id="container"><div id="main"><div id="content">
<form method="post" action="./PaperInfo.aspx?paperId=20521" id="Form1">
<h2 class="title" style="TEXT-ALIGN: center"><span id="lblTitle">Output Feedback Stabilization</span></h2>
<p style="TEXT-ALIGN: center"><span id="lblAuthors">{byline}</span></p>
<h3 class="underlinedhead">Keywords</h3>
<p class="first_paragraph"><span id="lblKeywords">Disturbance attenuation, time-delay systems</span></p>
<h3 class="underlinedhead">Abstract</h3>
<p class="first_paragraph">{abstract_span}</p>
<p>Important Links:</p><ul><li><span id="lblReferences"></span></li>
<li>DOI: <span id="lblDOI"><a href="http://dx.doi.org/10.2316/Journal.201.2004.3.201-1195">10.2316/Journal.201.2004.3.201-1195</a></span></li></ul>
</form></div></div></div></body></html>"""


def _parser(html):
    return ActaPress(BeautifulSoup(html, parser="lxml", features="lxml"))


def test_abstract_from_the_page_not_the_description_meta():
    out = parse_page(_page().encode(), "doi", URL)
    assert out["abstract"] == ABSTRACT_FLAT
    assert [a["name"] for a in out["authors"]] == NAMES
    assert all(a["affiliations"] == [] for a in out["authors"])


def test_inline_markup_kept_as_text():
    out = parse_page(_page(abstract="We propose a fast smile detection method based on the terms of "
                                    "<em>orientation of gradient</em>. HOG features are then classified.").encode(),
                     "doi", URL)
    assert out["abstract"] == ("We propose a fast smile detection method based on the terms of orientation of "
                               "gradient. HOG features are then classified.")


def test_bare_asterisk_is_not_a_corresponding_mark():
    out = parse_page(_page(byline="A.E.-M.M. Abd El-Aal∗", names=["A.E.-M.M. Abd El-Aal"]).encode(), "doi", URL)
    assert [a["name"] for a in out["authors"]] == ["A.E.-M.M. Abd El-Aal"]
    assert not any(a["is_corresponding"] for a in out["authors"])


def test_new_fields_absent():
    parsed = _parser(_page()).parse()
    assert parsed["acknowledgments"] is None
    assert parsed["funding_statement"] is None
    assert parsed["references"] == []
    assert parsed["references_complete"] is False


def test_empty_abstract_span_gives_no_abstract():
    parser = _parser(_page(abstract="  "))
    assert parser.is_publisher_specific_parser()
    assert parser.parse()["abstract"] is None


def test_listing_page_without_abstract_span_not_read():
    # "The Proceeding you were looking for was not found." pages carry no span#lblAbstract
    parser = _parser(_page(abstract=None))
    assert not parser.authors_found()


def test_lookalike_aspnet_page_not_claimed():
    # another publisher's ASP.NET page with the same span ids but its own citation_publisher
    parser = _parser(_page(publisher="Science and Engineering Research Support Society"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_page_without_publisher_meta_not_claimed():
    parser = _parser(_page(publisher=None))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
