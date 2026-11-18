"""Abstract fixes from check1's confirmed-worse pages (oxjob #2239, phase 2, round 8).

Each behaviour has its look-alike that must not change. Markup is cut from the stored pages.
"""
import pytest

from parseland_lib.abstract_language import english_part
from parseland_lib.not_abstract import clean_abstract, is_not_abstract
from parseland_lib.parse import _is_structured_abstract, parse_page

LONG = ("A taxonomic revision of the genus Cenophengus LeConte, 1881 (Coleoptera: Phengodidae) is provided, including "
        "new data on geographic ranges of the species. This is the first time this genus has been recorded for Belize "
        "and in Honduras. Four new species are described and a key to the valid species is given. The study "
        "includes diagnoses, descriptions, photographs and distribution maps of the thirty valid species.")


def seo_page(description, title):
    return (f'<html><head><meta name="citation_title" content="{title}">'
            f'<meta property="og:description" content="{description}"></head>'
            '<body><div id="app"></div></body></html>')


# --- a description tag that restates the item's title is still its abstract -----------------------------------------

def test_description_restating_its_title_is_the_abstract():
    title = "Revision of the genus Cenophengus LeConte, 1881 (Coleoptera, Phengodidae)"
    assert parse_page(seo_page(LONG, title), "doi")["abstract"] == LONG


def test_citation_line_with_the_title_is_still_not():
    title = "Harmonic Source Location in Radial Distribution Feeders"
    citation = ("Michael B. Walbank, Harmonic Source Location in Radial Distribution Feeders, Hesperia: The Journal of "
                "the American School of Classical Studies at Athens, Vol. 81, No. 2 (2012), pp. 231-262, with notes on "
                "the inscriptions and their dates, and a list of the documents.")
    assert parse_page(seo_page(citation, title), "pmh")["abstract"] in (None, "")


# --- a meeting abstract under Oxford Academic's "Extract" heading ----------------------------------------------------

def test_structured_opening_is_a_structured_abstract():
    assert _is_structured_abstract("Background: The assessment of mortality has been done. Purpose: The aim of the "
                                   "study is to compare. Methods: The meta-analysis included 3839 patients.")


def test_book_review_opening_is_not():
    assert not _is_structured_abstract("This book sets out to explain why. Methods matter, the author says: none.")


# --- page text glued to an abstract ----------------------------------------------------------------------------------

BODY = ("A child's education, both academic and social, is significantly improved through effective collaborations "
        "between families and schools. For young children with disabilities, partnerships are especially critical.")


def test_ms_word_style_sheet_is_cut():
    junk = ('Normal 0 false false false BS-LATN-BA X-NONE X-NONE /* Style Definitions */ table.MsoNormalTable '
            '{mso-style-name:"Table Normal"; mso-tstyle-rowband-size:0; font-family:"Times New Roman",serif;} ')
    assert clean_abstract(junk + BODY) == BODY


def test_text_about_normal_values_stays():
    text = "Normal 0 to 5 values were found in all false positive samples, and " + BODY
    assert clean_abstract(text) == text


@pytest.mark.parametrize("tail", [
    " HIGHLIGHTS Zhang's approach is validated for tailings.; The correlation among dosage was revealed.;",
    " Plain Language Summary. During bypass grafting, preparation of veins with saline damages the endothelium.",
    " MSC codes 39A10 39A12 Keywords oscillation difference equations linear second order",
    "\nKey messages: Nodule location is a risk factor.",
    "-Chatel, B., Bendahan, D., Pellerin, L., Messonnier, L. A. Role of MCT1 and CAII in skeletal muscle pH.",
])
def test_trailing_section_is_cut(tail):
    assert clean_abstract(BODY + tail) == BODY


def test_highlights_in_a_sentence_stay():
    text = BODY + " These highlights of the plain language summary approach are discussed in detail here."
    assert clean_abstract(text) == text


