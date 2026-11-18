"""Corresponding authors on PubMed Central article pages, pmc.ncbi.nlm.nih.gov (oxjob #2239, round 8).

Markup is cut down from stored PMC pages in the loop's check1 and dev draws. The byline gives each author a link, a
hidden pop-up and then ``<sup>`` labels (affiliation numbers or letters, and a symbol); "Author information" holds the
footnotes, each opened by its symbol. The meta-tag parser that wins these pages read neither, and marked no one.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.pmc import pmc_corresponding_names

URL = "https://pmc.ncbi.nlm.nih.gov/articles/PMC13347837/"


def _page(authors, notes, affs=("1", "2"), pmc=True, extra_byline=""):
    """authors: [(name, [sup labels])]; notes: [(sup symbol or None, footnote text)]"""
    head = '<meta name="ncbi_db" content="pmc">' if pmc else ""
    metas = "".join(f'<meta name="citation_author" content="{name}">' for name, _ in authors)
    byline = []
    for i, (name, marks) in enumerate(authors, 1):
        sups = "".join(f"<sup>{m}{',' if j < len(marks) - 1 else ''}</sup>" for j, m in enumerate(marks))
        byline.append(
            f'<a href="https://pubmed.ncbi.nlm.nih.gov/?term=x" class="usa-link" aria-describedby="id{i}">'
            f'<span class="name western">{name}</span></a><div hidden="hidden" id="id{i}"><h3>{name}</h3>'
            f'<div class="p"><sup>1</sup> Some University</div></div>\n{sups}')
    aff_divs = "".join(f'<div id="aff{i}"><sup>{label}</sup> Department {i}, Some University</div>'
                       for i, label in enumerate(affs, 1))
    fns = "".join(f'<div class="fn" id="fn{i}"><sup>{sym}</sup><p class="display-inline">{text}</p></div>' if sym
                  else f'<div class="fn" id="fn{i}"><p>{text}</p></div>' for i, (sym, text) in enumerate(notes))
    return (f'<html><head>{head}<meta name="citation_title" content="A paper">{metas}</head><body>'
            f'<section class="front-matter"><div class="ameta p"><hgroup><h1>A paper</h1></hgroup>'
            f'<div class="cg p">{", ".join(byline)}{extra_byline}</div>'
            f'<div class="cg p">Editor: <span class="name western">Ed Itor</span><sup>1</sup></div>'
            f'<div class="d-panels"><div id="aip_a" class="d-panel p">{aff_divs}'
            f'<div class="author-notes p">{fns}</div></div></div></div></section></body></html>')


def _marked(html):
    return [a["name"] for a in parse_page(html.encode(), "pmh", URL)["authors"] if a["is_corresponding"]]


def _flags(html):
    return [a["is_corresponding"] for a in parse_page(html.encode(), "pmh", URL)["authors"]]


THREE = ["Yaowapa Puanglai", "Anongnard Kasorn", "Fabien Loison"]


def test_envelope_on_the_byline_marks_that_author():
    html = _page([(THREE[0], ["1"]), (THREE[1], ["2"]), (THREE[2], ["1", "✉"])], [("✉", "Corresponding author.")])
    assert pmc_corresponding_names(BeautifulSoup(html, "lxml")) == ["Fabien Loison"]
    assert _flags(html) == [False, False, True]


def test_star_keyed_to_a_correspondence_footnote():
    html = _page([(THREE[0], ["a"]), (THREE[1], ["b"]), (THREE[2], ["a", "*"])],
                 [("*", "<strong>CONTACT</strong> Fabien Loison <span>fabien@example.org</span> Bangkok")],
                 affs=("a", "b"))
    assert _marked(html) == ["Fabien Loison"]


def test_star_in_the_text_after_pmcs_envelope_frontiers_style():
    # Frontiers' "*Correspondence:" footnote: PMC prints its ✉ first, the byline carries the publisher's "*"
    html = _page([(THREE[0], ["1", "#"]), (THREE[1], ["2", "#"]), (THREE[2], ["1", "*"])],
                 [(None, "Edited by: Some Editor, Some University"),
                  ("✉", "*Correspondence: Fabien Loison <span>fabien@example.org</span>"),
                  ("#", "Contributed equally.")])
    assert _marked(html) == ["Fabien Loison"]


def test_two_corresponding_authors():
    html = _page([(THREE[0], ["1", "✉"]), (THREE[1], ["2"]), (THREE[2], ["1", "✉"])],
                 [("✉", "Corresponding author.")])
    assert _marked(html) == ["Yaowapa Puanglai", "Fabien Loison"]


def test_starred_email_footnote_on_one_author():
    html = _page([(THREE[0], ["1"]), (THREE[1], ["2"]), (THREE[2], ["1", "*"])],
                 [("*", "Email: <span>nakano@example.ac.jp</span>.")])
    assert _marked(html) == ["Fabien Loison"]


def test_footnote_naming_the_author_without_a_byline_mark():
    html = _page([("Dana Peralta", ["1"]), ("Nikhita Nanduri", ["2"]), ("Monica E Lemmon", ["1"])],
                 [("✉", "Address correspondence to: Dana Peralta, MD. DUMC Box 102509, Durham. "
                        "<span>dana.peralta@example.edu</span>")])
    assert _marked(html) == ["Dana Peralta"]


def test_footnote_name_with_punctuated_initial():
    html = _page([("Lauren L Agoubi", ["1", "2"]), ("Beth Ann Reimel", ["1"])],
                 [("✉", "<strong>Corresponding Author/Address for Reprints:</strong> Lauren L. Agoubi, MD, MA, "
                        "Seattle, <span>lagoubi@example.edu</span>")])
    assert _marked(html) == ["Lauren L Agoubi"]


def test_footnote_name_without_the_bylines_middle_initial():
    html = _page([("Melinda L Furer", ["1"]), ("Siyuan Huang", ["2"]), ("Joshua M Smyth", ["3"])],
                 [(None, "Correspondence concerning this article should be addressed to Melinda Furer, C-128 I Smith "
                         "Building, Altoona, PA 16601, USA. mla233@example.edu")])
    assert _marked(html) == ["Melinda L Furer"]


def test_footnote_name_without_initials_that_two_authors_share_marks_no_one():
    html = _page([("Jun X Li", ["1"]), ("Jun Y Li", ["2"]), ("Joshua M Smyth", ["3"])],
                 [("✉", "Correspondence: Jun Li, Some University. jun@example.edu")])
    assert _flags(html) == [None, None, None]


def test_byline_mark_and_a_footnote_naming_another_author_both_count():
    # the byline's ✉ is on one author, the correspondence footnote names another: the page marks both
    html = _page([("Jan Poszepczyński", ["1"]), ("Michał Pietrusiński", ["1"]), ("Maciej Borowiec", ["1", "✉"])],
                 [("✉", "Corresponding author: Jan Poszepczyński janek@example.pl"),
                  (None, "Cite this article as: Poszepczyński J, Pietrusiński M, Borowiec M.")])
    assert _marked(html) == ["Jan Poszepczyński", "Maciej Borowiec"]


def test_digit_symbol_when_affiliations_use_letters():
    # PNAS: affiliations a, b; the correspondence footnote is "1"
    html = _page([("Benjamin Mayro", ["a"]), ("Ann Marie Pendergast", ["a", "1"])],
                 [("1", "To whom correspondence may be addressed. Email: <span>ann@example.edu</span>."),
                  (None, "Edited by Stephen Goff, Columbia University")], affs=("a", "b"))
    assert _marked(html) == ["Ann Marie Pendergast"]


def test_symbol_that_is_also_an_affiliation_label_marks_no_one():
    html = _page([("Benjamin Mayro", ["1"]), ("Ann Marie Pendergast", ["1"])],
                 [("1", "To whom correspondence may be addressed. Email: <span>someone@example.edu</span>.")])
    assert _flags(html) == [None, None]


def test_contributed_equally_and_correspondent_wording_mark_no_one():
    html = _page([(THREE[0], ["1", "†"]), (THREE[1], ["2", "†"]), (THREE[2], ["1"])],
                 [("†", "These authors had equal contribution to the first and correspondent authors.")])
    assert _flags(html) == [None, None, None]


def test_symbol_used_for_equal_contribution_too_marks_no_one():
    html = _page([(THREE[0], ["1", "*"]), (THREE[1], ["2", "*"]), (THREE[2], ["1", "✉"])],
                 [("✉", "Correspondence: Fabien Loison, fabien@example.org"),
                  ("*", "These authors contributed equally to this work")])
    assert _marked(html) == ["Fabien Loison"]


def test_email_footnote_on_every_author_is_no_mark():
    html = _page([(THREE[0], ["1", "*"]), (THREE[1], ["2", "*"])], [("*", "E-mail: a@example.org; b@example.org")])
    assert _flags(html) == [None, None]


def test_a_sole_authors_email_footnote_is_no_mark():
    html = _page([("Elisa Ruiz-Burga", ["a"])], [("a", "Email: <span>e.burga@example.ac.uk</span>")], affs=("1",))
    assert _flags(html) == [None]


def test_a_sole_authors_envelope_is_a_mark():
    html = _page([("Liqun Luo", ["1", "✉"])], [("✉", "Email: lqluo@example.edu.cn")])
    assert _marked(html) == ["Liqun Luo"]


def test_an_email_footnote_per_author_is_no_mark():
    # "*Email: a", "†Email: b", "‡Email: c" on three of four authors: an e-mail for each, not a correspondence mark
    html = _page([("Yeqing Zhou", ["2", "*"]), ("Jianxuan Liu", ["3", "†"]), ("Yanyuan Ma", ["4", "‡"]),
                  ("Fourth Author", ["1"])],
                 [("*", "Email: zhou@example.edu"), ("†", "Email: liu@example.edu"), ("‡", "Email: ma@example.edu")],
                 affs=("1", "2", "3", "4"))
    assert pmc_corresponding_names(BeautifulSoup(html, "lxml")) == []


def test_one_email_symbol_on_two_authors():
    # ACS: "*Email: ..." once per starred author
    html = _page([("Kangning Li", ["1"]), ("Jintao Yang", ["1", "*"]), ("Jie Feng", ["1", "*"])],
                 [("*", "Email: yang@example.edu.cn ."), ("*", "Email: feng@example.edu.cn .")])
    assert _marked(html) == ["Jintao Yang", "Jie Feng"]


def test_footnote_with_only_an_email_ties_to_no_one():
    html = _page([(THREE[0], ["1"]), (THREE[1], ["2"]), (THREE[2], ["1"])],
                 [("✉", "Correspondence: <span>someone@example.org</span>; Tel.: +82-54-912-0814")])
    assert _flags(html) == [None, None, None]


def test_orcid_footnote_is_no_mark():
    html = _page([("Ralf Steinborn", ["1", "†"]), ("Some Coauthor", ["2"])],
                 [("†", "ORCID: Ralf Steinborn, orcid.org/0000-0001-9287-5039")])
    assert _flags(html) == [None, None]


def test_labels_after_a_group_name_are_not_the_previous_authors():
    html = _page([("Peter Taylor", ["1"]), ("Colin M Dayan", ["2"])], [("✉", "Corresponding author.")],
                 extra_byline=', <span>on behalf of the CIR group</span><sup>✉</sup>')
    assert _flags(html) == [None, None]


def test_same_markup_without_pmcs_meta_is_not_read_here():
    html = _page([(THREE[0], ["1"]), (THREE[2], ["1", "✉"])], [("✉", "Corresponding author.")], pmc=False)
    assert pmc_corresponding_names(BeautifulSoup(html, "lxml")) == []
