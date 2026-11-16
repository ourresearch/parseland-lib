"""The English version of an abstract shown in several languages, whole structured abstracts, and texts that are not
this work's abstract (oxjob #2239, phase 2, class abstract-r2).

116 confirmed dev cases: about half were pages that show the abstract in several languages where the parser gave a
non-English one (the rubric: "If several language versions are shown, give the English one, else the first"); the
rest were cut structured abstracts (PMC), another work's abstract on a peer-review report's page, and stand-ins
(a title, a reference list, a site blurb, a publisher's history block). Markup below is cut down from those pages.
Offline, inline HTML only.
"""
import pytest
from bs4 import BeautifulSoup

from parseland_lib.abstract_language import english_part, is_english, is_other_language
from parseland_lib.not_abstract import clean_abstract, is_not_abstract
from parseland_lib.parse import parse_page, short_named_abstract
from parseland_lib.publisher.parsers.generic import GenericPublisherParser

EN = ("This study aims to establish an alternative methodology for determining the main transients on brushless "
      "exciters due to transients in the main generator armature. The models of the exciter and of the rotating "
      "rectifier were implemented and the voltages and currents of the bridge diodes were monitored for each of the "
      "faults that were applied. Simulation and experimental results are compared.")
PT = ("O presente trabalho visa estabelecer uma metodologia alternativa para o levantamento dos principais "
      "transitórios elétricos sofridos por excitatrizes brushless, decorrentes de transitórios ocorridos na armadura "
      "do gerador principal. Os modelos da excitatriz e da ponte retificadora rotativa foram implementados e as "
      "tensões e correntes dos diodos foram monitoradas. Resultados simulados e experimentais são comparados.")
ES = ("El objetivo de este artículo es propiciar una reflexión sobre el aumento de las patologías tropicales que se "
      "relacionan con la actividad laboral de los trabajadores desplazados a otros países, bien por necesidad de la "
      "empresa donde trabajan, bien de forma voluntaria, si se trata del destino elegido por motivo de vacaciones, "
      "y se describen las medidas de prevención que deben adoptar los servicios de salud laboral.")
RU = ("В статье представлены результаты исследования, направленного на апробацию методики выделения ключевых слов "
      "как инструмента диагностики понимания аутентичных текстов профессиональной направленности на английском "
      "языке студентами-первокурсниками неязыкового вуза в рамках вербального тестирования.")
ZH = ("蛛网膜下腔出血是卒中引起猝死的最常见原因，许多患者在就医途中死亡，而入院前死亡率在3%~26%。近年，系统回顾数据显示全球自发性蛛网膜下腔出血的年发病率"
      "为(2~16)/100,000，而且SAH后脑血管痉挛的致死、致残率极高。尼莫地平被认为是目前降低蛛网膜下腔出血后延迟性脑血管痉挛相关疾患发病率和死亡率的最佳方法。")
FR = ("Le processus de globalisation s’accompagne d’une importante restructuration des filières agricoles, se "
      "traduisant par une déconnexion de plus en plus forte entre opérateurs des filières et ceux des territoires, "
      "et entre lieux de production et usages des ressources locales. Les opérateurs des filières utilisent des "
      "ressources des territoires, mais n’y opèrent souvent qu’une partie de leur activité.")


BOTH_PRINTED = f"<table><tr><td>Resumo em português</td><td>{PT}</td></tr><tr><td>Resumo em inglês</td><td>{EN}</td></tr></table>"


def page(head="", body=""):
    return f"<html><head><title>A record</title>{head}</head><body>{body}</body></html>".encode()


def abstract(html, ns="pmh", url="https://repository.example.org/handle/1/2"):
    return parse_page(html, ns, url)["abstract"]


def meta(name, content, lang=None):
    return f'<meta name="{name}" content="{content}"' + (f' xml:lang="{lang}"' if lang else "") + " />"


# --- the language test itself ------------------------------------------------------------------------------------

def test_language_test_tells_english_from_other_languages_and_scripts():
    assert is_english(EN) and not is_other_language(EN)
    for other in (PT, ES, RU, ZH, FR):
        assert is_other_language(other) and not is_english(other)


def test_language_test_does_not_decide_on_terse_text():
    # a topic list has no function words either way: neither English nor another language, so nothing is changed
    terse = "Information technology; microwave engineering; mobile communication; network management; wireless."
    assert not is_english(terse) and not is_other_language(terse)


