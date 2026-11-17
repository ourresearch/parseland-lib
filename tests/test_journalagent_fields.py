"""JournalAgent article pages (jvi.aspx; LookUs Bilisim's journal platform) (oxjob #2289).

Markup is cut down from stored JournalAgent pages (17 Nov 2026). The byline is <span class='JAgAuthors'>, each name
followed by its <sup> affiliation number and the corresponding author's name underlined; the citation box below the
abstract (<div id=citat>) states "Corresponding Author: Name, Country" ("Sorumlu Yazar:" on Turkish pages). The
generic parser found that author only when the box named no one else: journalagent.com's own journals print the
"How to cite this article" line with every name in the same box, and Turkish pages carry no citation_author tags.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.journalagent import JournalAgent

URL = "https://jag.journalagent.com/tkd/pdfs/x.pdf"
NAMES = ["Leyla Arslan", "Samet Kurt", "Nadir D Ozer"]


def _byline(names, underlined=None, orcid=False, empty_marks=False):
    parts = []
    for i, n in enumerate(names, 1):
        shown = f"<u>{n}</u>" if n == underlined else n
        if orcid:
            shown = f'<a class=orcid target=_blank href="https://orcid.org/0000-0002-0000-000{i}">{shown}</a>'
        mark = "<u></u>" if empty_marks else ""
        parts.append(f"{shown}{mark}<sup>{i}{mark}</sup>")
    affs = "".join(f"<sup>{i}</sup>Department {i}, Some University, Istanbul-Turkey<br>" for i in range(1, len(names) + 1))
    return f"<span class='JAgAuthors'>{', '.join(parts)}</span></br><span class='JAgAffiliations'>{affs}</span>"


def _page(byline, citat, metas=True, names=NAMES):
    tags = "".join(f'<meta name="citation_author" content="{n.split()[-1]}, {" ".join(n.split()[:-1])}">'
                   for n in names) if metas else ""
    return ('<form method="post" action="./jvi.aspx?un=TKDA-56846" id="ctl00"><div class="row">'
            f'<head><meta name="citation_title" content="A study"><meta name="citation_firstpage" content="228">{tags}'
            '<meta name="citation_language" content="en"></head>'
            "<h2 class='journalArticleinTitleeng'>A study</h2>"
            f"{byline}<p>OBJECTIVE: an abstract of the study.</p><b>Keywords:</b>&nbsp;one, two<br>"
            f"<hr noshade size=4><div id=citat>{citat}</div></div></form>")


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _corr(html):
    return [a["name"] for a in _parse(html)["authors"] if a["is_corresponding"]]


HOW_TO_CITE = ("<b>How to cite this article</b><br> Leyla Arslan, Samet Kurt, <u>Nadir D Ozer</u>.&nbsp;A study.&nbsp;"
               "Turk Kardiyol Dern Ars.&nbsp;2016; 44(3):&nbsp;228-236<br><br>")


def test_statement_marks_corresponding_when_the_box_also_cites_every_author():
    html = _page(_byline(NAMES, underlined="Nadir D Ozer"),
                 HOW_TO_CITE + "<b>Corresponding Author: </b>Nadir D Ozer, United States<br>"
                               "<b>Manuscript Language: </b>English")
    out = _parse(html)
    assert [a["name"] for a in out["authors"]] == NAMES
    assert _corr(html) == ["Nadir D Ozer"]
    assert [a["is_corresponding"] for a in out["authors"]] == [False, False, True]


def test_turkish_page_without_author_tags():
    html = _page(_byline(NAMES, underlined="Leyla Arslan", orcid=True),
                 "<br><br><b>Sorumlu Yazar: </b>Leyla Arslan, Türkiye", metas=False)
    out = _parse(html)
    assert [a["name"] for a in out["authors"]] == NAMES
    assert _corr(html) == ["Leyla Arslan"]


def test_names_inside_orcid_links_and_underline_come_out_clean():
    html = _page(_byline(NAMES, underlined="Samet Kurt", orcid=True),
                 "<b>Corresponding Author: </b>Samet Kurt<br><b>Manuscript Language: </b>English")
    assert [a["name"] for a in _parse(html)["authors"]] == NAMES
    assert _corr(html) == ["Samet Kurt"]


def test_no_statement_marks_nobody():
    # empty <u></u> marks after every name and no "Corresponding Author" line (turkishfamilyphysician.com)
    html = _page(_byline(NAMES, empty_marks=True), HOW_TO_CITE + "<b>Makale Dili: </b>Türkçe")
    out = _parse(html)
    assert [a["name"] for a in out["authors"]] == NAMES
    assert not any(a["is_corresponding"] for a in out["authors"])


def test_statement_naming_no_byline_author_marks_nobody():
    html = _page(_byline(NAMES), "<b>Corresponding Author: </b>Someone Else, Türkiye")
    assert _corr(html) == []


def test_bilingual_page_reads_one_byline():
    byline = _byline(NAMES, underlined="Samet Kurt")
    html = _page(byline + "<p>Amac: bir ozet.</p><h2 class='journalArticleinTitletur'>Bir calisma</h2>" + byline,
                 "<b>Corresponding Author: </b>Samet Kurt, Türkiye")
    out = _parse(html)
    assert [a["name"] for a in out["authors"]] == NAMES
    assert _corr(html) == ["Samet Kurt"]


def test_claims_only_the_byline_span():
    soup = BeautifulSoup(_page(_byline(NAMES), "<b>Corresponding Author: </b>Samet Kurt"), "lxml")
    parser = JournalAgent(soup)
    assert parser.is_publisher_specific_parser()
    assert parser.authors_found()
    assert all(a["affiliations"] == [] for a in parser.parse()["authors"])


def test_lookalike_page_from_another_template_is_not_claimed():
    # DergiPark-like page: citation tags, a byline with sup numbers and a "Corresponding Author:" line, no JAgAuthors
    html = ('<html><head><meta name="citation_title" content="A study">'
            '<meta name="citation_author" content="Arslan, Leyla"><meta name="citation_author" content="Kurt, Samet">'
            '<meta name="citation_language" content="tr"></head><body>'
            "<span class='article-authors'>Leyla Arslan<sup>1</sup>, Samet Kurt<sup>2</sup></span>"
            "<div id=citat><b>Corresponding Author: </b>Samet Kurt, Türkiye</div></body></html>")
    parser = JournalAgent(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_page_misdecoded_by_its_declared_charset_is_left_alone():
    # jarengteah.org declares windows-1254 and serves UTF-8: lxml stops at the first byte that code page lacks (the 9E
    # of "Ş"), so the soup ends mid-byline and the citation box is gone. Not read: no half byline.
    names = ["Arzu Demir", "Halil Şen", "Sena Kaya"]
    html = _page(_byline(names, underlined="Arzu Demir"), "<b>Sorumlu Yazar: </b>Arzu Demir, Türkiye", metas=False,
                 names=names)
    html = '<meta http-equiv="Content-Type" content="text/html; charset=windows-1254">' + html
    assert parse_page(html.encode("utf-8"), "doi", URL)["authors"] == []


def test_byline_read_in_the_wrong_encoding_is_not_claimed():
    names = ["Semra AÃ§Ä±ksÃ¶z", "Sena Kaya"]  # "Açıksöz" read as windows-1254, with no byte that code page lacks
    soup = BeautifulSoup(_page(_byline(names), "<b>Sorumlu Yazar: </b>Sena Kaya", metas=False, names=names), "lxml")
    assert not JournalAgent(soup).authors_found()


def test_page_without_the_citation_box_is_not_claimed():
    soup = BeautifulSoup(_page(_byline(NAMES), "").replace("<div id=citat></div>", ""), "lxml")
    assert not JournalAgent(soup).authors_found()
