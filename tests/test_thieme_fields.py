"""Thieme Connect (oxjob #2289): the reference list its abstract pages print, and a claim that is cheap on other pages."""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.thieme import Thieme

HEAD = """<meta name="description" content="Thieme E-Books &amp; E-Journals"/>
<meta name="citation_publisher" content="Georg Thieme Verlag KG"/>
<meta name="citation_title" content="A study"/>
<meta name="citation_author" content="Anna Example"/>
<meta name="citation_author_institution" content="Department of Surgery, Example University, Berlin"/>
<meta name="citation_author" content="Ben Sample"/>
<meta name="citation_author_institution" content="Institute of Anatomy, Sample University, Munich"/>"""

BYLINE = """<h1>A study</h1>
<span id="authorlist"><span class="author"><div class="name">Anna Example</div></span>
<span class="author"><div class="name">Ben Sample</div></span></span>
<section id="abstract"><h3>Abstract</h3><p>The treatment of the example condition was studied in forty patients over
two years, and the outcomes were compared between both groups.</p></section>
<section id="htmlfulltext">&nbsp;</section>"""

# newer pages (xsdShared.ref-list): the heading in its own item, the number in <strong>, link buttons after the text
NEW_LIST = """<section id="references"><a name=""></a><ul class="literaturliste"><a name="jumpto-references"></a>
<li><h3>References</h3></li>
<li><a name="JR1-1"></a><strong>1</strong> Siegel RL, Jemal A. Cancer statistics, 2024. CA Cancer J Clin 2024; 74 (01) 12-49
<div class="referenceLinks"><div class="referenceLinkText"><a class="linkFunction" href="https://doi.org/10.3322/caac.21820"
target="linkout">Crossref</a><a href="https://pubmed.ncbi.nlm.nih.gov/38230766">PubMed</a>
<a href="https://scholar.google.com/scholar_lookup?title=Cancer">Google Scholar</a></div></div></li>
<li><a name="JR1-2"></a><strong>2</strong> Caples SM. <a href="/products/ejournals/linkout/10.1055/x/id/JR1-2">Sleep
disordered breathing in heart failure</a>. J Clin Sleep Med 2008; 4 (01) 43-44. </li>
</ul></section>"""

# older pages (thiemeFulltext.REFERENCE): the number printed as the item's first text
OLD_LIST = """<section id="references"><h3>Literatur</h3><ul class="literaturliste">
<li><a name="R364-1"></a>1 Grilo C M, Brownell K D. Teasing, body image, and self-esteem. Addict Behav. 1994; 19 443-450
<div class="referenceLinks"><a href="/products/ejournals/ris/10.1055/x/id/1/BIB"><div class="referenceLinkRis"></div></a>
<div class="referenceLinkText"><a href="https://doi.org/10.1016/0306-4603(94)90066-3" target="linkout">Crossref</a></div></div></li>
<li><a name="R364-2"></a>2 Myers A, Rosen J C. Obesity stigmatisation and coping. Int J Obes. 1999; 23 221-230</li>
<li><a name="R364-3"></a>3 Ernst A. Gleichgewicht. Stuttgart: Thieme; 2012</li>
</ul></section>"""


def _page(body, head=HEAD):
    return f"<html><head>{head}</head><body>{body}</body></html>"


def _parse(body, head=HEAD):
    return Thieme(BeautifulSoup(_page(body, head), "lxml")).parse()


def test_newer_list_is_read_whole_without_numbers_or_link_buttons():
    parsed = _parse(BYLINE + NEW_LIST)
    assert parsed["references"] == [
        {"position": 1, "raw": "Siegel RL, Jemal A. Cancer statistics, 2024. CA Cancer J Clin 2024; 74 (01) 12-49",
         "doi": "10.3322/caac.21820"},
        {"position": 2, "raw": "Caples SM. Sleep disordered breathing in heart failure. J Clin Sleep Med 2008; 4 (01) 43-44.",
         "doi": None},
    ]
    assert parsed["references_complete"] is True


def test_older_list_numbered_in_its_text_is_read_whole():
    parsed = _parse(BYLINE + OLD_LIST)
    assert [r["position"] for r in parsed["references"]] == [1, 2, 3]
    assert parsed["references"][0]["raw"].startswith("Grilo C M, Brownell K D. Teasing")
    assert parsed["references"][0]["doi"] == "10.1016/0306-4603(94)90066-3"
    assert parsed["references"][2] == {"position": 3, "raw": "Ernst A. Gleichgewicht. Stuttgart: Thieme; 2012", "doi": None}
    assert parsed["references_complete"] is True


def test_numbering_with_gaps_or_sub_letters_is_not_whole():
    body = BYLINE + """<section id="references"><ul class="literaturliste">
    <li><a name="R1"></a>1a Friedrich W. A synthesis. Chem. Ber. 1980; 113 1</li>
    <li><a name="R2"></a>1b Vitamin D. A review. Synthesis 1999; 1 2</li>
    <li><a name="R3"></a>3 Linker T. Photooxygenation. Synlett 2002; 3 4</li></ul></section>"""
    parsed = _parse(body)
    assert len(parsed["references"]) == 3
    assert parsed["references_complete"] is False


def test_empty_placeholder_list_is_no_list():
    parsed = _parse(BYLINE + '<section id="references"><a name=""></a><ul class="literaturliste"><li></li></ul></section>')
    assert parsed["references"] is None
    assert parsed["references_complete"] is False


def test_authors_and_affiliations_still_come_through_parse_page():
    out = parse_page(_page(BYLINE + NEW_LIST).encode(), "doi", "https://doi.org/10.1055/s-0000-0000000")
    assert [a["name"] for a in out["authors"]] == ["Anna Example", "Ben Sample"]
    assert out["authors"][0]["affiliations"] == [{"name": "Department of Surgery, Example University, Berlin"}]
    assert out["abstract"].startswith("The treatment of the example condition")


def test_claim_reads_the_platform_description_in_head():
    soup = BeautifulSoup(_page(BYLINE), "lxml")
    assert Thieme(soup).is_publisher_specific_parser()
    assert Thieme(soup).authors_found()


def test_look_alike_page_of_another_platform_is_not_taken():
    # another publisher's page with the same byline classes, citation_author tags and a list of the same class name:
    # not claimed, and its list is never read here (this parser stays a fallback for such pages' bylines, as before)
    head = HEAD.replace("Thieme E-Books &amp; E-Journals", "Hogrefe eContent").replace(
        "Georg Thieme Verlag KG", "Hogrefe AG")
    soup = BeautifulSoup(_page('<span class="authors">Anna Example, Ben Sample</span>' + BYLINE + NEW_LIST, head), "lxml")
    assert not Thieme(soup).is_publisher_specific_parser()
    parsed = Thieme(soup).parse()
    assert parsed["references"] is None
    assert parsed["references_complete"] is False


def test_fallback_test_matches_the_old_selects():
    # authors_found() still answers True on any page with an .authors element or a citation_author tag
    assert Thieme(BeautifulSoup('<html><body><dl><dt class="x authors">A. B</dt></dl></body></html>', "lxml")).authors_found()
    assert Thieme(BeautifulSoup('<html><head><meta name="citation_author" content="A. B"></head></html>', "lxml")).authors_found()
    assert not Thieme(BeautifulSoup('<html><head><meta name="citation_title" content="T"></head>'
                                    '<body><p class="author">A. B</p><div id="abstract">x</div></body></html>', "lxml")).authors_found()
