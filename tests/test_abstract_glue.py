"""Page text and markup glued onto an abstract come off; a contents list or a site blurb is not an abstract
(oxjob #2239, phase 2).

On a random 33,557 stored pages the parser returned 261 abstracts with raw HTML tags in them, 142 ending in
Springer's machine-keywords disclaimer, 28 in IGI Global's access notice, 16 starting with ACS's figure toolbar,
13 Wiley section lists, 11 opening with PubMan's HTML comments, 7 LWW abstracts with the machine-written summary
attached, and two sites' own descriptions. Markup below is cut down from those pages. Offline, inline HTML only.
"""
import pytest
from bs4 import BeautifulSoup

from parseland_lib.not_abstract import clean_abstract, is_not_abstract
from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.acs import ACS
from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.igi_global import IGIGlobal
from parseland_lib.publisher.parsers.springer import Springer

REAL = ("We recall the main elements of fire weather in the Mediterranean environment and present the Canadian Fire "
        "Weather Index (FWI) System as the fire danger rating system currently most widely applied in Mediterranean "
        "Europe. Finally we present a regression model that predicts monthly burned area from monthly averages of "
        "the Initial Spread Index, valid for the months May to November.")
DISCLAIMER = ("These keywords were added by machine and not by the authors. This process is experimental and the "
              "keywords may be updated as the learning algorithm improves.")


# --- Springer: machine-chosen keywords and their disclaimer inside the abstract's section -------------------------

SPRINGER = f"""<html><head><link rel="canonical" href="https://link.springer.com/chapter/10.1007/978-3-642-01754-4_6"/>
</head><body><section aria-labelledby="Abs1" data-title="Abstract" lang="en"><div class="c-article-section" id="Abs1-section">
<h2 class="c-article-section__title" id="Abs1">Abstract</h2><div class="c-article-section__content" id="Abs1-content">
<p>{REAL}</p><h3 class="c-article__sub-heading">Keywords</h3><ul class="c-article-subject-list">
<li class="c-article-subject-list__subject"><span>Fire Danger</span></li>
<li class="c-article-subject-list__subject"><span>Drought Code</span></li></ul>
<p><i>{DISCLAIMER}</i></p></div></div></section></body></html>"""


def test_springer_abstract_ends_where_its_keywords_start():
    assert Springer(BeautifulSoup(SPRINGER, "lxml")).parse_abstract() == REAL
    assert parse_page(SPRINGER.encode(), "doi", "https://link.springer.com/chapter/10.1007/978-3-642-01754-4_6")[
        "abstract"] == REAL


def test_springer_structured_abstract_keeps_every_paragraph():
    # sub-headings inside an abstract are its own structure; only "Keywords" ends it
    html = SPRINGER.replace(f"<p>{REAL}</p>", f'<h3 class="c-article__sub-heading">Background</h3><p>{REAL}</p>'
                            f'<h3 class="c-article__sub-heading">Results</h3><p>Burned area fell by half.</p>')
    assert Springer(BeautifulSoup(html, "lxml")).parse_abstract() == REAL + "\nBurned area fell by half."


@pytest.mark.parametrize("glued", [
    f"{REAL}\n{DISCLAIMER}",  # the Springer parser's own join, before its fix
    f"{REAL} Keywords Fire Danger Fire Weather Index Drought Code {DISCLAIMER}",  # a block reader: the list comes too
    f"{REAL}{DISCLAIMER}",
])
def test_keywords_disclaimer_comes_off_whichever_reader_took_it(glued):
    assert clean_abstract(glued) == REAL


def test_abstract_that_talks_about_keywords_is_kept():
    text = ("Keywords were added by machine to 4,000 abstracts and not by the authors, and we measure how often "
            "readers notice. Keywords chosen by a learning algorithm were judged as useful as the authors' own in "
            "three of four fields, which suggests that publishers may add them where authors gave none.")
    assert clean_abstract(text) is text


# --- raw HTML / JATS in the abstract's meta tag ------------------------------------------------------------------

