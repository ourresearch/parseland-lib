"""oxjob #2239 phase 2, class newkeys-r4: the three new keys (acknowledgments, funding_statement, references +
references_complete). A list is called whole only when nothing around it or in it says an entry is outside it, split
or not a reference; a bold label printed as a paragraph inside "Acknowledgments" heads a sub-section; a cited
reference's pop-up is not part of the text that cites it."""
from parseland_lib.parse import parse_page

OJS = '<meta name="generator" content="Open Journal Systems 3.3.0.13"/>'
SCIELO = "https://old.scielo.br/scielo.php?script=sci_arttext&pid=S0085-56261982000100002"
SPRINGER = "https://bmcresnotes.biomedcentral.com/articles/10.1186/1756-0500-3-146"


def parse(body, head="", url="https://example.org/article/1", ns="doi"):
    return parse_page(f"<html><head>{head}</head><body>{body}</body></html>".encode(), ns, url)


def tags(entries):
    return "".join(f'<meta name="citation_reference" content="{e}"/>' for e in entries)


def ojs_list(entries):
    return ('<section class="item references"><h2 class="label">References</h2><div class="value">'
            + "".join(f"<p>{e}</p>" for e in entries) + "</div></section>")


# ---------------------------------------------------------------- SciELO: a reference printed outside the list

SCIELO_ENTRIES = ["Brust, M. &amp; G. Fraenkel, 1955. The nutritional requirements of the larvae of a blowfly. "
                  "<i>Phys. Biol. 28:</i>186-204.",
                  "Cuthbertson, A., 1933. The habits and life histories of some Diptera in southern Rhodesia. "
                  "<i>Proc. Rhod. Sci. Ass. 32:</i>81-111.",
                  "Smit, B., 1931. A study of the sheep blowflies of South Africa. <i>Onderstepoort J. Vet. 17:</i> "
                  "299-421."]
STRAY = ("Guimarães, f. H., A. P. do Prado &amp; G. M. Buralli, 1980. Dispersal and distribution of three newly "
         "introduced species of <i>Chrysomya</i> in Brazil (Diptera, Calliphoridae). <i>Ibid.</i> 23 (4):245-255.")


def scielo(before, section='<div class="articleSection">'):
    items = "".join(f"<li><div>{e}</div></li>" for e in SCIELO_ENTRIES)
    body = (f'<div class="articleSection" data-anchor="Text"><p>Full text available only in PDF format.</p><p></p>'
            f'<p>{before}</p>\n</div>{section}<div class="ref-list"><ul class="refList">{items}</ul></div></div>')
    return parse(body, f'<link rel="canonical" href="{SCIELO}"/>', SCIELO, ns="pmh")


def test_scielo_reference_printed_as_a_paragraph_before_an_unnamed_list_makes_it_not_whole():
    out = scielo(STRAY)
    assert len(out["references"]) == 3 and out["references_complete"] is False


def test_scielo_unnamed_list_after_the_articles_own_last_paragraph_is_whole():
    for last in ("Recebido para publicação em 23.11.93. Aprovado em 01.03.94.", "**Bolsista da CAPES",
                 "We conclude that there was no difference after ingestion of 420 mg of caffeine (Silva, 2004)."):
        assert scielo(last)["references_complete"] is True


def test_scielo_list_under_its_own_references_heading_is_whole_whatever_precedes_the_heading():
    named = '<div class="articleSection" data-anchor="References"><h1 class="articleSectionTitle">References</h1>'
    assert scielo(STRAY, named)["references_complete"] is True


# ---------------------------------------------------------------- typed lists: an entry split at a line break

CITAS = ["Blanco, Sergio. Autoficción. Una ingeniería del yo. Madrid: Punto de Vista Editores, 2018.",
         "Blanco, Sergio. “Ostia”. Conjunto. Revista de Teatro Latinoamericano, núm. 177, 2015, pp. 42-77.",
         "Genette, Gerard. Metalepsis. De la figura a la ficción. Traducido por Luciano Padilla López,",
         "México: Fondo de Cultura Económica, 2004.",
         "Landsberg, Alison. Prosthetic Memory. New York: Columbia University Press, 2004.",
         "Musitano, Julia. “La autoficción: una aproximación teórica”. Acta Literaria, núm. 52, 2016, pp. 103-123.",
         "Zavala, Lauro. “Para nombrar las formas de ironía”. Discurso, núm. 13, 1992, pp. 59-83."]


