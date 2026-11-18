"""IAFOR (The International Academic Forum, iafor.org) paper pages: one WordPress site, two layouts (oxjob #2339).

Markup is cut down from stored pages of papers.iafor.org (the research archive's conference papers, /submission<id>/)
and iafor.org/journal/<journal>/<issue>/article-<n>/ (its journals). Each lists its authors as plain lines
"Name, Affiliation, Country" under a label: an "Author Information" heading (h3) above the abstract, or an
"Author Information" <strong> below it (older papers), or "Author:" / "Authors:" in bold on journal pages. The
WordPress byline ("Posted by James Alexander Gordon") is the site's poster, not an author.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.iafor import IAFOR

URL = "https://papers.iafor.org/submission95317/"
ABSTRACT = ("In recent years, the proliferation of e-learning systems has provided an unprecedented opportunity to collect "
            "and analyze vast amounts of data concerning student learning behaviors. This research aims to use data "
            "mining techniques to identify common learning patterns of at-risk students across various disciplines.")
PAPER_INFO = ('<div id="ap-search-filter-results"> <br /> <h3>Paper Information</h3> Conference: ECE2025<br /> '
              'Stream: Design<p> This paper is part of the ECE2025 Conference Proceedings (<a href="#">View</a>) <br />'
              ' Full Paper View / Download the full paper in a new tab/window</p></div>')
BYLINE = ('<p class="entry-byline"><a class="entry-byline-author" href="https://papers.iafor.org/author/amp21/">'
          ' James Alexander Gordon </a> <span class="entry-byline-on">on</span></p>')
FAV = '<button class="simplefavorite-button" data-postid="72196">Save as a Favourite</button>'


def _head(url, canonical=None, cites=()):
    og = f'<meta property="og:url" content="{url}" />' if url else ""
    link = f'<link rel="canonical" href="{canonical}" />' if canonical else ""
    tags = "".join(f'<meta name="citation_author" content=" {c}" />' for c in cites)
    return (f'<html><head><title>A title - The IAFOR Research Archive</title>{link}{og}'
            '<meta name="description" content="Academic Paper published by IAFOR under Creative Commons Attribution 4.0 '
            f'Attribution Non Commercial International" />{tags}</head>')


def page_heading_above(url=URL, head=None):
    """Current layout: <h3>Author Information</h3> lines, then <h3>Abstract</h3>."""
    head = head or _head(url, cites=("Chiu, Hon-Sun", "Wong, Adam"))
    return (f'{head}<body><article><header class="entry-header"><h1 class="entry-title">A title</h1>{BYLINE}</header>'
            '<div class="entry-content"> <br /><br /> <h3>Author Information</h3> Hon-Sun Chiu, The Hong Kong '
            'Polytechnic University, Hong Kong<br /> Adam Wong, The Hong Kong Polytechnic University, Hong Kong <br />'
            f'<br /> <h3>Abstract</h3> <p>{ABSTRACT}</p> {FAV} {PAPER_INFO}</div></article></body></html>')


def page_strong_below():
    """Older layout (2020-2022 papers, link rel=canonical only): <h4>Abstract</h4> first, then a bold label."""
    head = _head(None, canonical="https://papers.iafor.org/submission60608/",
                 cites=("Brito, Isabel", "Oliveira, Ema Patrícia", "Ramos, Ludovina"))
    return (f'{head}<body><article><header class="entry-header"><h1 class="entry-title">A title</h1>{BYLINE}</header>'
            f'<div class="entry-content"> <h4>Abstract</h4> <p>{ABSTRACT}</p> <p>Second paragraph of it.</p> {FAV} '
            '<br><br> <strong>Author Information</strong><br> Isabel Brito, University of Beira Interior, Portugal<br />'
            ' Ema Patrícia Oliveira, University of Beira Interior, Portugal<br /> Ludovina Ramos, University of Beira '
            f'Interior, Portugal <!-- single post area --> {PAPER_INFO}</div></article></body></html>')


def page_journal(label="Authors:", lines=("Adam Al Sultan, Imam Abdulrahman Bin Faisal University, Saudi Arabia",
                                          "Harvey Henson, Jr., Southern Illinois University, USA",
                                          "Peter J. Fadde, Southern Illinois University, USA")):
    url = "https://iafor.org/journal/iafor-journal-of-education/volume-6-issue-1/article-2/"
    sep = "<br />" if label == "Authors:" else ""
    people = "<br /> ".join(lines)
    return (f'{_head(url)}<body><article><div class="entry-content"><a href="https://iafor.org/archives/x.pdf" '
            f'class="pdfemb-viewer">10.22492.ije.6.1.02<br/></a> <p><strong>{label}</strong>{sep} {people}<br /> '
            '<strong>Email:</strong> <a href="/cdn-cgi/l/email-protection#81ec"><span class="__cf_email__">'
            '[email&#160;protected]</span></a><br /> <strong>Published:</strong> February 28, 2018<br /> '
            '<a href="https://doi.org/10.22492/ije.6.1.02">https://doi.org/10.22492/ije.6.1.02</a></p> '
            '<p><strong>Citation</strong>: Al Sultan, A. (2018). A title. IAFOR Journal of Education, 6(1).</p> <hr /> '
            f'<h4>Abstract</h4> <p>{ABSTRACT}</p> <h4>Keywords</h4> <p>science, literacy</p></div></article>'
            '</body></html>')


def _parse(html, url=URL):
    return parse_page(html.encode(), "doi", url)


def _names_affs(out):
    return [(a["name"], [x["name"] for x in a["affiliations"]]) for a in out["authors"]]


def test_heading_layout_authors_and_affiliations():
    out = _parse(page_heading_above())
    assert _names_affs(out) == [("Hon-Sun Chiu", ["The Hong Kong Polytechnic University, Hong Kong"]),
                                ("Adam Wong", ["The Hong Kong Polytechnic University, Hong Kong"])]


def test_wordpress_poster_and_paper_information_are_not_authors():
    names = [a["name"] for a in _parse(page_heading_above())["authors"]]
    assert "James Alexander Gordon" not in names and "Paper Information" not in names


def test_heading_layout_abstract_not_the_proceedings_note():
    """The parser returns no abstract; with the poster's byline no longer winning the page, parse_page's own
    "Abstract" heading reader prints the page's (it read "This paper is part of the ... Proceedings (View)")."""
    assert _parse(page_heading_above())["abstract"] == ABSTRACT


