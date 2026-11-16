"""Whole abstracts, their English version, and pages that have no abstract of their own (oxjob #2239, phase 2, class
abstract-r3).

The 32 confirmed dev cases two rounds left, plus the repeated texts the tripwire still found: a meta tag that holds one
part of the printed abstract (PubMed, RAND), language versions printed as sibling values or table rows (DSpace 7, WEKO),
the English version under "Summary" or in the middle of four, a part's page that carries the whole article's abstract
(PLOS figures, PeerJ, Pensoft, review reports), a publisher's copyright or address line glued to the end (APS, Wiley,
Thieme) and whole sections read as the abstract (LWW letters, Wiley's supporting information). Markup below is cut
down from those pages. Offline, inline HTML only.
"""
from bs4 import BeautifulSoup

from parseland_lib.abstract_language import english_part
from parseland_lib.not_abstract import clean_abstract, is_not_abstract
from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.lippincott import Lippincott

EN = ("This study aims to establish an alternative methodology for determining the main transients on brushless "
      "exciters due to transients in the main generator armature. The models of the exciter and of the rotating "
      "rectifier were implemented and the voltages and currents of the bridge diodes were monitored for each of the "
      "faults that were applied. Simulation and experimental results are compared.")
ES = ("El objetivo de este artículo es propiciar una reflexión sobre el aumento de las patologías tropicales que se "
      "relacionan con la actividad laboral de los trabajadores desplazados a otros países, bien por necesidad de la "
      "empresa donde trabajan, bien de forma voluntaria, si se trata del destino elegido por motivo de vacaciones, "
      "y se describen las medidas de prevención que deben adoptar los servicios de salud laboral.")
TR = ("Bireylerin, fiziksel ve sosyal çevrelerindeki uyumsuz koşullar nedeniyle, bedensel ve psikolojik sınırlarının "
      "ötesinde gayret harcamaları strese neden olur. Stres, bireyin rahatsız olduğu durumlara uyum sağlama çabası "
      "ile birlikte ortaya çıkan rahatsız edici duygusal durum olarak ifade edilebilir. Bu çalışmada, stres ile "
      "ilgili bir literatür taraması denemesi yapılmıştır.")
FR = ("Le stress est l’effort fourni par les individus au-delà de leurs limites physiologiques et psychologiques en "
      "raison de circonstances incompatibles issues de l’environnement physique et social. On peut définir le stress "
      "comme un état émotionnel perturbant l’individu du fait du reflet des efforts d’adaptation aux phénomènes qui "
      "le dérangent.")
UK = ("Стаття присвячена дослідженню процесу отримання структурованої меламіноформальдегідної смоли. Методом "
      "інфрачервоної спектроскопії визначені основні структурні зміни, які відбуваються в смолі на основних стадіях "
      "отримання. Досліджено вплив пластифікатору на структуру меламіноформальдегідної смоли.")
JA = ("この論文では，日本を代表する大手自動車販売会社の人事および製品取引データを用いて，店長の生産性効果や配置の問題を分析した．その結果，次の点が明らかになった．店長は重要である．"
      "店舗業績に対して大きな効果をもつ．平均的店長と比べて「悪い」店長を「良い」店長に置き換えると，新車販売による店舗獲得利益は約14％向上する．")
PARTS = ("Background: Methotrexate toxicity is a life-threatening complication in oncology patients who receive it "
         "at a high dose.", "Case presentation: We report a 19-year-old male with newly diagnosed Burkitt lymphoma "
         "who received high-dose methotrexate as part of induction chemotherapy and initially cleared it.",
         "Conclusions: This case highlights how altered pharmacokinetics in critical illness may render serum "
         "clearance thresholds unreliable and underscores the need for heightened clinical suspicion for delayed "
         "drug toxicity in critically ill patients with dynamic volume shifts or unexplained multiorgan dysfunction.")


def page(head="", body=""):
    return f"<html><head><title>A record</title>{head}</head><body>{body}</body></html>".encode()


def abstract(html, ns="pmh", url="https://repository.example.org/handle/1/2"):
    return parse_page(html, ns, url)["abstract"]


def meta(name, content, attr="name"):
    return f'<meta {attr}="{name}" content="{content}" />'


# --- a meta tag holds one part of the abstract the page prints whole -------------------------------------------------

