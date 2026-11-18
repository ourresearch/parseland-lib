"""Science Alert (scialert.net, the Asian Network for Scientific Information journals, DOI prefix 10.3923) abstract
pages (oxjob #2338).

Markup is cut down from stored scialert.net pages (17 Nov 2026). The site runs its own PHP / Bootstrap template with no
citation_* meta tags; its <head> carries twitter:site "@scialert". The abstract is the text of
<article class="sidebar text-justify"> up to its <hr> (the PDF / Fulltext / References buttons follow it). Words of the
abstract may be keyword links, and structured abstracts bold their part labels. The byline links each name to
ascidatabase.com and the sidebar shows only "Country: ..." per author: no affiliations, no corresponding-author marks.
The parser ships the abstract only: the live works already carry these authors (from Crossref).
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.scialert import ScienceAlert

URL = "https://doi.org/10.3923/xyz.2016.331.337"
HEAD = ('<head><script async src="https://www.googletagmanager.com/gtag/js?id=G-1"></script>'
        '<meta property="og:image" content="https://docsdrive.com/images/share/xyz.2016.331.337-fb.jpg" />'
        '<meta name="twitter:card" content="summary_large_image" />'
        '<meta name="twitter:site" content="{site}" />'
        '<meta name="twitter:title" content="Effect of a Thing on Another Thing" />'
        '<link rel="amphtml" href="https://scialert.net/abstract/amp.php?doi=xyz.2016.331.337">'
        '<meta charset="utf-8"><title>Effect of a Thing on Another Thing</title>'
        '<meta name="description" itemprop="description" content="Effect of a Thing on Another Thing" />'
        '<meta name="dc.identifier" content="doi:10.3923/xyz.2016.331.337"></head>')
AUTHOR = ("<a href='https://ascidatabase.com/author.php?author={first}&mid=&last={last}' target=_blank "
          'class="authors" title="Click to find out more papers by {first} {last}">{first} {last}</a>')
SIDEBAR_AUTHOR = ('<div class="post-item clearfix"><h4>' + AUTHOR + '</h4><time>Country: India</time></div><hr>')
PLAIN = ('Feeding was delayed by 12, 24 and 48 h in four groups of chicks to measure stress and mortality. '
         'Mortality rose with the delay and villus height fell. ')
STRUCTURED = ('\n<B>Background and objective:</B> Chicks are transported for days without feed. '
              '<B>Materials and Methods:</B> Groups G<SUB>1</SUB>-G<SUB>5</SUB> were fed after 0-72 h (p&lt;0.05). '
              '<B>Results:</B> Mortality was 22.50&plusmn;3.23% in G<SUB>5</SUB>. '
              '<B>Conclusion:</B> Delay raised stress. <hr>\n')
LINKED = ('\nLosses due to weed infestation grow with <a href="https://ascidatabase.com/result.php?searchin=Keywords'
          '&keyword=climate+change" target="_blank" title="Find more articles">climate change</a> and erratic '
          'rainfall in <i>Phytophthora</i> infected taro fields across the region. <hr>\n')
BUTTONS = ('<A href="../qredirect.php?doi=xyz.2016.331.337&linkid=pdf" target="_blank" class="btn btn-sm">PDF</A>'
           '<A class="btn btn-sm" href="../fulltext/?doi=xyz.2016.331.337">Fulltext</A>'
           '<A href="../fulltext/?doi=xyz.2016.331.337#ref" class="btn btn-sm">References</A>')
NAMES = [("Asha", "Rahman"), ("B.M.", "Lone")]


def _page(abstract=PLAIN + "<hr>\n", site="@scialert"):
    sidebar = "".join(SIDEBAR_AUTHOR.format(first=f, last=l) for f, l in NAMES)
    byline = ",\n".join(AUTHOR.format(first=f, last=l) for f, l in NAMES)
    return (f'<!DOCTYPE html><html lang="en">{HEAD.format(site=site)}<body><main id="main">'
            f'<div class="row"><div class="col-lg-4"><div class="sidebar"><h4 class="entry-title"><strong>Authors'
            f'</strong></h4><hr><div class="sidebar-item recent-posts">{sidebar}</div></div></div>'
            f'<div class="col-lg-8"><article class="sidebar"><h6><strong>Research Article</strong></h6>'
            f'<h4 class="entry-title"><strong>Effect of a Thing on Another Thing</strong></h4>'
            f'<div class="entry-content">{byline}</div></article>'
            f'<article class="sidebar text-justify">{abstract}{BUTTONS}</article>'
            f'<article class="sidebar"><h4 class="entry-title"><strong>How to cite this article</strong><hr></h4>'
            f'<div class="entry-content">Asha Rahman and B.M. Lone, 2016. Effect of a Thing on Another Thing.'
            f'</div></article></div></div></main></body></html>')


def _parse(html):
    return ScienceAlert(BeautifulSoup(html, "lxml")).parse()


def test_abstract_is_the_text_justify_block_up_to_its_rule():
    out = parse_page(_page().encode(), "doi", URL)
    assert out["abstract"] == PLAIN.strip()
    assert "PDF" not in out["abstract"] and "Fulltext" not in out["abstract"]


def test_structured_abstract_keeps_labels_and_joins_subscripts():
    out = parse_page(_page(STRUCTURED).encode(), "doi", URL)
    assert out["abstract"].startswith("Background and objective: Chicks are transported")
    assert "Groups G1-G5 were fed after 0-72 h (p<0.05)." in out["abstract"]
    assert "22.50±3.23% in G5." in out["abstract"]
    assert out["abstract"].endswith("Conclusion: Delay raised stress.")


def test_keyword_links_inside_the_abstract_keep_their_words():
    out = parse_page(_page(LINKED).encode(), "doi", URL)
    assert "grow with climate change and erratic rainfall in Phytophthora infected taro" in out["abstract"]


def test_a_block_holding_only_a_full_stop_is_no_abstract():
    assert _parse(_page("\n. <hr>\n"))["abstract"] is None
    assert parse_page(_page("\n. <hr>\n").encode(), "doi", URL)["abstract"] is None


def test_authors_are_not_output_and_country_is_no_affiliation():
    assert _parse(_page())["authors"] == []
    assert parse_page(_page().encode(), "doi", URL)["authors"] == []


def test_page_shows_no_new_fields():
    parsed = _parse(_page())
    assert not parsed.get("references") and not parsed.get("acknowledgments") and not parsed.get("funding_statement")


def test_claims_only_pages_whose_head_names_scialert():
    soup = BeautifulSoup(_page(), "lxml")
    assert ScienceAlert(soup).is_publisher_specific_parser() and ScienceAlert(soup).authors_found()
    # the same Bootstrap blog template run by another publisher (another twitter handle) is not claimed
    other = BeautifulSoup(_page(site="@medwelljournals"), "lxml")
    assert not ScienceAlert(other).is_publisher_specific_parser()
    assert not ScienceAlert(other).authors_found()


def test_cloudflare_challenge_page_is_not_claimed():
    html = ('<!DOCTYPE html><html lang="en-US"><head><title>Just a moment...</title>'
            '<meta name="robots" content="noindex,nofollow"></head><body><h1>www.scialert.net</h1>'
            '<h2 id="challenge-running">Checking if the site connection is secure</h2></body></html>')
    assert not ScienceAlert(BeautifulSoup(html, "lxml")).authors_found()


def test_page_without_the_abstract_block_is_not_read():
    html = _page().replace('class="sidebar text-justify"', 'class="sidebar"')
    assert not ScienceAlert(BeautifulSoup(html, "lxml")).authors_found()
