"""Corresponding marks the page does not make (oxjob #2239, phase 2, class corresponding-r2).

Each reader below marked an author the page marks nobody for, or a different person. Markup is cut from the stored
dev pages named in each test; every fix has the near case that must keep its mark.
"""
import json

from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.bmj import BMJ
from parseland_lib.publisher.parsers.elsevier_bv import ElsevierBV
from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.oxford import Oxford
from parseland_lib.publisher.parsers.parser import silverchair_corresponding_names


def _marked(authors):
    return [a["name"] if isinstance(a, dict) else a.name for a in authors
            if (a["is_corresponding"] if isinstance(a, dict) else a.is_corresponding)]


def _metas(names):
    return "".join(f'<meta name="citation_author" content="{n}">' for n in names)


# ---- the generic parser's starred byline: a legend's own star (Elsevier Pure portals) ----

def _pure(byline):
    names = ["Rosemarijn Looije", "Mark A. Neerincx", "Fokie Cnossen"]
    return (f"<html><head>{_metas(names)}</head><body><div class=\"rendering\"><ul class=\"relations persons\">"
            f"{byline}<div class=\"info-block\"><div class=\"info\"><sup>*</sup>"
            f"<span>Corresponding author for this work</span></div></div></ul></div></body></html>")


def _generic(html):
    return _marked(GenericPublisherParser(BeautifulSoup(html, "lxml")).parse()["authors"])


def test_legend_star_is_not_the_last_authors():
    # research.rug.nl, page 8c95709f: the legend follows the last author, who carries no star
    html = _pure('<li>Rosemarijn Looije<sup>*</sup></li><li>, Mark A. Neerincx</li>'
                 '<li>, <a rel="Person" class="link person"><span>Fokie Cnossen</span></a></li>')
    assert _generic(html) == ["Rosemarijn Looije"]


def test_starred_last_author_keeps_the_mark():
    html = _pure('<li>Rosemarijn Looije</li><li>, Mark A. Neerincx</li>'
                 '<li>, <a rel="Person" class="link person"><span>Fokie Cnossen</span></a><sup>*</sup></li>')
    assert _generic(html) == ["Fokie Cnossen"]


def test_first_and_last_author_both_starred():
    html = _pure('<li>Rosemarijn Looije<sup>*</sup></li><li>, Mark A. Neerincx</li>'
                 '<li>, <span>Fokie Cnossen</span><sup>*</sup></li>')
    assert _generic(html) == ["Rosemarijn Looije", "Fokie Cnossen"]


def test_lone_star_between_a_name_and_the_label_is_that_names():
    # no earlier star for a legend to explain: the one star belongs to the name before it
    html = (f"<html><head>{_metas(['Ann Lee', 'Bo Chen'])}</head><body>"
            f"<p class=\"authors\">Ann Lee, Bo Chen* Corresponding author: bo@example.org</p></body></html>")
    assert _generic(html) == ["Bo Chen"]


# ---- the generic parser's correspondence block: which author a block names ----

SPRINGER_CHAPTER = """<html><head>
<meta name="citation_author" content="Lee, Wen Si"/><meta name="citation_author" content="Aziz, Hamidi Abdul"/>
<meta name="citation_author" content="Wang, Lawrence K."/><meta name="citation_author" content="Wang, Mu-Hao Sung"/>
<meta name="citation_author" content="Hung, Yung-Tse"/></head><body>
<section><div class="c-article-section" id="author-information-section"><h2>Author information</h2>
<div class="c-article-section__content"><h3>Authors and Affiliations</h3><ol>
<li><p>School of Civil Engineering, Universiti Sains Malaysia</p><p>Wen Si Lee</p></li>
<li><p>Solid Waste Management Cluster, Universiti Sains Malaysia</p><p>Hamidi Abdul Aziz</p></li>
<li><p>Lenox Institute of Water Technology, Latham, NY, USA</p><p>Lawrence K. Wang &amp; Mu-Hao Sung Wang</p></li>
<li><p>Cleveland State University, Strongsville, OH, USA</p><p>Yung-Tse Hung</p></li></ol>
<h3 class="c-article__sub-heading" id="corresponding-author">Corresponding author</h3>
<p id="corresponding-author-list">Correspondence to <a id="corresp-c1" href="mailto:c@usm.my">Hamidi Abdul Aziz </a>.</p>
</div></div></section></body></html>"""


