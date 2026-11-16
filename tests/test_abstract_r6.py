"""Text that is not the abstract, returned as one (oxjob #2239, phase 2, class abstract-r6).

Round 6's confirmed dev cases: IEEE Xplore's "Advertisement." where an abstract would be (its sentences for other
front matter are left as they are: the golds disagree on them), the keyword line run on behind an abstract (DOAJ,
OJS), one-sentence language versions under "UK: ... EN: ... RU: ..." (a Ukrainian DSpace), a short abstract whose
English version is in a DC.Description tag only (OJS), and an English "ABSTRACT" label three wrappers deep beside a
"RESUMO" two deep (SciELO Chile). Markup below is cut down from those pages. Offline, inline HTML only.
"""
import pytest

from parseland_lib.abstract_language import english_part
from parseland_lib.not_abstract import clean_abstract, is_not_abstract
from parseland_lib.parse import parse_page

EN = ("Environmental disturbances in various systems and individuals can result in a tendency for fluctuating "
      "asymmetry, which consists of a non-directional deviation from symmetry of a bilateral structure in a normally "
      "distributed population. The results show that the leaves of the plant respond to the stress they were "
      "submitted to, which makes this an important analysis to ascertain the fitness of the plant.")
PT = ("Perturbações microambientais em diferentes sistemas e indivíduos podem resultar numa tendência para a "
      "assimetria flutuante, que consiste num desvio não direcional da simetria de uma estrutura bilateral numa "
      "população com distribuição normal. Os resultados mostram que as folhas da planta respondem ao estresse a que "
      "foram submetidas, sendo uma importante análise para averiguar o fitness da planta.")


def page(head="", body=""):
    return f"<html><head><title>A record</title>{head}</head><body>{body}</body></html>"


def abstract(html, ns="pmh", url="https://repository.example.org/handle/1/2"):
    return parse_page(html.encode(), ns, url)["abstract"]


# --- IEEE Xplore's item-type notices are stand-ins, not abstracts -----------------------------------------------------

@pytest.mark.parametrize("text", ["Advertisement.", "Advertisement, IEEE.", "ADVERTISEMENT"])
def test_ieee_advertisement_notice_is_not_an_abstract(text):
    assert is_not_abstract(text)
    assert clean_abstract(text) is None


@pytest.mark.parametrize("text", [
    # an advertisement given with its text, and texts that say something about the item: each stays
    "Advertisement: Keep up with the latest IEEE Computer Society publications and activities wherever you are.",
    "Advertisement of the first electric streetcars in the daily press of Richmond, Virginia, 1888 to 1890.",
    "The following topics are dealt with: information and computer technology; microwave engineering and "
    "communication; mobile and satellite communication; telecommunications network management.",
    "Lists Lester Eastman's students over the years.",
])
def test_ieee_look_alikes_stay(text):
    assert not is_not_abstract(text)
    assert clean_abstract(text) == text


IEEE_HEAD = ('<link rel="canonical" href="https://ieeexplore.ieee.org/document/5216833/"/>'
             '<meta property="og:title" content="{title}"/><meta property="og:description" content="{text}"/>'
             '<meta name="Description" content="{text}"/><meta property="twitter:description" content="{text}"/>')
IEEE_BODY = ('<script>xplGlobal.document.metadata={{"sections":{{"abstract":"true","authors":"false"}},'
             '"abstract":"{text}","doi":"10.1109/MSPEC.1973.5216833","isFreeDocument":true}};</script>')


def ieee_page(title, text):
    return page(IEEE_HEAD.format(title=title, text=text), IEEE_BODY.format(text=text))


def test_ieee_advertisement_page_has_no_abstract():
    html = ieee_page("[Advertisement]", "Advertisement.")
    assert abstract(html, "doi", "https://ieeexplore.ieee.org/document/5216833/") is None


def test_ieee_authorless_item_keeps_a_description_of_its_content():
    text = ("Discussion and author's closure of paper 40-134 by G. Leslie Hill, presented at the AIEE Pacific Coast "
            "convention, Los Angeles, Calif., August 27-30, 1940, and published in AIEE TRANSACTIONS, 1941, pages "
            "402-07.")
    html = ieee_page("Discussion", text)
    assert abstract(html, "doi", "https://ieeexplore.ieee.org/document/5216833/") == text