def test_block_tags_become_lines_and_inline_tags_close_up():
    raw = ("<h3>Background</h3>\n<p>Introduction of tumor necrosis factor alpha (TNF) inhibitors has revolutionized "
           "therapy of rheumatoid arthritis.<sup>1</sup> Adding Al(OH)<sub>3</sub> gave <i>R</i><sup>2</sup> = 0.87 "
           "at &lt;5&nbsp;&deg;C &amp; pH&nbsp;7.</p><h3>Methods</h3>\n<p>A cross-sectional study,<br/>two "
           "centres.</p>")
    assert clean_abstract(raw) == (
        "Background\nIntroduction of tumor necrosis factor alpha (TNF) inhibitors has revolutionized therapy of "
        "rheumatoid arthritis.1 Adding Al(OH)3 gave R2 = 0.87 at <5 °C & pH 7.\nMethods\nA cross-sectional study,"
        "\ntwo centres.")


def test_meta_tag_markup_is_plain_text_after_parse_page():
    body = "The dynamic behaviour of steel-concrete composite beams under CO<sub>2</sub> curing is studied here. " * 3
    html = (f'<html><head><meta name="citation_title" content="Composite beams"/>'
            f'<meta name="citation_author" content="Ana Ruiz"/>'
            f'<meta name="citation_abstract" content="&lt;div&gt;&lt;p&gt;{body.strip()}&lt;/p&gt;&lt;/div&gt;"/>'
            f'</head><body></body></html>')
    out = parse_page(html.encode(), "doi", "https://example.org/article/1")["abstract"]
    assert out == body.replace("CO<sub>2</sub>", "CO2").strip()


def test_copernicus_label_and_paragraph_tags():
    # citation_abstract on Copernicus journals and EGUsphere
    raw = ('<p><strong class="journal-contentHeaderColor">Abstract.</strong> The point cloud segmentation of gullies '
           'with high accuracy lays the groundwork for the gully parameter extraction for various '
           'roughness&rsquo;s of the channel bottom, and this method provides a new idea.</p>')
    assert clean_abstract(raw) == ("The point cloud segmentation of gullies with high accuracy lays the groundwork "
                                   "for the gully parameter extraction for various roughness’s of the channel "
                                   "bottom, and this method provides a new idea.")


@pytest.mark.parametrize("raw, plain", [
    # JATS, as Crossref-fed pages print it
    ("<jats:title>Abstract</jats:title><jats:sec><jats:title>Background</jats:title><jats:p>Midwives "
     "(<jats:italic>n</jats:italic> = 34) took part.</jats:p></jats:sec>", "Background\nMidwives (n = 34) took part."),
    # the label in its own paragraph
    ('<div lang="en" class="abs"><p class="abs_header">Abstract</p><p><em>Aims:</em> A validated method.</p></div>',
     "Aims: A validated method."),
    # markup escaped once more inside the tag
    ("&lt;p&gt;Recently, 3D generation methods have shown their power.&lt;/p&gt;",
     "Recently, 3D generation methods have shown their power."),
    # MathML and unknown elements the text itself closes
    ("collisions at <math><msqrt><msub><mi>s</mi><mi>NN</mi></msub></msqrt><mo>=</mo><mn>2.76</mn></math> TeV",
     "collisions at sNN=2.76 TeV"),
    ("the effects of <TEX>${\\gamma}$</TEX>-aminobutylic acid", "the effects of ${\\gamma}$-aminobutylic acid"),
    # sloppy markup: HAL closes <i> with <i/>; a wrapper <p> whose end was cut off
    ("<i>Mycoplasma bovis<i/> est un agent majeur; <i>M. bovis<i/> résiste à 10<sup>-4<sup/> M.",
     "Mycoplasma bovis est un agent majeur; M. bovis résiste à 10-4 M."),
    ("<p>In this paper we apply an existence theory and estimates on the mean <p> of the flow.",
     "In this paper we apply an existence theory and estimates on the mean <p> of the flow."),
    # the source's own line breaks are spaces once the text is HTML
    ("<p>Rhizosheath size varies with crop genotype,\nand root exudation drives it.</p><p>Second.</p>",
     "Rhizosheath size varies with crop genotype, and root exudation drives it.\nSecond."),
])
def test_markup_shapes(raw, plain):
    assert clean_abstract(raw) == plain


