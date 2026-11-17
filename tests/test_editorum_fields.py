"""Editorum article pages (naukaru.ru, editorum.ru and ~30 Russian university journal sites on the platform): byline,
corresponding author, reference list and funding row (oxjob #2289).

Markup is cut down from stored Editorum pages (17 Nov 2026, #2289 sample). The platform prints each author in a byline
card (`div.author-list-item` > `span.name`) with an envelope `mailto:` link for an author whose profile has an e-mail;
editorial-board cards share the class but carry a role in <b> and no `span.name`.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.editorum import Editorum

URL = "https://example-journal.ru/en/nauka/article/82422/view"
HEAD = ('<head><title>Journal - Эдиторум - Editorum</title>'
        '<link href="/bundles/asu/lib/bootstrap-3.3.5-dist/css/bootstrap.min.css" rel="stylesheet">'
        '<link href="/bundles/journals/css/journals.css" rel="stylesheet">{metas}</head>')


def _card(name, n, mail=None):
    sup = f'<a href="#author{n}"><sup class="author-id" data-toggle="collapse" data-target="#collapse-1">{n}</sup></a>'
    env = f'<a href="mailto:{mail}"><span class="glyphicon glyphicon-envelope"></span></a>' if mail else ""
    return (f'<div class="author-list-item"><img class="avatar" src="/bundles/journals/images/author.jpg">'
            f'<div class="info"><a href="/en/nauka/author/{n}00/view" target="_blank"><span class="name"> {name} '
            f'</span></a>{sup}{env}</div></div>')


EDITOR_CARD = ('<div class="author-list-item"><img class="avatar" src="/bundles/journals/images/author.jpg">'
               '<div class="info"><b> Deputy Editor in Chief </b><br><a href="/en/nauka/author/9/view"> Igor Abramov '
               '</a><br><a class="mail" href="mailto:editor@example.ru">editor@example.ru</a></div></div>')

REFS_ITEMS = ('<div class="anchor-id" id="article-references"></div><div class="content-block info-block">'
              '<div class="panel panel-article"><div class="panel-heading panel-article-heading">'
              '<div class="panel-title panel-article-title"><a href="#collapse-4"><span class="fa"></span> References'
              '</a></div></div><div id="collapse-4" class="panel-collapse collapse in"><div class="panel-body '
              'panel-article-body"><div class="article-text words-wrap">{items}</div></div></div></div></div>')

FUNDING_ROW = ('<div class="article-info-row"><div class="key"><b>Funding:</b></div><div class="value">\n The authors are '
               'grateful for the financial support of grant from the Russian Science Foundation No. 23-28-01774\n'
               '</div></div>')


def _page(cards, extra="", metas="", sidebar=EDITOR_CARD):
    return (f"<html>{HEAD.format(metas=metas)}<body><div class=\"col-sm-9 col-md-8 article-page-content\">"
            f'<div class="content-block info-block"><div class="entity-title"> A title </div></div>'
            f'<div class="content-block info-block">{"".join(cards)}</div>{extra}</div>'
            f'<div class="col-sm-3 col-xs-12"><div class="content-block info-block">'
            f'<h5 class="text-center"><b>The contact persons</b></h5>{sidebar}</div></div></body></html>')


def _authors(html):
    return parse_page(html.encode(), "doi", URL)["authors"]


def _corr(html):
    return [a["name"] for a in _authors(html) if a["is_corresponding"]]


def _parse(html):
    return Editorum(BeautifulSoup(html, parser="lxml", features="lxml")).parse()


def test_byline_names_are_read_without_meta_tags():
    html = _page([_card("Barkova A. S.", 1), _card("Shurmanova   E. I.", 2)])
    assert [a["name"] for a in _authors(html)] == ["Barkova A. S.", "Shurmanova E. I."]


def test_editorial_board_cards_are_not_authors():
    html = _page([_card("Perov S.", 1)])
    assert [a["name"] for a in _authors(html)] == ["Perov S."]


def test_issue_page_with_only_editor_cards_is_not_claimed():
    html = _page([], sidebar=EDITOR_CARD * 3)
    assert not Editorum(BeautifulSoup(html, parser="lxml", features="lxml")).authors_found()


def test_single_author_with_envelope_is_corresponding():
    assert _corr(_page([_card("Sayfutdinova Alsu", 1, "a@mail.ru")])) == ["Sayfutdinova Alsu"]


def test_lone_envelope_among_authors_is_corresponding():
    cards = [_card("Polyakova Irina", 1), _card("Grigorieva Maria", 2, "m@mail.ru"), _card("Ivanov Petr", 3)]
    assert _corr(_page(cards)) == ["Grigorieva Maria"]


def test_envelope_on_every_author_marks_no_one():
    cards = [_card("Elesina Irina", 1, "e@list.ru"), _card("Guz Olga", 2, "g@mail.ru")]
    assert _corr(_page(cards)) == []


def test_envelopes_on_several_authors_mark_no_one():
    cards = [_card("Panasiuk Leonid", 1, "p@gmail.com"), _card("Kravchenko Galina", 2, "k@mail.ru"),
             _card("Trufanova Elena", 3)]
    assert _corr(_page(cards)) == []


def test_placeholder_address_is_not_an_email():
    cards = [_card("Elovicova Tatyana", 1, "u@yandex.ru"), _card("Shimova Margarita", 2, "fake@neicon.ru")]
    assert _corr(_page(cards)) == ["Elovicova Tatyana"]


def test_no_envelope_marks_no_one():
    assert _corr(_page([_card("Amir Akhmetov", 1)])) == []


def test_numbered_reference_items_are_a_whole_list():
    items = ('<p id="reference-item">1. Rossinskij S.B. Zaderzhanie podozrevaemogo. Moskva: Prospekt, 2019. 188 s.</p>'
             '<p id="reference-item">2. Bahrah D.N. Administrativnoe pravo Rossii. Moskva: Eksmo, 2011. 622 s.</p>'
             '<p id="reference-item">3. Brace L.H. A global view. Geophys. Res. Lett. 1997. '
             '<a href="https://doi.org/10.1029/97GL02087">https://doi.org/10.1029/97GL02087</a></p>')
    out = _parse(_page([_card("Perov S.", 1)], REFS_ITEMS.format(items=items)))
    assert [r["position"] for r in out["references"]] == [1, 2, 3]
    assert out["references"][0]["raw"] == "Rossinskij S.B. Zaderzhanie podozrevaemogo. Moskva: Prospekt, 2019. 188 s."
    assert out["references"][2]["doi"] == "10.1029/97GL02087"
    assert out["references_complete"] is True


def test_plain_paragraph_references_are_read():
    items = ("<p>1. Shuraev O. P. Modelirovanie v srede Flow Vision // Vestn. 2006. № 20. S. 177-180.\n </p>"
             "<p>2. Elcut. Rukovodstvo pol'zovatelya. URL: www.elcut.ru/free_doc_r.htm.\n </p>")
    out = _parse(_page([_card("Perov S.", 1)], REFS_ITEMS.format(items=items)))
    assert [r["raw"] for r in out["references"]] == [
        "Shuraev O. P. Modelirovanie v srede Flow Vision // Vestn. 2006. № 20. S. 177-180.",
        "Elcut. Rukovodstvo pol'zovatelya. URL: www.elcut.ru/free_doc_r.htm."]
    assert out["references_complete"] is True


def test_numbering_gap_is_not_a_whole_list():
    items = '<p id="reference-item">1. Alpha A. Title. 2019.</p><p id="reference-item">3. Beta B. Title. 2020.</p>'
    out = _parse(_page([_card("Perov S.", 1)], REFS_ITEMS.format(items=items)))
    assert len(out["references"]) == 2
    assert out["references_complete"] is False


def test_text_outside_the_entries_is_not_a_whole_list():
    items = '<p id="reference-item">1. Alpha A. Title. 2019.</p>Gamma G. Another title. 2021.'
    out = _parse(_page([_card("Perov S.", 1)], REFS_ITEMS.format(items=items)))
    assert out["references_complete"] is False


def test_no_reference_panel_gives_no_references():
    out = _parse(_page([_card("Perov S.", 1)]))
    assert not out.get("references")
    assert not out.get("references_complete")


def test_funding_row_is_the_funding_statement():
    out = _parse(_page([_card("Perov S.", 1)], FUNDING_ROW))
    assert out["funding_statement"] == ("The authors are grateful for the financial support of grant from the Russian "
                                        "Science Foundation No. 23-28-01774")


def test_ojs_byline_with_span_name_is_not_claimed():
    # nearest look-alike: an Open Journal Systems author list also prints <span class="name"> and a mailto link
    html = ('<html><head><meta name="generator" content="Open Journal Systems 3.3.0.10"/>'
            '<link rel="stylesheet" href="/lib/pkp/styles/fontawesome/fontawesome.css"></head><body>'
            '<section class="item authors"><ul class="authors"><li><span class="name">Annisa Dwi</span>'
            '<a href="mailto:a@example.id">a@example.id</a></li><li><span class="name">Rully Anwar</span></li></ul>'
            '</section><div class="author-list-item"><span class="name">Rully Anwar</span></div></body></html>')
    assert not Editorum(BeautifulSoup(html, parser="lxml", features="lxml")).authors_found()


def test_bundle_path_alone_is_not_enough():
    html = ('<html><head><link href="/bundles/journals/css/journals.css" rel="stylesheet"></head><body>'
            '<div class="author"><span class="name">Some One</span></div></body></html>')
    assert not Editorum(BeautifulSoup(html, parser="lxml", features="lxml")).authors_found()
