"""Corresponding authors on Optica and IOP article pages (oxjob #2217).

Markup is cut down from stored pages (#2146's seeded sample, 10 Nov 2026; #2217 EXPLORE § 1).

Optica: the Author Affiliations box puts a symbol on byline names (`<sup>*</sup>`) and explains it in a note,
'<sup>*</sup>Corresponding author: x@y'. Parseland read only the meta tags, so it marked no one, or guessed from an
e-mail in an affiliation line.

IOP: the author list is a `dl` of `dt.author-list__name` + `dd` cards. The parser read the whole `dl` as each author's
scope, so one singular 'Author to whom any correspondence should be addressed' note marked every author, and the plural
'Authors to whom ...' note marked no one.
"""
from parseland_lib.parse import parse_page

OPTICA_URL = "https://opg.optica.org/ol/abstract.cfm?uri=ol-38-19-3862"


def _corr(html, url):
    return [a["name"] for a in parse_page(html.encode(), "doi", url)["authors"] if a["is_corresponding"]]


def _optica_page(names, byline, notes, affs=("Utsunomiya University, Japan",)):
    metas = "".join(f'<meta name="citation_author" content="{n}"/>'
                    f'<meta name="citation_author_institution" content="{affs[0]}"/>' for n in names)
    affs_html = "".join(f"<p><em><sup>{i + 1}</sup>{a}</em></p>" for i, a in enumerate(affs))
    return (f'<html><head><meta property="og:url" content="{OPTICA_URL}"/>{metas}'
            f'<meta name="citation_title" content="A title"/></head><body>'
            f'<div class="article-author-affiliations dropdown-menu" id="authorAffiliations">'
            f'<h5>Author Affiliations</h5><p><strong>{byline}</strong></p>{affs_html}{notes}</div></body></html>')


OPTICA_NAMES = ["Manabu Hakko", "Tomohiro Kiire", "Yoshio Hayasaki"]
OPTICA_BYLINE = ("\nManabu Hakko,<sup>1,</sup><sup>2,</sup><sup>*</sup>\nTomohiro Kiire,<sup>1</sup>\n"
                 "and Yoshio Hayasaki<sup>1</sup>\n")


def test_optica_starred_name_with_corresponding_note():
    notes = '<p>\n<sup>*</sup>Corresponding author: <a href="mailto:hakko@opt.example.jp">hakko@opt.example.jp</a>\n</p>'
    assert _corr(_optica_page(OPTICA_NAMES, OPTICA_BYLINE, notes), OPTICA_URL) == ["Manabu Hakko"]


def test_optica_note_outranks_email_in_an_affiliation_line():
    byline = "Xiaoqiang Chen,<sup>1</sup>\nShaoying Ke,<sup>2,</sup><sup>3</sup>\nand Songyan Chen<sup>1,</sup><sup>*</sup>"
    names = ["Xiaoqiang Chen", "Shaoying Ke", "Songyan Chen"]
    page = _optica_page(names, byline,
                        '<p><sup>†</sup>These authors contributed equally to this work.</p>'
                        '<p><sup>*</sup>Corresponding author: <a href="mailto:sy@xmu.example.cn">sy@xmu.example.cn</a></p>')
    page = page.replace('<meta name="citation_author" content="Shaoying Ke"/>',
                        '<meta name="citation_author" content="Shaoying Ke"/>'
                        '<meta name="citation_author_institution" content="syke@mnnu.example.cn"/>')
    assert _corr(page, OPTICA_URL) == ["Songyan Chen"]


def test_optica_unsymbolled_note_names_the_author_by_surname():
    byline = "Harry L. Graber,<sup>1</sup>\nRaphael Aronson,<sup>2</sup>\nand Randall L. Barbour<sup>3</sup>"
    names = ["Harry L. Graber", "Raphael Aronson", "Randall L. Barbour"]
    notes = ("<p>Corresponding author: Correspondence should be addressed to R. L. Barbour, SUNY Health Science "
             "Center at Brooklyn, Box 25, Brooklyn, New York 11203.</p>")
    assert _corr(_optica_page(names, byline, notes), OPTICA_URL) == ["Randall L. Barbour"]


def test_optica_without_a_note_keeps_the_old_reading():
    assert _corr(_optica_page(OPTICA_NAMES, OPTICA_BYLINE, ""), OPTICA_URL) == []