def _pubmed(block_class="abstract-content selected", description=PARTS[2].split(": ", 1)[1]):
    paras = "".join(f"<p>{p}</p>" for p in PARTS)
    return page(meta("description", description),
                f'<div class="abstract" id="abstract"><h2 class="title">Abstract</h2>'
                f'<div class="{block_class}" id="eng">{paras}</div></div>')


def test_description_that_is_the_last_part_of_the_printed_abstract_gives_the_whole_abstract():
    got = abstract(_pubmed())
    assert got.startswith("Background: Methotrexate") and got.endswith("multiorgan dysfunction.")
    assert "Case presentation:" in got


def test_short_citation_abstract_cut_after_two_sentences_gives_the_printed_one():
    two = "A discussion of the rice premium and agricultural policy in Thailand. The effects of the rice taxes on the " \
          "farmer, on retail prices, and on government revenues are described."
    third = " It is concluded that economic incentives are distorted and production retarded, and that the burden " \
            "of the rice tax is borne not by the farmer alone, but by all of Thailand."
    html = page(meta("citation_abstract", two) + meta("citation_title", "Security and Assistance in Thailand"),
                f'<div class="abstract product-page-abstract"><p>{two}{third}</p></div>')
    assert abstract(html, "doi", None).endswith("by all of Thailand.")


def test_description_cut_after_its_first_sentences_gives_the_printed_paragraph_block():
    cut = EN[:205]
    html = page(meta("description", cut) + meta("citation_title", "Transients on brushless exciters"),
                '<section class="html-abstract" id="html-abstract"><h2 id="html-abstract-title">Abstract</h2>'
                f'<div class="html-p">{EN}</div></section><section id="html-keywords"><div>Keywords: x</div></section>')
    assert abstract(html, "doi", "https://www.mdpi.com/2071-1050/18/5/2181") == EN


def test_description_that_is_the_whole_printed_abstract_stays_as_it_is():
    whole = " ".join(PARTS)
    assert abstract(_pubmed(description=whole)) == whole


def test_description_printed_outside_any_abstract_block_is_not_widened():
    text = PARTS[2].split(": ", 1)[1]
    html = page(meta("description", text), f"<div class='record'><p>{PARTS[0]}</p><p>{text}</p></div>")
    assert abstract(html) == text


def test_block_that_holds_two_versions_under_their_own_headings_is_not_taken_whole():
    reader = GenericPublisherParser(BeautifulSoup(page(
        meta("description", EN),
        f'<div class="abstracts"><h3>Abstract</h3><p>{EN}</p><h3>Resumen</h3><p>{ES}</p></div>'), features="lxml"))
    assert reader.whole_printed_abstract(EN) is None


def test_abstract_block_that_also_holds_a_notice_or_a_byline_is_not_taken_whole():
    text = PARTS[2].split(": ", 1)[1]
    notice = ('<div class="widget-Article_Abstract_Widget"><div class="article-full-text"><p><a>This article is only '
              "available in the PDF format. Download the PDF to view the article, as well as its associated figures "
              f'and tables.</a></p><div class="h3">Abstract</div><p>{text}</p></div></div>')
    byline = (f'<div class="JournalAbstract"><div class="authors">Fiorentina Guida 1 * Laura Andreozzi 1 Daniele Zama '
              f"1 Paediatric Emergency Unit, Department of Medicine and Surgery, Bologna</div><p>{text}</p></div>")
    titled = (f'<div class="fluid abstract"><div><h6>A test of knowledge</h6></div><div class="body"><label>author(s)'
              f'</label><br>BM Alekya and S Sahana, University of Agricultural Sciences</div><div class="body"><label>'
              f"abstract</label><br>{text}</div></div>")
    sections = (f'<div id="section_abstract"><h2>Abstract</h2> {text} <hr><h2>Keywords</h2><div>task offloading; '
                "wireless sensor networks; wireless power transfer; content caching</div><div><h2>Cite This Article"
                "</h2><div>Yang, X., Yang, S. (2026). Energy-efficient offloading. Computers, 88(1), 21.</div></div></div>")
    for body in (notice, byline, titled, sections):
        assert abstract(page(meta("description", text), body)) == text, body[:40]


def test_a_parsers_own_reading_of_a_block_is_never_widened():
    reader = GenericPublisherParser(BeautifulSoup(_pubmed(description="Another text altogether."), features="lxml"))
    assert reader.whole_printed_abstract(PARTS[2]) is None  # not a meta tag's content