# --- language versions in separate meta tags -----------------------------------------------------------------------

@pytest.mark.parametrize("ns", ["doi", "pmh"])
def test_english_tag_wins_when_the_tags_say_their_languages(ns):
    # the USP thesis library: two DCTERMS.abstract tags, xml:lang "pt-br" and "en"; the record page prints both
    html = page(meta("DCTERMS.abstract", PT, "pt-br") + meta("DCTERMS.abstract", EN, "en")
                + meta("citation_title", "Transitórios em excitatrizes brushless"), BOTH_PRINTED)
    assert abstract(html, ns) == EN


def test_english_tag_counts_as_shown_when_the_page_prints_only_the_other_version():
    # Open Journal Systems prints one language and lists every version in DC.Description. The dev gold gives the
    # English tag on 11 such pages and the printed version on 2 (listed for a decision, not settled here).
    html = page(meta("DC.Description", PT, "pt") + meta("DC.Description", EN, "en"),
                f'<section class="item abstract"><h2 class="label">Resumo</h2><p>{PT}</p></section>')
    assert abstract(html, "doi", "https://revistas.example.org/article/view/1") == EN


def test_english_tag_wins_when_every_tag_carries_the_same_language_attribute():
    # DSpace stamps one xml:lang on everything (UnB: "en" on the Portuguese text); a thesis note sits in the first
    # DC.description, the English abstract in the second
    html = page(meta("DCTERMS.abstract", PT, "en") + meta("DC.description", "Tese (doutorado), Universidade, 2014.", "en")
                + meta("DC.description", EN), BOTH_PRINTED)
    assert abstract(html) == EN


def test_english_version_in_eprints_abstract_tags():
    # cyberleninka.ru: the description tag holds the Russian version, two eprints.abstract tags hold both
    html = page(meta("description", RU) + meta("eprints.abstract", EN) + meta("eprints.abstract", RU),
                f'<div class="full abstract"><h2>Аннотация</h2><p itemprop="description">{RU}</p></div>')
    assert abstract(html) == EN


def test_one_language_only_stays_as_it_is():
    assert abstract(page(meta("DCTERMS.abstract", PT, "pt-br"))) == PT  # "else the first"
    assert abstract(page(meta("DCTERMS.abstract", EN) + meta("DCTERMS.abstract", PT), BOTH_PRINTED)) == EN


def test_note_in_english_is_not_taken_for_the_english_version():
    # a DC.description far from a translation's length is a note, not the abstract's English version
    note = "Thesis submitted in partial fulfilment of the requirements for the degree of Doctor of Philosophy. " * 12
    printed = f"<div><p>{ES}</p><p>{note.strip()}</p></div>"
    assert abstract(page(meta("DCTERMS.abstract", ES) + meta("DC.description", note.strip()), printed)) == ES


def test_site_blurb_in_english_never_replaces_the_abstract():
    blurb = ("This repository is the open archive of the university and holds the theses, articles and reports that "
             "its researchers have written, for everyone to read and to use under the terms that are stated on each "
             "of the records that are held in the collections of the library.")
    html = page(meta("citation_abstract", ES) + f'<meta property="og:description" content="{blurb}"/>')
    assert GenericPublisherParser(BeautifulSoup(html, "lxml")).parse_abstract_meta_tags() == ES


# --- language versions the page marks with lang attributes ---------------------------------------------------------

HAL_BODY = (f'<div class="abstract"><h4> Abstract </h4><div class="abstract-content en " lang="en">{EN}</div>'
            f'<div class="abstract-content fr active" lang="fr">{FR}</div></div>')


def test_block_marked_english_wins_over_the_other_language_in_the_meta_tag():
    # HAL: citation_abstract holds the French version only
    assert abstract(page(meta("citation_abstract", FR), HAL_BODY)) == EN


def test_block_marked_english_is_not_used_when_the_abstract_is_english_already():
    other = EN.replace("This study aims", "Our work sets out")
    html = page(meta("citation_abstract", other), f'<div class="abstract-content" lang="en">{EN}</div>')
    assert abstract(html) == other


def test_other_language_stays_when_no_block_is_marked_english():
    assert abstract(page(meta("citation_abstract", FR), f'<div class="abstract-content fr" lang="fr">{FR}</div>')) == FR


# --- language versions under their own headings --------------------------------------------------------------------

