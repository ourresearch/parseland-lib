"""JSTOR pages (www.jstor.org/stable/...) (oxjob #2239, phase 2).

Markup is cut down from stored JSTOR pages (random sample of 15 Nov 2026). No parser claimed them, so they parsed with
no authors. The gate's dev gold (v1.3) decides what is right:
- a journal item's page credits its authors in the byline, a review's in "Review by:", and an unrendered page only in
  its citation description ("Authors, Title, Journal, Vol. ..., pp. ...");
- a book's page carries schema.org Book JSON-LD with the book's authors and blurb, and most stored book pages were
  fetched for one CHAPTER of the book (JSTOR turns a chapter request away to the book: "?turn_away=true"). Gold gives
  such a page no authors and no abstract, and the HTML is the same whichever DOI it was fetched for, so a book page
  gives nothing.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.jstor import JSTOR

ASSETS = '<link rel="stylesheet" href="//www.jstor.org/assets/global_20230602T182841/build/global/css/global.css"/>'
ARTICLE_URL = "https://www.jstor.org/stable/3790989?origin=crossref"
JOURNAL_BLURB = ("Political Psychology is an interdisciplinary journal dedicated to the analysis of the "
                 "interrelationships between psychological and political processes. International contributors draw on "
                 "a diverse range of sources, including cognitive psychology, economics, history and sociology.")


def _page(title, description="", body="", head=""):
    meta = (f'<meta name="description" content="{description}"/><meta property="og:description" '
            f'content="{description}"/>') if description else ""
    return (f"<html><head><title> {title} on JSTOR </title>{ASSETS}{meta}{head}</head>"
            f'<body><main id="content" class="content">{body}</main></body></html>')


def _turnaway(title, byline="", extra=""):
    """The rendered page of a journal item, as a reader without access gets it."""
    return f"""<div class="turnaway-content"><div class="turnaway-content__article-summary-info">
        <div class="badge content-type-label" data-qa="content-type"> journal article </div>
        <turnaway-pharos-heading no-margin="true" class="title-font" level="1" preset="5"> {title}
        </turnaway-pharos-heading>
        {byline}
        <div class="turnaway-content__summary row"><div class="columns"><div> Political Psychology </div>
        <div> <turnaway-pharos-link href="/stable/i292662"> Vol. 8, No. 1 (Mar., 1987)</turnaway-pharos-link>,
        pp. 125-138 (14 pages) </div><div> Published By: International Society of Political Psychology </div></div>
        </div></div>
        <div class="turnaway-content__article-information">{extra}
        <turnaway-pharos-heading level="3" preset="2">Journal Information</turnaway-pharos-heading>
        <div class="turnaway-summary-preview"><p class="summary-paragraph">{JOURNAL_BLURB}</p></div></div></div>"""


def _byline(text):
    return f'<div class="author-font">\n                    {text}\n            </div>'


def _parse(html, url=ARTICLE_URL):
    return parse_page(html.encode(), "doi", url)


def _names(html, url=ARTICLE_URL):
    return [a["name"] for a in _parse(html, url)["authors"]]


BOOK_URL = "https://www.jstor.org/stable/jj.36233898?turn_away=true"
BOOK_BLURB = ("Emmanuel Levinas and His Interlocutors follows the conversations the philosopher held with thinkers of "
              "his century. Each chapter sets one exchange in its time and place and asks what it changed in his "
              "thought about responsibility for the other person, and what it left open...")


def _book_page(authors_json):
    """A book's page: an unrendered table of contents plus the book's JSON-LD. The stored HTML is the same whether
    the page was fetched for the book or for one of its chapters."""
    json_ld = ('{"@context":"https://schema.org","@type":"Book","provider":{"@type":"Organization","name":"JSTOR"},'
               '"mainEntityOfPage":"https://www.jstor.org/stable/jj.36233898","url":"https://www.jstor.org/stable/'
               'jj.36233898","name":"Emmanuel Levinas and His Interlocutors",' + authors_json +
               '"description":"' + BOOK_BLURB + '"}')
    body = ('<div id="toc-mount-point"></div><ul class="visuallyhidden"><li><ul>'
            '<li><a href="/stable/jj.36233898.1" aria-hidden="true">Front Matter</a></li>'
            '<li><a href="/stable/pdf/jj.36233898.1.pdf" aria-hidden="true">Download</a></li></ul></li><li><ul>'
            '<li><a href="/stable/jj.36233898.11" aria-hidden="true">Levinas and Buber</a></li>'
            '<li><a href="/stable/pdf/jj.36233898.11.pdf" aria-hidden="true">Download</a></li></ul></li></ul>'
            f'<script type="application/ld+json">{json_ld}</script>')
    return _page("Emmanuel Levinas and His Interlocutors", BOOK_BLURB, body,
                 '<link rel="canonical" href="https://www.jstor.org/stable/jj.36233898">')


def test_byline_names_in_page_order():
    html = _page("Political Participation: A Matter of Community, Stress, Job Autonomy, and Contact",
                 "Shawn M. Burn, Alison M. Konrad, Political Participation: A Matter of Community, Stress, Job Autonomy, "
                 "and Contact, Political Psychology, Vol. 8, No. 1 (Mar., 1987), pp. 125-138",
                 _turnaway("Political Participation: A Matter of Community, Stress, Job Autonomy, and Contact",
                           _byline("Shawn M. Burn and Alison M. Konrad")))
    out = _parse(html)
    assert [a["name"] for a in out["authors"]] == ["Shawn M. Burn", "Alison M. Konrad"]
    assert all(a["affiliations"] == [] and not a["is_corresponding"] for a in out["authors"])
    assert out["abstract"] is None  # the journal's own description is not this article's abstract


def test_byline_of_three_keeps_a_generational_suffix_with_its_name():
    html = _page("The Gray Bat (Myotis grisescens) in Indiana", "",
                 _turnaway("The Gray Bat (Myotis grisescens) in Indiana",
                           _byline("Virgil Brack, Jr., Russell E. Mumford and Virgil R. Holmes")))
    assert _names(html) == ["Virgil Brack, Jr.", "Russell E. Mumford", "Virgil R. Holmes"]


def test_review_credits_the_reviewer_not_the_reviewed_works_authors():
    reviewed = ('<div class="turnaway-content__summary"><div class="mbs" data-qa="reviewed-works"> Reviewed Work: '
                "<cite>Social Structure and Change Vol 1. Theory and Method</cite> by A. M. Shah, B. S. Baviscar, "
                'E. A. Ramaswamy </div><div class="contrib">\n        Review by:\n            Henrike Donner\n   </div>'
                "</div>")
    html = _page("Review: [Untitled]", "Henrike Donner, The Journal of the Royal Anthropological Institute, Vol. 5, "
                 "No. 4 (Dec., 1999), pp. 645-646", _turnaway("Review: [Untitled]", reviewed))
    assert _names(html) == ["Henrike Donner"]


def test_older_template_names_its_blocks_turn_away():
    body = ('<div class="row turnaway-padding turnaway-content-summary-container"><div class="columns mbl small-12">'
            '<div class="turn-away-content__article-summary"><div class="turn-away-content__article-summary-info">'
            '<div class="badge content-type-label" data-qa="content-type"> journal article </div>'
            '<turnaway-pharos-heading class="title-font" level="1" preset="5"> Review: [Untitled] '
            '</turnaway-pharos-heading><div class="turn-away-content__summary"><div class="mbs" '
            'data-qa="reviewed-works"> Reviewed Work: <cite>Antologia de la poesia</cite> by Julio Caillet-Bois </div>'
            '<div class="contrib">\n     Review by:\n       L. L. Barrett\n  </div></div></div></div></div></div>')
    html = _page("Review: [Untitled]", "L. L. Barrett, Hispania, Vol. 29, No. 3 (Aug., 1946), p. 477", body)
    assert _names(html) == ["L. L. Barrett"]


def test_unrendered_page_reads_the_authors_before_the_title_in_its_citation():
    shell = '<div id="cdt" data-content-id="f32cbf9d"></div><div id="turnaway-mount-point"></div>'
    one = _page("On &quot;Describing a World&quot;", "W. H. Werkmeister, On &quot;Describing a World&quot;, Philosophy "
                "and Phenomenological Research, Vol. 11, No. 3 (Mar., 1951), pp. 303-326", shell,
                '<link rel="canonical" href="https://www.jstor.org/stable/2103536" />')
    assert _names(one) == ["W. H. Werkmeister"]
    three = _page("Optimal Commodity Taxation and Tax Reform under Unemployment", "Maurice Marchand, Pierre Pestieau, "
                  "Serge Wibaut, Optimal Commodity Taxation and Tax Reform under Unemployment, The Scandinavian Journal "
                  "of Economics, Vol. 91, No. 3 (Sep., 1989), pp. 547-563", shell)
    assert _names(three) == ["Maurice Marchand", "Pierre Pestieau", "Serge Wibaut"]


def test_item_with_no_author_gives_none():
    shell = '<div id="turnaway-mount-point"></div>'
    unsigned = _page("Can Planes Be Stopped?", "Can Planes Be Stopped?, The Science News-Letter, Vol. 59, No. 14 "
                     "(Apr. 7, 1951), p. 214", shell)
    assert _names(unsigned) == []
    # a title with a name and a comma in it is still the title, not an author
    named_title = _page("Claes Oldenburg: Fireplugs", "Claes Oldenburg: Fireplugs, Design Quarterly, No. 74/75, "
                        "Process and Imagination (1969), pp. 36-43", shell)
    assert _names(named_title) == []
    empty_byline = _page("Front Matter", "Front Matter, The Journal of Aesthetic Education, Vol. 44, No. 3 (Fall 2010), "
                         "pp. i-iv", _turnaway("Front Matter", _byline("")))
    assert _names(empty_byline) == []


def test_unrendered_untitled_review_gives_nothing():
    # "Roger F. Malina, Leonardo, Vol. 24 ...": with no title to anchor on, the citation doesn't say where the
    # reviewer's name ends and the journal's begins
    html = _page("Review: [Untitled]", "Roger F. Malina, Leonardo, Vol. 24, No. 2, Connectivity: Art and Interactive "
                 "Telecommunications (1991), p. 249", '<div id="turnaway-mount-point"></div>')
    assert _names(html) == []


def test_unrendered_titled_review_reads_the_reviewer():
    html = _page("Review: &quot;Rheumatism&quot; and Arthritis", "J. R. Paul, &quot;Rheumatism&quot; and Arthritis, The "
                 "Milbank Memorial Fund Quarterly, Vol. 14, No. 1 (Jan., 1936), pp. 92-98",
                 '<div id="turnaway-mount-point"></div>')
    assert _names(html) == ["J. R. Paul"]


def test_a_part_that_is_not_a_persons_name_gives_nothing():
    html = _page("Report on Standards", "", _turnaway("Report on Standards", _byline(
        "Committee on Standards and Ethics")))
    assert _names(html) == []
    translated = _page("Three Poems", "", _turnaway("Three Poems", _byline("Li Bai and Translated by Ezra Pound")))
    assert _names(translated) == []


def test_book_page_gives_no_authors_and_no_abstract_for_author_strings():
    # stored for chapter 10.2307/jj.36233898.11: the book's author and blurb are not the chapter's
    out = _parse(_book_page('"author":["Hanoch Ben-Pazi"],'), BOOK_URL)
    assert out["authors"] == []
    assert out["abstract"] is None


def test_book_page_gives_no_authors_for_person_objects():
    people = '"author":[{"@type":"Person","name":"COLIN DAVEY"},{"@type":"Person","name":"THOMAS A. LESSER"}],'
    out = _parse(_book_page(people), BOOK_URL)
    assert out["authors"] == []
    assert out["abstract"] is None


def test_chapters_own_unrendered_page_gives_nothing():
    html = _page("Index from Class Matters: Inequality and Exploitation in 21st Century Britain",
                 "Index, Class Matters, pp. 203-214", '<div id="content-viewer-container"></div>',
                 '<link rel="canonical" href="https://www.jstor.org/stable/j.ctvqhtgc.17" />')
    assert _names(html, "https://www.jstor.org/stable/j.ctvqhtgc.17") == []


def test_page_with_no_byline_no_citation_and_no_json_ld():
    assert _names(_page("Bryant Chronology 1858-1864 from The Letters of William Cullen Bryant", "",
                        '<div id="content-viewer-container"></div>')) == []


def test_printed_abstract_is_still_read_beside_the_byline():
    abstract = ("A colony of approximately 400 gray bats was found in Clark Co., Indiana, after both adult males and "
                "reproductive females were captured over nearby Muddy Fork of Silver Creek. This colony is the first "
                "known maternity colony in Indiana and is located in a flooded abandoned limestone quarry.")
    block = ('<turnaway-pharos-heading level="3" preset="2">Abstract</turnaway-pharos-heading>'
             f'<div class="turnaway-summary-preview"><p class="summary-paragraph">{abstract}</p></div>')
    html = _page("The Gray Bat (Myotis grisescens) in Indiana", "", _turnaway(
        "The Gray Bat (Myotis grisescens) in Indiana", _byline("Virgil Brack, Jr. and Russell E. Mumford"), block))
    out = _parse(html)
    assert [a["name"] for a in out["authors"]] == ["Virgil Brack, Jr.", "Russell E. Mumford"]
    assert out["abstract"] == abstract


def test_another_sites_book_page_is_not_claimed():
    # a library catalogue with schema.org Book data, a byline in the same class and a citation-shaped description
    html = ('<html><head><title>A Corpus of Ammonite Inscriptions | Example Library</title>'
            '<link rel="canonical" href="https://catalogue.example.org/record/4411"/>'
            '<meta name="description" content="Walter E. Aufrecht, A Corpus of Ammonite Inscriptions, Example Studies, '
            'Vol. 4 (2019), pp. 1-400"/></head><body><div class="author-font">Walter E. Aufrecht</div>'
            '<script type="application/ld+json">{"@context":"https://schema.org","@type":"Book","name":"A Corpus of '
            'Ammonite Inscriptions","author":["Walter E. Aufrecht"],"provider":{"@type":"Organization","name":'
            '"Example Library"}}</script></body></html>')
    parser = JSTOR(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    assert _names(html, "https://catalogue.example.org/record/4411") == []


def test_a_page_that_only_mentions_jstor_in_its_title_is_not_claimed():
    html = ('<html><head><title>Ten open collections to read on JSTOR</title>'
            '<link rel="canonical" href="https://blog.example.org/ten-collections"/></head>'
            '<body><div class="author-font">Maria Example and John Sample</div></body></html>')
    parser = JSTOR(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