# --- language versions printed side by side ---------------------------------------------------------------------------

def _dspace7(first, second, tag="span", classes='class="dont-break-out ng-star-inserted"'):
    return page(meta("description", first) + meta("citation_abstract", first),
                f'<h2>Abstract</h2><div class="simple-view-element-body"><{tag} {classes}>{first}</{tag}>'
                f'<span class="separator"><br></span><{tag} {classes}>{second}</{tag}></div>')


def test_dspace_sibling_value_in_english_wins_over_the_first_value():
    assert abstract(_dspace7(UK, EN)) == EN


def test_dspace_sibling_value_in_another_language_changes_nothing():
    assert abstract(_dspace7(UK, ES)) == UK


def test_plain_paragraph_siblings_are_not_language_versions():
    assert abstract(_dspace7(UK, EN, tag="p", classes="")) == UK


def _weko(*values):
    rows = "".join('<tr><th>内容記述タイプ</th><td class="multiple-line">Abstract</td></tr>'
                   f'<tr><th>内容記述</th><td class="multiple-line">{v}</td></tr><tr><th>言語</th><td>ja</td></tr>'
                   for v in values)
    return page("", f"<table>{rows}</table>")


def test_weko_rows_typed_abstract_give_the_english_one_without_the_row_label():
    assert abstract(_weko(JA, EN)) == EN


def test_weko_single_row_gives_its_value_without_the_row_label():
    assert abstract(_weko(JA)) == JA


def test_first_abstract_in_english_is_kept_when_a_second_follows():
    other = EN.replace("This study aims", "A second study aimed")
    assert abstract(_weko(EN, other)) == EN


def _summary_page(resumen, summary, extra=""):
    return page(meta("citation_title", "Anticuerpos en ovinos"),
                f'<p align="center"><b>SUMMARY</b></p><p> </p><p>{summary}</p>{extra}'
                f'<p><b>RESUMEN</b></p><p>{resumen}</p>')


def test_english_version_under_summary_wins_over_the_resumen():
    assert abstract(_summary_page(ES, EN), "doi", "https://www.scielo.cl/scielo.php?pid=S0301") == EN


def test_summary_that_is_not_english_does_not_replace_the_resumen():
    assert abstract(_summary_page(ES, FR), "doi", "https://www.scielo.cl/scielo.php?pid=S0301") == ES


def test_lay_summary_beside_an_english_abstract_is_not_the_abstract():
    lay = EN.replace("This study aims", "In plain words, we wanted")
    html = page("", f"<h2>Summary</h2><p>{lay}</p><h2>Abstract</h2><p>{EN}</p>")
    assert abstract(html, "doi", "https://journal.example.org/a/1") == EN


def test_english_version_in_the_middle_of_four_is_cut_out():
    arabic = "الضغط النفسي هو الجهد الذي يبذله الشخص خارجًا عن حدوده البدنية والنفسية، بسبب الظروف البيئية غير المناسبة. " * 3
    got = english_part(f"{TR} {EN} {FR} {arabic}")
    assert got == EN


def test_english_abstract_with_other_languages_quoted_inside_is_not_cut():
    text = f"{EN} The Spanish title of the report is 'El objetivo de este artículo'. {EN}"
    assert english_part(text) == text


def test_springer_section_marked_english_wins_over_the_zusammenfassung():
    de = ("Die Leitlinien zur kardiopulmonalen Reanimation aus dem Jahr 2005 beinhalten keine Aussage zur konkreten "
          "Durchführung der Basismaßnahmen durch einen einzelnen Helfer, der mit einem Beatmungsbeutel ausgestattet "
          "ist und in der Beutel-Masken-Beatmung geübt ist. Ziel der Studie war es, die Effektivität der Positionen "
          "zu vergleichen.")
    html = page(meta("dc.description", de) + meta("citation_title", "Reanimation durch einen Helfer"),
                f'<section data-title="Zusammenfassung" lang="de"><h2>Zusammenfassung</h2><p>{de}</p></section>'
                f'<section data-title="Abstract" lang="en"><h2>Abstract</h2><p>{EN}</p></section>')
    assert abstract(html, "doi", "https://link.springer.com/article/10.1007/s10049-010-1391-y") == EN