def test_an_entry_split_at_a_line_break_whose_second_line_falls_out_of_alphabetical_order_is_broken():
    out = parse("", tags(CITAS))
    assert len(out["references"]) == 7 and out["references_complete"] is False
    assert parse(ojs_list(CITAS), OJS)["references_complete"] is False


def test_an_alphabetical_list_with_every_entry_in_one_piece_is_whole():
    joined = CITAS[:2] + [CITAS[2] + " " + CITAS[3]] + CITAS[4:] + ["Zizek, Slavoj. Visión de paralaje. México: FCE, 2006."]
    assert parse("", tags(joined))["references_complete"] is True


def test_an_entry_closed_with_a_comma_before_entries_in_order_is_not_a_break():
    # the author typed no full stop: nothing else says the next line continues it
    open_ended = CITAS[:2] + [CITAS[2], "Landsberg, Alison. Prosthetic Memory. New York: Columbia University Press,"] \
        + CITAS[5:] + ["Zizek, Slavoj. Visión de paralaje. México: FCE, 2006."]
    assert parse("", tags(open_ended))["references_complete"] is True


def test_a_closed_entry_before_a_line_out_of_alphabetical_order_is_not_a_break():
    closed = CITAS[:2] + [CITAS[2].rstrip(",") + "."] + CITAS[3:]  # "México: ..." would be a mis-sorted entry
    assert parse("", tags(closed))["references_complete"] is True


def test_letters_with_marks_sort_with_their_plain_letter():
    turkish = ["Akgül, A. (2003). Tıbbi araştırmalarda istatistiksel analiz teknikleri. Ankara: Emek Ofset.",
               "Büyüköztürk, Ş. (2002). Sosyal bilimler için veri analizi el kitabı. Ankara: Pegem.",
               "Çokluk, Ö. (2010). Çok değişkenli istatistik. Ankara: Pegem Akademi.",
               "Kline, R. B. (2005). Principles and practice of structural equation modeling. New York: Guilford.",
               "Sümer, N. (2000). Yapısal Eşitlik Modelleri. İstanbul: Türk Psikoloji",
               "Şişko, M. & Demirhan, Ş. (2002). İlköğretim okulları ve liselerde görev yapan öğretmenler. Eğitim, 5.",
               "Tabachnick, B. G. & Fidell, L. S. (2001). Using multivariate statistics. Boston: Allyn and Bacon.",
               "Yılmaz, V. (2004). Lisrel ile yapısal eşitlik modelleri. Dumlupınar Üniversitesi Dergisi, 11, 77-90."]
    assert parse(ojs_list(turkish), OJS)["references_complete"] is True


# ---------------------------------------------------------------- a placeholder is not a reference

def test_a_placeholder_typed_in_the_references_field_is_no_reference_list():
    for placeholder in ("-", "—", ".", "..."):
        out = parse("", f'<meta name="citation_reference" content="{placeholder}" />',
                    "https://dergipark.org.tr/tr/pub/teksmuh/article/631802", ns="pmh")
        assert out["references"] is None and out["references_complete"] is False


def test_one_real_reference_is_still_a_list():
    out = parse("", '<meta name="citation_reference" content="RGDIP, 1986, p. 249"/>')
    assert [r["raw"] for r in out["references"]] == ["RGDIP, 1986, p. 249"] and out["references_complete"] is True


def test_a_placeholder_among_references_is_dropped_and_the_list_is_not_whole():
    out = parse("", tags(["Smith J. A study of things. J Things. 2001;1:1-2.", "-",
                          "Doe A. More things. J Things. 2003;3:3-4."]))
    assert [r["raw"][:5] for r in out["references"]] == ["Smith", "Doe A"] and out["references_complete"] is False
    out = parse(ojs_list(["Smith J. A study of things. J Things. 2001;1:1-2.", "***",
                          "Doe A. More things. J Things. 2003;3:3-4."]), OJS)
    assert len(out["references"]) == 2 and out["references_complete"] is False