def test_block_naming_every_author_given_name_first_marks_the_one_the_note_names():
    # link.springer.com chapter read as a record page (fe325451): "Lawrence K. Wang & Mu-Hao Sung Wang" spelled
    # the tag "Wang, Mu-Hao Sung" and no other author's, so she took the mark the note gives Hamidi Abdul Aziz
    assert _generic(SPRINGER_CHAPTER) == ["Aziz, Hamidi Abdul"]


def test_citation_line_with_the_label_on_the_other_author_marks_no_one():
    # research.tue.nl (e4881cbd): only "Harting, Jens" matched the citation line, whose label is Ronsin's
    html = (f"<html><head>{_metas(['Olivier J.J. Ronsin', 'Jens Harting'])}</head><body><div class=\"rendering\">"
            f"<span><strong>Phase-Field Simulations.</strong></span> / Ronsin, Olivier J.J. (Corresponding author); "
            f"Harting, Jens. <br/>In: Advanced Theory and Simulations</div></body></html>")
    assert _generic(html) == []


def test_two_word_name_still_matches_in_either_order():
    html = (f"<html><head>{_metas(['Flood, Julie', 'Marsh, Ian'])}</head><body>"
            f"<p>Correspondence to Julie Flood, Dublin</p></body></html>")
    assert _generic(html) == ["Flood, Julie"]


# ---- HighWire: a sole author's e-mail tag whose address the page does not print ----

HIGHWIRE = '<script src="/sites/all/modules/highwire/highwire/js/highwire.js"></script>'
SPRINGERPUB = "https://connect.springerpub.com/content/sgrjcep/15/1/146"


def _highwire(authors, body=""):
    metas = "".join(f'<meta name="citation_author" content="{n}"/>'
                    + (f'<meta name="citation_author_email" content="{e}"/>' if e else "") for n, e in authors)
    html = (f"<html><head>{HIGHWIRE}{metas}<meta name=\"citation_title\" content=\"A title\"/></head>"
            f"<body>{body}</body></html>")
    return _marked(parse_page(html.encode(), "doi", SPRINGERPUB)["authors"])


def test_highwire_sole_author_email_tag_alone_marks_no_one():
    # connect.springerpub.com (20aece80): the address is in the tag only; the byline shows a name
    assert _highwire([("Daniel B. Wright", "d@example.com")], "<h1>A title</h1><p>Wright, Daniel B.</p>") == []


def test_highwire_sole_author_email_tag_with_the_address_printed_keeps_the_mark():
    # ccjm.org (070f5451): the author's pop-up prints "For correspondence: <address>"; older pages disguise it
    popup = ('<li class="author-corresp-email-link last"><span>For correspondence: '
             '<a href="mailto:waliah@example.org">waliah@example.org</a></span></li>')
    assert _highwire([("Harneet K. Walia", "waliah@example.org")], popup) == ["Harneet K. Walia"]
    disguised = '<li class="fn">E-mail: waliah{at}example.org</li>'
    assert _highwire([("Harneet K. Walia", "waliah@example.org")], disguised) == ["Harneet K. Walia"]


def test_highwire_email_tag_on_one_of_several_authors_keeps_the_mark():
    # the tag singles one author out (ERS congress abstracts, where the gate's corpus counts it): unchanged
    assert _highwire([("Simon Høj", "s@example.dk"), ("Vibeke Backer", None)]) == ["Simon Høj"]