def test_dove_byline_before_abstract_label_is_cut():
    byline = ("Xiaoyun Zhang,1 Shijie Zhang,1 Qin He,2 1Department of Clinical Laboratory, First Affiliated Hospital "
              "of Zhengzhou University, Zhengzhou, Henan 450052, China; 2Department of Medical Laboratory, Fuwai "
              "Central China Cardiovascular Hospital, Zhengzhou, China Abstract: ")
    assert clean_abstract(byline + BODY) == BODY


def test_marker_before_comma_byline_with_glued_label_is_cut():
    byline = ("Omary Mashiku Minzi1, Deus Buma2, Godeliver A Kagashe3 1Unit of Pharmacology and Therapeutics, School "
              "of Pharmacy, Muhimbili University of Health and Allied Sciences, Dar Es Salaam, Tanzania")
    assert clean_abstract(byline + "Background: " + BODY) == "Background: " + BODY


@pytest.mark.parametrize("notice", [
    "#Preprint #PeerReviewMe: Warning: This is a unreviewed preprint. Readers are warned that the document has not "
    "been peer-reviewed. Please cite this preprint only for review purposes (if you are the author).\r\n\t ",
    "Correction: On 16th February 2017, the author K. Peiris was removed from this paper. This error is regretted. "
    "- Editor",
    "Retraction Notice: The publisher wishes to retract the chapter Dev Kumar Mandal, 2026. The authors agree with "
    "the retraction.\n",
])
def test_leading_notice_is_cut(notice):
    assert clean_abstract(notice + BODY) == BODY


@pytest.mark.parametrize("tail", [
    "\nThis abstract is from the Experimental Biology 2018 Meeting. There is no full text article associated with "
    "this abstract published in The FASEB Journal.",
    "This article can also be found at the Monthly Review website, where most recent articles are published in "
    "full.Click here to purchase a PDF version of this article at the Monthly Review website.",
])
def test_site_notice_after_abstract_is_cut(tail):
    assert clean_abstract(BODY + tail) == BODY


# --- not an abstract -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "In: Abstracts of the annual meeting of the Southern African Society for Plant Pathology, Rob Ferreira, p. 27.",
    "22 - 62nd Meeting of the Phycological Society of America",
    "L'abstract è presente nell'allegato / the abstract is in the attachment",
    "Jika membutuhkan abstrak atau isi jurnal silahkan menghubungi author melalui email a@b.id .",
    "Для открытия архива необходима программа WinRAR версии 5.0 и выше.",
    "„Das Geheimnis des Glücks ist die Freiheit, das Geheimnis der Freiheit aber ist der Mut.“ Perikles",
    "(single paragraph). The incorrect statement was “In general, variance was low.” It was corrected to: ...",
    "Sun J-M, Chao Y, Kim S-B, et al. First-line tiragolumab plus atezolizumab. Lancet Oncol 2025; 26: 1-10. In this "
    "Article, the appendix was wrong. The file has been corrected as of Feb 2, 2026.",
    "Author Information Show + Alcínia Zita Sampaio * Department of Civil Engineering, University of Lisbon",
    "Beytulhikme An International Journal of Philosophy is a peer-reviewed, hybrid open-access academic journal, and "
    "is published quarterly.",
    "E-Journal IAIN Pekalongan adalah Web Portal yang memberikan berbagai konten bermanfaat dan berkualitas.",
    "Susanne Andreae, Peter Avelini, Melanie Berg, Ingo Blank, Annelie Burk, Anette Dierolf, Gerhard Dockter, "
    "Chiara Dold, Momo Evers",
    "Karla Poewe, (ed.), Charismatic Christianity as a Global Culture. Columbia, University of South Carolina Press "
    "1994, 300 pp. $34.95, ISBN 0 87249 996 0.\nUrsula King, Women and Spirituality. University Park, Pennsylvania "
    "State University Press 1992, 155 pp. $35.95, ISBN 0 8204 1914 1.\nCorrected version of a book review.",
    "The Valencian Digital Library (Bivaldi) is a free access repository whose purpose is the digitization of works.",
    "La Biblioteca Valenciana Digital (Bivaldi) es un repositorio de acceso libre cuya finalidad es la digitalización.",
])
def test_not_an_abstract(text):
    assert is_not_abstract(text)


