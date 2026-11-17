"""SciTePress Digital Library (www.scitepress.org) paper pages: byline affiliations and the whole abstract (oxjob #2338).

Markup is cut down from stored scitepress.org paper pages (#2338, 17 Nov 2026). The site is an ASP.NET WebForms app:
every field sits in a span whose id names it (ContentPlaceHolder1_LinkPaperPage_LinkPaperContent_...). The byline lists
authors, then affiliations; superscript numbers link them when there are several, and a paper with one affiliation prints
it with empty superscripts (label-v1: "unlinked", every author gets the whole list). The abstract is printed as a visible
span cut at about 1,000 characters, often mid-word, plus a hidden "(More)" span with the rest; the generic reader kept
the first span alone or nothing. No citation_author_institution tags, no corresponding-author marks, no references.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.scitepress import SciTePress

URL = "https://www.scitepress.org/Link.aspx?doi=10.5220/0004256900990108"
P = "ContentPlaceHolder1_LinkPaperPage_LinkPaperContent_"
HEAD = ('<meta name="description" content="Digital Library" /><meta name="title" content="SCITEPRESS" />'
        '<title>SciTePress - Publication Details</title>')
VISIBLE = ("This paper presents a simple interactive negotiation approach for conflicts in everyday life with "
           "incomplete information. We focus on mediation to obtain an agreement while going through alternating "
           "offers over a finite time bargaining game. The mediator searches and proposes a jointly optimal negotiat")
HIDDEN = ("ion text for all players participating in the negotiation process based on their conditional preference "
          "networks (CP-nets).")


def _numbers(kind, i, nums):
    out = []
    for j, n in enumerate(nums):
        if j:
            out.append(f'<span id="{P}{kind}Repeater_NumbersRepeater_{i}_LabelV_{j - 1}" '
                       f'class="PublicationsDetailNormal">; </span>')
        out.append(f'<span id="{P}{kind}Repeater_NumbersRepeater_{i}_Number_{j}">{n}</span>')
    return "<sup>" + "".join(out) + "</sup>"


def _page(authors, affs, visible=VISIBLE, hidden=HIDDEN, title_tag=HEAD, metas=None):
    """authors: [(given, family, [nums])]; affs: [([nums], text)]."""
    metas = metas if metas is not None else [f"{g} {f}" for g, f, _ in authors]
    meta_tags = "".join(f"<meta name='citation_author' content='{m}' />" for m in metas)
    byline = "".join(
        f'<a id="{P}AuthorsRepeater_LinkButtonAuthor_{i}" href="PersonProfile.aspx?PersonAccountID=x{i}">'
        f'<span id="{P}AuthorsRepeater_LabelAuthor_{i}" class="PublicationsDetailNormal">{g}&nbsp;{f}</span></a>'
        f'{_numbers("Authors", i, nums)}'
        f'<span id="{P}AuthorsRepeater_LabelComma_{i}" class="PublicationsDetailNormal">; </span>'
        for i, (g, f, nums) in enumerate(authors))
    aff_html = "".join(
        f'{_numbers("Affiliations", i, nums)}'
        f'<a id="{P}AffiliationsRepeater_LinkButtonAffiliation_{i}" href="AffiliationsProfile.aspx?Org=y{i}">'
        f'<span id="{P}AffiliationsRepeater_LabelAffiliation_{i}" class="PublicationsDetailNormal">{t}</span></a>'
        for i, (nums, t) in enumerate(affs))
    more = (f'<span id="{P}MoreAbstract" class="lessAbstract">{hidden}</span>'
            f'<a id="{P}MoreButton" onclick="CollapseExpandAbstract(this);">(More)</a>') if hidden else ""
    return (f'<html><head id="Head1">{title_tag}'
            f"<meta name='citation_title' content='Multi-player Multi-issue Negotiation with Mediator using CP-nets' />"
            f'{meta_tags}</head><body><div class="span6 publicationDetailsInfo">'
            f'<p class="PublicationsDetailBold"><span id="{P}LabelSearchAuthors" class="LabelSearchRepeater">Authors:'
            f'</span>{byline}</p>'
            f'<p class="PublicationsDetailBold"><span id="{P}LabelSearchAffiliations" class="LabelSearchRepeater">'
            f'Affiliations:</span>{aff_html}</p>'
            f'<p class="PublicationsDetailBold"><span id="{P}LabelKeywords" class="LabelSearchRepeater"> Keyword(s):'
            f'</span><span id="{P}LabelPublicationDetailKeywords">Negotiation, Mediation, CP-nets.</span></p>'
            f'<p class="PublicationsDetailNormal"><span id="{P}LabelAbstractTitle" class="LabelSearchRepeater">'
            f'Abstract: </span><span id="{P}LabelAbstract">{visible}</span>{more}'
            f'<div id="ctl00_{P}RadToolTip1" style="display:none;position:absolute;">'
            f'<span id="{P}LabelAbstractPopUp">{visible}{hidden}</span></div></p>'
            f'</div></body></html>')


NUMBERED = [("Thiri Haymar", "Kyaw", ["1"]), ("Sujata", "Ghosh", ["1", "2"]), ("Rineke", "Verbrugge", ["2"])]
NUMBERED_AFFS = [(["1"], "University of Technology (Yatanarpon Cyber City), Myanmar"),
                 (["2"], "University of Groningen, Netherlands")]


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _affs(out):
    return [[a["name"] for a in au["affiliations"]] for au in out["authors"]]


def test_numbered_affiliations_link_per_author():
    out = _parse(_page(NUMBERED, NUMBERED_AFFS))
    assert [a["name"] for a in out["authors"]] == ["Thiri Haymar Kyaw", "Sujata Ghosh", "Rineke Verbrugge"]
    assert _affs(out) == [["University of Technology (Yatanarpon Cyber City), Myanmar"],
                          ["University of Technology (Yatanarpon Cyber City), Myanmar",
                           "University of Groningen, Netherlands"],
                          ["University of Groningen, Netherlands"]]


def test_one_unnumbered_affiliation_goes_to_every_author():
    authors = [("Ferra", "Yanuar", []), ("Hazmira", "Yozza", []), ("Izzati", "Rahmi Hg", [])]
    out = _parse(_page(authors, [([], "Universitas Andalas , Indonesia")]))
    assert [a["name"] for a in out["authors"]] == ["Ferra Yanuar", "Hazmira Yozza", "Izzati Rahmi Hg"]
    assert _affs(out) == [["Universitas Andalas , Indonesia"]] * 3


def test_several_unnumbered_affiliations_are_unlinked():
    authors = [("Giacomo", "Cabri", []), ("Letizia", "Leonardi", [])]
    affs = [([], "Università di Modena e Reggio Emilia, Italy"), ([], "University of Groningen, Netherlands")]
    out = _parse(_page(authors, affs))
    assert _affs(out) == [[t for _, t in affs]] * 2


def test_abstract_joins_the_visible_and_hidden_spans():
    out = _parse(_page(NUMBERED, NUMBERED_AFFS))
    assert out["abstract"] == VISIBLE + HIDDEN
    assert "(More)" not in out["abstract"]


def test_short_abstract_without_a_hidden_span():
    out = _parse(_page(NUMBERED, NUMBERED_AFFS, visible="A short abstract of a position paper on agent "
                       "methodologies, with  a line\nbreak  copied from the PDF.", hidden=""))
    assert out["abstract"] == ("A short abstract of a position paper on agent methodologies, with a line break "
                               "copied from the PDF.")


def test_byline_wins_over_a_repeated_citation_author_tag():
    authors = [("Thibault", "Falque", ["1", "2"]), ("Bertrand", "Mazure", ["2"])]
    affs = [(["1"], "Exakis Nelite, Paris, France"), (["2"], "CRIL, Université d’Artois and CNRS, Lens, France")]
    out = _parse(_page(authors, affs, metas=["Thibault Falque", "Thibault Falque", "Bertrand Mazure"]))
    assert [a["name"] for a in out["authors"]] == ["Thibault Falque", "Bertrand Mazure"]
    assert _affs(out)[0] == ["Exakis Nelite, Paris, France", "CRIL, Université d’Artois and CNRS, Lens, France"]


def test_no_author_is_marked_corresponding():
    out = _parse(_page(NUMBERED, NUMBERED_AFFS))
    assert not any(a["is_corresponding"] for a in out["authors"])


def test_parse_returns_no_new_fields_the_page_does_not_show():
    parsed = SciTePress(BeautifulSoup(_page(NUMBERED, NUMBERED_AFFS), "lxml")).parse()
    for key in ("acknowledgments", "funding_statement", "references", "references_complete"):
        assert not parsed.get(key)


def test_proceedings_page_is_not_claimed():
    html = ('<html><head><title>SciTePress - Proceeding Details</title></head><body>'
            '<span id="ContentPlaceHolder1_ProceedingsDetailsPage_LabelTitle">WEBIST 2023</span></body></html>')
    assert not SciTePress(BeautifulSoup(html, "lxml")).authors_found()


def test_lookalike_aspnet_page_from_another_site_is_not_claimed():
    other = _page(NUMBERED, NUMBERED_AFFS, title_tag="<title>Digital Library - Publication Details</title>")
    parser = SciTePress(BeautifulSoup(other, "lxml"))
    assert not parser.authors_found()
    assert not parser.is_publisher_specific_parser()
    assert all(not a["affiliations"] for a in _parse(other)["authors"])