@pytest.mark.parametrize("text", [
    "Survival was longer in the treated group (p < 0.05), and for all 0<x<1 the bound a<b and c>d holds as stated.",
    "The scatter between photometric and spectroscopic redshifts (<Delta z/(1 + z(spec))> = 0.29) is larger.",
    "The steam fraction in the producer gas (X_<steam>) and the level L_<Aeq> were measured; <Hg-N> is 2.400 Å.",
    "Code is available in the repository <https://github.com/mra/clustering-workflow> and at <http://example.org/>.",
    "The mean momentum <p> and the order parameter <s> are computed, and an <EOS> token ends each sequence.",
    "Read et<iam>si remisso animo with the insertion <vel severissimo>, where homo refers to all humans.",
    "Johnson &Lindsay's buffer was used (C&EN, July 23); see trials/show.php?mid1=71771&copy=2&region=eu for data.",
    "Abstract interpretation is a theory of sound approximation of the semantics of computer programs.",
])
def test_text_that_only_looks_like_markup_is_kept(text):
    assert clean_abstract(text) is text


def test_untouched_abstract_keeps_its_own_spacing():
    text = "First paragraph of a plain abstract.\n\n  Second paragraph,  with its own spacing.\n"
    assert clean_abstract(text) is text


def test_label_stays_when_it_starts_a_sentence_inside_markup():
    assert clean_abstract("<p>Abstract interpretation is a theory of sound approximation.</p>") == (
        "Abstract interpretation is a theory of sound approximation.")


# --- IGI Global: the paywall's notice inside the abstract's element ----------------------------------------------

IGI_REAL = ("This chapter examines the role of law reform in promoting the development of technical standards for "
            "the authentication of parties. Neither approach has yet resolved the authentication problems facing "
            "businesses engaged in online commerce.")
IGI = f"""<html><head><meta property="og:url" content="https://www.igi-global.com/gateway/chapter/41803"/></head>
<body><span id="ctl00_cphFeatured_lblAffiliates">Jane K. Winn (University of Washington, USA)</span>
<span id="ctl00_cphMain_lblAbstract">{IGI_REAL}<div id="sample" class="xml-reader-bookstore">
<div class="preview-footer"><a href="#title-recommendation-form">Request access from your librarian to read this
chapter's full text.</a></div></div></span></body></html>"""


def test_igi_access_notice_is_not_abstract_text():
    soup = BeautifulSoup(IGI, "lxml")
    assert IGIGlobal(soup).parse_abstract() == IGI_REAL
    assert "Request access" in soup.get_text()  # the page other readers use is left whole
    assert parse_page(IGI.encode(), "doi", "https://www.igi-global.com/gateway/chapter/41803")["abstract"] == IGI_REAL


@pytest.mark.parametrize("notice", [
    " Request access from your librarian to read this chapter's full text.",
    "Request access from your librarian to read this article’s full text.",
])
def test_igi_notice_comes_off_whichever_reader_took_it(notice):
    assert clean_abstract(IGI_REAL + notice) == IGI_REAL


def test_abstract_about_library_access_requests_is_kept():
    text = ("Readers who request access from their librarian to read a chapter's full text wait a median of nine "
            "days. We surveyed 212 libraries on how such requests are handled and what share of them is granted.")
    assert clean_abstract(text) is text


# --- ACS: the graphical abstract's figure toolbar -----------------------------------------------------------------

ACS_REAL = ("Cyclopropanes are highly useful motifs that are often incorporated into drug candidates to improve "
            "potency. An expedient method for the α-cyclopropanation of ketones is described.")
ACS_PAGE = f"""<html><head><meta property="og:url" content="https://pubs.acs.org/doi/10.1021/acs.orglett.3c01768"/>
</head><body><ul class="loa"><li><div class="loa-info-name">Ana Ruiz</div></li></ul>
<h2 class="article_abstract-title" id="Abstract">Abstract</h2>
<div class="article_abstract-content hlFld-Abstract" id="abstractBox"><figure id="_i1" class="article__inlineFigure
article_abstract-img"><img class="inline-fig internalNav" src="/cms/ol3c01768_0009.gif" alt=""/>
<div class="figure-bottom-links"><div class="download-hi-res-img"><a title="High Resolution Image" href="/x.jpeg">
<span>High Resolution Image</span></a></div><div class="download-ppt"><a title="Download MS PowerPoint Slide"
href="/action/downloadFigures"><span>Download MS PowerPoint Slide</span></a></div></div></figure>
<p class="articleBody_abstractText">{ACS_REAL}</p></div></body></html>"""


