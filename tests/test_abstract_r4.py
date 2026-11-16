"""Text that is not the abstract, returned as one (oxjob #2239, phase 2, class abstract-r4).

Round 4's confirmed dev cases: the authors' biographies read as the abstract on an Open Journal Systems page (the
block after the abstract's), a keyword list printed inside the abstract's block (Esploro) or as its last paragraph, the
abstract printed twice behind a "Show more" toggle (Leiden), a pasted page around the abstract (AVESIS), the Galiciana
site description in Spanish, and a layout class ("has_sidebar") read as a sidebar. Markup below is cut down from those
pages. Offline, inline HTML only.
"""
import pytest
from bs4 import BeautifulSoup

from parseland_lib.not_abstract import clean_abstract, is_not_abstract
from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.parser import _in_page_chrome, _is_label_wrapper
from parseland_lib.publisher.parsers.utils import states_what_the_work_does

EN = ("Introducing the French astronomer Camille Flammarion (1842-1925), from his personal trajectory, intellectual "
      "production and historic context in one discussion in which aspects of his work are related to the presentation "
      "of data from a literature review. The shortage of studies that focus on the pedagogical potential of his work "
      "for contemporary science teaching was one of the results found.")
PT = ("Apresentamos o astrônomo francês Camille Flammarion (1842-1925), a partir de sua trajetória pessoal, produção "
      "intelectual e contexto histórico em uma discussão na qual aspectos de suas obras são relacionadas à "
      "apresentação dos dados provenientes de uma revisão de literatura. A escassez de estudos sobre o potencial "
      "pedagógico da obra foi um dos resultados encontrados.")
BIO = ("Doutoranda em Ensino de Ciência e Tecnologia. Mestre em História pela Universidade Federal do Paraná, "
       "Licenciada em Artes Visuais pela Universidade Estadual de Ponta Grossa com especialização em Arte e Ensino das "
       "Artes. É professora efetiva de Arte na Secretaria de Educação do Estado do Paraná.")
OJS_URL = "https://revistas.example.br/index.php/hcensino/article/view/60928"


def ojs_page(main):
    return ('<html><head><meta name="generator" content="Open Journal Systems 3.3.0.13"/>'
            '<meta name="citation_author" content="Carla Nascimento"/>'
            f'<meta name="citation_title" content="Camille Flammarion"/></head>'
            f'<body class="pkp_page_article"><div class="pkp_structure_page">'
            f'<div class="pkp_structure_content has_sidebar"><div class="pkp_structure_main" role="main">'
            f'<article class="obj_article_details"><div class="main_entry">{main}</div></article></div>'
            f'<div class="pkp_structure_sidebar left" role="complementary"><div class="pkp_block block_x">'
            f'<h2>Abstract</h2><p>{EN.replace("Introducing", "Sidebar")}</p></div></div></div></div></body></html>')


def page(head="", body=""):
    return f"<html><head><title>A record</title>{head}</head><body>{body}</body></html>"


def abstract(html, ns="pmh", url="https://repository.example.org/handle/1/2"):
    return parse_page(html.encode(), ns, url)["abstract"]


BIOS = ('<section class="item author_bios"><h2 class="label">Biografia do Autor</h2><section class="sub_item">'
        '<h3 class="label">Carla Nascimento, <span class="affiliation">UTFPR</span></h3>'
        f'<div class="value"><p>{BIO}</p></div></section></section>')


# --- the authors' biographies are never the abstract -----------------------------------------------------------------

def test_ojs_block_that_repeats_its_label_gives_the_english_version_not_the_biographies():
    # revistas.pucsp.br: "Resumo" is the block's label and the text's own first line; "Abstract" sits two wrappers deep
    main = (f'<section class="item abstract"><h2 class="label">Resumo</h2><p><strong>Resumo</strong></p>'
            f'<p><em>{PT}</em></p><p><strong><em>Palavras-chave</em></strong><em>: Astronomia, História</em></p>'
            f'<p><strong><em>Abstract</em></strong></p><p><em>{EN}</em></p>'
            f'<p><em> </em><strong><em>Keywords</em></strong><em>: Astronomy, History of Science</em></p></section>'
            + BIOS)
    assert abstract(ojs_page(main), "doi", OJS_URL) == EN