# --- the text after an "Abstract" heading ------------------------------------------------------------------------------

def test_structured_abstract_with_one_div_per_part_is_read_whole():
    style = 'style="text-align: justify;"'
    divs = "".join(f"<div {style}><strong>{label}</strong> {text}</div>" for label, text in (
        ("Introduction.", "Since abortion was legalized in Spain in 1985, eugenic abortion figures have raised."),
        ("Aim.", "To promote a new judicial framework for protecting human life right from the outset."),
        ("Conclusions.", "The legalization represents an open violation of the principle of non-discrimination.")))
    html = page("", f'<div class="desc"><h3>Abstract</h3>{divs}<div class="files-list"><h4>Files</h4>'
                    f'<a href="/a.pdf">a.pdf</a></div></div>')
    got = abstract(html, "doi", "http://www.pjph.eu/issues/a07/")
    assert got.startswith("Introduction. Since") and got.endswith("non-discrimination.") and "Aim. To promote" in got


def test_div_after_an_unlabelled_abstract_div_is_not_part_of_it():
    html = page("", f"<div><h3>Abstract</h3><div>{EN}</div><div>{ES}</div></div>")
    assert abstract(html, "doi", "https://journal.example.org/a/1") == EN


def test_empty_paragraph_in_the_abstracts_own_block_means_no_abstract():
    html = page("", '<div class="abstract"><h4>Abstract</h4><p></p></div><div class="versions"><h4>Information '
                    "about this Version</h4><p>This is a Submitted version. This version's date is: 2002. This item "
                    "is not peer reviewed and it is the version that the author sent to the repository.</p></div>")
    assert abstract(html) is None


def test_empty_rule_under_the_heading_is_not_an_empty_abstract():
    html = page("", '<div class="headingContainer" id="articleAbstract_n38"><h2>Abstract</h2><div class="rule"><br>'
                    f'</div></div><div class="abstractsContainer"><div><div class="indent">{EN}</div></div></div>')
    assert abstract(html, "doi", "https://psycnet.apa.org/fulltext/2027-32349-001.html") == EN


def test_heading_alone_in_a_label_wrapper_still_reads_the_value_after_it():
    html = page("", f'<div class="abstract-label"><h4>Abstract</h4></div><div class="value">{EN}</div>')
    assert abstract(html) == EN


# --- pages that have no abstract of their own -------------------------------------------------------------------------

PLOS_HEAD = (meta("citation_abstract", EN) + meta("citation_doi", "10.1371/journal.pone.0264292")
             + meta("citation_title", "Transients on brushless exciters"))
PLOS_FIGURE = ('<img class="figure-img" alt="Figure 5"><p class="article-id"> doi:  <a   href="https://doi.org/'
               '10.1371/journal.pone.0264292.g005">https://doi.org/10.1371/journal.pone.0264292.g005</a></p>')


def test_plos_figure_page_has_no_abstract_by_its_address_or_by_the_doi_it_prints():
    by_address = "https://journals.plos.org/plosone/article/figure?id=10.1371/journal.pone.0264292.g001"
    assert abstract(page(PLOS_HEAD), "doi", by_address) is None
    assert abstract(page(PLOS_HEAD, PLOS_FIGURE), "doi", None) is None


def test_plos_article_page_keeps_its_abstract():
    url = "https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0264292"
    body = '<p class="caption"><a href="https://doi.org/10.1371/journal.pone.0264292.g001">Fig 1</a></p>'
    assert abstract(page(PLOS_HEAD, body), "doi", url) == EN


def test_part_and_report_addresses_have_no_abstract_and_the_articles_own_address_does():
    head = meta("citation_abstract", EN) + meta("citation_title", "Transients on brushless exciters")
    for url in ("https://peerj.com/articles/1234/#fig-2", "https://peerj.com/articles/cs-77/#supp-1",
                "https://zookeys.pensoft.net/article/15061/element/2/120/",
                "https://egusphere.copernicus.org/preprints/2025/egusphere-2025-4435/#RC2",
                "https://essd.copernicus.org/articles/13/3321/2021/essd-13-3321-2021-discussion.html"):
        assert abstract(page(head), "doi", url) is None, url
    for url in ("https://peerj.com/articles/1234/", "https://zookeys.pensoft.net/article/15061/",
                "https://egusphere.copernicus.org/preprints/2025/egusphere-2025-4435/"):
        assert abstract(page(head), "doi", url) == EN, url