# ---- Silverchair author cards: what the correspondence block holds ----

def _card(name, note="", link=""):
    block = f'<div class="info-author-correspondence">{note}</div>' if note else ""
    return (f'<div class="al-author-name"><a class="linked-name js-linked-name">{name}</a>'
            f'<div class="al-author-info-wrap"><div class="info-card-author"><div class="name-role-wrap">'
            f'<div class="info-card-name">{name} <span class="info-card-footnote">{link}</span></div></div>'
            f'<div class="info-card-affilitation"><div class="aff">Oregon State University</div></div>{block}'
            f'</div></div></div>')


CF_EMAIL = ('<div content-id="cor1">Email: <a href="/cdn-cgi/l/email-protection#17"><span class="__cf_email__">'
            '[email&#160;protected]</span></a></div>')
XREF_CORRESP = '<a reveal-id="cor1" data-open="cor1" class="link link-ref link-reveal xref-corresp"></a>'
XREF_DEFAULT = '<a reveal-id="c1" data-open="c1" class="link link-ref link-reveal xref-default"></a>'


def _silverchair(*cards):
    return silverchair_corresponding_names(BeautifulSoup(f"<html><body>{''.join(cards)}</body></html>", "lxml"))


def test_silverchair_email_on_every_author_marks_no_one():
    # asmedigitalcollection.asme.org (71c4efac): each card's block holds that author's address and nothing else
    assert _silverchair(_card("Cole Jetton", CF_EMAIL), _card("Matthew Campbell", CF_EMAIL),
                        _card("Christopher Hoyle", CF_EMAIL)) == []


def test_silverchair_email_on_every_author_through_parse_page():
    names = ["Jetton, Cole", "Campbell, Matthew", "Hoyle, Christopher"]
    cards = _card("Cole Jetton", CF_EMAIL) + _card("Matthew Campbell", CF_EMAIL) + _card("Christopher Hoyle", CF_EMAIL)
    html = (f"<html><head>{_metas(names)}<meta name=\"citation_title\" content=\"Bayesian optimization\"></head>"
            f"<body>{cards}</body></html>")
    url = "https://asmedigitalcollection.asme.org/mechanicaldesign/article-abstract/doi/10.1115/1.4070429/1228334"
    assert _marked(parse_page(html.encode(), "doi", url)["authors"]) == []


def test_silverchair_labelled_note_among_emails_marks_its_author():
    # ASME (d79907eb): "1 Corresponding author. Email: ..." on one card, a bare address on the others
    labelled = '<div content-id="cor1">1 Corresponding author. Email: [email&#160;protected]</div>'
    assert _silverchair(_card("Tiezhou Wu", CF_EMAIL), _card("Feng Xu", labelled),
                        _card("Siyun Xu", CF_EMAIL)) == ["Feng Xu"]


def test_silverchair_email_on_some_authors_marks_them():
    # pubs.geoscienceworld.org (a2c6ed38), karger.com: the address singles two of five authors out
    assert _silverchair(_card("Qiuye Yang"), _card("Yan Zhang", "evezhangyan@mail.iggcas.ac.cn"),
                        _card("Li-Yun Fu", "* E-mail: lfu@upc.edu.cn"), _card("Yuchuan Ma")) == ["Yan Zhang", "Li-Yun Fu"]


def test_silverchair_sole_author_email_needs_the_correspondence_link():
    # academic.oup.com book reviews (d47ad544, 903163e7): an address behind a plain footnote link is no mark;
    # read.dukeupress.edu (824f75a8): the same address behind the "Corresponding author note" link is
    assert _silverchair(_card("Jeremy Strong", CF_EMAIL, XREF_DEFAULT)) == []
    assert _silverchair(_card("Rebecca M. Herzig", CF_EMAIL, XREF_CORRESP)) == ["Rebecca M. Herzig"]


