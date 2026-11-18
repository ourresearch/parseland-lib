"""oxjob #2239 phase 2, class newkeys-r8 (check1's funding texts; COI text, #2215).

1. A funding section that only lists funders, each in its own card, badge or list item, is the record's funder list,
   not a funding statement (the rubric: "not a funder list shown only as metadata badges"): ChemRxiv's badges,
   Atypon's "Funding Sources" list, figshare's grant cards, the Korean JATS funding box. One printed line stays.
2. Conflict-of-interest, competing-interest and financial-disclosure text is never acknowledgment or funding text, even
   inside the acknowledgments paragraph or under a Funding heading; thanks and the work's funding next to it stay.
"""
from bs4 import BeautifulSoup

from parseland_lib.back_matter import funder_list, headed_back_matter, without_coi
from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.figshare import Figshare


def parse(body, head="", url="https://example.org/article/1"):
    return parse_page(f"<html><head>{head}</head><body>{body}</body></html>".encode(), "doi", url)


def headed(html):
    return headed_back_matter(BeautifulSoup(html, "lxml"), html)


# ---------------------------------------------------------------------------------------------- funder lists

CHEMRXIV_BADGES = (  # cut from a stored ChemRxiv page (Cambridge Open Engage)
    '<div class="FundingInformation v-div"><h2 class="ml-2">Funding</h2> '
    '<div class="v-div font-smaller"><div class="v-div rounded d-inline-block"><strong>Science and Engineering '
    'Research Board</strong></div> <div class="v-div caption">EMRII/2017/001475</div> </div>'
    '<div class="v-div font-smaller"><div class="v-div rounded d-inline-block"><strong>Council for Scientific and '
    'Industrial Research (CSIR)</strong></div> <div class="v-div caption">02(0256)/16/EMR II</div> </div></div>')


def test_chemrxiv_funder_badges_are_no_funding_statement():
    assert "funding_statement" not in headed(CHEMRXIV_BADGES)


def test_atypon_funding_sources_list_is_no_funding_statement():
    html = ('<section class="core-funding"><h4>Funding Sources</h4><ul><li>Open Project Program of Wuhan National '
            'Laboratory for Optoelectronics</li></ul></section>')
    assert "funding_statement" not in headed(html)


def test_atypon_funder_rows_with_grant_numbers_are_no_funding_statement():
    html = ('<section class="core-funding"><h4>Funding Information</h4>'
            '<div role="paragraph">The National Key Research and Development Program of China: 2019YFA0307900</div>'
            '<div role="paragraph">The National Key Research and Development Program of China: 2021YFA1400300</div>'
            '<div role="paragraph">Keck Center for Quantum Magnetism at Rutgers University</div></section>')
    assert "funding_statement" not in headed(html)


def test_one_printed_funder_line_stays_the_funding_statement():
    # look-alike: one line under its own heading is the page's statement (gold: "Aspira Women's Health")
    html = ('<section class="core-funding"><h4>Funding Information</h4><div role="paragraph"><span class="named-content"'
            ' data-type="funder-name">Aspira Women\'s Health</span></div></section>')
    assert headed(html)["funding_statement"] == "Aspira Women's Health"


def test_funding_paragraphs_that_are_sentences_stay():
    html = ('<h2>Funding</h2><div><p>This work was supported by the National Science Foundation (DMR-1234).</p>'
            '<p>Open Access funding enabled and organized by Projekt DEAL.</p></div><h2>References</h2>')
    assert headed(html)["funding_statement"] == ("This work was supported by the National Science Foundation "
                                                 "(DMR-1234).\nOpen Access funding enabled and organized by Projekt DEAL.")


def test_a_list_that_a_sentence_introduces_stays():
    html = ('<h2>Funding</h2><p>This work was supported by:</p><ul><li>NSF grant 123456</li><li>NIH R01 GM1</li></ul>'
            '<h2>References</h2>')
    assert headed(html)["funding_statement"].startswith("This work was supported by:")