@pytest.mark.parametrize("text", [
    "In this study we examined 40 patients. In: vitro results were confirmed in vivo across all sites studied here.",
    "We compare compression by gzip, bzip2 and 7-zip on a corpus of scholarly PDFs and report ratios and speed.",
    "The Journal of Hydrology is an international journal; this study analyses its citations from 1990 to 2020 and "
    "shows how its authorship changed.",
    "Smith, Jones and colleagues measured fluxes at four sites, Berlin, Paris, Madrid and Rome, over two years.",
    "Reviews of three books on the Reformation. The first, by Ann Smith, ISBN 978-0-19-123456-7, argues that the "
    "printing press mattered less than thought; the second disagrees at length with every one of her points.",
])
def test_look_alike_is_still_an_abstract(text):
    assert not is_not_abstract(text)


# --- language versions -----------------------------------------------------------------------------------------------

def test_short_two_script_versions_give_the_english_one():
    text = ('Обґрунтування інструментів нейромаркетингової стратегії для підвищення ефективності просування '
            'кафе-кондитерської "Coockie". Substantiation of neuromarketing strategy tools to increase the '
            'effectiveness of the promotion of the "Coockie" confectionery cafe.')
    assert english_part(text) == ('Substantiation of neuromarketing strategy tools to increase the effectiveness of '
                                  'the promotion of the "Coockie" confectionery cafe.')


def test_short_one_language_text_stays():
    text = "Получены условия существования непрерывных решений одного класса систем уравнений (Lemma 2.1)."
    assert english_part(text) == text


def test_labelled_short_english_version_in_a_long_text():
    uk = "UK: " + "Наведені методичні матеріали та вказівки до виконання лабораторних робіт з дисципліни. " * 2
    ru = " RU: " + "Приведены методические материалы и указания к выполнению лабораторных работ по дисциплине. " * 2
    en = "The methodical materials and instructions for laboratory work on parallel computing."
    assert english_part(uk + "EN: " + en + ru) == en


def test_front_matter_in_another_language_does_not_replace_english():
    english = ("This paper summarizes part of a study concerning the industrial development prospects of French "
               "regions. The analysis presented is based on the notion of a process of international division of "
               "labor, and the position of French regions in this process is examined.")
    french = ("Ce document constitue une synthèse d'un travail de réflexion mené conjointement par le Laboratoire de "
              "Conjoncture et Prospective et la Société ACT, sur l'avenir de l'industrialisation des régions "
              "françaises. Les auteurs examinent les perspectives de développement industriel des régions dans le "
              "cadre de la division internationale du travail et de ses évolutions possibles.")
    html = ('<html><head><meta name="dc.Description" content="' + english + '"></head><body>'
            '<div class="abstractSection abstractInFull"><p>' + english + '</p></div>'
            '<div id="abstracts" data-extent="frontmatter"><section id="abstract"><h2>Résumé</h2><div '
            'role="paragraph">' + french + '</div></section></div></body></html>')
    assert parse_page(html, "doi")["abstract"] == english


# --- whose abstract it is --------------------------------------------------------------------------------------------

def test_publons_review_page_has_no_abstract():
    html = ('<html><head><meta name="description" content="View 3 peer reviews of Alcohol and Circadian Disruption '
            'Minimally Impact Bone Properties in Two Cohorts of Male Mice While Between-Cohort Differences Predominate '
            'on Publons"></head><body><h3>Abstract</h3><p>' + LONG + '</p></body></html>')
    assert parse_page(html, "doi", "https://publons.com/wos-op/publon/50892161/")["abstract"] is None