TWO_HEADINGS = (f"<div><p><b>Resumen:</b> {ES}</p></div><hr><div><p><b>Abstract:</b> {EN}</p></div>"
                f"<hr><div><p><b>Resumo:</b> {PT}</p></div>")


def test_text_under_the_english_heading_wins():
    # scielo.conicyt.cl prints Resumen, Abstract, Resumo in that order
    assert abstract(page(body=TWO_HEADINGS)) == EN
    assert abstract(page(body=TWO_HEADINGS), "doi", "https://journal.example.org/article/1") == EN


def test_other_language_heading_alone_still_gives_its_text():
    assert abstract(page(body=f"<div><h3>Resumen</h3><p>{ES}</p></div>")) == ES


def test_two_different_texts_under_english_headings_are_still_nobodys():
    # a publisher page that prints two "Abstract" texts shows other works too: no telling which is this one
    other = EN.replace("brushless", "static")
    body = f"<div><h2>Abstract</h2><p>{EN}</p></div><div><h2>Abstract</h2><p>{other}</p></div>"
    assert abstract(page(body=body), "doi", "https://journal.example.org/article/1") is None


# --- language versions run together in one block -------------------------------------------------------------------

def test_english_after_another_script():
    # hanspub.org's description tag: the Chinese abstract, two spaces, the English one
    assert english_part(f"{ZH}  {EN}") == EN
    assert english_part(f"{RU} Abstract: {EN}") == EN  # DOAJ: Arabic or Russian, then "Abstract:"


def test_english_before_another_script():
    assert english_part(f"{EN} {RU}") == EN


def test_english_beside_another_latin_script_language():
    assert english_part(f"{EN} {ES}") == EN
    assert english_part(f"{ES} {EN}") == EN
    assert english_part(f"{PT} {ES} {EN}") == EN  # DOAJ: Portuguese, Spanish, English
    assert english_part(f"{EN} [{ES}]") == EN  # the translation in brackets


def test_labelled_versions():
    # Ukrainian DSpace repositories: "UK: ... EN: ... RU: ..." in the one field
    assert english_part(f"UK: {RU}\nEN: {EN}\nRU: {RU}") == EN
    # SSRN
    assert english_part(f"Portuguese abstract: {PT} English abstract: {EN}") == EN


@pytest.mark.parametrize("text", [
    EN,
    PT,
    ZH,
    # an English abstract that names its subject in another script, or quotes a few words
    EN + " The Bakuhan-Regime 幕藩体制 is taken as the example, and the 学文 of the lords is described.",
    EN + " Species: Quercus robur, Fagus sylvatica, Picea abies, Pinus sylvestris, Betula pendula, Alnus glutinosa.",
    # an abstract about a text in another language, quoted at length but not a version of it
    EN + " As the poet says: «en la noche de los tiempos se perdió la voz».",
])
def test_one_version_is_left_alone(text):
    assert english_part(text) == text


def test_run_together_versions_come_apart_on_a_page():
    html = page(meta("description", f"{ZH}  {EN}") + meta("citation_title", "尼莫地平预防脑血管痉挛"),
                f"<div class='abstract'><p>{ZH}</p><p>{EN}</p></div>")
    assert abstract(html) == EN


# --- a structured abstract, one <section> per part (PMC) -----------------------------------------------------------

PMC = """<section class="abstract" id="abstract1"><h2>Abstract</h2>
<section id="st1"><h3 class="pmc_sec_title">Introduction:</h3><p>Aneurysmal bone cysts (ABCs) are non-neoplastic
expansile, vascular, osteolytic benign tumors in the long bone, spine, and sternum. The location in the pelvis is
sparse.</p></section><section id="st2"><h3 class="pmc_sec_title">Case Report:</h3><p>A 12-year-old female presented
with pain in her left pelvis for 6 months. Curettage and bone grafting were done.</p></section>
<section id="st3"><h3 class="pmc_sec_title">Conclusion:</h3><p>This case report demonstrates a rare ABC of the ilium
that was managed with curettage and bone grafting.</p></section>
<section id="kwd-group1" class="kwd-group"><p><strong>Keywords:</strong> Pelvic iliac bone, curettage</p></section>
</section><section id="sec1"><h2>Introduction</h2><p>An aneurysmal bone cyst is a bone lesion.</p></section>"""