def test_person_profile_page_has_no_abstract():
    biography = ("Teaching experience in anaesthesiology and intensive care since 2008 and until now, working with "
                 "the residency programme of the university: anaesthesiology and reanimatology for young doctors.")
    head = meta("citation_abstract", biography) + meta("citation_title", "Kumpaitiene, Birute")
    url = "https://lsmu.lt/cris/entities/person/7122402a"
    assert abstract(page(head + meta("og:type", "profile", "property")), "pmh", url) is None
    assert abstract(page(head + meta("og:type", "article", "property")), "pmh", url) == biography


def test_materials_project_description_is_kept_though_its_title_is_a_formula():
    text = ("Mo₃OBr₆ is Indium structured and crystallizes in the tetragonal I4/m space group. The structure is "
            "zero-dimensional and consists of two Mo₃OBr₆ clusters. Mo²⁺ is bonded in a distorted single-bond "
            "geometry to one O²⁻ and four equivalent Br¹⁻ atoms. The Mo–O bond length is 1.72 Å.")
    head = meta("og:title", "mp-732041: Mo3Br6O (Tetragonal, I4/m, 87)", "property") + meta(
        "og:description", text, "property")
    body = "<div id='app'>Loading...</div>"
    assert abstract(page(head + meta("og:site_name", "Materials Project", "property"), body), "doi", None) == text
    assert abstract(page(head + meta("og:site_name", "Some Portal", "property"), body), "doi", None) is None


# --- texts that are not abstracts ------------------------------------------------------------------------------------

def test_stand_in_lines_are_not_abstracts():
    for text in ("'Probenquittierung' published in 'Lexikon der Medizinischen Laboratoriumsdiagnostik'",
                 "'Geometry of Discrete Groups' published in 'Foundations of Hyperbolic Manifolds'",
                 "Seloste artikkelista: Jalkanen, R., Büttner, C. & von Bargen, S. 2007. Cherry leaf roll virus "
                 "abundant on Betula pubescens in Finland. Silva Fennica 41(4): 755–762. Näytä lisää",
                 "The digital library of Galicia forms part of Galiciana. It is promoted by the Council of Culture "
                 "and Tourism of the Xunta de Galicia and managed by the Library of Galicia.",
                 "Figure S1. Attachment and growth of clonal-density primary human melanocytes on ECM.\nPlease note: "
                 "The publisher is not responsible for the content or functionality of any supporting information "
                 "supplied by the authors. Any queries (other than missing content) should be directed to the "
                 "corresponding author for the article."):
        assert is_not_abstract(text), text


def test_abstracts_that_look_like_the_stand_ins_are_kept():
    for text in (f"'Hamlet', published in 1603, is read here beside its sources. {EN}",
                 f"{EN} Details are given in the supporting information supplied by the authors.",
                 f"Seloste artikkelista ei ole saatavilla, mutta tutkimus osoittaa seuraavaa. {EN} {EN}"):
        assert not is_not_abstract(text) and clean_abstract(text) == text, text


def test_publishers_copyright_and_address_lines_come_off_the_end():
    assert clean_abstract(EN + " \\textcopyright{} 1996 The American Physical Society.") == EN
    assert clean_abstract(EN + " This article is protected by copyright. All rights reserved.") == EN
    assert clean_abstract(EN + " Publication History Article published online: 31 July 2025 © 2025. Thieme. All "
                               "rights reserved. Georg Thieme Verlag KG Oswald-Hesse-Straße 50, 70469 Stuttgart, "
                               "Germany") == EN
    assert clean_abstract(
        EN + " Publication History Article published online: 31 January 2025 © 2025. The Author(s). This is an open "
             "access article published by Thieme under the terms of the Creative Commons Attribution License, "
             "permitting unrestricted use, distribution, and reproduction so long as the original work is properly "
             "cited. (https://creativecommons.org/licenses/by/4.0/). Georg Thieme Verlag KG Oswald-Hesse-Straße 50, "
             "70469 Stuttgart, Germany") == EN


