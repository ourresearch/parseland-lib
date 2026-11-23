"""Bentham Science (eurekaselect.com) article and chapter pages (oxjob #2289).

Markup is cut down from stored eurekaselect.com pages (#2289's Bentham sample, 17 Nov 2026). The byline is
"Author(s):" followed by the names: an author whose affiliation the site knows is a pop-up link (data-content holds
the affiliation list), every other author is plain text between commas and "and". The parser read the pop-up links
only, so a byline such as "Kenji Okajima and <a>Naoaki Harada</a>" lost Kenji Okajima, and one with no pop-ups lost
everyone (11 of 42 sample pages). Chapter pages print the same byline in a <p>, which no parser read. Newer article
pages print the whole reference list in #reference-box, numbered [1]..[n].
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.bentham import BenthamScience

URL = "https://www.eurekaselect.com/article/13195"
HEAD = ('<meta property="og:url" content="https://www.eurekaselect.com/article/13195" />'
        '<meta property="og:site_name" content="http://www.eurekaselect.com" />'
        '<link rel="stylesheet" href="https://www.eurekaselect.com/css/style.css">')


def _pop(name, affs):
    items = "".join(f"<li>{a} </li>" for a in affs)
    return ('<a href="javascript:void(0)" class="text-secondary" title="Affiliation" data-html="true" '
            f'data-toggle="popover" data-content="<ul>{items}</ul>">{name}</a>')


def _article(byline, extra="", head=HEAD):
    return (f"<html><head>{head}<meta name=\"citation_title\" content=\"A title\" /></head><body>"
            '<div id="side-b" class="col-md-7"><h1>A title</h1>'
            f'<span class="l-h-3"><strong>Author(s):</strong>{byline}</span></div>'
            '<div id="abstract"><p>Insulin-like growth factor-I (IGF-I) plays various important roles in cellular '
            'proliferation, and this is the abstract of the article.</p></div>'
            f"{extra}</body></html>")


def _chapter(byline):
    return (f"<html><head>{HEAD}"
            '<meta property="og:description" content="The mucosa lining the oral cavity varies significantly in its '
            'structure and function, and this is the chapter abstract that the page prints below." /></head><body>'
            '<div id="side-b" class="col-md-7"><h1 class="h3">Structure and Function of the Cells of Oral Mucosa</h1>'
            f"<p><strong>Author(s):</strong> {byline}</p><p><strong>Pp:</strong> 1-6 (6) </p></div>"
            '<main id="chapter"><div class="card"><div class="card-header"><h5 class="m-0">Abstract</h5></div>'
            '<div class="card-body"><p> The mucosa lining the oral cavity varies significantly in its structure and '
            "function, and this is the chapter abstract that the page prints below.</p></div></div></main>"
            "</body></html>")


def _authors(html):
    return parse_page(html.encode(), "doi", URL)["authors"]


AFF = "Department of Translational Medical Science Research, Nagoya City University, Nagoya 467-8601, Japan"


def test_plain_text_author_before_popover_is_kept():
    authors = _authors(_article(f"\n      Kenji      Okajima and \n {_pop('Naoaki      Harada', [AFF])}"))
    assert [a["name"] for a in authors] == ["Kenji Okajima", "Naoaki Harada"]
    assert authors[0]["affiliations"] == []
    assert [x["name"] for x in authors[1]["affiliations"]] == [AFF]


def test_byline_with_no_popovers_is_read():
    authors = _authors(_article(" Sai-Ching Jim Yeung, Christopher Gully and Mong-Hong Lee "))
    assert [a["name"] for a in authors] == ["Sai-Ching Jim Yeung", "Christopher Gully", "Mong-Hong Lee"]
    assert not any(a["is_corresponding"] for a in authors)


def test_popover_byline_keeps_affiliations_order_and_star():
    orcid = '<a title="OrcID Profile" class="green-orcid" href="https://orcid.org/0000-0003-0076-9226"><img src="/images/orcid.png"></a>'
    byline = (f"{_pop('Nicoleta      Ene', ['Univ A, Bucharest', 'Institute B, Bucharest'])}{orcid}, "
              f"{_pop('Maria      Spiridon', ['Institute B, Bucharest'])} and "
              f"{_pop('Emanuel      Vamanu*', ['Univ A, Bucharest'])}{orcid}")
    authors = _authors(_article(byline))
    assert [a["name"] for a in authors] == ["Nicoleta Ene", "Maria Spiridon", "Emanuel Vamanu"]
    assert [len(a["affiliations"]) for a in authors] == [2, 1, 1]
    # the site's own mark, read as before (#2289 leaves this rule as it was)
    assert [a["is_corresponding"] for a in authors] == [False, False, True]


def test_placeholder_popover_is_no_affiliation():
    """3e82c6d8 and 25ae352e (fresh set): an author the site has no affiliation for gets a pop-up whose only entry is
    ",0"; the parser returned ",0" as the affiliation."""
    aff = "Department of Agriculture, Crop Production and Rural Environment, University of Thessaly, Volos, Greece.,Greece"
    byline = (f"{_pop('Spyridon   A.   Petropoulos', [aff])}, \n    {_pop('Isabel   C.F.R.   Ferreira', [',0'])} and "
              f"\n    {_pop('Lilian      Barros', [',0'])}")
    for html in (_article(byline), _chapter(byline)):
        authors = _authors(html)
        assert [a["name"] for a in authors] == ["Spyridon A. Petropoulos", "Isabel C.F.R. Ferreira", "Lilian Barros"]
        assert [[x["name"] for x in a["affiliations"]] for a in authors] == [[aff], [], []]


def test_abstract_is_unchanged():
    out = parse_page(_article(" Kenji Okajima and Naoaki Harada ").encode(), "doi", URL)
    assert out["abstract"].startswith("Insulin-like growth factor-I (IGF-I)")


def test_chapter_byline_is_read():
    byline = ("Bruno      Vincent,\n    Moustapha      Cissé and \n    "
              + _pop("Frédéric      Checler", ["Institute of Molecular Biosciences, Mahidol University, Thailand"]))
    out = parse_page(_chapter(byline).encode(), "doi", URL)
    assert [a["name"] for a in out["authors"]] == ["Bruno Vincent", "Moustapha Cissé", "Frédéric Checler"]
    assert [len(a["affiliations"]) for a in out["authors"]] == [0, 0, 1]
    assert out["abstract"].startswith("The mucosa lining the oral cavity")


def test_chapter_star_is_not_a_corresponding_mark():
    # the page never says what the star means (label-v1: a bare star is not a mark)
    authors = _authors(_chapter(_pop("Eliade      Stefanescu *", ["Romanian Academy, Bucharest, Romania"]) + " ."))
    assert [a["name"] for a in authors] == ["Eliade Stefanescu"]
    assert not authors[0]["is_corresponding"]


def _refs(n, skip=None):
    lines = "".join(
        f'<div class="line"><a name="r{i}"></a><div class="list-count">[{i}]</div><div class="list-contact">'
        f"Author{i} A. A reference title {i}. J Chem 2021; 7(2): 104-16.<br> "
        f'[<a target="_blank" href="http://dx.doi.org/10.1038/s41578-021-0038{i}-0">http://dx.doi.org/10.1038/s41578-021-0038{i}-0</a>]'
        f"<br></div></div>" for i in range(1, n + 1) if i != skip)
    return (f'<div class="card"><button id="refrences"><strong>References</strong></button><div class="collapse">'
            f'<div class="card-body"><div id="reference-box"><div class="reference">{lines}</div></div></div></div></div>')


def _parsed(html):
    return BenthamScience(BeautifulSoup(html, "lxml")).parse()


def test_reference_list_is_whole():
    out = _parsed(_article(" Kenji Okajima and Naoaki Harada ", _refs(3)))
    assert [r["position"] for r in out["references"]] == [1, 2, 3]
    assert out["references"][0]["raw"] == "Author1 A. A reference title 1. J Chem 2021; 7(2): 104-16."
    assert out["references"][2]["doi"] == "10.1038/s41578-021-00383-0"
    assert out["references_complete"] is True


def test_reference_list_with_a_gap_is_not_whole():
    out = _parsed(_article(" Kenji Okajima and Naoaki Harada ", _refs(4, skip=3)))
    assert len(out["references"]) == 3
    assert out["references_complete"] is False


def _ref_line(i, contact):
    return (f'<div class="line"><a name="r{i}"></a><div class="list-count">[{i}]</div>'
            f'<div class="list-contact">{contact}</div></div>')


def _box(lines):
    return (f'<div class="card"><button id="refrences"><strong>References</strong></button><div class="collapse">'
            f'<div class="card-body"><div id="reference-box"><div class="reference">{lines}</div></div></div></div></div>')


def test_compound_entry_keeps_every_citation():
    # chemistry journals print several citations in one numbered entry: a) ...; b) ...; each with its own site links
    compound = ('a) Donalson, W.A. <i>Tetrahedron</i><i>, </i> <b>2001</b>, <em>57</em>, 8589-8627.<br> '
                '[<a target="_blank" href="http://dx.doi.org/10.1016/S0040-4020(01)00777-3">'
                'http://dx.doi.org/10.1016/S0040-4020(01)00777-3</a>]; <br>b) <i>J. Chem. Rev.</i><i>, </i> '
                '<b>2003</b>, <em>103</em>, 1051-1070.; <br>c) Wessjohann, L.A.; Brandt, W. <i>Chem. Rev.</i><i>, </i> '
                '<b>2003</b>, <em>103</em>(4), 1625-1648.<br> [<a target="_blank" href="http://dx.doi.org/10.1021/cr0100188">'
                'http://dx.doi.org/10.1021/cr0100188</a>] [PMID: <a target="_blank" '
                'href="http://www.ncbi.nlm.nih.gov/pubmed/12683792">12683792</a>]<br>')
    out = _parsed(_article(" Kenji Okajima and Naoaki Harada ", _box(_ref_line(1, compound))))
    assert out["references"][0]["raw"] == ("a) Donalson, W.A. Tetrahedron, 2001, 57, 8589-8627.; b) J. Chem. Rev., "
                                           "2003, 103, 1051-1070.; c) Wessjohann, L.A.; Brandt, W. Chem. Rev., 2003, "
                                           "103(4), 1625-1648.")
    assert out["references"][0]["doi"] == "10.1016/S0040-4020(01)00777-3"
    assert out["references_complete"] is True


def test_link_inside_the_citation_is_kept():
    contact = ('WHO. Global report. Available from: <a href="https://www.who.int/report">https://www.who.int/report</a> '
               '(Accessed on: 2020).<br>')
    out = _parsed(_article(" Kenji Okajima and Naoaki Harada ", _box(_ref_line(1, contact))))
    assert out["references"][0]["raw"] == ("WHO. Global report. Available from: https://www.who.int/report "
                                           "(Accessed on: 2020).")


def test_bracketed_link_that_is_not_a_link_out_is_kept():
    contact = ('Smith J. Dataset of soils [<a href="https://archive.example.org/item/9">archived record</a>]. 2019.<br> '
               '[<a target="_blank" href="http://dx.doi.org/10.1000/xyz">http://dx.doi.org/10.1000/xyz</a>]<br>')
    out = _parsed(_article(" Kenji Okajima and Naoaki Harada ", _box(_ref_line(1, contact))))
    assert out["references"][0]["raw"] == "Smith J. Dataset of soils [archived record]. 2019."


def test_page_without_reference_list():
    out = _parsed(_article(" Kenji Okajima and Naoaki Harada "))
    assert "references" not in out


def test_same_byline_markup_on_another_site_is_not_claimed():
    other = ('<meta property="og:site_name" content="Example Journals" />'
             '<meta property="og:url" content="https://journals.example.org/article/1" />')
    parser = BenthamScience(BeautifulSoup(_article(" Kenji Okajima and Naoaki Harada ", head=other), "lxml"))
    assert not parser.authors_found()
    assert not parser.is_publisher_specific_parser()


def test_bentham_open_page_is_not_claimed():
    # benthamopen.com is another template (JATS-rendered articles): its own stylesheet, citation_author tags
    page = ('<html><head><link rel="stylesheet" href="../../../scripts/bentham.css">'
            '<meta name="citation_author" content="Song, Jie"/><meta name="citation_title" content="A title"/></head>'
            '<body><a href="http://benthamopen.com/a">1</a><a href="http://benthamopen.com/b">2</a>'
            '<a href="http://benthamopen.com/c">3</a><a href="http://benthamopen.com/d">4</a>'
            '<a href="http://benthamopen.com/e">5</a><span class="l-h-3"><strong>Author(s):</strong> Jie Song</span>'
            "</body></html>")
    parser = BenthamScience(BeautifulSoup(page, "lxml"))
    assert not parser.authors_found()
    assert not parser.is_publisher_specific_parser()