def test_structured_abstract_keeps_every_section_and_no_keywords():
    got = abstract(page(body=PMC))
    assert got.startswith("Introduction: Aneurysmal bone cysts")
    assert "Case Report: A 12-year-old female" in got
    assert got.endswith("managed with curettage and bone grafting.")
    assert "Keywords" not in got and "bone lesion" not in got


def test_sections_beside_a_heading_outside_an_abstract_container_are_not_read_on():
    # here the sections after the first are the article's body
    body = (f"<div class='article'><h2>Abstract</h2><section><p>{EN}</p></section>"
            f"<section><h2>Introduction</h2><p>{ES}</p></section></div>")
    assert abstract(page(body=body)) == EN


# --- another work's abstract on a peer-review report's page --------------------------------------------------------

REVIEWED = f'<div><h3>Abstract</h3><p>{EN}</p></div><div><h3>Reviewer report</h3><p>The paper is sound.</p></div>'


@pytest.mark.parametrize("url", [
    "https://publons.com/publon/51945721/",
    "https://elifesciences.org/articles/81573#sa2",
    "https://scipost.org/submissions/2106.05354v1/#report_2",
    "https://nbpublish.com/library_read_article.php?id=79459#review_35150",
])
def test_report_page_does_not_take_the_reviewed_works_abstract(url):
    assert abstract(page(body=REVIEWED), "doi", url) is None


@pytest.mark.parametrize("url", [
    "https://elifesciences.org/articles/81573",
    "https://scipost.org/submissions/2106.05354v1/",
    "https://journal.example.org/article/view/35150#abstract",
])
def test_the_works_own_page_keeps_its_abstract(url):
    assert abstract(page(body=REVIEWED), "doi", url) == EN


# --- stand-ins that are not abstracts ------------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "A document by Carlos Zetina Rosales. Click on the document to view its contents.",
    "Publication History Article published online: 23 September 2025 © 2025. Thieme. All rights reserved. Georg "
    "Thieme Verlag KG, Oswald-Hesse-Straße 50, 70469 Stuttgart, Germany",
    "Die Online Collection der Staatlichen Kunstsammlungen Dresden ist das öffentliche Abbild des 2008 gestarteten "
    "Projekts zur Erfassung der Bestände.",
    "Elektra es el Archivo Digital de las Artes escénicas de Andalucía que contiene un conjunto organizado de "
    "documentos.",
])
def test_stand_ins_are_not_abstracts(text):
    assert is_not_abstract(text) and clean_abstract(text) is None


@pytest.mark.parametrize("text", [
    "A document by the committee sets out how the publication history of the journal was reconstructed from its "
    "archive, and what the records show about its first editors.",
    EN,
])
def test_look_alike_abstracts_are_kept(text):
    assert not is_not_abstract(text) and clean_abstract(text) == text


def test_spie_access_notice_comes_off():
    real = "This excerpt gives a succinct explanation of contrast vs spatial and temporal coherence."
    assert clean_abstract(real + " Online access to SPIE eBooks is limited to subscribing institutions.") == real
    assert clean_abstract(real) == real


def test_link_or_reference_list_under_the_heading_is_not_the_abstract():
    refs = ("Referências Batty, M. (2016) Editorial: Big Data, Cities and Herodotus. Built Environment. 42(3), "
            "317-320. Hillier, B. (1996) Space is the machine. Cambridge University Press, Cambridge.")
    assert abstract(page(body=f"<div><h2>Resumo</h2><div></div><div>{refs}</div></div>")) is None
    info = ("https://doi.org/10.1177/2054358120919003 Article information Volume: 7 Article first published online: "
            "May 18, 2020 Issue published: January 2020")
    assert abstract(page(body=f"<div><h2>Abstract</h2><div>{info}</div></div>")) is None
    # an abstract that talks about references is one
    real = "References to the classical authors are frequent in this corpus, and " + EN[0].lower() + EN[1:]
    assert abstract(page(body=f"<div><h2>Abstract</h2><div>{real}</div></div>")) == real


TITLE = "Modernizing Warfare: US Grant and Military Engineering in the Middle Mississippi Valley during the Civil War"


