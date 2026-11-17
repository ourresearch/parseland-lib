"""The Conversation's article pages on theconversation.com (oxjob #2330).

Markup is cut down from stored theconversation.com pages (17 Nov 2026). The pages carry no citation_author tags, so no
parser read their byline. The byline is an "Author(s)" list (name and role line per person) and a one-line synopsis
that gives each name its institution: "A, Inst1, B, C, Inst2" means A is at Inst1, B and C at Inst2. A Q&A piece adds
an "Interviewed" list: those people are not the piece's authors. The description tag is a teaser, never an abstract.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.the_conversation import TheConversation

URL = "https://theconversation.com/sweet-little-lies-maple-syrup-fraud-201343"
OG_URL = "http://theconversation.com/sweet-little-lies-maple-syrup-fraud-201343"


def _group(heading, people):
    items = "".join(
        f'<li class="vcard" itemprop="author" itemscope itemtype="http://schema.org/Person">'
        f'<a href="/profiles/x-1" rel="author"><span class="fn author-name" itemprop="name">\n  {name}\n  </span></a>'
        f'<p class="role">\n  {role}\n  </p></li>' for name, role in people)
    return f'<div class="content-authors-group"><h3 class="border">{heading}</h3><ol>{items}</ol></div>'


def _synopsis(entries):
    parts = [f'<span class="nobr">{e[1:]}</span>' if e.startswith("@") else f'<em class="institution_name">{e}</em>'
             for e in entries]
    return ('<div class="content-authors-synopsis"><a class="content-authors-toggle" href="#">'
            '<i class="icon-caret-down"></i> ' + ", ".join(parts) + "</a></div>")


def _page(groups, synopsis, og_url=OG_URL, site_name="The Conversation"):
    metas = "".join(f'<meta name="author" content="{n}" />' for heading, people in groups if heading.startswith("Author")
                    for n, _ in people)
    return (f'<html><head><meta charset="utf-8" /><title>Sweet little lies</title>'
            f'<meta name="description" content="Maple syrup can often be adulterated with other syrups." />{metas}'
            f'<meta property="og:site_name" content="{site_name}" />'
            f'<meta property="og:title" content="Sweet little lies" />'
            f'<meta property="og:description" content="Maple syrup can often be adulterated with other syrups." />'
            f'<meta property="og:url" content="{og_url}" />'
            f'<meta name="citation_doi" content="10.64628/AAM.9yan4sdnw" /></head><body>'
            f'<article><h1 class="legacy entry-title instapaper_title">Sweet little lies</h1>'
            f'<div class="grid-ten content-body"><p>Maple syrup is Canada&#8217;s liquid gold.</p></div>'
            f'<aside aria-label="Article information"><section class="content-authors">{synopsis}'
            + "".join(_group(h, p) for h, p in groups) +
            '</section><section class="content-disclosure-statement"><h3 class="border">Disclosure statement</h3>'
            '<p><span>Robert Hanner has received funding from the Arrell Food Institute.</span></p></section>'
            '<section class="content-partners"><h3 class="border">Partners</h3><p class="funding-statement">'
            '<a href="https://theconversation.com/institutions/university-of-guelph-1071">University of Guelph</a> '
            'provides funding as a founding partner of The Conversation CA.</p></section></aside></article></body></html>')


SINGLE = _page([("Author", [("Monique Mann", "Vice Chancellor&#8217;s Research Fellow in Regulation of Technology, "
                                              "Queensland University of Technology")])],
               _synopsis(["@Monique Mann", "Queensland University of Technology"]))
SHARED = _page([("Authors", [("Maleeka Singh", "PhD Candidate, Food Science, University of Guelph"),
                             ("Robert Hanner", "Professor, Department of Integrative Biology, University of Guelph")])],
               _synopsis(["@Maleeka Singh", "@Robert Hanner", "University of Guelph"]))
TWO_INSTITUTIONS = _page(
    [("Authors", [("João Stacciarini", "Professor, Instituto Federal Goiano (IF Goiano); Universidade Federal de Goiás (UFG)"),
                  ("Ricardo Assis Gonçalves", "Professor, Universidade Estadual de Goiás (UEG)")])],
    _synopsis(["@João Stacciarini", "Instituto Federal Goiano (IF Goiano)", "Universidade Federal de Goiás (UFG)",
               "@Ricardo Assis Gonçalves", "Universidade Estadual de Goiás (UEG)"]))
INTERVIEW = _page(
    [("Authors", [("Emily Costello", "Director of Collaborations + Local News, The Conversation US"),
                  ("Thalia Plata", "Editor")]),
     ("Interviewed", [("Natasha Mikles", "Assistant Professor in Philosophy and Religious Studies, Texas State University"),
                      ("Seth Winberg", "Executive Director of Brandeis Hillel, Brandeis University")])],
    _synopsis(["@Emily Costello", "The Conversation", "@Thalia Plata", "The Conversation", "@Natasha Mikles",
               "@Seth Winberg"]))


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _soup(html):
    return BeautifulSoup(html, parser="lxml", features="lxml")


def _byline(html):
    return [(a["name"], [x["name"] for x in a["affiliations"]]) for a in _parse(html)["authors"]]


def test_single_author_gets_the_institution_from_the_byline_synopsis():
    assert _byline(SINGLE) == [("Monique Mann", ["Queensland University of Technology"])]


def test_authors_listed_before_one_institution_share_it():
    assert _byline(SHARED) == [("Maleeka Singh", ["University of Guelph"]), ("Robert Hanner", ["University of Guelph"])]


def test_author_with_two_institutions_keeps_both():
    assert _byline(TWO_INSTITUTIONS) == [
        ("João Stacciarini", ["Instituto Federal Goiano (IF Goiano)", "Universidade Federal de Goiás (UFG)"]),
        ("Ricardo Assis Gonçalves", ["Universidade Estadual de Goiás (UEG)"])]


def test_people_interviewed_are_not_authors():
    assert _byline(INTERVIEW) == [("Emily Costello", ["The Conversation"]), ("Thalia Plata", ["The Conversation"])]


def test_no_author_is_marked_corresponding():
    # the pages mark no corresponding author (no label, no envelope, no "Correspondence to")
    assert not any(a["is_corresponding"] for a in _parse(SHARED)["authors"])


def test_teaser_description_is_not_the_parsers_abstract():
    assert TheConversation(_soup(SHARED)).parse()["abstract"] is None


def test_disclosure_and_partner_funding_are_not_the_works_funding_or_acknowledgments():
    # "X receives funding from ..." is a competing-interests disclosure about the author, and the partner note is
    # the outlet's own funding: neither is printed under a funding heading for this work
    out = _parse(SHARED)
    assert out["funding_statement"] is None and out["acknowledgments"] is None and not out["references"]
    parsed = TheConversation(_soup(SHARED)).parse()
    assert not parsed.get("funding_statement") and not parsed.get("acknowledgments") and not parsed.get("references")


def test_page_is_claimed_by_its_og_url():
    parser = TheConversation(_soup(SINGLE))
    assert parser.is_publisher_specific_parser()
    assert parser.authors_found()


def test_page_without_an_author_list_is_left_to_the_generic_parser():
    html = _page([], _synopsis([]))
    parser = TheConversation(_soup(html))
    assert parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_look_alike_page_on_another_host_is_not_claimed():
    # same byline markup and site name, another host
    html = _page([("Author", [("Ana Author", "Lecturer, University of Somewhere")])],
                 _synopsis(["@Ana Author", "University of Somewhere"]),
                 og_url="https://www.example-news.org/an-article-1234")
    parser = TheConversation(_soup(html))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    assert _parse(html)["authors"] == []


def test_page_that_only_links_to_the_conversation_is_not_claimed():
    html = _page([("Author", [("Ana Author", "Lecturer, University of Somewhere")])],
                 _synopsis(["@Ana Author", "University of Somewhere"]),
                 og_url="https://blog.example.edu/repost?from=https://theconversation.com/x-1")
    assert not TheConversation(_soup(html)).is_publisher_specific_parser()