def test_older_layout_canonical_only_authors_after_abstract():
    out = _parse(page_strong_below(), "https://doi.org/10.22492/issn.2188-1162.2021.1")
    assert _names_affs(out) == [("Isabel Brito", ["University of Beira Interior, Portugal"]),
                                ("Ema Patrícia Oliveira", ["University of Beira Interior, Portugal"]),
                                ("Ludovina Ramos", ["University of Beira Interior, Portugal"])]
    assert out["abstract"].startswith(ABSTRACT) and out["abstract"].endswith("Second paragraph of it.")


def test_journal_layout_authors_with_name_suffix():
    out = _parse(page_journal(), "https://iafor.org/journal/iafor-journal-of-education/volume-6-issue-1/article-2/")
    assert _names_affs(out) == [("Adam Al Sultan", ["Imam Abdulrahman Bin Faisal University, Saudi Arabia"]),
                                ("Harvey Henson Jr.", ["Southern Illinois University, USA"]),
                                ("Peter J. Fadde", ["Southern Illinois University, USA"])]
    assert out["abstract"] == ABSTRACT


def test_journal_layout_single_author_on_the_label_line():
    out = _parse(page_journal("Author:", ("Mark Williams, Akita International University, Japan",)))
    assert _names_affs(out) == [("Mark Williams", ["Akita International University, Japan"])]


def test_no_corresponding_mark_on_these_pages():
    for html in (page_heading_above(), page_strong_below(), page_journal()):
        assert not any(a["is_corresponding"] for a in _parse(html)["authors"])


def test_no_new_fields_from_the_parser():
    out = IAFOR(BeautifulSoup(page_heading_above(), "lxml")).parse()
    assert not out.get("references") and not out.get("acknowledgments") and not out.get("funding_statement")


def test_proceedings_listing_page_not_read():
    """A DOI that resolves to a proceedings volume's listing: no author block, so the parser does not read it."""
    html = (f'{_head("https://papers.iafor.org/proceedings/conference-proceedings-acp2025/")}<body><article>'
            '<div class="entry-content"><h2>Conference Proceedings</h2><p>ISSN: 2187-4743</p></div></article></body></html>')
    assert not IAFOR(BeautifulSoup(html, "lxml")).authors_found()


def test_lookalike_wordpress_page_from_another_site_not_claimed():
    """Same WordPress markup and label on another site's page: not IAFOR's."""
    html = page_heading_above(head=_head("https://papers.example-forum.org/submission95317/",
                                         canonical="https://papers.example-forum.org/submission95317/",
                                         cites=("Chiu, Hon-Sun",)))
    parser = IAFOR(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_iafor_in_a_path_of_another_site_not_claimed():
    html = page_heading_above(head=_head("https://www.example.org/mirror/papers.iafor.org/submission95317/"))
    assert not IAFOR(BeautifulSoup(html, "lxml")).authors_found()