def test_optica_email_only_note_on_every_author_marks_no_one():
    byline = "Ann Bee,<sup>*</sup>\nand Cy Dee<sup>*</sup>"
    notes = '<p><sup>*</sup><a href="mailto:x@example.org">x@example.org</a></p>'
    assert _corr(_optica_page(["Ann Bee", "Cy Dee"], byline, notes), OPTICA_URL) == []


IOP_URL = "https://iopscience.iop.org/article/10.1088/2053-1591/aab8ec"


def _card(name, note=None, email=None):
    dd = '<p class="author-list__heading">AFFILIATIONS</p><div class="mb-1"><p class="mb-05">Some University</p></div>'
    if email:
        dd += (f'<p class="author-list__heading">EMAIL</p><div class="mb-1"><p class="mb-05">'
               f'<a href="mailto:{email}">{email}</a></p></div>')
    if note:
        dd += f'<h2 class="author-list__heading">Author notes</h2><div class="mb-1"><p class="mb-05">{note}</p></div>'
    return f'<dt class="author-list__name"><span itemprop="name">{name}</span></dt><dd class="mb-15 mt-1">{dd}</dd>'


def _iop_page(names, cards):
    metas = "".join(f'<meta name="citation_author" content="{n}"/>' for n in names)
    return (f'<html><head><link rel="canonical" href="{IOP_URL}"/>{metas}'
            f'<meta name="citation_title" content="A title"/></head><body>'
            f'<div id="nav-dropdown-authors"><dl class="overflow-y">{"".join(cards)}'
            f'<div class="author-list__notes"><h2 class="replica-h4">Notes</h2></div></dl></div></body></html>')


IOP_NAMES = ["Yuanpeng Wu", "Meiling Guo", "Dan Liu", "Weiwei Lei"]


def test_iop_plural_note_marks_each_noted_author():
    note = "Authors to whom any correspondence should be addressed."
    cards = [_card("Yuanpeng Wu", note, "ypwu@example.cn"), _card("Meiling Guo"),
             _card("Dan Liu", note, "dan.liu@example.au"), _card("Weiwei Lei", note, "weiwei.lei@example.au")]
    assert _corr(_iop_page(IOP_NAMES, cards), IOP_URL) == ["Yuanpeng Wu", "Dan Liu", "Weiwei Lei"]


def test_iop_singular_note_marks_only_its_author():
    names = ["M. Minissale", "C. Pardanaud", "R. Bisson"]
    cards = [_card("M. Minissale", "Author to whom any correspondence should be addressed.", "marco@example.fr"),
             _card("C. Pardanaud"), _card("R. Bisson")]
    assert _corr(_iop_page(names, cards), IOP_URL) == ["M. Minissale"]


def test_iop_card_name_with_native_script_matches_the_meta_name():
    names = ["Xi-Ling Xue", "Bo Li"]
    cards = [_card("Xi-Ling Xue (薛希玲)", "Author to whom any correspondence should be addressed."), _card("Bo Li")]
    assert _corr(_iop_page(names, cards), IOP_URL) == ["Xi-Ling Xue"]


def test_iop_div_layout_note_marks_its_author():
    """The `p.author-list__name` layout: each author's card is its own `div` (2024-2025 pages)."""
    def block(name, note=""):
        notes = (f'<h2 class="author-list__heading">Author notes</h2><div class="mb-1"><p class="mb-05"><sup>*</sup> '
                 f'{note}</p></div>') if note else ""
        return (f'<div><div class="mb-15 mt-05"><p class="author-list__name"><span itemprop="name">{name}</span></p>'
                f'<p class="author-list__heading">AFFILIATIONS</p><div class="mb-1"><p class="mb-05">A University</p>'
                f'</div>{notes}</div></div>')
    names = ["Matthew Grimley", "Gabriel Chan"]
    page = (f'<html><head><link rel="canonical" href="{IOP_URL}"/>'
            + "".join(f'<meta name="citation_author" content="{n}"/>' for n in names)
            + '</head><body><div class="overflow-y" data-toolbar-container="authors">'
            + block("Matthew Grimley", "Author to whom any correspondence should be addressed.") + block("Gabriel Chan")
            + '<div class="author-list__notes"><h2 class="replica-h4">Notes</h2></div></div></body></html>')
    assert _corr(page, IOP_URL) == ["Matthew Grimley"]