def test_title_printed_as_the_abstract_is_not_one():
    head = meta("citation_title", TITLE)
    # Digital Commons: the title and the author under "Abstract"; an IRIS record: "Titolo: <title>" in the tag
    assert abstract(page(head, f"<div><h2>Abstract</h2><p>{TITLE} William Mulligan Jr.</p></div>")) is None
    assert short_named_abstract(BeautifulSoup(page(head + meta("DCTERMS.abstract", "Titolo: " + TITLE)), "lxml")) is None
    # an abstract that opens with its title's words and goes on is kept
    real = f"{TITLE} is the subject of this paper. {EN}"
    assert abstract(page(head, f"<div><h2>Abstract</h2><p>{real}</p></div>")) == real


def test_teaser_cut_with_a_bracketed_ellipsis_is_not_an_abstract():
    # MDPI editorials: the first sentence of the text, then "[...]"
    teaser = ("Climate change is no longer only a long-term environmental concern; it is a present driver of "
              "disruption for rural communities [...]")
    soup = BeautifulSoup(page(meta("citation_abstract", teaser) + meta("citation_title", "Editorial")), "lxml")
    assert short_named_abstract(soup) is None
    whole = teaser.replace(" [...]", ".")
    soup = BeautifulSoup(page(meta("citation_abstract", whole) + meta("citation_title", "Editorial")), "lxml")
    assert short_named_abstract(soup) == whole


# --- IEEE Xplore pages whose record lists no authors ---------------------------------------------------------------

IEEE_ABSTRACT = ("The following topics are dealt with: information and computer technology; microwave engineering "
                 "and communication; mobile and satellite communication; telecommunications network management; "
                 "wireless communication.")


def ieee(has_abstract):
    return page(f'<link rel="canonical" href="https://ieeexplore.ieee.org/document/1188288/"/>'
                f'<meta property="og:description" content="{IEEE_ABSTRACT}"/>'
                f'<meta property="og:title" content="4th National Conference on Telecommunication Technology"/>'
                '<script>xplGlobal.document.metadata={"sections":{"abstract":"%s","authors":"false"},'
                '"abstract":"%s"};</script>' % (has_abstract, IEEE_ABSTRACT))


def test_ieee_page_without_authors_keeps_its_abstract():
    url = "https://ieeexplore.ieee.org/document/1188288/"
    assert abstract(ieee("true"), "doi", url) == IEEE_ABSTRACT
    assert abstract(ieee("false"), "doi", url) is None  # the record says it has none: the tag is not one


# --- Oxford Academic's "Extract" -----------------------------------------------------------------------------------

def oup(section_class, heading="Extract", title_class="at-Extract-Title"):
    return page('<link rel="canonical" href="https://academic.oup.com/isle/article-abstract/17/3/589/716902"/>'
                f'<meta name="citation_title" content="Bluewillow"/><meta name="citation_author" content="A Poet"/>',
                '<div class="widget-ArticleFulltext"><div class="widget-items" data-widgetname="ArticleFulltext">'
                f'<h2 class="abstract-title {title_class}">{heading}</h2>'
                f'<section class="{section_class}"><p class="chapter-para">{EN}</p></section></div></div>')


def test_oup_extract_is_the_works_opening_not_its_abstract():
    url = "https://academic.oup.com/isle/article-abstract/17/3/589/716902"
    assert abstract(oup("abstract extract"), "doi", url) is None
    assert abstract(oup("abstract", "Abstract", "at-Abstract-Title"), "doi", url) == EN


# --- a title page glued around the abstract (Dove Medical Press records on DOAJ) -----------------------------------

DOVE_HEAD = ("Vanessa B Davis,1 Mark Li,1 Ryu Komatsu,2 Jiang Wu1 1Department of Anesthesiology and Pain Medicine, "
             "University of Washington Medical Center, Seattle, WA, USA; 2Multi-Specialty Anesthesiology, Cleveland "
             "Clinic, Cleveland, OH, USACorrespondence: Jiang Wu, Email ")


@pytest.mark.parametrize("label", ["jiangwu@uw.eduAbstract: ", "[email protected] : "])
def test_title_page_and_keywords_come_off_the_abstract(label):
    glued = DOVE_HEAD + label + EN + " Keywords: thoracic epidural analgesia, retrograde, laminectomy"
    assert clean_abstract(glued) == EN


def test_abstract_that_mentions_correspondence_is_kept():
    real = EN + " Correspondence: the two series agree. Keywords: brushless exciter, transients"
    assert clean_abstract(real) == real


# --- the value under a heading: text with inline markup, or a block that holds only a link -------------------------