# ---------------------------------------------------------------- acknowledgments: a bold label is a sub-heading

def sn_section(title, content):
    return (f'<section data-title="{title}"><div class="c-article-section"><h2 class="c-article-section__title">{title}'
            f'</h2><div class="c-article-section__content">{content}</div></div></section>')


THANKS = "The authors express their gratitude to Gabrielle Braun for her technical contribution to this report."
SUPPORT = ("This study was supported by the German Research Foundation (DFG, AL 1179/1-1). The authors deny any "
           "conflicts of interest related to this study.")


def test_springer_bold_label_paragraph_inside_acknowledgments_heads_a_sub_section():
    body = sn_section("Acknowledgments", f"<p>{THANKS}</p><p>\n <b>Sources of support</b>\n </p><p>{SUPPORT}</p>")
    out = parse(body, url=SPRINGER)
    assert out["acknowledgments"] == THANKS
    # its conflict-of-interest sentence is not funding text (#2239 round 8, #2215)
    assert out["funding_statement"] == "This study was supported by the German Research Foundation (DFG, AL 1179/1-1)."


def test_springer_bold_label_that_names_no_key_ends_the_acknowledgments():
    body = sn_section("Acknowledgments", f"<p>{THANKS}</p><p><strong>Competing interests</strong></p>"
                      "<p>The authors declare that they have no competing interests.</p>")
    out = parse(body, url=SPRINGER)
    assert out["acknowledgments"] == THANKS and out["funding_statement"] is None


def test_springer_bold_sentence_or_run_in_label_stays_in_the_acknowledgments():
    sentence = "<p><b>We thank all the patients who took part in this study.</b></p>"
    run_in = "<p><b>Author contributions:</b> AB wrote the paper and CD revised it.</p>"
    out = parse(sn_section("Acknowledgments", f"<p>{THANKS}</p>{sentence}{run_in}"), url=SPRINGER)
    assert out["acknowledgments"] == (f"{THANKS}\nWe thank all the patients who took part in this study.\n"
                                      "Author contributions: AB wrote the paper and CD revised it.")


# ---------------------------------------------------------------- a cited reference's pop-up is not the text

POP_UP = ('<div class="dropBlock reference-citations"><a href="#bb0120" class="reference-citations__ctrl">[24]</a>'
          '<div class="dropBlock__holder"><div class="dropBlock__body"><ul class="rlist reference-citations__loa">'
          '<li class="loa__item">Houghton D. </li><li class="loa__item">Thoma C. </li></ul><div '
          'class="reference-citations__detials">Exercise reduces liver lipids in a randomized controlled trial.'
          '<div class="popup-ref"><i>Clin Gastroenterol Hepatol.</i> 2016; </div></div><div '
          'class="reference-citations__links"><ul class="rlist"><li><a href="/servlet/linkout?dbid=8">PubMed</a></li>'
          '<li><a class="google-scholar" href="http://scholar.google.com/scholar_lookup">Google Scholar</a></li></ul>'
          '</div></div><a href="#" class="dropBlock__ctrl--close" title="Close info"></a></div></div>')


def test_a_cited_references_pop_up_inside_the_acknowledgments_is_not_part_of_them():
    body = ('<section><h2 class="top"><span class="top__text">Acknowledgments</span></h2><div class="section-paragraph">'
            f'The authors would like to thank Houghton D et al. [{POP_UP}] for providing additional data on request.</div>'
            '</section><section class="refs"><h2 class="top">References</h2></section>')
    out = parse(body, url="https://secure.jbs.elsevierhealth.com/article/S0026-0495(16)30197-1/fulltext")
    assert out["acknowledgments"] == ("The authors would like to thank Houghton D et al. [[24]] for providing "
                                      "additional data on request.")