def test_ojs_empty_abstract_block_never_gives_the_block_after_it():
    empty = '<section class="item abstract"><h2 class="label">Resumo</h2></section>'
    references = (f'<section class="item references"><h2 class="label">Referências</h2><div class="value">'
                  f'<p>{BIO}</p></div></section>')
    assert abstract(ojs_page(empty + BIOS), "doi", OJS_URL) is None
    assert abstract(ojs_page(empty + references), "doi", OJS_URL) is None


@pytest.mark.parametrize("heading", [
    "Biografia do Autor", "Author Biography", "Author Biographies", "Biografía del autor/a", "About the Author(s)",
    "About the Authors", "Biografia de l'autor/a", "Biographie de l'auteur-e", "Biografie auteur", "Biogram autora",
    "Autor/innen-Biografie", "Författarbiografi", "Forfatterbiografi", "Біографії авторів", "Биография автора",
    "Сведения об авторах", "Sobre os autores", "作者简介"])
def test_block_headed_as_author_biography_is_not_the_abstract(heading):
    # a custom theme, any site: the "Abstract" label sits in a wrapper of its own and its value is missing
    body = (f'<div class="article"><div class="label"><h3>Abstract</h3></div>'
            f'<div class="bio"><h3>{heading}</h3><p>{BIO}</p></div></div>')
    assert abstract(page(body=body)) is None
    assert abstract(page(body=body), "doi", "https://journal.example.org/article/7") is None


def test_block_headed_with_a_part_of_the_abstract_is_still_read():
    # look-alike: the block after the label's wrapper opens with a heading of its own, a structured abstract's part
    body = (f'<div class="article"><div class="label"><h3>Abstract</h3></div>'
            f'<div class="text"><h4>Background</h4><p>{EN}</p></div></div>')
    assert abstract(page(body=body)) == f"Background {EN}"


def test_abstract_that_talks_about_the_author_is_kept():
    text = "About the author of this diary little is known. " + EN
    assert abstract(page(body=f"<h2>Abstract</h2><p>{text}</p>")) == text


def test_label_two_wrappers_deep():
    body = f"<div><p><strong><em>Abstract</em></strong></p><p>{EN}</p></div>"
    assert abstract(page(body=body)) == EN


def test_label_wrapper_holds_the_label_and_nothing_else():
    soup = BeautifulSoup("<div id='a'><p><b>Abstract</b></p></div><div id='b'><p><b>Abstract</b></p> and more</div>",
                         "lxml")
    first, second = soup.find_all("b")
    assert _is_label_wrapper(soup.find(id="a"), first)
    assert not _is_label_wrapper(soup.find(id="b"), second)
    assert not _is_label_wrapper(soup.body, first)


# --- keywords are not abstract text ----------------------------------------------------------------------------------

def esploro(text):
    return page(body=(
        '<div class="section-content"><h2 class="section-title" id="section-title-abstract"> Abstract </h2>'
        '<esp-description-and-keywords><mulo-keywords class="mulo-keywords display-block">'
        '<mulo-keyword-item class="mulo-keyword-item"><span class="content"> anxiety </span></mulo-keyword-item>'
        '<mulo-keyword-item class="mulo-keyword-item"><span class="content"> behavioral economics </span>'
        '</mulo-keyword-item></mulo-keywords><mulo-expandable class="mulo-expandable abstract">'
        f'<div class="content"><span>{text}</span></div></mulo-expandable></esp-description-and-keywords></div>'))


def test_keyword_list_inside_the_abstract_block_is_left_out():
    assert abstract(esploro(EN)) == EN


def test_keyword_list_with_a_notice_under_the_heading_is_no_abstract():
    # scholarship.libraries.rutgers.edu: a correction notice of 68 characters; the keywords made it long enough
    assert abstract(esploro("[This corrects the article on p. 77 in vol. 11, PMID: 28270744.].")) is None


