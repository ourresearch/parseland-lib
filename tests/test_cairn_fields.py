"""Cairn.info reference lists (oxjob #2268).

Markup is cut down from stored Cairn pages (16 Nov 2026, #2268 sample). Both of Cairn's templates print the reference
list the same way: <section id="decoupe-bibliographie"> with one <li class="refbiblio" id="rbN"> per entry, numbered
from rb1. The old template (www.cairn.info) puts the byline in div.auteur, which cairn.py already reads; the current one
(shs. / stm. / droit.cairn.info) prints the byline without markup, so its authors and abstract stay the generic
parser's (citation_* meta tags) and only the reference list is new.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.cairn import CAIRN

OLD_URL = "https://www.cairn.info/revue-pouvoirs-2005-4-page-41.htm"
NEW_URL = "https://shs.cairn.info/navigation-2025-1-page-87?lang=fr"


def _biblio(items, heading="Bibliographie"):
    lis = "".join(f'<li class="refbiblio" id="rb{i}"><!--placeholder::reference::rb{i}-->{t}</li>'
                  for i, t in items)
    head = f'<h1 class="titre traitementparticulier-non">{heading}</h1>' if heading else ""
    return (f'<section id="decoupe-bibliographie"><div class="biblio profondeur-1">{head}'
            f'<ul class="wrapper-children-biblio">{lis}</ul></div></section>')


def _old_page(body, og_url=OLD_URL):
    return (f'<html><head><meta property="og:url" content="{og_url}"/>'
            '<meta name="citation_title" content="Un titre"/><meta name="citation_author" content="Alain Chenal"/>'
            '</head><body><div class="auteur typeaut-auteur"><div class="nompers"><span class="prenom">Alain</span> '
            '<span class="nomfamille">Chenal</span></div><div class="affiliation">Maître de conférences en droit '
            f'public à l’université Paris X-Nanterre</div></div>{body}</body></html>')


def _new_page(body, og_url=NEW_URL):
    return (f'<html><head><meta property="og:url" content="{og_url}"/>'
            '<meta property="og:site_name" content="SHS Cairn.info"/>'
            '<meta name="citation_title" content="Un titre"/><meta name="citation_author" content="Abdulazez Alamim"/>'
            '</head><body><ul><li><span class="font-normal">Par</span> <a href="#">Abdulazez Alamim</a></li></ul>'
            f'<div id="article-biblio">{body}</div></body></html>')


REFS = [(1, "Didier Billion (dir.), <em>La Turquie vers un rendez-vous décisif</em>, IRIS/PUF, 2004."),
        (2, '<a class="btn btn-default btn-xs reference-vers-autre-contenu typef-b" '
            'href="./numero.php?ID_NUMPUBLIE=DEC_BOZAR_2016_01"><span class="icon-cairn"></span> En ligne</a>'
            "Hamit Bozarslan, <em>Histoire de la Turquie contemporaine</em>, La Découverte, 2004."),
        (3, "Élise Massicard, <em>L’Autre Turquie</em>, PUF, 2005.")]


def _parse(html):
    return CAIRN(BeautifulSoup(html, "lxml")).parse()


def test_old_template_reference_list_is_read_whole():
    out = _parse(_old_page(_biblio(REFS)))
    assert [r["position"] for r in out["references"]] == [1, 2, 3]
    assert out["references"][0]["raw"] == ("Didier Billion (dir.), La Turquie vers un rendez-vous décisif, "
                                            "IRIS/PUF, 2004.")
    assert out["references_complete"] is True


def test_en_ligne_button_is_not_part_of_the_reference():
    out = _parse(_old_page(_biblio(REFS)))
    assert out["references"][1]["raw"] == "Hamit Bozarslan, Histoire de la Turquie contemporaine, La Découverte, 2004."


def test_old_template_byline_is_unchanged():
    out = parse_page(_old_page(_biblio(REFS)).encode(), "doi", OLD_URL)
    assert [a["name"] for a in out["authors"]] == ["Alain Chenal"]
    assert out["authors"][0]["affiliations"][0]["name"].startswith("Maître de conférences")


def test_reference_text_is_kept_as_printed():
    # French spacing before a colon stays; a line break in the markup is one space
    items = [(1, "Dahan, J. ; Schonen, E. (de) 2000. <em>Se séparer sans se déchirer. La médiation\nfamiliale : "
                 "renouer le dialogue</em>, Paris, Robert Laffont.")]
    raw = _parse(_old_page(_biblio(items)))["references"][0]["raw"]
    assert raw == ("Dahan, J. ; Schonen, E. (de) 2000. Se séparer sans se déchirer. La médiation familiale : "
                   "renouer le dialogue, Paris, Robert Laffont.")


def test_heading_printed_as_first_entry_is_skipped():
    items = [(1, "BIBLIOGRAFÍA")] + [(i + 1, t) for i, t in REFS]
    out = _parse(_old_page(_biblio(items, heading=None)))
    assert len(out["references"]) == 3
    assert out["references"][0]["raw"].startswith("Didier Billion")
    assert out["references_complete"] is True


def test_gap_in_numbering_is_not_whole():
    items = [REFS[0], (3, REFS[2][1])]
    out = _parse(_old_page(_biblio(items)))
    assert len(out["references"]) == 2
    assert out["references_complete"] is False


def test_doi_link_and_printed_doi():
    items = [(1, 'Bates, M., Information Seeking, <a href="https://doi.org/10.1177/0165551520950000">'
                 'https://doi.org/10.1177/0165551520950000</a>, 2022.'),
             (2, "Crawford, K., Governance, MIT Press, 2024, doi: 10.7551/mitpress/1234.001.0001.")]
    refs = _parse(_old_page(_biblio(items)))["references"]
    assert refs[0]["doi"] == "10.1177/0165551520950000"
    assert refs[1]["doi"] == "10.7551/mitpress/1234.001.0001"


def test_page_without_reference_list_has_no_reference_keys():
    out = _parse(_old_page(""))
    assert "references" not in out
    assert "references_complete" not in out


def test_new_template_reference_list_is_read():
    html = _new_page(_biblio([(1, "Bates, M., Information Seeking in the Age of AI, 2022."),
                              (2, "Crawford, K., Governance in the Age of Generative AI, MIT Press, 2024.")],
                             heading="Bibliography"))
    soup = BeautifulSoup(html, "lxml")
    parser = CAIRN(soup)
    assert parser.is_publisher_specific_parser() and parser.authors_found()
    out = parser.parse()
    assert [r["raw"] for r in out["references"]][1] == "Crawford, K., Governance in the Age of Generative AI, MIT Press, 2024."
    assert out["references_complete"] is True


def test_new_template_authors_stay_the_meta_tags():
    html = _new_page(_biblio([(1, "Bates, M., Information Seeking in the Age of AI, 2022.")]))
    out = parse_page(html.encode(), "doi", NEW_URL)
    assert [a["name"] for a in out["authors"]] == ["Abdulazez Alamim"]
    assert not any(a["affiliations"] for a in out["authors"])


def test_new_template_without_reference_list_is_not_taken():
    parser = CAIRN(BeautifulSoup(_new_page(""), "lxml"))
    assert not parser.authors_found()


def test_lookalike_from_another_site_is_not_claimed():
    # same reference-list and byline markup, on an OpenEdition journal page: not Cairn's
    html = _old_page(_biblio(REFS), og_url="https://journals.openedition.org/pole/1234")
    parser = CAIRN(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert "references" not in parser.parse()
    new = CAIRN(BeautifulSoup(_new_page(_biblio(REFS), og_url="https://journals.openedition.org/pole/1234"), "lxml"))
    assert not new.authors_found()