def test_funder_list_rule():
    assert funder_list(["NCI", "WHI", "NIH"])
    assert funder_list(["Open Project Program of Wuhan National Laboratory"], listed=True)
    assert not funder_list(["FONDECYT 1981193"])  # one printed line
    assert not funder_list(["None."])
    assert not funder_list(["NIH", "This work was supported by the NIH."])
    assert not funder_list(["Merck & Co., Inc.", "Pfizer Inc."])  # a full stop reads as a sentence: kept


def figshare(cards):
    html = ('<html><head><meta name="application-name" content="figshare"></head><body><div class="BMOMY">'
            '<h2 class="EbFsx">Funding</h2>' + "".join(f'<div class="_7P-Hc"><h3 class="jSqDa">{c}</h3></div>'
                                                      for c in cards) + '</div></body></html>')
    return Figshare(BeautifulSoup(html, "lxml"))._funding()


def test_figshare_cards_that_only_name_funders_are_no_statement():
    assert figshare(["NCI", "WHI", "National Heart, Lung, and Blood Institute", "NIH"]) is None


def test_figshare_n_a_card_is_no_statement():
    assert figshare(["n/a"]) is None


def test_figshare_single_funder_card_and_sentence_cards_stay():
    assert figshare(["Canadian Cancer Society"]) == "Canadian Cancer Society"
    assert figshare(["This work was supported by the National Natural Science Foundation of China."]) == (
        "This work was supported by the National Natural Science Foundation of China.")


# ---------------------------------------------------------------------------------------------- COI trim

def test_coi_label_run_onto_the_acknowledgment_is_trimmed():
    # PMC: "Conflict of interest" printed in the acknowledgment's paragraph
    text = "We thank J. Smith for technical help. Conflict of interest: none declared."
    assert without_coi(text) == "We thank J. Smith for technical help."


def test_declared_conflicts_and_the_disclosures_after_them_are_trimmed():
    # Springer/Adis: the declarations inside "Acknowledgements"
    text = ("No sources of funding were used to assist in the preparation of this review. The following potential "
            "conflicts of interest are declared: Maurizio Fava, M.D. has received research support from Abbott "
            "Laboratories and Pfizer. Dr. Mischoulon has received research support from Nordnaturals.")
    assert without_coi(text) == "No sources of funding were used to assist in the preparation of this review."


def test_disclosures_are_trimmed_under_a_funding_heading_too():
    text = "This work was supported by the Medical Research Council. ADM has received honoraria for lectures from Novo Nordisk."
    assert without_coi(text) == "This work was supported by the Medical Research Council."


def test_whole_coi_value_is_none():
    assert without_coi("The authors declare no conflict of interest.") is None
    assert without_coi("Competing interests\nThe authors declare that they have no competing interests.") is None


def test_a_coi_label_on_its_own_line_heads_the_next_paragraph_only():
    text = ("We thank the staff.\nConflict of interests\nThe authors declare no conflicts of interest.\n"
            "Data availability statement\nAll data are in the article.")
    assert without_coi(text) == "We thank the staff.\nData availability statement\nAll data are in the article."


def test_mixed_sentence_keeps_its_funding_clause():
    text = ("Financial support for this study was generously provided by the North Shore Cancer League of Chicago; "
            "however, the authors declare that they have no conflicts of interest.")
    assert without_coi(text) == ("Financial support for this study was generously provided by the North Shore Cancer "
                                 "League of Chicago.")


def test_mixed_sentence_drops_a_disclosed_grant_clause():
    text = "GW has received travel grants from BMS, and received honoraria from Pfizer and Knight Therapeutics."
    assert without_coi(text) is None


def test_thanks_and_funding_after_a_coi_sentence_stay():
    text = ("Authors declare that they have no conflict of interest. We thank the three anonymous reviewers for their "
            "comments.\nThe authors declare no competing interests. This work was funded by the DFG (HA 1/2).")
    assert without_coi(text) == ("We thank the three anonymous reviewers for their comments.\n"
                                 "This work was funded by the DFG (HA 1/2).")