# --- the keyword line behind the abstract -----------------------------------------------------------------------------

BODY = ("In this paper the results of architecture development, layout design of analytical microsystem-on-chip "
        'with the structures "silicon-on-insulator" (SOI) and its elements schemotechnical computer simulation for '
        "determine their electrical and time characteristics are presented.")


@pytest.mark.parametrize("tail", [
    " Keywords: analytical microsystem-on-chip, silicon-on-insulator structure, gate array, ring oscillator.",
    "\nKata Kunci: Sistem Pendukung Keputusan, Metode SAW, Karyawan Terbaik",
    "Keywords: halal certification; house of risk; MSMEs; risk management\xa0ABSTRAKUMKM Camilan Berlian,",
    "\r\nKEY WORDS: Anaemia, Chronic kidney disease, Erythropoietin.",
    "    Keywords   : packaging design optimization, storage efficiency, sustainable logistics",
    " Key words: Lemon, Cordial, Citric acid DOI:10.3329/jbs.v16i0.3755 J. bio-sci. 16: 125-127, 2008",
    " Palabras clave: relaciones de pareja, sexualidad, tradición, modernidad.",
    "\nKeywords: ASEAN's economic cooperation, democratic leadership\nDOI: 10.17576/sinergi.0302.2023.03\n"
    "Article information: Submission date: 17 July 2023; Acceptance date: 16 October 2023.",
])
def test_keyword_line_behind_the_abstract_is_left_out(tail):
    assert clean_abstract(BODY + tail) == BODY


def test_keywords_named_inside_a_sentence_stay():
    text = BODY + " The literature was searched with the keywords: microsystem, silicon-on-insulator and gate array."
    assert clean_abstract(text) == text


def test_keyword_row_before_the_abstract_is_not_a_tail():
    # a thesis record's front block: "Keyword：" stands before the abstract's text, not behind it
    text = ("Title of thesis: The organic village\nTotal pages: 201 pages\nKeyword： organic village, space model, "
            "design participation\nAbstract： " + BODY + " " + BODY + " " + BODY)
    assert clean_abstract(text) == text


def test_keyword_line_far_from_the_end_is_not_cut():
    # more than a keyword line and its trimmings follow the label: it is not the text's tail
    text = BODY + " Keywords: microsystem, gate array. " + " ".join([BODY] * 3)
    assert clean_abstract(text) == text


def test_doaj_record_abstract_without_its_keywords():
    html = page('<meta name="citation_title" content="Analytical microsystem-on-chip"/>',
                f'<main><h2>Abstract</h2><p class="article-details__abstract">{BODY} Keywords: analytical '
                'microsystem-on-chip, silicon-on-insulator structure, gate array, ring oscillator.</p></main>')
    assert abstract(html, url="https://doaj.org/article/5b76797b114748a89d4f7efe2342fe1d") == BODY


# --- one-sentence language versions under the page's own codes --------------------------------------------------------

CODED = ("UK: В роботі запропонували рекомендаційні заходи підвищення надійності\n"
         "EN: The paper proposed recommendations for improving reliability\n"
         "RU: В работе предложили рекомендационные мероприятия повышения надежности")


def test_short_coded_versions_give_the_english_one():
    assert english_part(CODED) == "The paper proposed recommendations for improving reliability"


@pytest.mark.parametrize("text", [
    # one label only: nothing to choose between
    "EN: In this article the principal causes of youth unemployment on a labor market are investigated.",
    # the part under EN is a few words: a title or a keyword, not a version
    "UK: Надійність підшипників\nEN: Bearing reliability\nRU: Надежность подшипников",
    # not labels at the text's start
    "The codes are UK: United Kingdom EN: England RU: Russia, as used in the tables of this report on trade.",
])
def test_short_text_without_coded_versions_is_untouched(text):
    assert english_part(text) == text