def test_silverchair_correspondence_notes_keep_their_marks():
    notes = ["Correspondence to: Tyler McKechnie, Division of General Surgery, McMaster University",
             "a) Author to whom correspondence should be addressed: [email&#160;protected]",
             "Sanjeev Swami can be contacted at: [email&#160;protected]",
             "Present address and correspondence: Jane Roe, Leiden University, jane@example.nl"]
    for note in notes:
        assert _silverchair(_card("Ann Lee", note)) == ["Ann Lee"], note
    assert _silverchair(_card("Ann Lee", "Corresponding author. ann@example.org"),
                        _card("Bo Chen", "Corresponding author. bo@example.org")) == ["Ann Lee", "Bo Chen"]


def _oxford(*cards):
    html = (f'<html><head><meta property="og:url" content="https://academic.oup.com/brain/article/143/3/976/5753887">'
            f'</head><body><div class="at-ArticleAuthors">{"".join(cards)}</div></body></html>')
    return _marked(Oxford(BeautifulSoup(html, "lxml")).parse()["authors"])


def test_oxford_present_address_is_not_a_correspondence_mark():
    # academic.oup.com/brain (121f1772): Skouras's block is his present address, Molinuevo's the correspondence note
    assert _oxford(
        _card("Stavros Skouras", "Present address: Department of Biological and Medical Psychology, University of "
                                 "Bergen, Bergen, Norway"),
        _card("Jordi Torner"),
        _card("José L Molinuevo", "Correspondence to: José Luis Molinuevo Guix Scientific Director, Barcelonaβeta "
                                  'Brain Research Center E-mail: <a href="mailto:j@example.org">j@example.org</a>'),
    ) == ["José L Molinuevo"]


def test_oxford_sole_author_with_only_an_address_is_not_marked():
    assert _oxford(_card("Todd Davis", '<div class="addr-line"><a href="mailto:t@psu.edu">t@psu.edu</a></div>')) == []
    assert _oxford(_card("Todd Davis", "Corresponding author. E-mail: t@psu.edu")) == ["Todd Davis"]


# ---- BMJ: a sole author is not thereby corresponding ----

def _bmj(body):
    html = (f'<html><head><meta property="og:url" content="https://www.bmj.com/content/384/bmj.q47">'
            f'<meta name="citation_author" content="Pritam Biswas"/></head><body>{body}</body></html>')
    return _marked(BMJ(BeautifulSoup(html, "lxml")).parse()["authors"])


BMJ_BYLINE = '<ol class="contributor-list"><li class="last" id="contrib-1"><span class="name">Pritam Biswas</span></li></ol>'


def test_bmj_sole_author_without_a_note_is_not_marked():
    # bmj.com obituary (1d85c845): a byline of one name, no correspondence note, no address
    assert _bmj(BMJ_BYLINE + "<p>Akhil Chandra Biswas, consultant paediatrician, has sadly died.</p>") == []


def test_bmj_sole_author_with_a_correspondence_note_keeps_the_mark():
    note = '<ul><li class="corresp">Correspondence to: P Biswas, Royal College of Physicians, London</li></ul>'
    assert _bmj(BMJ_BYLINE + note) == ["Pritam Biswas"]


# ---- ScienceDirect (Elsevier BV parser): a surname two authors share ----

def _sd_author(given, surname, icon=False):
    svg = '<svg class="icon icon-person react-xocs-author-icon" title="Correspondence author icon"></svg>' if icon else ""
    return (f'<button data-xocs-content-type="author"><span class="button-link-text">'
            f'<span class="react-xocs-alternative-link"><span class="given-name">{given}</span> '
            f'<span class="text surname">{surname}</span></span>{svg}</span></button>')