def test_tandfonline_cut_description_is_not_the_abstract():
    cut = ("The target article by Jecker and colleagues is a call to arms for the field of bioethics, to take the "
           "ethics of war more seriously as a public health issue, and to use the tools of bioethics to add...")
    html = ('<html><head><meta property="og:url" content="https://www.tandfonline.com/doi/full/10.1080/1"><meta '
            'name="dc.Description" content="' + cut + '"><meta name="dc.Creator" content="Ann Smith"></head><body>'
            '</body></html>')
    assert parse_page(html, "doi")["abstract"] is None


def test_description_naming_the_record_at_its_end_is_not_the_abstract():
    title = "Secretary's Department - London Letters - To London (Indexed) September 1960 - May 1961"
    text = ("Size: 39.5MB | Series: London Letters (1912 to 1975) | Read the full record details for Files & Documents: "
            "Secretary's Department - London Letters - To London (Indexed) September 1960 - May 1961")
    assert parse_page(seo_page(text, title), "doi")["abstract"] in (None, "")


def test_clinical_english_front_matter_still_replaces_a_cut_tag():
    part = ("Transcatheter mitral valve replacement (TMVR) is an alternative to redo surgery for failed mitral "
            "bioprostheses, but left ventricular outflow tract (LVOT) obstruction remains a major limitation.")
    whole = ("Background " + part + " Case Summary An 86-year-old woman presented with heart failure due to severe "
             "prosthetic mitral restenosis. Screening CT predicted a critically small neo-LVOT, rendering TMVR "
             "prohibitive. Short-term mavacamten enlarged the predicted neo-LVOT and TMVR was performed safely.")
    html = ('<html><head><meta name="dc.Description" content="' + part + '"></head><body><div id="abstracts" '
            'data-extent="frontmatter"><section id="abstract"><h2>Abstract</h2><div role="paragraph">' + whole +
            '</div></section></div></body></html>')
    assert parse_page(html, "doi")["abstract"] == whole


# --- stock descriptions of the item's kind (round 8 follow-up) -------------------------------------------------------

@pytest.mark.parametrize("text", [
    "Presents the table of contents/splash page of the proceedings record.",
    "Presents the table of contents for this issue of the periodical.",
    "Presents the front cover/table of contents for this issue of the periodical.",
    "Presents the front cover, title page, or splash screen of the proceedings record.",
    "Presents the cover from the proceedings of this conference.",
    "The author index contains an entry for each author and coauthor included in the proceedings record.",
    "Presents an index of the authors whose articles are published in the conference proceedings record.",
    "Provides instructions and guidelines to prospective authors who wish to submit manuscripts.",
    "Presents the copyright information for the conference. May include reprint permission information.",
    "Provides a listing of current staff, committee members and society officers.",
    "Ab-initio phonon calculation for BaNd2ZnO5 / I4/mcm (140)\nPhonon band structure, phonon DOS, thermal properties at "
    "constant volume, and phonon raw data are presented.\nThe initial crystal structure used to perform phonon calculation "
    "is obtained from the Materials Project using\npymatgen MPRester. The phonon band structure paths are determined "
    "using SeeK-path.",
])
def test_stock_item_description_is_not_an_abstract(text):
    assert is_not_abstract(text)


@pytest.mark.parametrize("text", [
    "Presents the table of contents for this issue of the periodical, and reviews the five papers on radar imaging in it.",
    "We present an ab-initio phonon calculation for BaNd2ZnO5 and show that its thermal conductivity is low because "
    "of strong anharmonic scattering of acoustic phonons.",
    "Ab-initio phonon calculation for AlPO4 / P3_221 (154)\nPhonon band structure, phonon DOS, thermal properties at "
    "constant volume, and phonon raw data are presented.\nWe find two soft modes that drive the alpha-beta transition.",
])
def test_stock_item_description_look_alike_stays(text):
    assert not is_not_abstract(text)