def test_dspace_record_with_coded_versions_gives_the_english_one():
    html = page(f'<meta name="Generator" content="DSpace 7.6.3"/><meta name="description" content="{CODED}"/>'
                '<meta name="citation_title" content="Дослідження шляхів забезпечення надійності"/>',
                '<div class="simple-view-element"><h2 class="simple-view-element-header">Abstract</h2>'
                f'<div class="simple-view-element-body"><span class="dont-break-out">{CODED}</span></div></div>')
    assert abstract(html) == "The paper proposed recommendations for improving reliability"


# --- a short abstract's English version, in the page's tags only ------------------------------------------------------

PT_SHORT = ('O problema de cálculo dos ângulos de extinção de faces de uma mesma zona, com referência ao eixo da zona, '
            'é tratado pelo autor através dos símbolos projetivos de Fedorow.')
EN_SHORT = ('Using the projective symbols by Fedorow, it is possible to calculate the angles of extinction of the '
            'faces of a same zone, in relation to the axis of the zone, as it is demonstrated by the author.')


def ojs_record(tags):
    return page('<meta name="generator" content="Open Journal Systems 3.3.0.13"/>'
                '<meta name="citation_title" content="Ângulos de extinção"/>' + tags,
                f'<section class="item abstract"><h2 class="label">Resumo</h2>{PT_SHORT}</section>')


def test_short_abstract_gives_the_english_version_its_tags_list():
    html = ojs_record(f'<meta name="citation_abstract" xml:lang="pt" content="{PT_SHORT}"/>'
                      f'<meta name="DC.Description" xml:lang="pt" content="{PT_SHORT}"/>'
                      f'<meta name="DC.Description" xml:lang="en" content="{EN_SHORT}"/>')
    assert abstract(html, url="https://www.revistas.example.br/aesalq/article/view/43227") == EN_SHORT


def test_short_abstract_stays_when_the_other_tag_is_not_its_english_version():
    # a note in the second DC.Description, not a version: far shorter than a translation, and not English prose
    html = ojs_record(f'<meta name="DC.Description" xml:lang="pt" content="{PT_SHORT}"/>'
                      '<meta name="DC.Description" xml:lang="en" content="Anais da Escola Superior de Agricultura '
                      'Luiz de Queiroz, v. 19 (1962), Piracicaba, Universidade de São Paulo, ISSN 0071-1276, pp. '
                      '188-196"/>')
    assert abstract(html, url="https://www.revistas.example.br/aesalq/article/view/43227") == PT_SHORT


def test_printed_abstract_stays_when_no_tag_holds_it():
    # the tags are another text's versions (not this abstract's): nothing says the English tag translates it
    html = ojs_record(f'<meta name="DC.Description" xml:lang="en" content="{EN_SHORT}"/>')
    assert abstract(html, url="https://www.revistas.example.br/aesalq/article/view/43227") == PT_SHORT


# --- an "ABSTRACT" label deeper in wrappers than the "RESUMO" beside it -----------------------------------------------

def scielo_page(english_label):
    return page('<meta name="citation_title" content="Assimetria flutuante"/>',
                '<div class="content"><p align="justify"><font face="Verdana" size="3"><b>RESUMO</b></font></p>'
                f'<p align="justify"><font face="Verdana" size="2">{PT}</font></p>'
                '<p align="justify"><font face="Verdana" size="2"><b>Palavras-chave:</b> assimetria, estresse.</font></p>'
                f'<hr><p align="justify">{english_label}</p>'
                f'<p align="justify"><font face="Verdana" size="2"><i>{EN}</i></font></p>'
                '<p align="justify"><font face="Verdana" size="2"><b>Key words:</b> asymmetry, stress.</font></p></div>')


def test_english_label_three_wrappers_deep_is_read():
    html = scielo_page('<font face="Verdana" size="3"><b><i>ABSTRACT</i></b></font>')
    assert abstract(html, url="http://www.scielo.cl/scielo.php?script=sci_arttext&pid=S0718-34292011000300007") == EN


def test_wrapper_that_holds_more_than_the_label_is_not_climbed():
    # the label's third wrapper also holds a sentence: what follows that wrapper is not the label's text
    html = scielo_page('<font face="Verdana" size="3"><b><i>ABSTRACT</i></b> of the thesis, as deposited</font>')
    assert abstract(html, url="http://www.scielo.cl/scielo.php?script=sci_arttext&pid=S0718-34292011000300007") == PT
