"""Fortune Journals article pages (fortunejournals.com; oxjob #2339).

Markup is cut down from stored pages (17 Nov 2026): article.fullTextBody holds the title, the byline as the first
<p><strong> (after an "Article Information" heading on older pages), one <p> per affiliation led by its <sup> key, a
"*Corresponding Author:" line and, at the end, "References" over one <ol>. Names below are made up.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.fortunejournals import FortuneJournals

URL = "https://www.fortunejournals.com/articles/a-study.html"
ABSTRACT = ("Background of the study and what it set out to measure in a cohort of adult patients. "
            "Methods, results and the conclusion follow in the full text, which this abstract summarises at length.")


def _page(front, back="", publisher="Fortune Journals", older=False):
    info = '<h4 class="sub-title"><span>Article Information</span></h4>' if older else ""
    return (
        "<html><head>"
        f'<meta name="citation_publisher" content="{publisher}" />'
        '<meta name="citation_title" content="A Study">'
        '<meta name="citation_author" content="Ana Silva">'
        '<meta name="description" content="A Study. Open Access Research Article.">'
        "</head><body><div class=\"col-md-6\"><article class=\"blog-grid fullTextBody\">"
        '<div class="heading-v4"><h3>A Study</h3></div>'
        f"{info}{front}"
        "<p><strong>Received: </strong>21 February 2026; <strong>Accepted: </strong>03 March 2026</p>"
        "<p class='citationStyles'><strong>Citation:</strong> Ana Silva. A Study. Journal 10 (2026): 34-48.</p>"
        '<h4 class="sub-title"><span>Abstract</span></h4>'
        f'<div class="abstract-display"><p style="text-align:justify">{ABSTRACT}</p></div>'
        '<h4 class="sub-title"><span>Article Details</span></h4><h4>1. Introduction</h4><p>Text [1].</p>'
        f"{back}</article></div></body></html>"
    )


NUMBERED = (
    "<p><strong>Ana Silva<sup>1,2</sup>, Ben Okoro<sup>1</sup>, Chen Wei<sup>2*</sup></strong></p>"
    "<p><sup>1</sup>Department of Medicine, North University, Springfield, USA</p>"
    "<p><sup>2</sup>Institute of Research, South University, Shelbyville, USA</p>"
    '<p class="correspondingStyles"><strong>*Corresponding author:</strong> Chen Wei, Institute of Research, '
    "South University, Shelbyville, USA.</p>"
)

REFERENCES = (
    "<h4>References</h4><ol>"
    "<li>Doe J, Roe R. A first paper. Journal A 1 (2020): 1-9.</li>"
    "<li>Poe P. A second paper. Journal B 2 (2021): 10-19. doi: 10.1000/abc.123</li>"
    "<li>Moe M, et al. A third paper. Journal C 3 (2022): 20-29.</li>"
    "</ol>"
)


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _affs(author):
    return [a["name"] for a in author["affiliations"]]


def test_numbered_byline_links_each_author_to_their_affiliations():
    authors = _parse(_page(NUMBERED))["authors"]
    assert [a["name"] for a in authors] == ["Ana Silva", "Ben Okoro", "Chen Wei"]
    assert _affs(authors[0]) == ["Department of Medicine, North University, Springfield, USA",
                                 "Institute of Research, South University, Shelbyville, USA"]
    assert _affs(authors[1]) == ["Department of Medicine, North University, Springfield, USA"]
    assert _affs(authors[2]) == ["Institute of Research, South University, Shelbyville, USA"]


def test_starred_author_is_corresponding_when_the_page_explains_the_star():
    authors = _parse(_page(NUMBERED))["authors"]
    assert [a["is_corresponding"] for a in authors] == [False, False, True]


def test_bare_star_without_a_corresponding_note_marks_no_one():
    front = NUMBERED.split('<p class="correspondingStyles">')[0]
    authors = _parse(_page(front))["authors"]
    assert not any(a["is_corresponding"] for a in authors)


def test_older_layout_one_unkeyed_affiliation_for_every_author_and_glued_star():
    front = ("<p><strong>Ana Silva and Ben Okoro*</strong></p>"
             "<p>Department of Medicine, North University, Springfield, USA</p>"
             "<p><strong><sup>*</sup>Corresponding Author:</strong> Ben Okoro, Department of Medicine, "
             "North University, Springfield, USA</p>")
    authors = _parse(_page(front, older=True))["authors"]
    assert [a["name"] for a in authors] == ["Ana Silva", "Ben Okoro"]
    assert all(_affs(a) == ["Department of Medicine, North University, Springfield, USA"] for a in authors)
    assert [a["is_corresponding"] for a in authors] == [False, True]


def test_corresponding_by_name_when_the_byline_has_no_star():
    front = ("<p><strong>Ana Silva, Ben Okoro</strong></p>"
             "<p>Department of Medicine, North University, Springfield, USA</p>"
             '<p class="correspondingStyles"><strong>*Corresponding author:</strong> Dr. Ben Okoro, Department of '
             "Medicine, North University, Springfield, USA.</p>")
    authors = _parse(_page(front))["authors"]
    assert [a["is_corresponding"] for a in authors] == [False, True]


def test_split_strong_tags_letter_keys_star_first_and_degrees_are_not_authors():
    front = ("<p><strong>Ana </strong><strong>Silva</strong><strong><sup>*,a</sup></strong><strong>, "
             "Ben Okoro, MD, MPH<sup>b</sup>, </strong><strong>Chen Wei PhD<sup>a</sup><sup>,b</sup></strong></p>"
             "<p><sup>a</sup>Department of Medicine, North University, Springfield, USA</p>"
             "<p><sup>b</sup>Institute of Research, South University, Shelbyville, USA</p>"
             "<p><strong>*Corresponding author: </strong>Ana Silva, North University.</p>")
    authors = _parse(_page(front))["authors"]
    assert [a["name"] for a in authors] == ["Ana Silva", "Ben Okoro", "Chen Wei"]
    assert _affs(authors[0]) == ["Department of Medicine, North University, Springfield, USA"]
    assert _affs(authors[1]) == ["Institute of Research, South University, Shelbyville, USA"]
    assert len(_affs(authors[2])) == 2
    assert [a["is_corresponding"] for a in authors] == [True, False, False]


def test_two_affiliations_in_one_paragraph_and_a_superscript_inside_the_text():
    front = ("<p><strong>Ana Silva<sup>1-2*</sup>, Ben Okoro<sup>2</sup></strong></p>"
             "<p><sup>1</sup>Department of Medicine, North University, USA<br/> <sup>2</sup>5<sup>th</sup> year "
             "student, South University, USA</p>"
             '<p class="correspondingStyles"><strong><sup>*</sup>Corresponding Author: </strong>Ana Silva.</p>')
    authors = _parse(_page(front))["authors"]
    assert _affs(authors[0]) == ["Department of Medicine, North University, USA", "5th year student, South University, USA"]
    assert _affs(authors[1]) == ["5th year student, South University, USA"]


def test_several_unkeyed_affiliations_go_to_every_author():
    front = ("<p><strong>Ana Silva, Ben Okoro<sup>*</sup></strong></p>"
             "<p>Department of Medicine, North University, Springfield, USA</p>"
             "<p>Institute of Research, South University, Shelbyville, USA</p>"
             '<p class="correspondingStyles"><strong>*Corresponding author:</strong> Ben Okoro.</p>')
    authors = _parse(_page(front))["authors"]
    assert all(len(_affs(a)) == 2 for a in authors)


def test_degree_abbreviations_between_commas_are_not_authors():
    front = ("<p><strong>Ana Silva, MD, MHS<sup>1*</sup>, Ben Okoro, FACC<sup>1</sup></strong></p>"
             "<p><sup>1</sup>Department of Medicine, North University, Springfield, USA</p>"
             '<p class="correspondingStyles"><strong>*Corresponding author:</strong> Ana Silva.</p>')
    authors = _parse(_page(front))["authors"]
    assert [a["name"] for a in authors] == ["Ana Silva", "Ben Okoro"]
    assert [a["is_corresponding"] for a in authors] == [True, False]


def test_2026_redesign_card_is_read():
    html = _page("").replace('<article class="blog-grid fullTextBody">', '<article class="ft-card"><div class="ft-body">'
                             + NUMBERED + "<p><strong>Received: </strong>10 August 2026</p></div>")
    authors = _parse(html)["authors"]
    assert [a["name"] for a in authors] == ["Ana Silva", "Ben Okoro", "Chen Wei"]
    assert _affs(authors[1]) == ["Department of Medicine, North University, Springfield, USA"]


def test_abstract_is_still_read():
    assert _parse(_page(NUMBERED))["abstract"] == ABSTRACT


def test_reference_list_is_read_whole_with_dois():
    soup = BeautifulSoup(_page(NUMBERED, REFERENCES), "lxml")
    out = FortuneJournals(soup).parse()
    assert [r["position"] for r in out["references"]] == [1, 2, 3]
    assert out["references"][0]["raw"] == "Doe J, Roe R. A first paper. Journal A 1 (2020): 1-9."
    assert out["references"][1]["doi"] == "10.1000/abc.123"
    assert out["references"][0]["doi"] is None
    assert out["references_complete"] is True


def test_reference_list_in_a_strong_label_inside_a_paragraph():
    back = REFERENCES.replace("<h4>References</h4>", "<p>Last sentence [3].<br/><strong>References</strong></p>")
    out = FortuneJournals(BeautifulSoup(_page(NUMBERED, back), "lxml")).parse()
    assert len(out["references"]) == 3 and out["references_complete"] is True


def test_list_that_starts_past_one_is_not_whole():
    out = FortuneJournals(BeautifulSoup(_page(NUMBERED, REFERENCES.replace("<ol>", '<ol start="4">')), "lxml")).parse()
    assert len(out["references"]) == 3 and out["references_complete"] is False


def test_lookalike_page_from_another_publisher_is_not_claimed():
    html = _page(NUMBERED, REFERENCES, publisher="Another Press")
    parser = FortuneJournals(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    assert not any(a["affiliations"] for a in _parse(html)["authors"])


def test_page_without_the_article_block_is_not_read():
    html = _page(NUMBERED).replace('class="blog-grid fullTextBody"', 'class="blog-grid"')
    assert not FortuneJournals(BeautifulSoup(html, "lxml")).authors_found()

