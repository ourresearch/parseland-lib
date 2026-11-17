"""SciRP (Scientific Research Publishing, scirp.org) article pages (oxjob #2289).

Every SciRP article page is one ASP.NET template: the byline in div#JournalInfor_div_paper as one
<a href="articles?searchcode=...&searchfield=authors"> link per author, each followed by a <sup> of affiliation numbers
and marks ("1,2*#"), the affiliations in span#JournalInfor_div_affs (numbered by <sup> when there are several), the
full text in div#htmlContent with <p class="E-Title1"> section headings ("Acknowledgements", "NOTES": "#Corresponding
author."). The generic parser read the citation_author tags only: no affiliations, and on recent pages a name with an
accent split in two at a broken entity ("Lucas S&amp;#225" / "vio ..."). Markup below is cut down from stored pages;
names are placeholders.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.scirp import SciRP

URL = "https://www.scirp.org/journal/paperinformation?paperid=110776"
ABSTRACT = ("We report a case of a pedestrian admitted with a severe traumatic brain injury and massive epistaxis "
            "from a ruptured artery; emergency endovascular management is discussed together with a review of the "
            "literature on the timing of embolization.")


def _author(name, sup=None):
    q = name.replace(" ", "+")
    link = f"<a href='articles?searchcode={q}&searchfield=authors&page=1' target='_blank'>{name}</a>"
    return link + (f"<sup>{sup}</sup>" if sup is not None else "")


def _aff(text, num=None):
    q = text.replace(" ", "+")
    return ((f"<sup>{num}</sup>" if num else "")
            + f"<a href='articles?searchcode={q}&searchfield=affs&page=1' target='_blank'>{text}</a>.<br />")


def _page(authors, affs, full_text="", metas=None, publisher="Scientific Research Publishing", head_extra=""):
    metas = metas if metas is not None else [name for name, _ in authors]
    tags = "".join(f'<meta name="citation_author" content="{m}" />' for m in metas)
    byline = ", ".join(_author(n, s) for n, s in authors)
    aff_span = f'<span id="JournalInfor_div_affs">{"".join(affs)}</span>' if affs else ""
    return f"""<html><head><title>A title</title>