def test_copyright_and_places_inside_or_after_an_abstract_are_not_cut():
    for text in (f"This article is protected by copyright. All rights reserved. So said the notice we study. {EN}",
                 f"{EN} The cohort was recruited in Stuttgart, Germany",
                 f"{EN} © 2020 Elsevier B.V. All rights reserved.",
                 f"We typeset \\textcopyright{{}} 1996 notices in LaTeX and compare them. {EN}"):
        assert clean_abstract(text) == text, text


# --- LWW: the body is the abstract only when it is one -----------------------------------------------------------------

def _lww(body):
    html = f'<html><body><div class="ejp-fulltext-content"><section id="ArticleBody">{body}</section></div></body></html>'
    return Lippincott(BeautifulSoup(html, features="lxml")).parse()["abstract"]


def test_lww_letter_body_with_its_closing_statements_is_not_an_abstract():
    letter = (f"<p>Dear Editor,</p><p>{EN}</p><h2>Financial support and sponsorship</h2><p>Nil.</p>"
              "<h2>Conflicts of interest</h2><p>There are no conflicts of interest.</p>")
    assert _lww(letter) is None
    assert _lww(f"<p>We read with great interest the study.</p><p>{EN}</p><h2>CONFLICTS OF INTEREST</h2><p>None.</p>") is None


def test_lww_meeting_abstract_printed_as_the_body_is_kept():
    poster = ("<h2>Background:</h2><p>Aging-related glycocalyx loss causes renal fibrosis in aging mice.</p>"
              "<h2>Methods:</h2><p>We measured it in two cohorts.</p><h2>Results:</h2><p>It fell by half.</p>"
              "<h2>Conclusions:</h2><p>Loss drives fibrosis.</p><h2>Funding:</h2><p>NIDDK Support</p>")
    assert _lww(poster).startswith("Background:") and "NIDDK Support" in _lww(poster)


# --- a title page with no "Abstract:" label (Dove Medical Press records on DOAJ) -------------------------------------

STRUCTURED = ("Background: Titanium implant-associated infection, which is mostly caused by bacterial adhesion and "
              "biofilm formation, may result in implant failure and secondary surgery.Purpose: We built a coating "
              "that kills bacteria on contact.Results: The coating killed nearly all bacteria in two hours and it "
              "did not harm the bone cells that were grown on it for a week")
BYLINE = ("Ming Guan,1,2 Yangmengfan Chen,1 Yong Wei,3 Wei Xiong11Department of Orthopedics, Tongji Hospital, Wuhan "
          "430030, People’s Republic of China; 2Wuhan National Lab for Optoelectronics, Wuhan 430074, People’s "
          "Republic of China")


def test_title_page_without_a_label_ends_where_the_first_part_label_is_glued_on():
    assert clean_abstract(BYLINE + STRUCTURED + "Keywords: bacterial infection, silver nanoparticles") == STRUCTURED
    with_email = BYLINE + "Correspondence: Wei Xiong, Tongji Hospital, Wuhan, Email xiong@example.com" + STRUCTURED
    assert clean_abstract(with_email) == STRUCTURED


def test_texts_that_only_look_like_a_title_page_are_kept():
    for text in (STRUCTURED,                                          # no byline before it
                 BYLINE + " " + STRUCTURED.replace("Background: ", "The background is this. "),  # no glued label
                 "In 2020,3 groups reported it. " + STRUCTURED):     # a label after a space is a part, not a start
        assert clean_abstract(text) == text, text


def test_english_quotation_inside_another_languages_text_is_not_its_english_version():
    de = ("Die unternehmensübergreifende Ermittlung der Bestellmengen und der Losgrößen ist das Ziel der in diesem "
          "Abschnitt dargestellten Planungsansätze, welche die Interdependenz der Entscheidungen zwischen vor- und "
          "nachgelagerten Wertschöpfungsstufen berücksichtigen und die jeweiligen individuell optimalen Lösungen "
          "der dargestellten Planungsmodelle für den Abnehmer und für den Lieferanten miteinander vergleichen. ")
    quote = ("„But it is often the case that an optimal solution for the buyer is unacceptable to the vendor, and "
             "likewise, the optimal solution for the vendor is unacceptable to the buyer, and this is the problem "
             "that the models of this section were built for.“ ")
    text = de * 2 + quote + de * 3
    assert english_part(text) == text