def test_bare_text_under_a_label_runs_on_through_inline_markup():
    # dovepress.com: "<strong>Abstract:</strong> ... 5/0 Vicryl<sup>®</sup> sutures ..." in one paragraph
    first, rest = EN[:150], EN[150:]
    body = (f"<div><p>Mahmoud Machmouchi<br/>Department of Pediatrics<br/><br/><strong>Abstract:</strong> {first}"
            f"<sup>®</sup>{rest}<br/>It ends <i>here</i>.</p><p>© 2011 The Author(s).</p></div>")
    got = abstract(page(body=body))
    assert got.startswith(first) and rest.strip() in got and got.endswith("It ends here .")
    assert "Author(s)" not in got


def test_abstract_block_that_holds_only_a_link_is_empty():
    # RSNA: the abstract's own block is a supplement link; the text after its wrapper is the article's body
    body = ('<div class="hlFld-Abstract"><h2>Abstract</h2><div class="abstractSection abstractInFull"><p>'
            '<a href="/doi/suppl/10.1148/x"><i>Supplemental material is available for this article.</i></a></p></div>'
            f'</div><div class="hlFld-Fulltext"><p>{EN}</p></div>')
    assert abstract(page(body=body), "doi", "https://pubs.example.org/doi/10.1148/x") is None
    # a short link line between the heading and the text is still skipped (DOAJ's "Read online")
    body = f'<section><h2>Abstract</h2><p><a href="/x">Read online</a></p><p class="abstract">{EN}</p></section>'
    assert abstract(page(body=body)) == EN


# --- Springer Nature: the "Impact" bullet list after the abstract --------------------------------------------------

def test_springer_abstract_ends_before_the_impact_list():
    from parseland_lib.publisher.parsers.springer import Springer
    html = (f'<section data-title="Abstract"><div class="c-article-section__content"><h3>Background</h3><p>{EN}</p>'
            '<h3 class="c-article__sub-heading">Impact Statement</h3><ul><li><p>This study found a difference.</p>'
            '</li><li><p>It matters for practice.</p></li></ul></div></section>')
    assert Springer(BeautifulSoup(html, "lxml")).parse_abstract() == EN
    # a structured abstract's own sub-headings are kept
    kept = html.replace("Impact Statement", "Results")
    assert "It matters for practice." in Springer(BeautifulSoup(kept, "lxml")).parse_abstract()


def test_inline_value_after_a_bare_colon_does_not_run_on_into_the_next_field():
    # "<b>Abstract</b>: <span>text</span> <span>Keywords: ...</span>": the first span is the whole value
    body = f"<div><b>Abstract</b>: <span>{EN}</span> <span>Keywords: exciter, rectifier, transients</span></div>"
    got = abstract(page(body=body))
    assert EN in got and "Keywords" not in got


def test_block_marked_english_in_a_related_works_panel_is_not_this_works_abstract():
    panel = f'<div class="related-articles"><div class="abstract-content" lang="en">{EN}</div></div>'
    assert abstract(page(meta("citation_abstract", FR), panel)) == FR


def test_block_marked_english_comes_without_its_heading_and_language_switch():
    # Wiley: <h3>Abstract</h3><a class="lang" hreflang="en">en</a> open the English section; ScienceDirect: an <h2>
    body = (f'<section class="article-section__abstract" lang="de"><h3>Zusammenfassung</h3><p>{FR}</p></section>'
            '<section class="article-section article-section__abstract" lang="en"><h3 class="article-section__header">'
            f'Abstract</h3><a class="lang" hreflang="en">en</a><div><h4>Objectives</h4><p>{EN}</p></div></section>')
    assert abstract(page(meta("citation_abstract", FR), body)) == "Objectives " + EN


def test_lay_summary_inside_the_abstract_is_left_out():
    # PMC pages of MDPI articles: "Simple Summary" first, then the part headed "Abstract"
    body = ('<section class="abstract" id="abstract1"><h2>Abstract</h2><section id="sec1"><h3>Simple Summary</h3>'
            f'<p>{ES}</p></section><section id="sec2"><h3>Abstract</h3><p>{EN}</p></section></section>'
            f'<section id="sec3"><h2>1. Introduction</h2><p>{FR}</p></section>')
    assert abstract(page(body=body)) == EN
    # only a lay summary: no abstract, and never the body text after the container
    only = body.replace(f'<section id="sec2"><h3>Abstract</h3><p>{EN}</p></section>', "")
    assert abstract(page(body=only)) is None