<meta property="og:site_name" content="SCIRP" />
<meta name="citation_publisher" content="{publisher}" />{tags}
<meta name="citation_title" content="A title" />
<meta name="citation_doi" content="10.4236/ojmn.2021.113024" />
<meta name="citation_abstract" content="{ABSTRACT}" />{head_extra}
</head><body><div class="container"><div id="JournalInfor_div_paper" class="articles_main">
<div class="art_title">A title</div>
<div style="float: left; width: 100%; margin-top: 5px; margin-bottom: 10px;">
{byline} <br />
{aff_span}
<span id="JournalInfor_showDOI"><b>DOI: </b><a href="https://doi.org/10.4236/ojmn.2021.113024">10.4236/ojmn.2021.113024</a></span>
</div>
<div><p style="font-weight: bold; font-size: 16px;"><a name="abstract">Abstract</a></p><p>{ABSTRACT}</p></div>
<div style="margin-top:10px;" id="htmlContent">{full_text}</div>
</div></div></body></html>"""


def _parsed(html):
    return parse_page(html.encode(), "doi", URL)


def _affs(html):
    return [(a["name"], [x["name"] for x in a["affiliations"]]) for a in _parsed(html)["authors"]]


def _corr(html):
    return [a["name"] for a in _parsed(html)["authors"] if a["is_corresponding"]]


def test_numbered_affiliations_follow_each_authors_numbers():
    html = _page([("Ana Example", "1,2"), ("Ben Sample", "2"), ("Cy Placeholder", "3")],
                 [_aff("Faculty of Medicine, Bamako, Mali", 1), _aff("Kati University Hospital, Kati, Mali", 2),
                  _aff("Department of Public Health, Bamako, Mali", 3)])
    assert _affs(html) == [
        ("Ana Example", ["Faculty of Medicine, Bamako, Mali", "Kati University Hospital, Kati, Mali"]),
        ("Ben Sample", ["Kati University Hospital, Kati, Mali"]),
        ("Cy Placeholder", ["Department of Public Health, Bamako, Mali"]),
    ]


def test_one_unnumbered_affiliation_belongs_to_every_author():
    html = _page([("Ana Example", None), ("Ben Sample", None)],
                 [_aff("Stony Brook University Hospital, New York, USA")])
    assert _affs(html) == [("Ana Example", ["Stony Brook University Hospital, New York, USA"]),
                           ("Ben Sample", ["Stony Brook University Hospital, New York, USA"])]


def test_unnumbered_affiliations_of_a_lone_author_are_all_theirs():
    html = _page([("Ana Example", "")], [_aff("ISGlobal, Barcelona, Spain"), _aff("University of Barcelona, Spain")])
    assert _affs(html) == [("Ana Example", ["ISGlobal, Barcelona, Spain", "University of Barcelona, Spain"])]


def test_unnumbered_affiliations_of_several_authors_are_linked_by_the_pages_json_ld():
    ld = ('<script type="application/ld+json">{"@context":"https://schema.org","@type":"ScholarlyArticle","author":['
          '{"@type":"Person","name":"Ana Example","affiliation":[{"@type":"Organization","name":"Medak College, Medak, India"}]},'
          '{"@type":"Person","name":"Ben Sample","affiliation":[{"@type":"Organization","name":"Kakatiya University, Warangal, India"}]}'
          ']}</script>')
    affs = [_aff("Kakatiya University, Warangal, India"), _aff("Medak College, Medak, India")]
    html = _page([("Ana Example", None), ("Ben Sample", None)], affs, head_extra=ld)
    assert _affs(html) == [("Ana Example", ["Medak College, Medak, India"]),
                           ("Ben Sample", ["Kakatiya University, Warangal, India"])]
    # without the JSON-LD the page links none of them to anyone: no affiliation is guessed
    assert _affs(_page([("Ana Example", None), ("Ben Sample", None)], affs)) == [("Ana Example", []),
                                                                                  ("Ben Sample", [])]


def test_the_visible_name_beats_a_meta_tag_split_at_a_broken_entity():
    html = _page([("Lucas S&#225;vio Oliveira", "")], [_aff("University of Aveiro, Aveiro, Portugal")],
                 metas=["Lucas S&amp;#225", "vio Oliveira"])
    assert _affs(html) == [("Lucas Sávio Oliveira", ["University of Aveiro, Aveiro, Portugal"])]


def test_names_lose_the_bylines_double_spaces():
    html = _page([("Soulemane  Pessinaba", "1"), ("Rita Claudia Djolla  Epe", "1")], [_aff("Campus Hospital, Lomé", 1)])
    assert [a["name"] for a in _parsed(html)["authors"]] == ["Soulemane Pessinaba", "Rita Claudia Djolla Epe"]


def test_corresponding_author_is_the_mark_the_notes_explain():
    notes = ('<p class="E-Title1">4. Conclusion</p><p>Text.</p><p class="E-Title1">NOTES</p>'
             '<p>*Joint first author.</p> <p><sup>#</sup>Corresponding author.</p>')
    html = _page([("Ana Example", "1*"), ("Ben Sample", "1*#"), ("Cy Placeholder", "1")],
                 [_aff("Mohammed V University, Rabat, Morocco", 1)], full_text=notes)
    assert _corr(html) == ["Ben Sample"]


def test_a_star_the_notes_call_corresponding_marks_that_author():
    notes = '<p class="E-Title1">NOTES</p><p> <sup>*</sup>Corresponding author.</p>'
    html = _page([("Ana Example", "1*"), ("Ben Sample", "2")],
                 [_aff("Mansoura University, Egypt", 1), _aff("Cairo University, Egypt", 2)], full_text=notes)
    assert _corr(html) == ["Ana Example"]
    assert [a["is_corresponding"] for a in _parsed(html)["authors"]] == [True, False]


def test_a_bare_star_the_page_never_explains_is_not_a_corresponding_mark():
    html = _page([("Ana Example", "1,2*"), ("Ben Sample", "1")],
                 [_aff("Faculty of Medicine, Bamako, Mali", 1), _aff("Kati University Hospital, Kati, Mali", 2)],
                 full_text='<p class="E-Title1">5. Conclusion</p><p>Text.</p>')
    assert _corr(html) == []


def test_abstract_is_the_citation_abstract():
    html = _page([("Ana Example", "")], [_aff("University of Aveiro, Aveiro, Portugal")])
    assert _parsed(html)["abstract"] == ABSTRACT


def test_acknowledgments_section_without_its_heading():
    text = ('<p class="E-Title1">4. Conclusion</p><p>We conclude.</p>'
            '<p class="E-Title1">Acknowledgements</p><p>The authors would like to acknowledge a colleague for technical '
            'assistance. Funding for this study was provided by a growers association.</p>'
            '<p class="E-Title1">Abbreviations</p><p>BED: biologically effective dose.</p>'
            '<p class="E-Title1">NOTES</p><p> <sup>*</sup>Corresponding author.</p>')
    html = _page([("Ana Example", "")], [_aff("University of Guelph, Canada")], full_text=text)
    parsed = SciRP(BeautifulSoup(html, "lxml")).parse()
    assert parsed["acknowledgments"] == ("The authors would like to acknowledge a colleague for technical assistance. "
                                         "Funding for this study was provided by a growers association.")
    # a combined acknowledgments-and-funding paragraph stays in acknowledgments (#2215 contract)
    assert parsed.get("funding_statement") is None
    assert _parsed(html)["acknowledgments"] == parsed["acknowledgments"]
    no_ack = _page([("Ana Example", "")], [_aff("University of Guelph, Canada")],
                   full_text='<p class="E-Title1">1. Introduction</p><p>Text.</p>')
    assert SciRP(BeautifulSoup(no_ack, "lxml")).parse().get("acknowledgments") is None


def test_other_publishers_pages_are_not_claimed():
    # another publisher whose name starts the same way, with the same byline links
    other = _page([("Ana Example", "1")], [_aff("Some University", 1)],
                  publisher="Scientific Research Publishing House of Example")
    assert not SciRP(BeautifulSoup(other, "lxml")).authors_found()
    # SciRP's publisher tag on a page without the article template (a journal or search page)
    listing = ('<html><head><meta name="citation_publisher" content="Scientific Research Publishing" /></head>'
               '<body><div class="list"><a href="articles?searchcode=Ana+Example&searchfield=authors">Ana Example</a>'
               '</div></body></html>')
    assert not SciRP(BeautifulSoup(listing, "lxml")).authors_found()
    # an Open Journal Systems page (the nearest other template: citation_* tags, a linked byline, no SciRP mark)
    ojs = ('<html><head><meta name="generator" content="Open Journal Systems 3.3.0.10"/>'
           '<meta name="citation_author" content="Ana Example"/><meta name="citation_publisher" content="Example Press"/>'
           '</head><body><section class="item authors"><ul class="authors"><li><span class="name">Ana Example</span>'
           '<span class="affiliation">Some University</span></li></ul></section></body></html>')
    assert not SciRP(BeautifulSoup(ojs, "lxml")).authors_found()
    assert not SciRP(BeautifulSoup(ojs, "lxml")).is_publisher_specific_parser()
