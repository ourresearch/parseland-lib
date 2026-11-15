"""oxjob #2239 round 5: Ingenta Connect article pages; Zenodo records on InvenioRDM (zenodo.org/records/)."""
import json

from parseland_lib.parse import parse_page

ABSTRACT = "In an effort to guarantee the stable action and photovoltaic absorption capability of the mesh, we model it."


def parse_ingenta(byline, affiliations, abstract=ABSTRACT):
    page = f"""<html><head><meta name="DC.creator" content="Xing, Manjiang"/>
<meta name="IC.identifier" content="asp/jno/2024/00000019/00000002"/></head><body>
<div id="infoArticle"><div class="supMetaData"><p><strong>Authors: </strong>{byline}</p></div></div>
<div id="Abst" class="tab-pane active">{abstract}</div>
<div id="Info"><p><strong>Document Type:</strong> Research Article</p>
<p><strong>Affiliations:</strong> {affiliations}</p></div></body></html>""".encode()
    return parse_page(page, "doi", "https://www.ingentaconnect.com/content/asp/jno/2024/00000019/00000002/art00013")


def author_link(name):
    return (f'<a href="/search;jsessionid=x?option2=author&amp;value2={name.replace(" ", "+")}" '
            f'title="Search for articles by this author">{name}</a>')


def names_and_affiliations(out):
    return [(a["name"], [x["name"] for x in a["affiliations"]]) for a in out["authors"]]


def test_ingenta_one_affiliation_goes_to_every_author():
    out = parse_ingenta(f'{author_link("Xing, Manjiang")}; {author_link("Jiang, Haojie")}',
                        "Graduate School of Kyonggi University, Suwon, South Korea")
    assert names_and_affiliations(out) == [
        ("Manjiang Xing", ["Graduate School of Kyonggi University, Suwon, South Korea"]),
        ("Haojie Jiang", ["Graduate School of Kyonggi University, Suwon, South Korea"])]
    assert out["abstract"] == ABSTRACT


def test_ingenta_numbered_affiliations_follow_the_byline_marks():
    byline = (f'{author_link("Wang, Jianzhou")} <sup> <a href="#aff_1">1</a> </sup> ; '
              f'{author_link("Tong, Weicheng")} <sup> <a href="#aff_2">2</a> </sup>')
    affs = ('<strong id="aff_1">1: </strong> <span id="aff_1_contents"> Yuncheng University, China </span> '
            '<strong id="aff_2">2: </strong> <span id="aff_2_contents"> Wuhan Institute of Technology, China</span>')
    assert names_and_affiliations(parse_ingenta(byline, affs)) == [
        ("Jianzhou Wang", ["Yuncheng University, China"]), ("Weicheng Tong", ["Wuhan Institute of Technology, China"])]


def test_ingenta_no_abstract_placeholder_is_not_an_abstract():
    out = parse_ingenta(author_link("Spener, Maja"), "University of Birmingham, UK", "No Abstract")
    assert [a["name"] for a in out["authors"]] == ["Maja Spener"]
    assert not out["abstract"]


def test_zenodo_records_page_reads_creators_and_no_archive_pdf():
    creators = [{"@type": "Person", "name": "Marisa Mazzotta",
                 "affiliation": [{"@type": "Organization", "name": "US Environmental Protection Agency"}]},
                {"@type": "Person", "name": "Huart, M. C.-L.", "givenName": "M. C.-L.", "familyName": "Huart"},
                {"@type": "Organization", "name": "Not A Person"}]
    ld = {"@context": "http://schema.org", "@type": "ScholarlyArticle", "creator": creators, "name": "A record"}
    page = f"""<html><head><meta property="og:url" content="https://zenodo.org/records/5807860"/>
<script type="application/ld+json">{json.dumps(ld)}</script></head><body>
<a role="button" class="ui compact mini button archive-link" href="https://zenodo.org/api/records/5807860/files-archive">
Download all</a></body></html>""".encode()
    out = parse_page(page, "pmh", "https://zenodo.org/records/5807860")
    assert names_and_affiliations(out) == [
        ("Marisa Mazzotta", ["US Environmental Protection Agency"]), ("Huart, M. C.-L.", [])]
    # InvenioRDM's "Download all" link is a zip of every file, not a PDF
    assert not [u for u in out["urls"] if u["content_type"] == "pdf"]