def test_highlighted_keyword_inside_a_sentence_stays():
    text = EN.replace("astronomer", '<span class="keyword">astronomer</span>')
    assert abstract(page(body=f'<h2>Abstract</h2><div class="value">{text}</div>')) == EN


def test_keyword_paragraph_ends_the_abstract():
    body = (f"<h2>Resumo</h2><p>{PT}</p><p><strong>Palavras-chave</strong>: Astronomia, História da Ciência</p>"
            f"<p>{BIO}</p>")
    assert abstract(page(body=body)) == PT


def test_paragraph_that_only_mentions_keywords_is_kept():
    second = "Keywords such as these were then searched in three databases, and the results were compared by hand."
    assert abstract(page(body=f"<h2>Abstract</h2><p>{EN}</p><p>{second}</p>")) == f"{EN} {second}"


# --- the abstract printed twice behind a "Show more" toggle ----------------------------------------------------------

def test_abstract_behind_a_show_more_toggle_is_given_once():
    # Leiden's repository: the tag holds the whole text; the block prints a cut copy, then the whole
    cut = EN[:230]
    html = page(head=f'<meta name="citation_title" content="A thesis"/><meta name="citation_abstract" content="{EN}"/>',
                body=f'<dl><dd class="abstract"><span class="toggle-wrapper"><span>{cut}...<a href="#" '
                     f'class="toggler">Show more</a></span><span>{EN}<a href="#" class="toggler">Show less</a></span>'
                     f'</span></dd></dl>')
    assert abstract(html) == EN


def test_tag_that_holds_one_part_still_gives_the_whole_printed_abstract():
    # look-alike (round 3): what the block adds is new text
    parts = ("Background: Methotrexate toxicity is a life-threatening complication in oncology patients who receive it "
             "at a high dose and clear it slowly.",
             "Conclusions: This case highlights how altered pharmacokinetics in critical illness may render serum "
             "clearance thresholds unreliable and underscores the need for heightened clinical suspicion for delayed "
             "drug toxicity in critically ill patients with dynamic volume shifts or unexplained multiorgan failure.")
    html = page(head=f'<meta name="citation_title" content="A case"/><meta name="description" content="{parts[1]}"/>',
                body=f'<div class="abstract" id="abstract"><h2>Abstract</h2><p>{parts[0]}</p><p>{parts[1]}</p></div>')
    assert abstract(html) == " ".join(parts)


# --- a pasted page around the abstract -------------------------------------------------------------------------------

TR = ("Bu çalışmanın amacı, kedilerde veteriner kliniğine transport sırasında gözlenen korku, kaygı ve/veya stres "
      "belirtilerini azaltmak amacı ile gabapentin kullanımının etkinliğini belirlemektir.\r\nMateryal ve method: "
      "Çalışmaya 1 yaşından büyük, farklı ırklardan 20 sağlıklı kedi dahil edilmiştir.\r\nSonuç: Gabapentin, uygun "
      "dozda ve sürede kullanıldığında stres belirtilerini azaltmak için kullanılabilir.")
PASTED = ("14. Ulusal 3. Uluslararası Veteriner İç Hastalıkları Kongresi\r\n    30.11-03.12.2023 Marmaris\r\n    "
          "https://www.vih2023.org\r\n    \r\n    2\r\n  \r\nVeteriner kliniğine gelirken stres belirtileri gösteren "
          "kedilerde gabapentin kullanımıEbru\r\nYALÇIN, Azize KAHRAMAN, Gizem DOĞANBursa Uludağ Üniversitesi, "
          "Veteriner\r\nFakültesi İç Hastalıkları Ana Bilim DalıÖzet\r\n\r\n\r\n" + TR
          + "\r\n\r\n\r\n\r\nAnahtar kelimeler: Korku, kaygı, stres, kedi, gabapentin")


def test_pasted_page_gives_the_text_after_its_glued_label():
    assert clean_abstract(PASTED) == TR


