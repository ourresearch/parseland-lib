"""Editorial System (Bentus, Poland) article pages: one parser for the template's ~70 journal sites (oxjob #2268).

Markup is cut down from stored pages of the template (psychiatriapolska.pl, ecoeet.com, combustion-engines.eu, aaem.pl,
populationmedicine.eu ...). The byline is div.magAbstractAuthors, each author a div#author_<id> whose
highlightAffs('1,2', ...) names its affiliation numbers; the affiliations sit in #articleDetailsId as a table
(td.affIndex / td.affName) or a list (div.list-row-small#aff_<n>); a "Corresponding author" block links the author's
page (a.corrAuthorLink). Reference list, funding and acknowledgments are labelled sections below the abstract.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.editorial_system import EditorialSystem

URL = "https://www.example-journal.pl/A-title,82194,0,2.html"
ABSTRACT = ("The Internet, being generally available, is used by all age groups for professional purposes and also as a "
            "form of education and entertainment. It is, however, possible to use the Internet excessively, resulting "
            "in an addiction. This paper presents data on the incidence of Internet addiction and reviews the models.")


def _author(aid, name, affs, mail=None, sup_extra=""):
    env = (f'<div class="dirLeft"><a href="mailto:{mail}"><div class="icon icon-envelope-o"></div></a></div>'
           if mail else "")
    return (f'<div class="dirLeft"><div class="dirLeft" id="author_{aid}" '
            f"onmouseover=\"highlightAffs('{affs}', 1, {aid}); return false;\" "
            f"onmouseout=\"highlightAffs('{affs}', 0, {aid}); return false;\">"
            f'<a href="https://www.example-journal.pl/Author-x/{aid}" class="black">{name}</a>'
            f'<span class=""><sup> {affs}{sup_extra} </sup></span></div>{env}'
            f'<div class="dirLeft pad-right-5">,</div><div class="clearAll">&nbsp;</div></div>')


def _aff_table(affs):
    rows = "".join(f'<tr><td class="affIndex">{n}</td><td class="affName"><div><span id="aff_{n}">{t}</span></div></td></tr>'
                   for n, t in affs)
    return f'<div class="affiliations"><table cellspacing="0" cellpadding="0" border="0" width="100%">{rows}</table></div>'


def _aff_list(affs, corr=""):
    rows = "".join(f'<div class="list-row-small" id="aff_{n}"><div class="dirLeft w-23px pad-left-4 em-08">{n}</div>'
                   f'<div class="dirLeft w-100-c23 em-095">{t}</div><div class="clearAll">&nbsp;</div></div>'
                   for n, t in affs)
    dates = ('<div class="simple-list pad-top-12 pad-bot-10"><div class="list-row-small-2"><div class="dirLeft w-23px">'
             '&nbsp;</div><div class="dirLeft w-100-c23 em-08">Publication date: 2023-04-26</div></div></div>')
    return f'<div class="affiliations"><div class="simple-list">{rows}</div>{dates}<div class="simple-list">{corr}</div></div>'


def _corr_block(aid, name):
    return ('<div style="padding-bottom: 5px;" class="corrAuthorLabel"><b>CORRESPONDING AUTHOR</b></div><div>'
            f'<a href="https://www.example-journal.pl/Author-x/{aid}" class="corrAuthorLink">{name}</a> '
            '<a href="mailto:x@example.pl"><div class="icon icon-envelope-o"></div></a><br/>'
            'Some University, ul. Długa 1, 00-001 Warszawa, Polska</div>')


def _page(names, byline, details, back=""):
    metas = "".join(f'<meta name="citation_author" content="{n}"/>' for n in names)
    return (f'<html><head><meta property="og:url" content="{URL}"/><meta name="citation_title" content="A title"/>'
            f'<meta name="citation_doi" content="10.12740/PP/82194"/>{metas}<meta name="description" content="{ABSTRACT}"/>'
            f'</head><body><div class="articleTitle">A title</div><div class="magAbstractAuthors">{byline}'
            '<div class="clearAll">&nbsp;</div></div>'
            '<a class="articleDetails" href="#" id="moreDetailsId">More details</a>'
            f'<div id="articleDetailsId">{details}<div class="magBibliography">Publication date: 2019-02-28</div></div>'
            f'<div class="abstractLabel">ABSTRACT</div><div class="abstractContent realAbstract">{ABSTRACT}</div>{back}'
            '<div class="copyright">Journal hosting platform by <a href="http://www.bentus.com">Bentus</a></div>'
            '</body></html>')


def _parsed(html):
    return parse_page(html.encode(), "doi", URL)


def _raw(html):
    return EditorialSystem(BeautifulSoup(html, "lxml")).parse()


NAMES = ["Andrzej Cudo", "Emilia Zabielska-Mendyk", "Jan Kowalski"]
UNIV = "Katolicki Uniwersytet Lubelski Jana Pawła II"
OTHER = "Department of Chemistry, Texas A&amp;M University-Commerce, TX, USA"


def _three_authors(mails=(None, None, None), affs=("1", "1", "1,2")):
    return "".join(_author(70 + i, n.replace(" ", "  "), affs[i], mails[i]) for i, n in enumerate(NAMES))


def test_table_affiliations_follow_each_authors_numbers():
    html = _page(NAMES, _three_authors(), _aff_table([(1, UNIV), (2, OTHER)]))
    authors = _parsed(html)["authors"]
    assert [a["name"] for a in authors] == NAMES
    assert [[x["name"] for x in a["affiliations"]] for a in authors] == [
        [UNIV], [UNIV], [UNIV, "Department of Chemistry, Texas A&M University-Commerce, TX, USA"]]


def test_list_affiliations_skip_the_dates_row():
    html = _page(NAMES, _three_authors(affs=("1", "2", "2")), _aff_list([(1, "Forestry Master Program, Hasanuddin "
                                                                          "University, Makassar, Indonesia"),
                                                                         (2, "Department of Forestry, Hasanuddin "
                                                                          "University, Makassar, Indonesia")]))
    affs = [[x["name"] for x in a["affiliations"]] for a in _parsed(html)["authors"]]
    assert affs[0] == ["Forestry Master Program, Hasanuddin University, Makassar, Indonesia"]
    assert affs[1] == affs[2] == ["Department of Forestry, Hasanuddin University, Makassar, Indonesia"]


def test_contribution_letters_and_equal_contribution_marks_are_not_affiliations_or_names():
    byline = (_author(1, "Yongzheng Bao<sup>+</sup>", "1,2") +
              _author(2, "Bohdan Pac", "2", sup_extra='<span rel="contributionRel" style="display: none;">, A-F</span>'))
    html = _page(["Yongzheng Bao<sup>+</sup>", "Bohdan Pac"], byline, _aff_table([(1, UNIV), (2, "Medical University, "
                                                                                       "Lublin, Poland")]))
    authors = _parsed(html)["authors"]
    assert [a["name"] for a in authors] == ["Yongzheng Bao", "Bohdan Pac"]
    assert [len(a["affiliations"]) for a in authors] == [2, 1]


def test_corresponding_block_names_the_author_even_when_others_show_an_email():
    byline = _three_authors(mails=("a@example.pl", "b@example.pl", None))
    html = _page(NAMES, byline, _aff_table([(1, UNIV), (2, OTHER)]) + _corr_block(71, "Emilia  Zabielska-Mendyk"))
    assert [a["is_corresponding"] for a in _parsed(html)["authors"]] == [False, True, False]


def test_corresponding_block_in_the_list_layout():
    corr = ('<div class="list-row-small"><div class="dirLeft w-23px">&nbsp;</div><div class="dirLeft w-100-c23">'
            '<div class="em-085"><b>Corresponding author</b></div><div class="em-095">'
            '<a href="https://www.example-journal.pl/Author-x/72" class="corrAuthorLink" class="black">Jan Kowalski</a>'
            '</div></div></div>')
    html = _page(NAMES, _three_authors(mails=("a@x.pl", "b@x.pl", "c@x.pl")), _aff_list([(1, UNIV), (2, OTHER)], corr))
    assert [a["is_corresponding"] for a in _parsed(html)["authors"]] == [False, False, True]


def test_one_author_singled_out_by_an_envelope_is_corresponding():
    html = _page(NAMES, _three_authors(mails=(None, "b@example.pl", None)), _aff_table([(1, UNIV), (2, OTHER)]))
    assert [a["is_corresponding"] for a in _parsed(html)["authors"]] == [False, True, False]


def test_an_email_for_every_author_marks_no_one():
    html = _page(NAMES, _three_authors(mails=("a@x.pl", "b@x.pl", "c@x.pl")), _aff_table([(1, UNIV), (2, OTHER)]))
    assert not any(a["is_corresponding"] for a in _parsed(html)["authors"])


def test_abstract_is_the_one_the_page_prints():
    html = _page(NAMES, _three_authors(), _aff_table([(1, UNIV), (2, OTHER)]))
    assert _parsed(html)["abstract"] == ABSTRACT


def _refs(entries, stated):
    items = "".join(
        f'<a class="anchor" id="{i}"></a><div class="ref" id="ref_{i}"><div class="dirLeft refNo">{i}.</div>'
        f'<div class="dirLeft refText"><div style="word-break: break-word;">{text}</div><div class="refLinks">'
        + (f'<div class="dirLeft"><a target="_blank" href="https://doi.org/{doi}">CrossRef</a></div>' if doi else "")
        + f'<div class="dirLeft"><a target="_blank" href="https://scholar.google.com/scholar?q=x">Google Scholar</a>'
          '</div></div></div><div class="clearAll">&nbsp;</div></div>'
        for i, (text, doi) in enumerate(entries, 1))
    cited_by = ('<div class="abstractLabel">CITATIONS (1) :</div><div class="abstractContent"><div class="ref">'
                '<div class="dirLeft refNo">1.</div><div class="dirLeft refText">A later paper citing this one<br/>'
                '<div class="refLinks"><a href="https://doi.org/10.1016/j.srhc.2022.100748">CrossRef</a></div></div>'
                '</div></div>')
    return ('<a class="anchor" id="references"></a><div class="abstractLabel"><span class="block">REFERENCES</span>'
            f'<span class="block">&nbsp;</span><span class="block">({stated})</span></div>'
            f'<div class="abstractContent">{items}</div>{cited_by}')


REFS = [("LEE, C.S., REITZ, R.D. Effect of split injection on a diesel spray. Atomization Spray. 2006, 16(5), 543-562.",
         "10.1615/AtomizSpr.v16.i5.40"),
        ("WANG, Z.M., XU, H.M. Experimental study on diesel spray with split injection. Fuel. 2016, 174, 140-152.", None)]


def test_reference_list_whole_when_numbers_and_stated_count_agree():
    out = _raw(_page(NAMES, _three_authors(), _aff_table([(1, UNIV)]), _refs(REFS, 2)))
    assert out["references"] == [{"position": 1, "raw": REFS[0][0], "doi": "10.1615/AtomizSpr.v16.i5.40"},
                                 {"position": 2, "raw": REFS[1][0], "doi": None}]
    assert out["references_complete"] is True


def test_reference_list_not_whole_when_the_stated_count_is_larger():
    out = _raw(_page(NAMES, _three_authors(), _aff_table([(1, UNIV)]), _refs(REFS, 3)))
    assert len(out["references"]) == 2 and out["references_complete"] is False


def test_funding_and_acknowledgments_sections():
    back = ('<div class="abstractLabel">ACKNOWLEDGEMENTS</div><div class="abstractContentReal">We thank the Department '
            'of Neuroscience, University of Turin, for the support.</div>'
            '<div class="abstractLabel">FUNDING</div><div class="abstractContentReal">This research was funded by the '
            'grant PON "Green" for Research and innovation.</div>'
            '<div class="abstractLabel">CONFLICT OF INTEREST</div><div class="abstractContentReal">The authors declare '
            'no conflicts of interest.</div>')
    out = _raw(_page(NAMES, _three_authors(), _aff_table([(1, UNIV)]), back))
    assert out["acknowledgments"] == "We thank the Department of Neuroscience, University of Turin, for the support."
    assert out["funding_statement"] == 'This research was funded by the grant PON "Green" for Research and innovation.'


def test_no_back_matter_keys_when_the_page_shows_none():
    out = _raw(_page(NAMES, _three_authors(), _aff_table([(1, UNIV)])))
    assert out["acknowledgments"] is None and out["funding_statement"] is None
    assert out["references"] == [] and out["references_complete"] is False


def test_other_bentus_layout_and_look_alike_pages_are_not_claimed():
    # termedia.pl's own portal (same vendor, older layout): div.dAuthor byline, div.dAffiliations with affIndex/affName
    portal = ('<html><head><meta name="citation_author" content="Marzena Michalak-Kloc"/></head><body>'
              '<h3><div class="dirLeft"><div class="dirLeft dAuthor" id="author_73044">Marzena Michalak-Kloc</div>'
              '<div class="dirLeft dAuthorAff"><sup>1</sup></div></div></h3><div class="dAffiliations">'
              '<div class="affIndex">1.</div><div class="affName">Neonatology Department, University Hospital in '
              'Zielona Gora, Poland</div></div></body></html>')
    # another platform's byline with an "affiliations" block and a mailto
    other = ('<html><head><meta name="citation_author" content="Ann Smith"/></head><body><div class="authors">'
             '<span id="author_1">Ann Smith<sup>1</sup></span><a href="mailto:a@b.org">mail</a></div>'
             '<div class="affiliations"><table><tr><td class="affIndex">1</td><td class="affName">Univ X</td></tr>'
             '</table></div></body></html>')
    for html in (portal, other):
        parser = EditorialSystem(BeautifulSoup(html, "lxml"))
        assert not parser.is_publisher_specific_parser()
        assert not parser.authors_found()
        assert not any(a["affiliations"] for a in _parsed(html)["authors"])


def test_older_inline_byline_of_spans():
    # aaem.pl, jafs.com.pl, combustion-engines.eu: authors as <span id="author_<id>">, the number and envelope after it
    byline = ("<span id=\"author_116031\" onmouseover=\"highlightAffs('1', 1, 116031); return false;\">"
              '<a class="black" href="http://www.aaem.pl/Author-Robert-W/116031">Robert Węgłowski</a></span> <sup>1</sup> '
              '<a href="mailto:r.w@wp.pl"><div class="icon icon-envelope-o"></div></a>, '
              "<span id=\"author_93355\" onmouseover=\"highlightAffs('2', 1, 93355); return false;\">"
              '<a class="black" href="http://www.aaem.pl/Author-Pawel-Polak/93355">Paweł Polak</a></span> <sup>2</sup>')
    html = _page(["Robert Węgłowski", "Paweł Polak"], byline,
                 _aff_table([(1, "University of Physical Education in Warsaw, Poland"), (2, UNIV)]))
    authors = _parsed(html)["authors"]
    assert [a["name"] for a in authors] == ["Robert Węgłowski", "Paweł Polak"]
    assert [[x["name"] for x in a["affiliations"]] for a in authors] == [
        ["University of Physical Education in Warsaw, Poland"], [UNIV]]
    assert [a["is_corresponding"] for a in authors] == [True, False]


def test_a_line_break_in_the_page_source_is_not_a_paragraph():
    back = ('<div class="abstractLabel">FUNDING</div><div class="abstractContentReal">This work was supported by '
            'Tianshan Talent Cultivation Program of\nXinjiang Uygur Autonomous Region (2024TSYCJC0065).<br/>'
            'Second paragraph.</div>')
    out = _raw(_page(NAMES, _three_authors(), _aff_table([(1, UNIV)]), back))
    assert out["funding_statement"] == ("This work was supported by Tianshan Talent Cultivation Program of Xinjiang "
                                        "Uygur Autonomous Region (2024TSYCJC0065).\nSecond paragraph.")


def test_the_envelope_of_a_sole_author_marks_them():
    # the gate's dev gold (ecoeet.com, adjudicated): "The sole author has an envelope mailto icon next to the name,
    # treated as a corresponding mark"
    html = _page(["Kazimierz H. Dyguś"], _author(216, "Kazimierz H. Dyguś", "1", "k@wseiz.pl"), _aff_table([(1, UNIV)]))
    assert [a["is_corresponding"] for a in _parsed(html)["authors"]] == [True]