def _sd_state(authors):
    entries = [{"#name": "author", "$$": [{"#name": "given-name", "_": g}, {"#name": "surname", "_": s},
                                          {"#name": "cross-ref", "$": {"refid": "af005"}},
                                          *([{"#name": "cross-ref", "$": {"refid": "cor1"}}] if cor else [])]}
               for g, s, cor in authors]
    return json.dumps({"authors": {"content": [{"#name": "author-group", "$$": entries}],
                                   "affiliations": {"af005": {"$$": [{"#name": "textfn", "_": "Yonsei University"}]}}}})


def _sd(dom, state):
    html = (f'<html><body><div class="author-group" id="author-group">{dom}</div>'
            f'<dl class="affiliation"><dt></dt><dd>Yonsei University</dd></dl>'
            f'<script>window.__PRELOADED_STATE__ = {state};</script></body></html>')
    return _marked(ElsevierBV(BeautifulSoup(html, "lxml")).parse()["authors"])


def test_sciencedirect_shared_surname_does_not_pass_the_mark_on():
    # 10.1016/j.cej.2025.160537 (a4265289): Dongwook Lee is corresponding, Sangyup Lee is not
    dom = _sd_author("Eunsil", "Kim") + _sd_author("Sangyup", "Lee") + _sd_author("Jinwon", "Park") + _sd_author(
        "Dongwook", "Lee", icon=True)
    state = _sd_state([("Eunsil", "Kim", False), ("Sangyup", "Lee", False), ("Jinwon", "Park", True),
                       ("Dongwook", "Lee", True)])
    assert _sd(dom, state) == ["Jinwon Park", "Dongwook Lee"]


def test_sciencedirect_shared_surname_matches_on_the_full_name():
    # no icon in the byline: the page state alone marks the first of the two Lees, by full name
    dom = _sd_author("Sangyup", "Lee") + _sd_author("Jinwon", "Park") + _sd_author("Dongwook", "Lee")
    state = _sd_state([("Sangyup", "Lee", True), ("Jinwon", "Park", False), ("Dongwook", "Lee", False)])
    assert _sd(dom, state) == ["Sangyup Lee"]


def test_sciencedirect_unshared_surname_still_reads_the_page_state():
    dom = _sd_author("Eunsil", "Kim") + _sd_author("Jinwon", "Park")
    state = _sd_state([("Eunsil", "Kim", False), ("Jinwon", "Park", True)])
    assert _sd(dom, state) == ["Jinwon Park"]


# ---- Copernicus: a comment's page carries the discussed preprint's marks ----

def test_copernicus_comment_page_takes_no_marks_from_any_reader():
    # egusphere ...#RC2 (afa56d15): the meta-tag parser reads the preprint's pop-up as well as the Copernicus
    # reader, which is switched off on these pages
    names = ["Narivelo, Herizo", "do Nascimento, Thiago V. M.", "Huebler, Gunther"]
    body = ('<div class="authors-full"><span>Herizo Narivelo</span>, <span>Thiago V. M. do Nascimento</span>, and '
            '<span>Gunther Huebler</span></div><div class="modal"><div class="modal-header">'
            '<h5>Gunther Huebler</h5></div><div class="modal-body"><div>CORRESPONDING AUTHOR</div>'
            '<div><a href="mailto:g@example.org">g@example.org</a></div></div></div>')
    html = (f'<html><head><link rel="preconnect" href="https://contentmanager.copernicus.org/"/>{_metas(names)}'
            f'<meta name="citation_title" content="A preprint"></head><body>{body}</body></html>').encode()
    page = "https://egusphere.copernicus.org/preprints/2025/egusphere-2025-4435/"
    assert _marked(parse_page(html, "doi", page + "#RC2")["authors"]) == []
    assert _marked(parse_page(html, "doi", page)["authors"]) == ["Huebler, Gunther"]


# ---- Elsevier BV parser: an address every author has ----