def test_label_on_its_own_line_or_after_capitals_is_left_alone():
    two_versions = TR + "\r\nAbstract\r\n" + EN  # a second version's label, on a line of its own
    assert clean_abstract(two_versions) == two_versions
    acronym = "A study of the structure of DNAAbstract\n" + EN
    assert clean_abstract(acronym) == acronym


# --- a site's description, a layout class ----------------------------------------------------------------------------

GALICIANA_ES = ("La biblioteca digital de Galicia forma parte de Galiciana. Está impulsada por la Consejería de Cultura "
                "y Turismo de la Xunta de Galicia y gestionada por la Biblioteca de Galicia con el objetivo de difundir "
                "y preservar el rico acervo bibliográfico y patrimonial gallego. El proyecto pretende no sólo la "
                "digitalización de los fondos patrimoniales sino también la normalización del acceso.")
GALICIANA_GL = GALICIANA_ES.replace("La biblioteca digital", "A biblioteca dixital")
GALICIANA_EN = ("The digital library of Galicia forms part of Galiciana. It is promoted by the Council of Culture and "
                "Tourism of the Xunta de Galicia and managed by the Library of Galicia with the aim to spread and "
                "preserve the rich acervo bibliographic and patrimonial Galician. The project pretends no only the "
                "digitalisation of the bottoms patrimoniales but also the normalisation of the access.")


def test_galiciana_description_in_spanish_is_not_an_abstract():
    assert is_not_abstract(GALICIANA_ES)
    head = ('<meta name="DC.title" content="La Voz de Galicia: 1 de enero de 1900"/>'
            + "".join(f'<meta name="DC.description" lang="{lang}" content="{text}"/>'
                      for lang, text in (("gl", GALICIANA_GL), ("es", GALICIANA_ES), ("en", GALICIANA_EN))))
    assert abstract(page(head=head)) is None


def test_abstract_that_names_the_library_is_kept():
    text = EN + " Las fuentes proceden de la biblioteca digital de Galicia, que forma parte de Galiciana."
    assert not is_not_abstract(text)


@pytest.mark.parametrize("classes,chrome", [
    ("pkp_structure_content has_sidebar", False), ("content with-sidebar", False), ("page no-sidebar", False),
    ("layout has-sidebar", False), ("pkp_structure_sidebar left", True), ("sidebar", True), ("left-sidebar", True),
    ("site_sidebar", True)])
def test_class_that_says_the_layout_has_a_sidebar_is_not_chrome(classes, chrome):
    soup = BeautifulSoup(f'<body><div class="{classes}"><h2 id="h">Abstract</h2></div></body>', "lxml")
    assert _in_page_chrome(soup.find(id="h")) is chrome


def test_abstract_in_a_has_sidebar_layout_is_read_and_the_sidebar_is_not():
    # a repository record on an OJS site (no OJS reader for records): the generic heading reader now sees the column
    main = f'<section class="item abstract"><h2 class="label">Abstract</h2><p>{EN}</p></section>'
    assert abstract(ojs_page(main)) == EN
    assert abstract(ojs_page("<p>No abstract on this page.</p>")) is None


# --- rules that stay as they are -------------------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    # Taylor & Francis chapter openings (a813a452, 9888b266): body text
    "Orthotropic Steel Bridge Decks (OSD) are lightweight compared with reinforced concrete decks and are generally "
    "used in long-span bridges. Figure 17.1 shows a typical box girder with OSD.",
    "Speaking about his collaboration with Leon Garfield when they were reframing some of the ancient Greek myths as "
    "The God Beneath the Sea Edward Blishen said, ‘It was like working with a sort of radium of story’.",
    # Bloomsbury synopses (32818fce, 5afa88cf): written about the item, but they do not say what the work does
    "I shall shortly be eighty-eight. High time to be giving serious thought to the direction my life should be "
    "taking. In an upper-crust retirement home, Geoffrey Wythenshaw sits down to write his memoir.",
    "New Zealand born pianist/composer Mike Nock is one of the acknowledged masters of jazz with over twenty-five "
    "years working in the USA with many of the world’s top jazz musicians."])
def test_the_descriptive_test_keeps_none_of_these(text):
    assert not states_what_the_work_does(text)
