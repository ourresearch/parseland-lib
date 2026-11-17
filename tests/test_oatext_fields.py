"""OA Text (oatext.com) article pages (oxjob #2339).

Markup is cut down from stored oatext.com pages (17 Nov 2026). The site writes no citation_* meta tags; its byline is
one Foundation pop-up per author (the pop-up holds the affiliations and an e-mail line), the "Author Info" tab names
the corresponding author, and the "Article" tab ends with a "References" heading over one <ol>.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.oatext import OAText

URL = "https://doi.org/10.15761/xyz.1000100"
KEYWORDS = '<meta name="keywords" content="OA Text, OAT, Open Access Text, OAtext, OATEXT oatext, oat, open access text" />'


def _author(i, name, lines, email="bhuvaneswari.bibleraaj@uhsm.nhs.uk", tip_class="tool-tip f-dropdown custom-tooltip-content"):
    affs = "".join(f'<p class="mb5">{line}</p>' for line in lines)
    return (f'<div data-dropdown="a{i}" data-options="is_hover:false" class="custom-tootip-head">'
            f'<p class="pt5 mb10 f14 author-title"><i class="fa fa-dot-circle-o pr5"></i> {name} </p></div>'
            f'<div id="a{i}" class="{tip_class}" data-dropdown-content>{affs}'
            f'<p><i class="fa fa-envelope-o"></i> E-mail : <a href="mailto:{email}">{email}</a></p></div>')


def _page(byline, author_info="", article="", keywords=KEYWORDS, prefix=""):
    return (f"<!doctype html><html class=\"no-js\" lang=\"en\"><head><title>A title</title>"
            f"<meta charset=\"utf-8\" />{keywords}"
            f"<meta name=\"description\" content=\"OA Text is an independent open-access scientific publisher\" />"
            f"</head><body><div class=\"inner-page\"><div class=\"row\"><div class=\"large-8 columns\">"
            f"<div class=\"inner-left\"><h2 class=\"w600\"> A title </h2>{byline}"
            f"<p class=\"mt10\">DOI: 10.15761/XYZ.1000100 </p><div class=\"custom-horizontal\"><div class=\"tabs-content\">"
            f"<div id=\"{prefix}Article\" class=\"content active\"><div class=\"text-justify\">{article}</div></div>"
            f"<div id=\"{prefix}Article_Info\" class=\"content\"><h4>Article Type</h4><p>Research Article</p></div>"
            f"<div id=\"{prefix}Author_Info\" class=\"content\">{author_info}</div>"
            f"</div></div></div></div></div></div></body></html>")


def _corresponding(*entries):
    """entries: (name, address) pairs, as the Author Info tab prints them."""
    out = '<h4 class="mb10"><span class="">Corresponding author</span></h4>'
    for i, (name, address) in enumerate(entries):
        out += ("<hr/>" if i else "") + (f'<h4 class="mb10"><span class="black-text">{name}</span></h4>'
                                         f"<p>{address}</p><p><i class=\"fa fa-envelope-o\"></i> E-mail : x@y.org</p>")
    return out


BYLINE = (_author(1, "Ana Silva", ["Department of Biology, University of Somewhere, Lisbon, Portugal"])
          + _author(2, "Ben Okafor", ["Faculty of Medicine, Lagos State University, Lagos, Nigeria"]))


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _raw(html):
    return OAText(BeautifulSoup(html, parser="lxml", features="lxml")).parse()


def test_byline_names_and_popup_affiliations():
    out = _parse(_page(BYLINE, _corresponding(("Ana Silva", "Department of Biology, University of Somewhere, Portugal"))))
    assert [a["name"] for a in out["authors"]] == ["Ana Silva", "Ben Okafor"]
    assert out["authors"][0]["affiliations"] == [{"name": "Department of Biology, University of Somewhere, Lisbon, Portugal"}]
    assert out["authors"][1]["affiliations"] == [{"name": "Faculty of Medicine, Lagos State University, Lagos, Nigeria"}]


def test_popup_lines_split_on_br_and_correspondence_line_dropped():
    byline = _author(1, "Ana Silva", ["Institute of Physics, University of Somewhere, Portugal <br/>\n<br/>\n"
                                      "Hospital Santa Maria, Lisbon, Portugal",
                                      "Correspondence to: Ana Silva, Institute of Physics, University of Somewhere"])
    authors = _raw(_page(byline))["authors"]
    assert authors[0]["affiliations"] == ["Institute of Physics, University of Somewhere, Portugal",
                                          "Hospital Santa Maria, Lisbon, Portugal"]


def test_corresponding_author_from_author_info_initials_form():
    out = _parse(_page(BYLINE, _corresponding(("Okafor B", "Faculty of Medicine, Lagos State University, Nigeria"))))
    assert [a["is_corresponding"] for a in out["authors"]] == [False, True]


def test_corresponding_name_with_degrees_and_two_corresponding_authors():
    info = _corresponding(("Dr. Ana Silva, MD, PhD", "Department of Biology, University of Somewhere, Portugal"),
                          ("Pr. Ben Okafor", "Faculty of Medicine, Lagos State University, Nigeria"))
    assert [a["is_corresponding"] for a in _raw(_page(BYLINE, info))["authors"]] == [True, True]


def test_corresponding_name_not_on_byline_marks_nobody():
    out = _parse(_page(BYLINE, _corresponding(("Kemal Aydin", "Elazig Training Hospital, Turkey"))))
    assert not any(a["is_corresponding"] for a in out["authors"])


def test_corresponding_label_and_name_in_one_unclosed_heading():
    info = ('<h4 class="mb10"><span class="">Corresponding author</span>'
            '<h4 class="mb10"><span class="black-text">Ana Silva</span></h4></h4><p>Rua Augusta 10, Lisbon, Portugal</p>')
    assert [a["is_corresponding"] for a in _raw(_page(BYLINE, info))["authors"]] == [True, False]


def test_correspondence_address_at_another_institution_is_a_second_affiliation():
    info = _corresponding(("Ana Silva", "Department of Intensive Medicine, University Medical Center Ljubljana, "
                                        "Slovenia, Tel: +386 1 522 5050"))
    assert _raw(_page(BYLINE, info))["authors"][0]["affiliations"] == [
        "Department of Biology, University of Somewhere, Lisbon, Portugal",
        "Department of Intensive Medicine, University Medical Center Ljubljana, Slovenia"]


def test_correspondence_address_of_the_same_institution_or_a_bare_street_is_not_added():
    same = _corresponding(("Ana Silva", "University of Somewhere, Lisbon, Portugal, Tel: 403.220.5278"))
    street = _corresponding(("Ana Silva", "5 East 98th St, 4th Floor, New York, NY 10029, USA"))
    for info in (same, street):
        assert _raw(_page(BYLINE, info))["authors"][0]["affiliations"] == [
            "Department of Biology, University of Somewhere, Lisbon, Portugal"]


def test_older_template_with_journal_prefixed_tabs_and_plain_popup_paragraphs():
    byline = _author(1, "Rossi G", ["Department of Cardiology, Policlinico Hospital, Milan, Italy"],
                     tip_class="tool-tip f-dropdown").replace('<p class="mb5">', "<p>")
    out = _parse(_page(byline, _corresponding(("Giulia Rossi", "Policlinico Hospital, Milan, Italy")), prefix="JIC_"))
    assert out["authors"] == [{"name": "Rossi G", "affiliations": [
        {"name": "Department of Cardiology, Policlinico Hospital, Milan, Italy"}], "is_corresponding": True}]


REFS = ("<h2>References</h2><ol>"
        "<li>Rietschel E (1994) Bacterial endotoxin. <em>FASEB J</em> 8: 217-225.</li>"
        "<li>Raetz C (2000) Lipopolysaccharide endotoxins. <em>Annu Rev Biochem</em> 71: 635-670. "
        '<a href="http://www.ncbi.nlm.nih.gov/pubmed/12045108" target="_blank">[Crossref]</a></li>'
        "<li>Chou KC (2015) Impacts of bioinformatics. <em>Med Chem</em> 11: 218-234. doi: 10.2174/1573406411666141229162834</li>"
        "\n2021 Copyright OAT. All rights reserv\n</ol>")


def test_reference_list_whole_with_dois_and_no_link_labels():
    out = _raw(_page(BYLINE, article="<h2>Abstract</h2><p>Text.</p>" + REFS))
    assert [r["position"] for r in out["references"]] == [1, 2, 3]
    assert out["references"][1]["raw"] == "Raetz C (2000) Lipopolysaccharide endotoxins. Annu Rev Biochem 71: 635-670."
    assert [r["doi"] for r in out["references"]] == [None, None, "10.2174/1573406411666141229162834"]
    assert out["references_complete"] is True


def test_reference_text_after_the_list_is_not_whole():
    article = REFS + "<p>Tune JD, Richmond KN (2002) Control of coronary blood flow. Am J Physiol 2: 3-4.</p>"
    out = _raw(_page(BYLINE, article=article))
    assert len(out["references"]) == 3 and out["references_complete"] is False


def test_unnumbered_list_is_not_whole():
    article = "<h2>References</h2><ul><li>Rietschel E (1994) Bacterial endotoxin. FASEB J 8: 217-225.</li></ul>"
    out = _raw(_page(BYLINE, article=article))
    assert len(out["references"]) == 1 and out["references_complete"] is False


def test_abstract_and_back_matter_left_to_shared_readers():
    abstract = ("Lipopolysaccharide is an integral part of the cell wall of Gram negative bacteria. It is a complex "
                "molecule that is involved in a variety of functions both related to the cell and its environment.")
    article = (f"<h2>Abstract</h2><p>{abstract}</p><h2>Key Words</h2><p>Endotoxin, Lipid A</p>"
               "<h2>Introduction</h2><p>Body text.</p><h2>Acknowledgements</h2>"
               "<p>The authors thank the members of the laboratory for their help.</p>" + REFS)
    page = _page(BYLINE, article=article)
    raw = _raw(page)
    assert raw["abstract"] is None and raw["acknowledgments"] is None and raw["funding_statement"] is None
    out = _parse(page)
    assert out["abstract"] == abstract
    assert out["acknowledgments"] == "The authors thank the members of the laboratory for their help."


def test_lookalike_foundation_popup_byline_from_another_site_is_not_claimed():
    other = '<meta name="keywords" content="journals, medicine, open access" />'
    soup = BeautifulSoup(_page(BYLINE, _corresponding(("Ana Silva", "Lisbon")), keywords=other),
                         parser="lxml", features="lxml")
    parser = OAText(soup)
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