def test_funders_role_statement_is_funding_text():
    # a funding-role statement is part of the funding section (the contract's "verbatim"), not COI text
    text = ("This work was supported by NRF grant 2014R1A2A2A01007291. The funders had no role in study design, data "
            "collection and interpretation, or the decision to submit the work for publication.")
    assert without_coi(text) == text


def test_disclosure_list_after_a_disclosure_label_is_trimmed():
    text = ("N.J.L. was supported by a Chinese Scholarship Council award.\nDisclosure: N.-J. Lu, None; F. Hafezi, chief "
            "scientific officer of EMAGine AG (E); co-inventor of the PCT applications (P)")
    assert without_coi(text) == "N.J.L. was supported by a Chinese Scholarship Council award."


def test_look_alikes_that_are_not_coi_stay():
    for text in (
            # SAGE's funding lead-in, Springer's no-funding line, a funding statement under "Financial disclosure"
            "The authors disclosed receipt of the following financial support for the research, authorship, and/or "
            "publication of this article: This work was supported by the National Research Foundation of Korea.",
            "The authors have not disclosed any funding.",
            "Financial disclosure: Supported by the National Center for Advancing Translational Sciences (UL1TR000114).",
            # consultants and advisory boards thanked, a consultancy named as a funder
            "The authors appreciate help provided by Yi-Jing Duh, PhD (StatServ Consulting Inc) with statistical analysis.",
            "We thank the TGG-N Advisory Board and the participants of the workshop for their input.",
            "This work was supported by the Office of the Deputy Vice Chancellor - Academic, Research and Consultancy.",
            "We thank Dr. Ma for the gift of the plasmid. The authors are grateful to Prof. Lee."):
        assert without_coi(text) == text, text


def test_parse_page_trims_coi_from_the_acknowledgments():
    body = ('<h2>Results</h2><p>We found it.</p><h2>Acknowledgments</h2><p>We thank Emilio Ungerfeld for discussion. '
            'The authors declare that they have no conflict of interest.</p><h2>References</h2>')
    assert parse(body)["acknowledgments"] == "We thank Emilio Ungerfeld for discussion."


# ---------------------------------------------------------------------------------------------- entry DOIs

from parseland_lib.back_matter import _clean_doi, _printed_doi, springer_nature_back_matter  # noqa: E402


def test_sici_doi_printed_with_escaped_brackets_is_whole():
    # AMS's citation tags: "...544–547.10.1175/1520-0450(1965)004&lt;0544:RSFATT&gt;2.0.CO;2"
    text = ("Fuchs, M., and TannerC. B. , 1965: Radiation shields for air temperature thermometers. J. Appl. Meteor., 4, "
            "544–547.10.1175/1520-0450(1965)004&lt;0544:RSFATT&gt;2.0.CO;2")
    assert _printed_doi(text) == "10.1175/1520-0450(1965)004<0544:RSFATT>2.0.CO;2"
    assert _printed_doi("J. Biomed. Mater. Res. 51 (2000) 200-208. https://doi.org/10.1002/(SICI)1097-4636(200008)51:2"
                        "&lt;200::AID-JBM8&gt;3.0.CO;2-Z.") == "10.1002/(SICI)1097-4636(200008)51:2<200::AID-JBM8>3.0.CO;2-Z"


def test_markup_printed_as_text_still_ends_a_doi():
    # look-alike: "&lt;" that opens a tag printed into the text is not part of the DOI
    assert _clean_doi("10.1016/j.cell.2020.115117&lt;/li") == "10.1016/j.cell.2020.115117"


def test_link_query_parameters_are_not_part_of_the_doi():
    assert _clean_doi("https://doi.org/10.1007/s00405-015-3760-0&casa_token=_oanxz-fdngaaaaa:grfrm3z8") == \
        "10.1007/s00405-015-3760-0"
    assert _clean_doi("https://www.taylorfrancis.com/books/10.1201/b17601&type=googlepdf") == "10.1201/b17601"
    assert _clean_doi("/servlet/linkout?key=10.1002/x.1&amp;dbid=16") == "10.1002/x.1"


