"""IUCN Red List species assessments on iucnredlist.org (oxjob #2330).

The stored pages are the site's JavaScript app shell (an empty div#redlist-js): the assessment itself is never in the
markup, only the citation_* meta tags. Each citation_author tag carries the assessor's affiliation in a closing
parenthetical ("Nigel Taylor (RBG Kew)"), which the generic reader keeps inside the name. The site parser splits it
off, as both blind labellers do (label-v1), and drops placeholder e-mail addresses the site writes as authors.
Markup is cut down from stored sample pages.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.iucn_red_list import IUCNRedList

URL = "https://www.iucnredlist.org/species/152170/605372"


def _page(authors, journal="IUCN Red List of Threatened Species", canonical=URL,
          og_url="https://www.iucnredlist.org/en"):
    metas = "".join(f"<meta content='{a}' name='citation_author'>" for a in authors)
    return (
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
        "<meta content='IUCN Red List of Threatened Species' property='og:site_name'>"
        f"<meta content='{og_url}' property='og:url'>"
        "<meta content='Established in 1964, the IUCN Red List of Threatened Species has evolved to become the "
        "world&#8217;s most comprehensive information source on the global conservation status of animal, fungi "
        "and plant species.' property='og:description'>"
        f"<link href='{canonical}' rel='canonical'>"
        "<meta content='IUCN Red List of Threatened Species: Melocactus matanzanus' name='citation_title'>"
        f"{metas}<meta content='{journal}' name='citation_journal_title'>"
        "<meta content='2011/07/26' name='citation_publication_date'></head>"
        "<body class='page-content'><div id='content'><main><div id='redlist-js'></div></main></div></body></html>"
    )


def _authors(html):
    return parse_page(html.encode(), "doi", URL)["authors"]


def _soup(html):
    return BeautifulSoup(html, parser="lxml", features="lxml")


def test_assessors_split_from_their_affiliations():
    html = _page(["Nigel Taylor (RBG Kew)",
                  "Luis Roberto González-Torres (IUCN SSC Cuban Plant Specialist Group)",
                  "Duniel Barrios (Jardín Botánico Nacional, Universidad de La Habana, Cuba)"])
    authors = _authors(html)
    assert [a["name"] for a in authors] == ["Nigel Taylor", "Luis Roberto González-Torres", "Duniel Barrios"]
    assert [[f["name"] for f in a["affiliations"]] for a in authors] == [
        ["RBG Kew"], ["IUCN SSC Cuban Plant Specialist Group"],
        ["Jardín Botánico Nacional, Universidad de La Habana, Cuba"]]


def test_author_without_parenthetical_keeps_no_affiliation():
    authors = _authors(_page(["Liliana M. Davalos", "Adrian Tejedor (Museo Nacional de Historia Natural)"]))
    assert [a["name"] for a in authors] == ["Liliana M. Davalos", "Adrian Tejedor"]
    assert [len(a["affiliations"]) for a in authors] == [0, 1]


def test_group_whose_parenthetical_repeats_its_name_has_no_affiliation():
    authors = _authors(_page(["BirdLife International (BirdLife International)"]))
    assert [(a["name"], a["affiliations"]) for a in authors] == [("BirdLife International", [])]


def test_group_whose_parenthetical_is_part_of_its_name_has_no_affiliation():
    authors = _authors(_page(["IUCN SSC Amphibian Specialist Group (IUCN SSC)"]))
    assert [(a["name"], a["affiliations"]) for a in authors] == [("IUCN SSC Amphibian Specialist Group", [])]


def test_region_taxon_group_project_or_role_is_not_an_affiliation():
    # what assessors also put in the parenthetical; both blind labellers give these authors no affiliation
    authors = _authors(_page(["Dirk Van Damme (Europe, North Africa, Africa)", "M Weksler (South American Marsupials)",
                              "Francesca Cassola (Global Mammal Assessment)",
                              "Gianbattista Nardi (European Red List: terrestrial mollusc assessor)"]))
    assert [a["name"] for a in authors] == ["Dirk Van Damme", "M Weksler", "Francesca Cassola", "Gianbattista Nardi"]
    assert all(a["affiliations"] == [] for a in authors)


def test_specialist_groups_and_red_list_authorities_are_affiliations():
    authors = _authors(_page(["Konstantinos Triantis (IUCN SSC Mollusc Specialist Group)",
                              "Rémy Amice (New-Caledonia Plant RLA)", "Emily Beech (IUCN SSC Global Tree SG / BGCI)"]))
    assert [[f["name"] for f in a["affiliations"]] for a in authors] == [
        ["IUCN SSC Mollusc Specialist Group"], ["New-Caledonia Plant RLA"], ["IUCN SSC Global Tree SG / BGCI"]]


def test_nested_parentheses_split_at_the_last_balanced_group():
    group = "Botanic Gardens Conservation International (BGCI)"
    authors = _authors(_page([f"{group} ({group}, Descanso House, 199 Kew Road, Richmond TW9 3BW, England)"]))
    assert [a["name"] for a in authors] == [group]
    assert [f["name"] for f in authors[0]["affiliations"]] == [
        f"{group}, Descanso House, 199 Kew Road, Richmond TW9 3BW, England"]


def test_placeholder_email_author_is_dropped():
    group = "Botanic Gardens Conservation International (BGCI)"
    authors = _authors(_page(["false.email@globaltrees.org", f"{group} ({group}, Richmond, England)"]))
    assert [a["name"] for a in authors] == [group]


def test_no_corresponding_mark_and_no_abstract():
    out = parse_page(_page(["Nelson Zamora (Museo Nacional de Costa Rica, Herbario Nacional de Costa Rica)"]).encode(),
                     "doi", URL)
    assert not any(a["is_corresponding"] for a in out["authors"])
    assert out["abstract"] is None  # og:description is the site's blurb, not the assessment's


def test_parse_returns_none_of_the_new_fields():
    parsed = IUCNRedList(_soup(_page(["Nigel Taylor (RBG Kew)"]))).parse()
    assert not parsed.get("acknowledgments") and not parsed.get("funding_statement") and not parsed.get("references")


def test_lookalike_page_from_another_site_is_not_claimed():
    # a journal page with the same "Name (Affiliation)" citation_author habit
    html = _page(["Ana Silva (Universidade de Lisboa)"], journal="Revista de Biologia",
                 canonical="https://revista.example.org/article/view/123", og_url="https://revista.example.org/")
    parser = IUCNRedList(_soup(html))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    assert [a["name"] for a in parse_page(html.encode(), "doi", "https://revista.example.org/article/view/123")[
        "authors"]] == ["Ana Silva (Universidade de Lisboa)"]


def test_journal_title_alone_does_not_claim_a_page_off_the_site():
    html = _page(["Ana Silva (Universidade de Lisboa)"], canonical="https://mirror.example.org/species/1/2")
    assert not IUCNRedList(_soup(html)).is_publisher_specific_parser()


def test_one_tag_naming_several_assessors_is_split():
    authors = _authors(_page(["Sheppard, A., Fenner, D., Edwards, A., Abrar, M. & Ochavillo, D."]))
    assert [(a["name"], a["affiliations"]) for a in authors] == [
        ("A. Sheppard", []), ("D. Fenner", []), ("A. Edwards", []), ("M. Abrar", []), ("D. Ochavillo", [])]
    assert [a["name"] for a in _authors(_page(["Moelants, T., Contreras-MacBeath, T. & Van Damme, D."]))] == [
        "T. Moelants", "T. Contreras-MacBeath", "D. Van Damme"]


def test_names_with_an_ampersand_that_are_not_a_cited_list_stay_whole():
    authors = _authors(_page(["Allen Allison (Global Amphibian, Reptile & Mammal Assessments / Bishop Museum, Hawaii)",
                              "Fauna & Flora International"]))
    assert [a["name"] for a in authors] == ["Allen Allison", "Fauna & Flora International"]
