"""CSIRO Publishing (publish.csiro.au) article pages: the corresponding author on the old byline (oxjob #2338).

Markup is cut down from stored publish.csiro.au pages (#2338, 17 Nov 2026). The site has two bylines. Articles from
about 2004 on print `<span class="editors">` with lettered affiliations and a "Corresponding author" footnote, which
csiro.py has always read. Older articles print `<div class="Editors">` with plain names and, when the site knows the
corresponding author, wrap that one name in a mailto link (the page's citation_author_email tag repeats the address).
The gold marks the one author whose e-mail the byline shows (#2166 OJS, dev gold notes); an e-mail link on every
author is not a mark. On the old byline the citation_author tags still give the authors and the abstract stays the
generic reader's: only the mark is new.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.csiro import CSIRO

URL = "https://doi.org/10.1071/ch01027"
ABSTRACT = ("Polyfluorinated 1,3-diketones containing carbocycles react with aldehydes under Lewis-acid catalysis and "
            "also with dimethylformamide-dimetylacetal without catalysis, yielding exclusively (E)-configured "
            "condensation products involving the methylene group of the carbocycle.")


def _old_page(names, byline, og_url="https://www.publish.csiro.au/ch/ch01027", emails=()):
    metas = "".join(f'<meta name="citation_author" content="{n}">' for n in names)
    metas += "".join(f'<meta name="citation_author_email" content="{e}">' for e in emails)
    return (f'<html><head><meta name="citation_publisher" content="CSIRO PUBLISHING">{metas}'
            f'<meta name="citation_title" content="Condensation of 2-Polyfluoroacylcycloalkanones">'
            f'<meta name="citation_abstract" content="{ABSTRACT}">'
            f'<meta property="og:url" content="{og_url}"></head><body>'
            f'<section class="region-main-content"><h1>Condensation of 2-Polyfluoroacylcycloalkanones</h1>'
            f'<div class="Editors">{byline}</div>'
            f'<div class="Journal_editors"><p><i>Australian Journal of Chemistry</i> 54(3) 157 - 163</p></div>'
            f'<div class="journal-abstract green-item"><h2>Abstract</h2>{ABSTRACT}</div>'
            f'</section></body></html>')


OLD_NAMES = ["D. V. Sevenard", "O. G. Khomutov", "G.-V. R&#246;schenthaler"]
OLD_LINKED = ('D. V. Sevenard, O. G. Khomutov and <a href="mailto:gv@chemie.uni-bremen.de"> '
              'G.-V. R&#246;schenthaler</a>')


def _parsed(html):
    return parse_page(html.encode(), "doi", URL)


def _corr(html):
    return [a["name"] for a in _parsed(html)["authors"] if a["is_corresponding"]]


def test_old_byline_mail_link_marks_that_author():
    html = _old_page(OLD_NAMES, OLD_LINKED, emails=["gv@chemie.uni-bremen.de"])
    out = _parsed(html)
    assert [a["name"] for a in out["authors"]] == ["D. V. Sevenard", "O. G. Khomutov", "G.-V. Röschenthaler"]
    assert [a["is_corresponding"] for a in out["authors"]] == [False, False, True]
    assert out["abstract"].startswith("Polyfluorinated 1,3-diketones")


def test_old_byline_two_authors_first_linked():
    names = ["Robert S. Hill", "David C. Christophel"]
    byline = '<a href="mailto:Bob.Hill@adelaide.edu.au"> Robert S. Hill</a> and David C. Christophel'
    assert _corr(_old_page(names, byline, og_url="https://www.publish.csiro.au/sb/sb00025")) == ["Robert S. Hill"]


def test_old_byline_without_mail_link_marks_no_one():
    html = _old_page(OLD_NAMES, "D. V. Sevenard, O. G. Khomutov and G.-V. R&#246;schenthaler")
    out = _parsed(html)
    assert [a["name"] for a in out["authors"]] == ["D. V. Sevenard", "O. G. Khomutov", "G.-V. Röschenthaler"]
    assert not any(a["is_corresponding"] for a in out["authors"])
    assert not CSIRO(BeautifulSoup(html, "lxml")).authors_found()  # left to the generic reader, as before


def test_mail_link_on_every_author_marks_no_one():
    names = ["KL Viggers", "DM Spratt"]
    byline = ('<a href="mailto:kv@example.edu.au">KL Viggers</a> and '
              '<a href="mailto:ds@example.edu.au">DM Spratt</a>')
    assert _corr(_old_page(names, byline, og_url="https://www.publish.csiro.au/wr/wr9950311")) == []


def test_link_to_a_name_not_in_the_tags_marks_no_one():
    byline = 'D. V. Sevenard and <a href="mailto:office@example.org">Editorial Office</a>'
    assert _corr(_old_page(["D. V. Sevenard", "O. G. Khomutov"], byline)) == []


def test_new_byline_still_read_from_lettered_affiliations():
    html = ('<html><head><meta name="citation_publisher" content="CSIRO PUBLISHING">'
            '<meta name="citation_author" content="Paul V. Bernhardt">'
            '<meta name="citation_author" content="Raymond M. Carman">'
            '<meta property="og:url" content="https://www.publish.csiro.au/ch/CH14597"></head><body>'
            '<span class="editors"> Paul V. Bernhardt <sup>A</sup> , Raymond M. Carman <sup>A</sup> <sup>B</sup> </span>'
            '<div id="full-description"><span id="hide-description">- Author Affiliations</span><br/>'
            '<p><sup>A</sup> School of Chemistry and Molecular Biosciences, The University of Queensland, '
            'Brisbane, Qld 4072, Australia. </p>'
            '<p><sup>B</sup> Corresponding author. Email: <a class="reftools" href="mailto:carman@uq.edu.au">'
            'carman@uq.edu.au</a> </p></div></body></html>')
    out = _parsed(html)
    assert [a["name"] for a in out["authors"]] == ["Paul V. Bernhardt", "Raymond M. Carman"]
    assert [bool(a["is_corresponding"]) for a in out["authors"]] == [False, True]
    assert out["authors"][0]["affiliations"][0]["name"].startswith("School of Chemistry and Molecular Biosciences")


def test_look_alike_byline_on_another_site_is_not_claimed():
    html = _old_page(OLD_NAMES, OLD_LINKED, og_url="https://journal.example.org/article/123")
    parser = CSIRO(BeautifulSoup(html, "lxml"))
    assert not parser.authors_found()
    assert not parser.is_publisher_specific_parser()


def test_silverchair_book_editors_list_is_not_read():
    # connectsci.au (Silverchair) book pages carry class "editors" on their byline; csiro.py read junk there
    html = ('<html><head><meta property="og:url" content="https://connectsci.au/books/edited-volume/382/chapter/42989/">'
            '</head><body><div class="al-authors-list editors"><div class="al-author-prefix">Edited by</div>'
            '<div class="al-author-name"><a class="linked-name">A. Editor</a></div></div></body></html>')
    assert not CSIRO(BeautifulSoup(html, "lxml")).authors_found()