def test_english_version_glued_between_two_others_is_cut_at_the_sentence_ends():
    got = english_part(f"{ES}AbstractAn account. {EN}Riassunto{FR.replace('Le stress', 'Lo stress è')}")
    assert got.endswith("are compared.") and "This study aims" in got and "objetivo" not in got and "effort" not in got


# --- second pack (abstract-r3b): versions in blocks of their own, a quotation, a meeting abstract under "Extract" -----

TR2 = TR + " Çalışmada, stres konusundaki araştırmaların tarihçesi ve stresin izlediği seyir ele alınmıştır."


def test_dergipark_language_tabs_give_the_english_block():
    def tab(text):
        return (f'<div class="tab-pane"><div class="article-abstract data-section"><h3 class="dergipark">Öz</h3>'
                f"<p><span>{text}</span></p></div></div>")
    html = page(meta("citation_abstract", TR2) + meta("citation_title", "Modern çağın hastalığı"), tab(TR2) + tab(EN))
    assert abstract(html, "pmh", None) == EN
    assert abstract(page(meta("citation_abstract", TR2), tab(TR2) + tab(ES)), "pmh", None) == TR2


def test_dspace_theme_with_one_abstract_block_per_value_gives_the_english_one():
    def value(text):
        return (f'<div class="mb-4"><div class="abstract-text clamped-abstract"> {text} </div>'
                '<div class="mt-1"><button>Show more</button></div><hr></div>')
    ru = UK.replace("Стаття присвячена", "Статья посвящена")
    html = page(meta("description", UK), "<h2>Abstract</h2>" + value(UK) + value(ru) + value(EN))
    assert abstract(html) == EN


def test_abstract_blocks_of_other_works_are_not_this_works_english_version():
    related = f'<div class="related-articles"><div class="article-abstract">{EN}</div></div>'
    html = page(meta("citation_abstract", TR2), f'<div class="article-abstract">{TR2}</div>' + related)
    assert abstract(html, "pmh", None) == TR2


def test_english_quotation_that_ends_another_languages_abstract_is_not_cut_out():
    de = ("Der Startpunkt für die Anwendung der Fuzzy-Logik in der Mustererkennung, und später auch in der "
          "Bildverarbeitung, war ein Artikel, in dem die Autoren die Musterklassifikation als Abstraktion und "
          "Generalisierung von Daten ansahen. Im Jahre 1970 stellte Prewitt fest, daß man Bildmengen, die ein Objekt "
          "repräsentieren, als Fuzzy-Mengen betrachten kann: ")
    quote = ("„… a pictorial object is a fuzzy set which is specified by some membership function defined on all "
             "picture points. From this point of view, each image point participates in many memberships. Some of "
             "this uncertainty is due to degradation, but some of it is inherent, and this is the point of the "
             "method that is used for the analysis of the pictures.“")
    assert english_part(de + quote) == de + quote


OUP_EXTRACT = ('<div class="widget-ArticleFulltext"><h2 class="abstract-title at-Extract-Title">Extract</h2>'
               '<section class="abstract extract">{}</section></div>')
OUP_URL = "https://academic.oup.com/eurheartj/article-abstract/38/suppl_1/ehx502.P2596/4089320"


def test_meeting_abstract_printed_under_extract_is_kept():
    parts = ("<p><strong>Introduction:</strong> Chronic thromboembolic pulmonary hypertension is a leading cause of "
             "pulmonary hypertension and endarterectomy is the treatment of choice.</p><p><strong>Methods:</strong> "
             "All patients evaluated by a multidisciplinary team from 1996 to 2015 were included.</p><p><strong>"
             "Results:</strong> A total of 1006 patients were referred and survival rose over the years.</p>")
    got = abstract(page(meta("citation_title", "Survival over years"), OUP_EXTRACT.format(parts)), "doi", OUP_URL)
    assert got and got.startswith("Introduction:") and "Results:" in got


def test_opening_printed_under_extract_is_still_not_an_abstract():
    opening = ("<p>Valley is, of course, the chief and the most remarkable. But the State is full of wonderful "
               "natural phenomena; and when the tourist has seen the Yosemite, the Calaveras Big Tree Grove, the "
               "Geysers and Mount Shasta, he has left unseen still Mono Lake and many a quiet mountain road.</p>")
    html = page(meta("citation_title", "A journey"), OUP_EXTRACT.format(opening))
    assert abstract(html, "doi", OUP_URL.replace("P2596", "001")) is None