def _portal_card(name, label=False, contact=True):
    icon = '<i aria-hidden="true" class="icon-gizmo-person faded"></i>' if label else ""
    group = ('<span class="article-header__info__group__label">Correspondence</span>'
             '<div class="article-header__info__sub-label">Corresponding author.</div>') if label else ""
    link = ('<div class="article-header__info__social"><a class="article-header__info__email default" '
            f'href="/cdn-cgi/l/email-protection#6e" title="Send email to {name}"><span> Contact </span></a></div>'
            ) if contact else ""
    return (f'<li class="loa__item author"><div class="dropBlock article-header__info">'
            f'<a href="#" class="loa__item__name article-header__info__ctrl">{name}{icon}</a>'
            f'<div class="article-header__info__holder">{group}<div class="article-header__info__body">{link}</div>'
            f'</div></div></li>')


def _portal(*cards):
    html = f'<html><body><ul class="loa">{"".join(cards)}</ul></body></html>'
    return _marked(ElsevierBV(BeautifulSoup(html, "lxml")).parse()["authors"])


def test_elsevier_portal_contact_link_is_not_a_mark_beside_a_labelled_author():
    # 10.1016/j.fsigen.2016.11.007 (99b00bfa): every card has the "Contact" link, one says "Correspondence"
    assert _portal(_portal_card("Jerry Hoogenboom", label=True), _portal_card("Kristiaan J. van der Gaag"),
                   _portal_card("Titia Sijen")) == ["Jerry Hoogenboom"]


def test_elsevier_portal_contact_link_marks_when_no_author_is_labelled():
    assert _portal(_portal_card("Ann Lee"), _portal_card("Bo Chen", contact=False)) == ["Ann Lee"]


def _email_tags(authors):
    metas = "".join(f'<meta name="citation_author" content="{n}"/>'
                    + (f'<meta name="citation_author_email" content="{e}"/>' if e else "") for n, e in authors)
    html = f"<html><head>{metas}</head><body></body></html>"
    return _marked(ElsevierBV(BeautifulSoup(html, "lxml")).parse()["authors"])


def test_elsevier_email_tag_on_every_author_marks_no_one():
    # link.springer.com (65fd85c1): Springer writes a tag per author; the byline's own mark decides in parse_page
    assert _email_tags([("Xue, Ru", "r@example.com"), ("Luo, Hongbing", "l@example.com"),
                        ("Chen, Wei", "w@example.com")]) == []


def test_elsevier_email_tag_on_some_authors_keeps_the_mark():
    assert _email_tags([("Xue, Ru", None), ("Luo, Hongbing", "l@example.com"), ("Chen, Wei", None)]) == ["Luo, Hongbing"]
    assert _email_tags([("Luo, Hongbing", "l@example.com")]) == ["Luo, Hongbing"]


def _sd_emails(authors):
    """authors: (given, surname, has an e-address in the page state); no correspondence cross-ref, no icon."""
    entries = [{"#name": "author", "$$": [{"#name": "given-name", "_": g}, {"#name": "surname", "_": s},
                                          *([{"#name": "e-address", "_": f"{s.lower()}@example.org"}] if e else [])]}
               for g, s, e in authors]
    state = json.dumps({"authors": {"content": [{"#name": "author-group", "$$": entries}], "affiliations": {}}})
    return _sd("".join(_sd_author(g, s) for g, s, _ in authors), state)


def test_sciencedirect_address_for_every_author_marks_no_one():
    # 10.1016/j.infsof.2011.01.010 (2db65431), 10.1016/j.energy.2026.142393 (680e4f21): no correspondence
    # footnote, an address in the page state for both authors / the sole author
    assert _sd_emails([("Gabriela", "Avram", True), ("Volker", "Wulf", True)]) == []
    assert _sd_emails([("Badr Saad", "Alotaibi", True)]) == []


def test_sciencedirect_address_for_one_of_two_authors_keeps_the_mark():
    assert _sd_emails([("Gabriela", "Avram", False), ("Volker", "Wulf", True)]) == ["Volker Wulf"]