def test_acs_figure_toolbar_is_not_abstract_text():
    soup = BeautifulSoup(ACS_PAGE, "lxml")
    assert ACS(soup).get_abstract() == ACS_REAL
    assert soup.select_one("#abstractBox figure") is not None  # the page other readers use is left whole


@pytest.mark.parametrize("glue", [
    "High Resolution Image Download MS PowerPoint Slide ",  # ACS, read by a block reader
    "CiteSeerX - Document Details (Isaac Councill, Lee Giles, Pradeep Teregowda): ",
    "CiteSeerX - Document Details (Isaac Councill, Lee Giles, Pradeep Teregowda): Abstract: ",
])
def test_glued_openings_come_off(glue):
    assert clean_abstract(glue + ACS_REAL) == ACS_REAL


def test_abstract_about_image_downloads_is_kept():
    text = ("High resolution image download speeds limit teleradiology in rural clinics. We compare three "
            "compression schemes for MS PowerPoint slide decks and DICOM series over links of 1 to 10 Mbit/s.")
    assert clean_abstract(text) is text


# --- a list of section headings is a table of contents ------------------------------------------------------------

WILEY_CONTENTS = ("This chapter contains sections titled:\n\n         \n\nIntroduction\n\n\nCCR5 Antagonist Programs"
                  "\n\n\nMolecular Interactions and Binding Modes of CCR5 Receptor Antagonists\n\n\nResistance to "
                  "CCR5 Receptor Antagonists\n\n\nOutlook\n\n\nReferences")


def test_wiley_section_list_is_not_an_abstract():
    assert is_not_abstract(WILEY_CONTENTS)
    assert is_not_abstract(WILEY_CONTENTS + "\n\n\nFurther reading" * 200)  # whatever its length
    assert clean_abstract(WILEY_CONTENTS) is None


def test_abstract_that_describes_its_sections_is_kept():
    text = ("This chapter contains three sections on CCR5 antagonists. The first reviews the discovery programs, the "
            "second the binding modes of the receptor antagonists, and the third the resistance seen in the clinic.")
    assert not is_not_abstract(text)


# --- PubMan (MPG PuRe, GFZ, PIK): HTML comments are not printed text ---------------------------------------------

PUBMAN_REAL = ("We discuss the peeling behaviour of the Weyl tensor near null infinity for an asymptotically flat "
               "higher dimensional spacetime and describe how these results can be used to write the Bondi energy "
               "flux in terms of Newman-Penrose Weyl components.")
PUBMAN = f"""<html><body><!-- Abstract Tile --><div class="third_area0 tile_category borderBrown">
<!-- Abstract title and image --><div class="third_area0_p6"><h5 class="tile_title">
<img src="../resources/images/overviewPage/abstract_31.png" class="big_imgBtn" align="right" />Abstract</h5></div>
<!-- If no abstracts are available show message-->
<!-- Iterator for abstracts --><div class="third_area0_p6">{PUBMAN_REAL}</div></div></body></html>"""


def test_html_comments_are_not_read_as_abstract_text():
    assert GenericPublisherParser(BeautifulSoup(PUBMAN, "lxml")).parse_headed_abstract_section() == PUBMAN_REAL
    assert parse_page(PUBMAN.encode(), "pmh", None)["abstract"] == PUBMAN_REAL


def test_iop_empty_video_abstract_slot_is_two_comments():
    # "Start article video abstract End article video abstract" opened IOP abstracts read by the heading reader
    html = (f'<html><body><div class="article-text"><h2>Abstract</h2><!-- Start article video abstract -->'
            f'<!-- End article video abstract --><div class="wd-jnl-art-abstract"><p>{PUBMAN_REAL}</p></div></div>'
            f'</body></html>')
    assert GenericPublisherParser(BeautifulSoup(html, "lxml")).parse_headed_abstract_section(
        main_article=True) == PUBMAN_REAL


