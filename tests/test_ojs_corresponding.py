"""Corresponding authors on Open Journal Systems (OJS) article pages (oxjob #2166).

Markup is cut down from stored long-tail OJS pages (11 Nov 2026, #2166 EXPLORE § 1). No publisher parser claims OJS
sites, so the citation_author meta tags win and carry no correspondence flag. Gold v1.3 marks the author an OJS page
singles out: the theme's primary contact, the one author whose e-mail the author list shows, a starred byline name with
a "(*) Corresponding Author" note, or "Author for correspondence." in the About-the-authors tab.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.ojs import ojs_corresponding_marks

URL = "https://e-journal.example.ac.id/index.php/j/article/view/60170"
GENERATOR = '<meta name="generator" content="Open Journal Systems 3.3.0.10"/>'


def _page(names, body, generator=GENERATOR):
    metas = "".join(f'<meta name="citation_author" content="{n}"/>' for n in names)
    return (f"<html><head>{generator}{metas}<meta name=\"citation_title\" content=\"A title\"/>"
            f"<meta name=\"citation_doi\" content=\"10.20473/x.v1i1.1\"/></head><body>{body}</body></html>")


def _corr(html):
    return [a["name"] for a in parse_page(html.encode(), "doi", URL)["authors"] if a["is_corresponding"]]


def _authors_list(items):
    return '<section class="item authors"><ul class="authors">' + "".join(f"<li>{i}</li>" for i in items) + "</ul></section>"


NAMES = ["Annisa Dwi Fajriyah", "Rully Khairul Anwar", "Siti Chaerani Djen Amar"]


def test_primary_contact_is_marked():
    items = [f'<span class="name">{n}</span><span class="affiliation">Universitas Padjadjaran</span>' for n in NAMES]
    items[1] = items[1].replace("</span>", '</span><div class="primary_contact"><i class="fa fa-envelope-o"></i> '
                                'rully@unpad.ac.id (Primary Contact)</div>', 1)
    assert _corr(_page(NAMES, _authors_list(items))) == ["Rully Khairul Anwar"]


def test_lone_email_in_author_list_is_marked():
    items = [f'<span class="name">{n}</span><span class="affiliation">Poltekkes Palu</span>' for n in NAMES]
    items[0] += '<span class="email"><a href="mailto:annisa@example.id">annisa@example.id</a></span>'
    assert _corr(_page(NAMES, _authors_list(items))) == ["Annisa Dwi Fajriyah"]


def test_cloudflare_protected_email_counts():
    items = [f'<span class="name">{n}</span>' for n in NAMES]
    items[2] += ('<div class="email"><a href="/cdn-cgi/l/email-protection#1b7a62"><span class="__cf_email__" '
                 'data-cfemail="15746c">[email&#160;protected]</span></a></div>')
    assert _corr(_page(NAMES, _authors_list(items))) == ["Siti Chaerani Djen Amar"]


def test_every_author_with_an_email_marks_no_one():
    items = [f'<span class="name">{n}</span><a href="mailto:a{i}@example.id">mail</a>' for i, n in enumerate(NAMES)]
    assert _corr(_page(NAMES, _authors_list(items))) == []


def test_starred_byline_with_corresponding_note():
    names = ["Hussein Mohammed Hathal", "Abdulkareem Swadi Abdullah", "Ramzy Salim Ali"]
    byline = ('<div id="authorString"><a title="Mustansiriyah University">Hussein Mohammed Hathal</a><sup>(1)</sup>, '
              '<a title="University of Basrah">Abdulkareem Swadi Abdullah</a><sup>(2*)</sup>, '
              '<a title="University of Basrah">Ramzy Salim Ali</a><sup>(3)</sup></div>'
              '<br/> <sup>(*)</sup> <i>Corresponding author</i>')
    assert _corr(_page(names, byline, generator="")) == []  # not an OJS page: no PKP marker
    html = _page(names, byline + '<img src="/lib/pkp/templates/images/icons/mail.gif"/>', generator="")
    assert _corr(html) == ["Abdulkareem Swadi Abdullah"]  # the note's own (*) is not a byline name


def test_starred_name_in_span_with_family_name_first():
    names = ["Priyadarshini, V. M", "P. Madhanakumari"]
    body = ('<p class="bold mb-0"> Priyadarshini, V. M <span>*</span> <span><i class="fas fa-envelope"></i></span></p>'
            '<p>Department of Horticulture</p><p class="bold mb-0"> P. Madhanakumari </p>'
            '<p>*Author to whom correspondence should be addressed.</p>')
    assert _corr(_page(names, body)) == ["Priyadarshini, V. M"]


def test_star_without_a_note_is_no_ojs_mark():
    # a copyright line's star with no correspondence note (gold: no mark); the generic parser's own star rule is separate
    html = _page(["Raul Gindo Cahayo", "Hermalia Fauziah"],
                 "<p>Copyright (c) 2024 Raul Gindo Cahayo<sup>*</sup>, Hermalia Fauziah</p>")
    assert ojs_corresponding_marks(BeautifulSoup(html, "lxml"), html) == []


def test_author_for_correspondence_in_about_the_authors():
    names = ["S. O. Kazaryan", "Yu. G. Borisenko"]
    body = ('<div id="tabs-3"><h2 class="label">About the authors</h2>'
            '<h3><a href="/search/authors/view?lastName=Kazaryan">S. O. Kazaryan</a></h3> North-Caucasus Federal University'
            '<p><strong>Author for correspondence.</strong><br> Email: <a href="mailto:s@mail.ru">s@mail.ru</a></p>'
            '<h3><a href="/search/authors/view?lastName=Borisenko">Yu. G. Borisenko</a></h3> North-Caucasus Federal University'
            '<p>Email: <a href="mailto:b@yandex.ru">b@yandex.ru</a></p></div>')
    assert _corr(_page(names, body)) == ["S. O. Kazaryan"]


def test_name_with_trailing_separator():
    names = ["Hawhila Julyse Daryani", "Erna Prasetya Ningrum -"]
    items = [f'<span class="name">{n}</span>' for n in names]
    items[1] += '<div class="primary_contact">erna@mail.ugm.ac.id (Primary Contact)</div>'
    assert _corr(_page(names, _authors_list(items))) == ["Erna Prasetya Ningrum -"]