def springer_entry(text_link, button_doi):
    return ('<ol><li class="c-article-references__item"><p class="c-article-references__text" id="ref-CR1">Liu X, Yang Y '
            '(2015) Expression of recombinant protein using Corynebacterium glutamicum. Crit Rev Biotechnol 36:1–13. '
            f'<a href="https://doi.org/{text_link}">https://doi.org/{text_link}</a></p><p class="c-article-references__links">'
            f'<a data-doi="{button_doi}" href="https://doi.org/{button_doi}">Article</a></p></li></ol>')


def test_springer_printed_link_wins_over_a_button_naming_another_doi():
    html = springer_entry("10.3109/07388551.2015.1004519", "10.3109/07388551.2013.811636")
    refs = springer_nature_back_matter(BeautifulSoup(html, "lxml"))["references"]
    assert refs[0]["doi"] == "10.3109/07388551.2015.1004519"


def test_springer_button_wins_over_a_link_that_lost_its_marks():
    # look-alike: the printed link dropped a SICI DOI's "<"; the button's is the same DOI, printed whole
    html = springer_entry("10.1130/0091-7613(2000)28703:TOBTEM>2.0.CO;2", "10.1130/0091-7613(2000)28<703:TOBTEM>2.0.CO;2")
    refs = springer_nature_back_matter(BeautifulSoup(html, "lxml"))["references"]
    assert refs[0]["doi"] == "10.1130/0091-7613(2000)28<703:TOBTEM>2.0.CO;2"


def test_springer_button_and_link_agreeing_is_unchanged():
    html = springer_entry("10.1007/s00253-011-3281-8", "10.1007/s00253-011-3281-8")
    assert springer_nature_back_matter(BeautifulSoup(html, "lxml"))["references"][0]["doi"] == "10.1007/s00253-011-3281-8"


def test_a_link_query_after_a_question_mark_is_not_part_of_the_doi():
    assert _clean_doi("https://www.tandfonline.com/doi/full/10.1080/00033790903047733?scroll=top&needAccess=true") == \
        "10.1080/00033790903047733"
    # look-alike: "&" inside a DOI, not a query parameter
    assert _clean_doi("https://doi.org/10.1207/s15327752jpa5503&4_10") == "10.1207/s15327752jpa5503&4_10"


def test_wiley_hidden_doi_with_a_lost_hyphen_takes_the_printed_links():
    from parseland_lib.back_matter import literatum_back_matter
    html = ('<section class="article-section__references"><ul><li data-bib-id="r1">Eweade, B. S. 2024. "Climate Policy '
            'Uncertainty." Natural Resources Forum: 1–22. <a href="https://doi.org/10.1111/1477-8947.12496">'
            'https://doi.org/10.1111/1477-8947.12496</a>. <div class="extra-links getFTR"><span class="hidden data-doi">'
            '10.1111/1477?8947.12496</span></div></li></ul></section>')
    refs = literatum_back_matter(BeautifulSoup(html, "lxml"), html)["references"]
    assert refs[0]["doi"] == "10.1111/1477-8947.12496"


def test_wiley_hidden_doi_with_a_lost_hyphen_takes_the_entrys_doi_link_when_the_print_is_unreadable():
    from parseland_lib.back_matter import literatum_back_matter
    html = ('<section class="article-section__references"><ul><li data-bib-id="r1">Hiyama DT. Peritonitis. '
            '<i>Br J Surg</i> (2000) 87: 1366–1374<a class="accessionId" href="https://doi.org/10.1046/j.1365-2168.2000'
            '.01552.x">10.1046/j.1365-2168.2000.01552.x</a><a class="accessionId" href="https://pubmed.ncbi.nlm.nih.gov/'
            '11044163">11044163</a><div class="extra-links getFTR"><span class="hidden data-doi">10.1046/j.1365?2168.2000'
            '.01552.x</span></div></li></ul></section>')
    refs = literatum_back_matter(BeautifulSoup(html, "lxml"), html)["references"]
    assert refs[0]["doi"] == "10.1046/j.1365-2168.2000.01552.x"
