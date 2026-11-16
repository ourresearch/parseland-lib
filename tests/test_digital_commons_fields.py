"""Digital Commons (bepress, now Elsevier) item pages (oxjob #2268).

Markup is cut down from stored Digital Commons pages (16 Nov 2026, #2268 template sample). Every item page prints its
fields as <div class="element" id="..."> blocks inside div#alpha and carries bepress_citation_* meta tags. The generic
parser already reads the byline, affiliations and abstract; what no reader took was the "References" field some
journals fill in: one <p> per entry (newer template, h2.field-heading), or one <p> holding the whole pasted list, one
"[n] ..." per line (older template, h4). The look-alike is a Drupal journal page whose metatag module also writes
bepress_citation_* tags.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.digital_commons import DigitalCommons
from parseland_lib.publisher.parsers.generic import GenericPublisherParser

URL = "https://scholarhub.example.edu/journal/vol6/iss2/5/"
ABSTRACT = ("The article discusses the use of wavelet transforms and spline algorithms in the digital processing of "
            "cardiosignals in a number of medical applications, where the sequence of heartbeats is converted into a "
            "power spectrum of fluctuations of the duration of the RR intervals.")
METAS = ('<meta name="bepress_citation_title" content="Spline methods for cardiosignals"/>'
         '<meta name="bepress_citation_author" content="Zaynidinov, Hakimjon"/>'
         '<meta name="bepress_citation_author_institution" content="Tashkent University of Information Technologies"/>'
         '<meta name="bepress_citation_author" content="Yusupov, Ibrohimbek"/>'
         '<meta name="bepress_citation_doi" content="10.51348/tuitmct123"/>'
         f'<meta name="description" content="{ABSTRACT}"/>')

REFS_ONE_PARAGRAPH = ("<div id='references' class='element'>\n<h4>References</h4>\n<p>"
                      "[1] Smolentsev N. K. Osnovi teorii veyvletov. M. : DMK Press, 2008. - 448 s.\n"
                      "[2] Zaynidinov H.N. Methods of reconstructing signals. European journal of computer science, "
                      "Vol.3, No.2, pp.52-59, May 2015.\n"
                      "[3] Singh D., Zaynidinov H. Signal Processing Applications Using Multidimensional Polynomial "
                      "Splines. Springer, 2019. doi:10.1007/978-981-13-2239-6</p>\n</div>")
REFS_ONE_P_EACH = ('<div id="references" class="element"><h2 class="field-heading">References</h2>'
                   '<p>1. Georgii H.O. Gibbs measures and Phase transitions. Walter de Gruyter, Berlin (1992).</p>'
                   '<p>2. Wu F.Y. The Potts model. Reviews of modern physics. Vol. 54, 235-268 (1982). '
                   '<a href="https://doi.org/10.1103/RevModPhys.54.235">https://doi.org/10.1103/RevModPhys.54.235</a></p>'
                   '<p>3. Preston Ch.J. Gibbs states on countable sets. Cambridge University Press, London (1974).</p>'
                   '</div>')
REFS_UNNUMBERED = ('<div id="references" class="element"><h2 class="field-heading">References</h2>'
                   '<p>Alfian, M. and Purwanto, P., 2022. Prototipe sistem kendali smart home. <em>Prosiding SENAFTI'
                   '</em>, 1(1), pp. 493-502.<strong></strong></p>'
                   '<p>Cramer, M.N., Jay, O. and Flouris, A.D., 2022. Human temperature regulation under heat stress. '
                   '<em>Physiological Reviews</em>, 102(4), pp. 1907-1989. doi: 10.1152/physrev.00047.2021.</p>'
                   '<p>WorkSafeBC., 2007. Heat Stress. [online].</p></div>')


def _page(refs="", metas=METAS):
    return (f'<html><head><title>Spline methods for cardiosignals</title>{metas}</head><body>'
            f'<div id="container"><div id="wrapper"><div id="content"><div id="main" class="text">'
            f'<div id="alpha">'
            f"<div id='title' class='element'><h1><a href='{URL}'>Spline methods for cardiosignals</a></h1></div>"
            f"<div class='clear'></div>"
            f"<div id='authors' class='element'><h2 class='visually-hidden'>Authors</h2>"
            f'<p class="author"><a href="/do/search/?q=author"><strong>Hakimjon Zaynidinov</strong>, '
            f'<em>Tashkent University of Information Technologies</em></a><br/>'
            f'<a href="/do/search/?q=author"><strong>Ibrohimbek Yusupov</strong></a><br/></p></div>'
            f"<div class='clear'></div>"
            f"<div id='abstract' class='element'><h4>Abstract</h4><p>{ABSTRACT}</p></div>"
            f"<div class='clear'></div>{refs}"
            f"<div id='recommended_citation' class='element'><h4>Recommended Citation</h4>"
            f"<p>Zaynidinov, H. (2018) &quot;Spline methods,&quot; <em>Bulletin of TUIT</em>: Vol. 1: Iss. 1.</p></div>"
            f'</div></div></div></div></div>'
            f'<div id="footer"><p><a href="https://network.bepress.com/">Digital Commons Network</a> powered by '
            f'<a href="https://www.elsevier.com/solutions/digital-commons">Digital Commons</a></p></div>'
            f'</body></html>')


def _soup(html):
    return BeautifulSoup(html, "lxml")


def _refs(html):
    parsed = DigitalCommons(_soup(html)).parse()
    return [(r["position"], r["raw"], r["doi"]) for r in parsed["references"] or []], parsed["references_complete"]


def test_claims_digital_commons_pages():
    parser = DigitalCommons(_soup(_page()))
    assert parser.is_publisher_specific_parser()
    assert parser.authors_found()


def test_byline_and_abstract_are_the_generic_readers():
    soup = _soup(_page(REFS_ONE_P_EACH))
    ours, generic = DigitalCommons(soup).parse(), GenericPublisherParser(soup).parse()
    assert ours["authors"] == generic["authors"] and ours["abstract"] == generic["abstract"]
    out = parse_page(_page(REFS_ONE_P_EACH).encode(), "doi", URL)
    assert [a["name"] for a in out["authors"]] == ["Zaynidinov, Hakimjon", "Yusupov, Ibrohimbek"]  # as the tags give them
    assert out["authors"][0]["affiliations"] == [{"name": "Tashkent University of Information Technologies"}]
    assert out["authors"][1]["affiliations"] == []
    assert not any(a["is_corresponding"] for a in out["authors"])
    assert out["abstract"] == ABSTRACT


def test_whole_list_pasted_in_one_paragraph_one_entry_per_line():
    refs, complete = _refs(_page(REFS_ONE_PARAGRAPH))
    assert [r[0] for r in refs] == [1, 2, 3]
    assert refs[0][1] == "Smolentsev N. K. Osnovi teorii veyvletov. M. : DMK Press, 2008. - 448 s."
    assert refs[2][2] == "10.1007/978-981-13-2239-6"
    assert complete is True


def test_numbered_list_one_paragraph_per_entry():
    refs, complete = _refs(_page(REFS_ONE_P_EACH))
    assert len(refs) == 3 and refs[0][1].startswith("Georgii H.O. Gibbs measures")
    assert refs[1][2] == "10.1103/RevModPhys.54.235"
    assert refs[0][2] is None
    assert complete is True


def test_reference_list_reaches_parse_page():
    out = parse_page(_page(REFS_ONE_P_EACH).encode(), "doi", URL)
    assert [r["position"] for r in out["references"]] == [1, 2, 3]
    assert out["references_complete"] is True


def test_unnumbered_list_is_read_but_not_called_whole():
    refs, complete = _refs(_page(REFS_UNNUMBERED))
    assert len(refs) == 3 and refs[1][2] == "10.1152/physrev.00047.2021"
    assert complete is False


def test_numbering_with_a_gap_is_not_whole():
    refs, complete = _refs(_page(REFS_ONE_P_EACH.replace("<p>2. ", "<p>4. ")))
    assert len(refs) == 3
    assert complete is False


def test_page_without_a_references_field():
    parsed = DigitalCommons(_soup(_page())).parse()
    assert parsed["references"] is None and parsed["references_complete"] is False


def test_drupal_page_with_bepress_tags_is_not_claimed():
    drupal = ('<html><head><meta name="generator" content="Drupal 7 (https://www.drupal.org)"/>'
              '<meta name="citation_title" content="A mini-review"/><meta name="citation_author" content="A. Author"/>'
              '<meta name="bepress_citation_title" content="A mini-review"/>'
              '<meta name="bepress_citation_author" content="A. Author"/></head><body>'
              '<div id="page"><div class="region-content"><h1>A mini-review</h1>'
              f'{REFS_ONE_P_EACH}</div></div></body></html>')
    assert not DigitalCommons(_soup(drupal)).is_publisher_specific_parser()
    assert parse_page(drupal.encode(), "doi", "https://journal.example.com/content/a-mini-review")["references"] is None
