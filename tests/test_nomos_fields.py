"""Authors on Nomos eLibrary's platform (oxjob #2268, template "nomos"): Inlibra's PDF viewer, the older chapter card.

Markup is cut down from stored inlibra.com pages (16 Nov 2026). A chapter or article DOI lands on the platform's PDF
viewer ("/document/view/pdf/uuid/..."). Its citation_* meta tags describe the whole book or journal issue, so the
generic reader gives a chapter its book's editors (or nothing, on an issue), while the page's own chapter panel
("Kapitelinformationen", #panel-info) names the chapter's authors. The bibliographic panel (#panel-bibinfo) lists the
book's or the whole issue's people and is never read. The panel's "Kapitelvorschau" is a preview, not an abstract.
Stored pages from before the move to Inlibra (nomos-, beck-, tectum-elibrary.de) show a chapter as a card ("<chapter>
in: <book>") whose person tags are its authors, with no citation tags; tags labelled "(Hrsg.)" or "(ed.)" are the
book's editors.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.nomos import NomosInlibra

URL = "https://www.inlibra.com/de/document/view/pdf/uuid/1ac7dce4-e39c-36b9-81ba-46882f794bc7"


def _people(dt, names):
    buttons = '<span aria-hidden="true"> | </span>'.join(
        f'<button data-prg-target="link" class="link | is-blue-textlink" '
        f'aria-label="Weitere Publikationen von {n} anzeigen"> {n} </button>' for n in names)
    return f"<div><dt>{dt}</dt><dd>{buttons}</dd></div>"


def _page(chapter_authors=(), book_people=(), meta_authors=(), dt="Autor:innen:", preview="",
          title="Ein Kapitel"):
    metas = "".join(f'<meta content="{n}" name="citation_author" />' for n in meta_authors)
    chapter_dl = _people(dt, chapter_authors) if chapter_authors else ""
    book_dl = _people("Autor:innen:", book_people) if book_people else ""
    return (
        '<html><head><meta content="book" name="og:type" /><meta content="Inlibra" name="og:site_name" />'
        '<meta content="10.5771/9783000000000" name="citation_doi" />'
        '<meta content="Ein Sammelband" name="citation_title" />' + metas +
        '</head><body><main id="main" class="pdf-viewer" data-controller="pdf-viewer">'
        f'<header class="pdf-viewer__header"><h1 class="h3">{title}</h1></header>'
        '<div class="pdf-viewer__sidebar">'
        '<div class="pdf-viewer__panel" id="panel-toc" data-pdf-viewer-target="panel"><h2>Inhaltsverzeichnis</h2></div>'
        '<div class="pdf-viewer__panel" id="panel-bibinfo" aria-labelledby="headline-bibinfo" '
        'data-pdf-viewer-target="panel"><div class="panel-header"><h2 class="h4" id="headline-bibinfo">'
        'Bibliographische Infos</h2></div><div class="panel-body | s-flow"><div><p class="h4">Ein Sammelband</p></div>'
        f'<dl class="grid gap-xs text-small">{book_dl}<div><dt>Verlag</dt><dd>Nomos, Baden-Baden</dd></div></dl>'
        '</div></div>'
        '<div class="pdf-viewer__panel" id="panel-info" aria-labelledby="headline-info" '
        'data-pdf-viewer-target="panel"><div class="panel-header"><h2 class="h4" id="headline-info">'
        'Kapitelinformationen</h2></div><div class="panel-body | s-flow"><div>'
        f'<p class="h4">{title}</p></div><hr><dl class="grid gap-xs text-small">{chapter_dl}'
        '<div><dt>ISBN-Print</dt><dd>978-3-0000-0000-0</dd></div></dl><hr>'
        '<dl class="s-flow"><dt>Kapitelvorschau:</dt><dd class="box theme-border text-small"><picture>'
        f'{preview}</picture></dd></dl></div></div></div></main></body></html>')


def _names(html):
    return [a["name"] for a in parse_page(html.encode(), "doi", URL)["authors"]]


def _parser(html):
    return NomosInlibra(BeautifulSoup(html, "lxml"))


def test_chapter_panel_authors_replace_the_books_editors():
    html = _page(chapter_authors=["Lena Beispiel"], book_people=["Paul Herausgeber", "Eva Herausgeberin"],
                 meta_authors=["Prof. Dr. Paul Herausgeber", "Prof. Dr. Eva Herausgeberin"])
    assert _names(html) == ["Lena Beispiel"]


def test_journal_issue_page_without_author_tags_gets_the_articles_authors():
    # The issue's meta tags carry no citation_author; the bibliographic panel lists everyone in the issue.
    html = _page(chapter_authors=["Jonas Muster"], book_people=["Anna Eins", "Jonas Muster", "Karl Drei"])
    out = parse_page(html.encode(), "doi", URL)
    assert [a["name"] for a in out["authors"]] == ["Jonas Muster"]
    assert out["authors"][0]["affiliations"] == []
    assert not out["authors"][0]["is_corresponding"]


def test_all_chapter_authors_in_page_order():
    names = ["Cora Erste", "Gerd Zweiter", "Mia Dritte", "Olaf Vierter"]
    html = _page(chapter_authors=names, meta_authors=["Book Author"])
    assert _names(html) == names


def test_english_panel_label():
    html = _page(chapter_authors=["Lena Beispiel", "Tom Example"], dt="Authors:", meta_authors=["Book Editor"])
    assert _names(html) == ["Lena Beispiel", "Tom Example"]


def test_panel_without_authors_is_left_to_the_meta_tags():
    # A monograph's chapter: the panel names nobody, the book's author tag stays what Parseland reads.
    html = _page(meta_authors=["Werner Buchautor"], book_people=["Werner Buchautor"])
    assert not _parser(html).authors_found()
    assert _names(html) == ["Werner Buchautor"]


def test_editors_in_the_chapter_panel_are_not_authors():
    html = _page(chapter_authors=["Paul Herausgeber"], dt="Herausgeber:innen:", meta_authors=["Paul Herausgeber"])
    assert not _parser(html).authors_found()


def test_preview_text_is_not_an_abstract():
    preview = "<p>" + "Die in die Jahre gekommene Richtlinie wurde im Juni 2021 abgelöst. " * 5 + "</p>"
    html = _page(chapter_authors=["Lena Beispiel"], preview=preview)
    assert _parser(html).parse()["abstract"] is None
    assert parse_page(html.encode(), "doi", URL)["abstract"] is None


def test_claims_the_platform_not_a_domain():
    html = _page(chapter_authors=["Lena Beispiel"])
    p = _parser(html)
    assert p.is_publisher_specific_parser() and p.authors_found()


CARD_URL = "https://doi.org/10.17104/9783406000000-58"


def _tag(name):
    q = name.split(" (")[0].replace(" ", "%20")
    return (f'<a class="pl-tag pl-tag--ghost pl-tooltip--tag" href="/?qms=1&amp;slocal=0&amp;page-search-location='
            f'eLibrary&amp;q=&amp;extSearch=1&amp;qtt=&amp;qa={q}&amp;qIdent=" data-tippy-content="{name}">'
            f'<span class="pl-tag__icon"></span><span>{name}</span></a>')


def _card_page(tags, topline="<i> 7. Ein Kapitel</i> in:", meta_authors=(), site="Beck eLibrary"):
    metas = "".join(f'<meta name="citation_author" content="{n}" />' for n in meta_authors)
    top = f'<div class="pl-card__topline">{topline}</div>' if topline else ""
    return (f'<html><head><meta property="og:title" content="{site}" />{metas}</head><body><main class="pl-main">'
            '<section><div class="pl-card pl-card--document js--tracking-document" data-trackingdoi="10.17104/1">'
            f'<div class="pl-card__information">{top}<h2 class="pl-card__headline">Ein Buch, Seite 58 - 65</h2>'
            '<div class="pl-card__tags"><div class="pl-tag__row">' + "".join(_tag(t) for t in tags) +
            '</div></div></div></div></section><h2>Zusammenfassung</h2><p>Das Buch beschreibt ...</p>'
            '</main></body></html>')


def test_older_elibrary_chapter_card_names_the_chapters_authors():
    # The older eLibrary chapter page (nomos-, beck-, tectum-elibrary.de): no citation tags, the card's person tags.
    html = _card_page(["Lena Beispiel", "Jonas Muster"])
    assert [a["name"] for a in parse_page(html.encode(), "doi", CARD_URL)["authors"]] == ["Lena Beispiel",
                                                                                         "Jonas Muster"]


def test_older_elibrary_card_editors_are_not_authors():
    html = _card_page(["Paul Herausgeber (Hrsg.)", "Eva Herausgeberin (ed.)"])
    assert not _parser(html).authors_found()
    assert parse_page(html.encode(), "doi", CARD_URL)["authors"] == []


def test_older_elibrary_book_card_is_not_claimed():
    # A book's own card (no "... in:" line): the book page also lists every chapter, so it is left to the meta tags.
    html = _card_page(["Lena Beispiel"], topline=None)
    assert not _parser(html).authors_found()


def test_older_elibrary_chapter_with_author_tags_is_left_to_them():
    # Older chapter cards carry the chapter's citation_author tag and the book's editors as card tags.
    html = _card_page(["Paul Herausgeber (Hrsg.)"], topline="<i>Lena Beispiel, Ein Kapitel</i> in:",
                      meta_authors=["Lena Beispiel"])
    assert not _parser(html).authors_found()
    assert [a["name"] for a in parse_page(html.encode(), "doi", CARD_URL)["authors"]] == ["Lena Beispiel"]


def test_other_sites_card_markup_is_not_claimed():
    # The same "pl-card" class names on another platform, without the eLibrary's person-search tags.
    html = _card_page([], site="Other Press").replace(
        '<div class="pl-tag__row">', '<div class="pl-tag__row"><a class="pl-tag" href="/authors/lena-beispiel">'
        '<span>Lena Beispiel</span></a>')
    p = _parser(html)
    assert not p.is_publisher_specific_parser()
    assert not p.authors_found()


def test_other_pdf_viewer_page_is_not_claimed():
    # Another site's PDF viewer with the same class name and an info panel, but not Inlibra's panel set.
    html = ('<html><head><meta name="citation_author" content="Someone Else" /></head><body>'
            '<main id="main" class="pdf-viewer"><div id="panel-info"><dl><dt>Authors:</dt>'
            '<dd><button>Lena Beispiel</button></dd></dl></div></main></body></html>')
    p = _parser(html)
    assert not p.is_publisher_specific_parser()
    assert not p.authors_found()
    assert _names(html) == ["Someone Else"]