# --- LWW: the abstract's own tab, not the machine-written summary beside it ---------------------------------------

LWW_REAL = ("Myocardial remodeling, a complex adaptive response to pathological stimuli, plays a pivotal role in the "
            "progression of various cardiovascular diseases. This review covers safer therapeutic strategies for "
            "managing myocardial remodeling and its associated cardiovascular diseases.")
LWW = """<html><head><meta property="og:url" content="https://journals.lww.com/md-journal/fulltext/2025/06060/x.aspx"/>
</head><body><section id="ejp-article-authors"><p id="P7">Ruiz, Ana MD<sup>a</sup></p></section>
<section class="ejp-article-tabs" id="abstractWrap"><div aria-label="Tabs" class="ejp-article-tabs__tablist"
role="tablist"><button class="ejp-article-tabs__tablist-item" id="tab1" role="tab">Abstract</button>
<button class="ejp-article-tabs__tablist-item ejp-article-tabs__ai-summary" id="tab4" role="tab">Plain Language
Summary</button></div><div class="ejp-article-tabs__tabpanel" id="panel1" role="tabpanel">
<div id="article-abstract-content1"><div class="ejp-article-text-abstract"><p>%s</p></div></div></div>
<div class="ejp-article-tabs__tabpanel" id="panel4" role="tabpanel"><div id="article-abstract-content3"><p>
<span class="ejp-indicator">Plain Language Summary</span>Myocardial remodeling is a key factor in the progression of
heart diseases like arrhythmias and heart failure.</p><p><i>Text is machine generated and may contain inaccuracies.
</i><a href="https://lww.com/Pages/plainlanguagesummaries.aspx">FAQ</a></p></div></div></section></body></html>"""


@pytest.mark.parametrize("real", [
    LWW_REAL,
    # an abstract that itself talks about such summaries is kept whole
    ("A Plain Language Summary now accompanies many journal articles. We compared reader comprehension of 60 "
     "abstracts with and without one, and found that text which is machine generated may contain inaccuracies "
     "that readers do not notice."),
])
def test_lww_abstract_without_the_machine_written_summary(real):
    out = parse_page((LWW % real).encode(), "doi", "https://journals.lww.com/md-journal/fulltext/2025/06060/x.aspx")
    assert out["abstract"] == real


# --- a site's own description, reworded or translated since the list was frozen -----------------------------------

BVPH = ("The Virtual Library of Historical Newspapers (BVPH), managed by the Subdirectorate General for Library "
        "Coordination under the umbrella of the Ministry of Culture, is a digital newspaper library where the "
        "public has access to an extensive, varied and growing collection of historical newspapers and cultural "
        "magazines in Spanish languages.")
GALICIANA = ("A biblioteca dixital de Galicia forma parte de Galiciana. Está impulsada pola Consellería de Cultura e "
             "Turismo da Xunta de Galicia e xestionada pola Biblioteca de Galicia co obxectivo de difundir e "
             "preservar o rico acervo bibliográfico e patrimonial galego.")


@pytest.mark.parametrize("blurb", [BVPH, GALICIANA, GALICIANA + " Galiciana está presente en Hispana."])
def test_site_description_is_not_an_abstract(blurb):
    assert is_not_abstract(blurb)


def test_site_description_in_a_record_page_tag_gives_no_abstract():
    html = (f'<html><head><meta name="DC.title" content="El Avisador numantino: Año XIV Número 1340"/>'
            f'<meta name="DC.description" content="{BVPH}"/></head><body><h1>El Avisador numantino</h1></body></html>')
    assert parse_page(html.encode(), "pmh", "https://prensahistorica.mcu.es/es/consulta/registro.do?id=1")[
        "abstract"] is None


def test_abstract_about_the_newspaper_library_is_kept():
    text = ("We study how the Virtual Library of Historical Newspapers (BVPH), managed by the Subdirectorate General "
            "for Library Coordination, digitised 2,000 titles, and what its readers searched for between 2010 and "
            "2020.")
    assert not is_not_abstract(text)
