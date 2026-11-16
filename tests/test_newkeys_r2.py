"""oxjob #2239 phase 2, class newkeys-r2: the three new keys (acknowledgments, funding_statement, references +
references_complete). A section ends where the next one starts, a funder widget or an unfilled template slot is not a
statement, a review report's page carries no back matter of its own, an entry's DOI is the one it prints and never
half of one, and a list is called whole only when nothing in it says an entry is broken, merged or missing."""
from parseland_lib.back_matter import _clean_doi, _printed_doi
from parseland_lib.parse import parse_page

LITERATUM = '<div class="pb-dropzone" data-pb-dropzone="x"></div>'
OJS = '<meta name="generator" content="Open Journal Systems 3.3.0.13"/>'


def parse(body, head="", url="https://example.org/article/1", ns="doi"):
    return parse_page(f"<html><head>{head}</head><body>{body}</body></html>".encode(), ns, url)


def sn_item(text, counter=None, doi=None):
    counter = f' data-counter="{counter}"' if counter else ""
    button = f'<p class="c-article-references__links"><a data-doi="{doi}" href="https://doi.org/{doi}">Article</a></p>' \
        if doi else ""
    return (f'<li class="c-article-references__item"{counter}><p class="c-article-references__text">{text}</p>'
            f'{button}</li>')


def sn_section(title, content):
    return (f'<section data-title="{title}"><div class="c-article-section"><h2 class="c-article-section__title">{title}'
            f'</h2><div class="c-article-section__content">{content}</div></div></section>')


def ojs_list(entries):
    return ('<section class="item references"><h2 class="label">References</h2><div class="value">'
            + "".join(f"<p>{e}</p>" for e in entries) + "</div></section>")


SPRINGER = "https://link.springer.com/article/10.1007/s13555-022-00735-9"

# ---------------------------------------------------------------- acknowledgments and funding: where a section ends


def test_springer_acknowledgements_end_at_their_first_sub_heading():
    body = sn_section("Acknowledgements", '<p>We thank the group facilitators for their time.</p>'
                      '<h3 class="c-article__sub-heading">Funding</h3><p>This study was funded by the National '
                      'Institute on Disability, Grant H133N110006.</p><h3 class="c-article__sub-heading">Author '
                      'contributions</h3><p>JC wrote the manuscript and all authors revised it.</p>')
    out = parse(body, url=SPRINGER)
    assert out["acknowledgments"] == "We thank the group facilitators for their time."
    assert out["funding_statement"] == "This study was funded by the National Institute on Disability, Grant H133N110006."


def test_springer_acknowledgements_made_only_of_other_sub_sections_are_no_acknowledgments():
    body = sn_section("Acknowledgements", '<h3 class="c-article__sub-heading">Funding</h3><p>No funding or sponsorship '
                      'was received for this study.</p><h3 class="c-article__sub-heading">Disclosures</h3>'
                      '<p>The authors have nothing to disclose at all.</p>')
    out = parse(body, url=SPRINGER)
    assert out["acknowledgments"] is None
    assert out["funding_statement"] == "No funding or sponsorship was received for this study."


def test_springer_acknowledgements_without_sub_headings_keep_every_paragraph():
    body = sn_section("Acknowledgements", "<p>We thank the reviewers.</p><p>We also thank the editors of the volume.</p>")
    assert parse(body, url=SPRINGER)["acknowledgments"] == "We thank the reviewers.\nWe also thank the editors of the volume."


ACS_MENU = ('<div class="article_content-sections"><span>ARTICLE SECTIONS</span><div class="article_sections-dropBlock">'
            '<a href="#"><span>Jump To</span></a></div></div>')


def test_a_heading_wrapped_with_its_section_menu_reads_the_text_after_the_wrapper():
    body = ('<div class="ack" id="ack1"><div class="article_content-header"><div class="article_content-header-row">'
            f'<div class="article_content-title"><h2 id="_i54">Acknowledgments</h2></div>{ACS_MENU}</div></div><hr/>'
            '<p class="last">We thank CSIRO and Imperial College London for a studentship (to K.A.B.).</p></div>')
    out = parse(body, url="https://pubs.acs.org/doi/10.1021/acs.joc.0c00067")
    assert out["acknowledgments"] == "We thank CSIRO and Imperial College London for a studentship (to K.A.B.)."


def test_a_heading_inside_a_header_block_with_its_own_text_keeps_that_text():
    body = ('<div class="section-header"><h2>Funding</h2><p>This work was supported by the Wellcome Trust (107653).</p>'
            '</div><p>The rest of the page is about something else entirely.</p>')
    assert parse(body)["funding_statement"] == "This work was supported by the Wellcome Trust (107653)."


def test_a_funding_statement_ends_at_a_paragraph_that_opens_with_another_sections_label():
    body = ('<h2>ACKNOWLEDGEMENTS</h2><p class="chapter-para">We thank the sequencing facility for its patient help.</p>'
            '<p class="chapter-para"><em>Author contributions</em>: A.K.C. and R.P.M. designed the study.</p>'
            '<h2>FUNDING</h2><p class="chapter-para">Australian Research Council [DE180100929]; NHMRC [1159752].</p>'
            '<p class="chapter-para"><em>Conflict of interest statement</em>. None declared.</p><h2>REFERENCES</h2>')
    out = parse(body, url="https://academic.oup.com/nar/article/49/1/1/6000000")
    assert out["funding_statement"] == "Australian Research Council [DE180100929]; NHMRC [1159752]."
    # under "Acknowledgements" a run-in paragraph is part of the section as the page prints it
    assert out["acknowledgments"] == ("We thank the sequencing facility for its patient help.\n"
                                      "Author contributions: A.K.C. and R.P.M. designed the study.")


def test_facility_and_software_notes_after_the_acknowledgments_are_not_part_of_them():
    body = ('<h2 id="Acknowledgments">Acknowledgments</h2><div class="article-text"><p>M.H. would like to acknowledge '
            'NASA support via award 80NSSC21K1536.</p><p><em>Facility:</em> Keck:I, APF, TESS.</p>'
            '<p><em>Software:</em> exoplanet (Foreman-Mackey et al. 2021).</p></div>')
    assert parse(body)["acknowledgments"] == "M.H. would like to acknowledge NASA support via award 80NSSC21K1536."


def test_a_section_whose_own_text_opens_with_such_a_word_is_kept():
    body = ('<h2>Acknowledgments</h2><p>Software development was supported by the Sloan Foundation.</p>'
            '<p>Conflicting schedules were resolved by the observatory staff, whom we thank.</p>')
    assert parse(body)["acknowledgments"] == ("Software development was supported by the Sloan Foundation.\n"
                                              "Conflicting schedules were resolved by the observatory staff, whom we thank.")


# ---------------------------------------------------------------- funder widgets and unfilled templates


def test_a_label_value_list_of_awards_is_not_a_funding_statement():
    zenodo = ('<div class="ui grid"><div class="column"><h3 class="ui header">Funding</h3></div><div class="column">'
              '<dl class="details-list"><dt class="ui tiny header"><span>Characterising viral antibody evasion.</span>'
              '<span class="ui mini basic label">107653</span></dt><dd class="text-muted">Wellcome Trust</dd></dl>'
              '</div></div>')
    assert parse(zenodo, ns="pmh")["funding_statement"] is None


def test_a_table_of_funders_after_the_funding_text_is_left_out():
    pure = ('<div class="rendering"><h3 class="subheader">Funding</h3><p>The research was funded in part by the '
            'Coordination for the Development of Higher Education Personnel (CAPES), Grand Code 001.</p>'
            '<table class="properties funders_informations_table"><tbody><tr><th>Funders</th><th>Funder number</th></tr>'
            '<tr><td>Laboratório Vagner</td></tr><tr><td>CAPES</td><td>001</td></tr></tbody></table></div>')
    assert parse(pure, ns="pmh")["funding_statement"] == (
        "The research was funded in part by the Coordination for the Development of Higher Education Personnel "
        "(CAPES), Grand Code 001.")


def test_a_template_slot_nobody_filled_in_is_not_a_statement():
    body = ('<div class="module3" id="fundingArea"><h5 class="title">Funding</h5><div class="fundingContent">'
            '<span class="text">{{article.fundingStatement}}</span></div></div>')
    assert parse(body)["funding_statement"] is None
    filled = body.replace("{{article.fundingStatement}}", "Supported by the National Natural Science Foundation of China.")
    assert parse(filled)["funding_statement"] == "Supported by the National Natural Science Foundation of China."


# ---------------------------------------------------------------- a review report's page


def test_a_review_reports_page_carries_the_reviewed_articles_back_matter_not_its_own():
    head = ('<meta name="citation_reference" content="Bertolini G. Landslides in Emilia-Romagna. Landslides. 2005;2:302."/>'
            '<meta name="citation_reference" content="Zhu D. Revival deformation of Hefeng Landslide. Geomorphology. 2011;1:2."/>')
    body = '<h2>Acknowledgements</h2><p>We thank Z Ji for preliminary experiments with SUN2 truncations.</p>'
    for url in ("https://essd.copernicus.org/articles/13/3321/2021/essd-13-3321-2021-discussion.html",
                "https://elifesciences.org/articles/81573#sa2",
                "https://egusphere.copernicus.org/preprints/2025/egusphere-2025-4435/#RC2"):
        out = parse(body, head, url)
        assert out["references"] is None and out["references_complete"] is False and out["acknowledgments"] is None
    for url in ("https://elifesciences.org/articles/81573", "https://www.peer-review-journal.org/article/7#abstract"):
        article = parse(body, head, url)
        assert len(article["references"]) == 2 and article["acknowledgments"].startswith("We thank Z Ji")


# ---------------------------------------------------------------- an entry's DOI


def test_a_doi_read_from_text_stops_where_the_doi_does():
    assert _clean_doi("https://doi.org/10.1016/j.engstruct.2022.115117</li") == "10.1016/j.engstruct.2022.115117"
    assert _clean_doi("http://www.blackwell-synergy.com/links/doi/10.1111/j.0013-8703.2004.00128.x/abs/") == \
        "10.1111/j.0013-8703.2004.00128.x"
    assert _clean_doi("https://doi.org/10.1007/978-3-642-28990-3_17#Sec4") == "10.1007/978-3-642-28990-3_17"
    assert _clean_doi("https://www.degruyterbrill.com/document/doi/10.1515/9783110311075-026/html") == \
        "10.1515/9783110311075-026"
    assert _clean_doi("http://dx.doi.org/10.1016/j.regsciurbeco.2008.06.005%0Ahttps://www.researchgate.net/x") == \
        "10.1016/j.regsciurbeco.2008.06.005"
    assert _printed_doi("https://doi.org/10.4236/ajcc.2012.11001Brini, R. (2021). Renewable") == "10.4236/ajcc.2012.11001"
    assert _clean_doi("https://doi.org/10.1080/23299460.2020.1791506(open in a new window)") == \
        "10.1080/23299460.2020.1791506"
    assert _clean_doi("https://doi.org/10.1023/A%3A1009456825063.") == "10.1023/A:1009456825063"
    assert _clean_doi("(doi:10.1000/abc).") == "10.1000/abc"


def test_a_dois_own_brackets_and_angle_brackets_stay():
    assert _clean_doi("https://doi.org/10.1061/(asce)0733-9429(1988)114:8(877)") == "10.1061/(asce)0733-9429(1988)114:8(877)"
    assert _clean_doi("doi: 10.1175/1520-0477(1998)079<0061:APGTWA>2.0.CO;2") == "10.1175/1520-0477(1998)079<0061:APGTWA>2.0.CO;2"
    assert _clean_doi("10.1002/(SICI)1096-9063(199701)49:1<1::AID-PS488>3.0.CO;2-#") == \
        "10.1002/(SICI)1096-9063(199701)49:1<1::AID-PS488>3.0.CO;2-#"


def test_a_doi_the_print_breaks_in_two_is_no_doi():
    assert _printed_doi("City. 18(3), 307-320. Disponível em: https://doi.org/10.1080/13604813. 2014.906716.") is None
    assert _printed_doi("Am J Hosp Palliat Care. 2020;37(10):816-22. doi:10.1177/1049909120 907601.") is None
    assert _printed_doi("Agrosavia. http://dx.doi.org/10.21930/agrosavia.estudio devigilancia.2023.2") is None
    assert _printed_doi("Revista Ibero-Americana. DOI: 10.6008/CBPC2179- 6858.2018.003.0015") is None
    assert _clean_doi("10.6008/CBPC2179-") is None
    assert _printed_doi("Pendidikan Nonformal, 10(1), 1 – 13. http://dx.doi.org/10.17977/um041v10i1p1%20-%2013.") is None
    assert _clean_doi("https://doi.org/10.1000/abc%20") == "10.1000/abc"  # an encoded space after the DOI is not in it


def test_a_whole_doi_followed_by_more_words_is_kept():
    assert _printed_doi("J Foo. 2019;1:2. doi:10.1000/abc. Accessed 3 May 2020.") == "10.1000/abc"
    assert _printed_doi("Lancet. 2010. doi:10.1000/abc PMID: 20123456") == "10.1000/abc"
    assert _printed_doi("Nurs Res Pract. 2018;2018:1659040. doi: 10.1155/2018/1659040.") == "10.1155/2018/1659040"
    # the year after the DOI (Copernicus journals) is not the rest of the DOI
    assert _printed_doi("Q. J. Roy. Meteor. Soc., https://doi.org/10.1002/qj.2297, 2014.") == "10.1002/qj.2297"
    assert _printed_doi("J. Climate, 26, 4518, https://doi.org/10.1175/JCLI-D-12-00544.1 2013.") == "10.1175/JCLI-D-12-00544.1"


def test_springer_entry_takes_its_buttons_doi_and_the_printed_one_when_the_button_or_link_is_cut():
    cut = sn_item('O’Brien JS, Julien PY (1988) Laboratory Analysis of Mudflow Properties. J Hydraul Eng 114:877–887. '
                  '<a href="https://doi.org/10.1061/(asce)0733-9429(1988)114:8(877)">https://doi.org/10.1061/(asce)0733-'
                  '9429(1988)114:8(877)</a>', "1.", "10.1061/(asce)0733")
    glued = sn_item('Anand, P.P.: Capabilities and health. J. Med. Ethics 31(5), 299–303 (2005). doi:<a href="https://'
                    'doi.org/10.1136/jme.2004.008706pmid">10.1136/jme.2004.008706pmid</a>', "2.", "10.1136/jme.2004.008706")
    short_link = sn_item('Lundeby, H. (2008). Exploring the experiences of parents. Scand J Disabil Res, 10, 258–274. '
                         '<a href="https://doi.org/10.1080/1501741080246970">https://doi.org/10.1080/1501741080246970'
                         '</a>0.', "3.")
    section = sn_item('Teetz C (2007) Schnelllaufende Hochleistungsdieselmotoren. Abschn. <a href="https://doi.org/'
                      '10.1007/978-3-642-28990-3_17#Sec4">17.4</a> Springer Berlin Heidelberg', "4.")
    button_only = sn_item("Bachrach SM (2014) Computational organic chemistry. Wiley, New York", "5.",
                          "10.1002/9781118671191")
    print_only = sn_item("Remer LA (2002) Validation of MODIS aerosol retrieval. Geophys. Res. Lett., 29(12), "
                         "doi: 10.1029/2001GL013204.", "6.")
    out = parse('<ol class="c-article-references">' + cut + glued + short_link + section + button_only + print_only
                + "</ol>", url=SPRINGER)
    assert [r["doi"] for r in out["references"]] == [
        "10.1061/(asce)0733-9429(1988)114:8(877)", "10.1136/jme.2004.008706", "10.1080/15017410802469700",
        "10.1007/978-3-642-28990-3_17", "10.1002/9781118671191", "10.1029/2001GL013204"]
    assert out["references_complete"] is True


def tf_entry(n, text, key=None):
    link = (f'<span class="xlinks-container"><a href="/servlet/linkout?suffix=e_1&amp;dbid=16&amp;'
            f'doi=10.1080%2F15412550902835168&amp;key={key.replace("/", "%2F")}">[Crossref]</a></span>') if key else ""
    return f'<li id="CIT{n:04d}"><span>{text} {link}</span></li>'


def test_atypon_entry_takes_its_links_doi_over_the_print_and_the_print_when_there_is_no_link():
    entries = (tf_entry(1, "Lancellotti P. 2021. Imaging in valve disease. JACC Cardiovasc Imaging 14: 541. Erratum in: "
                           "JACC Cardiovasc Imaging. 2021;14(6):1297. doi: 10.1016/j.jcmg.2021.04.019",
                        "10.1016/j.jcmg.2020.08.017")
               + tf_entry(2, "Davén J. 2022. Encountering Patients With Anorexia Nervosa. Int J Qual Stud Health "
                             "Well-Being 17: 2069651. https://doi.org/10.1080/17482631.2022.206965.",
                          "10.1080/17482631.2022.2069651")
               + tf_entry(3, "Whelpton PK. 1936. An empirical method of calculating future population, JASA "
                             "31(195): 457–473. https://doi.org/10.2307/2278370")
               + tf_entry(4, "Fogarty S. 2014. The role of complementary medicine. Eat Disord 22, no. 5: 375–385. "
                             "https://doi.org/10.1080/10640266.2014.915692Fg.", "10.1080/10640266.2014.915692"))
    body = f'{LITERATUM}<div id="references-Section"><ul class="references numeric-ordered-list">{entries}</ul></div>'
    out = parse(body, url="https://www.tandfonline.com/doi/full/10.1080/15412550902835168")
    assert [r["doi"] for r in out["references"]] == ["10.1016/j.jcmg.2020.08.017", "10.1080/17482631.2022.2069651",
                                                     "10.2307/2278370", "10.1080/10640266.2014.915692"]


# ---------------------------------------------------------------- one entry per reference


def wiley_links(doi):
    return (f'<div class="extra-links getFTR"><span class="hidden data-doi">{doi}</span><span><a href="/servlet/linkout'
            f'?suffix=null&amp;dbid=32&amp;doi=10.1002%2Fsolr.202300714&amp;refDoi={doi.replace("/", "%2F")}">CAS</a>'
            f'</span></div>')


def wiley_list(items):
    return (f'{LITERATUM}<section class="article-section__references"><ul class="rlist separator">'
            + "".join(f'<li data-bib-id="bib-{n:04d}"><span class="bullet">{n}</span>{item}</li>'
                      for n, item in enumerate(items, 1)) + "</ul></section>")


WILEY = "https://onlinelibrary.wiley.com/doi/10.1002/solr.202300714"


def test_wiley_references_lettered_under_one_number_are_one_entry_each():
    first = ('a) <span class="author">A. Kojima</span>, <i>J. Am. Chem. Soc.</i> <span class="pubYear">2009</span>, 131, '
             f'6050; {wiley_links("10.1021/ja809598r")}b) <span class="author">A. K. Jena</span>, <i>Chem. Rev.</i> '
             f'<span class="pubYear">2019</span>, 119, 3036. {wiley_links("10.1021/acs.chemrev.8b00539")}')
    second = ('<span class="author">S. De Wolf</span>, <i>J. Phys. Chem. Lett.</i> <span class="pubYear">2014</span>, 5, '
              f'1035. {wiley_links("10.1021/jz500279b")}')
    out = parse(wiley_list([first, second]), url=WILEY)
    assert [(r["raw"], r["doi"]) for r in out["references"]] == [
        ("A. Kojima, J. Am. Chem. Soc. 2009, 131, 6050;", "10.1021/ja809598r"),
        ("A. K. Jena, Chem. Rev. 2019, 119, 3036.", "10.1021/acs.chemrev.8b00539"),
        ("S. De Wolf, J. Phys. Chem. Lett. 2014, 5, 1035.", "10.1021/jz500279b")]
    assert out["references_complete"] is True


def test_wiley_lettered_references_with_no_link_block_to_split_at_are_not_a_whole_list():
    first = 'a) A. Kojima, J. Am. Chem. Soc. 2009, 131, 6050; b) A. K. Jena, Chem. Rev. 2019, 119, 3036.'
    second = f'S. De Wolf, J. Phys. Chem. Lett. 2014, 5, 1035. {wiley_links("10.1021/jz500279b")}'
    out = parse(wiley_list([first, second]), url=WILEY)
    assert len(out["references"]) == 2 and out["references_complete"] is False


def test_wiley_unlettered_citations_under_one_number_stay_one_entry():
    run = (f'O. Kratky, Naturwissenschaften 42, 237 (1955); {wiley_links("10.1007/BF00637827")}Angew. Chem. 72, 467 '
           f'(1960); {wiley_links("10.1002/ange.19600721402")}Progress in Biophysics 13, 105 (1963). '
           f'{wiley_links("10.1016/S0079-6107(63)80015-2")}')
    single = f'G. Porod, Fortschr. Hochpolymeren Forsch. 2, 363 (1961). {wiley_links("10.1007/BFb0050494")}'
    out = parse(wiley_list([run, single]), url=WILEY)
    assert [(r["raw"][:9], r["doi"]) for r in out["references"]] == [("O. Kratky", "10.1007/BF00637827"),
                                                                    ("G. Porod,", "10.1007/BFb0050494")]
    assert out["references_complete"] is True


def test_wiley_plain_numbered_references_stay_whole():
    items = [f'Author {n}. A title with b) in it. J Med 2002; 22: 268. {wiley_links(f"10.1000/j.{n}")}' for n in (1, 2)]
    out = parse(wiley_list(items), url=WILEY)
    assert len(out["references"]) == 2 and out["references_complete"] is True


ENTRIES = ["Brown, G. & Yule, G. (1983). Discourse Analysis. Cambridge: Cambridge University Press.",
           "Chilton, P. (2004). Analysing Political Discourse. London: Routledge.",
           "Creswell, J. (2014). Research Design (4th ed.). London: Sage.",
           "Fairclough, N. (1989). Language and Power. New York: Longman.",
           "McGarty, C. (1999). Categorization in Social Psychology. London: SAGE Publications.",
           "Van Dijk, T. A. (1993). Discourse and Society. California: Sage."]


def test_typed_list_numbers_are_not_part_of_the_entries():
    numbered = [f"{n}. {entry}" for n, entry in enumerate(ENTRIES, 1)]
    out = parse(ojs_list(numbered), OJS)
    assert [r["raw"] for r in out["references"]] == ENTRIES and out["references_complete"] is True


def test_an_unnumbered_line_in_a_numbered_list_is_the_rest_of_a_broken_entry():
    numbered = [f"{n}. {entry}" for n, entry in enumerate(ENTRIES, 1)]
    numbered.insert(3, "Care Cancer. 2020;28:3227-35. doi: 10.1007/s00520-019-05155-8.")
    out = parse(ojs_list(numbered), OJS)
    assert len(out["references"]) == 7 and out["references_complete"] is False


def test_an_entry_that_stops_on_a_bare_word_before_a_line_out_of_alphabetical_order_is_broken():
    broken = ENTRIES[:5] + ["Safitri, D. (2015) A Critical Discourse Analysis of Racism in Nbc News Online Mass",
                            "Media of Michael Brown's Case in Ferguson. Undergraduate thesis, UIN Sunan Ampel."] + ENTRIES[5:]
    assert parse(ojs_list(broken), OJS)["references_complete"] is False
    head = "".join(f'<meta name="citation_reference" content="{e}"/>' for e in broken)
    assert parse("", head)["references_complete"] is False


def test_an_entry_with_no_full_stop_in_an_alphabetical_list_is_not_a_break():
    open_ended = ENTRIES[:3] + [ENTRIES[3].rstrip(".")] + ENTRIES[4:]
    assert parse(ojs_list(open_ended), OJS)["references_complete"] is True
    out_of_order = ENTRIES[:4] + ["Wodak, R. (2003). Critical Discourse Analysis. Hampshire: Palgrave."] + ENTRIES[4:]
    assert parse(ojs_list(out_of_order), OJS)["references_complete"] is True  # a closed entry out of order is whole
    linked = ENTRIES[:4] + ["Safitri, D. (2015). Racism in news. Available from: https://example.org/news-and-health",
                            "Media Watch. (2016). Annual report. London: Media Watch."] + ENTRIES[5:]
    assert parse(ojs_list(linked), OJS)["references_complete"] is True  # it ends on its link, not on a bare word


def test_sub_headings_printed_inside_the_list_make_it_not_whole_one_short_entry_does_not():
    headed = ["Archival materials"] + ENTRIES[:3] + ["Published works"] + ENTRIES[3:]
    assert parse(ojs_list(headed), OJS)["references_complete"] is False
    assert parse(ojs_list(ENTRIES + ["• Elektronik Kaynaklar"]), OJS)["references_complete"] is False  # names a list
    assert parse(ojs_list(["Список литературы"] + ENTRIES), OJS)["references_complete"] is False
    for short in ("Solidworks; n.d.", "Summa Theologiae"):
        assert parse(ojs_list(ENTRIES + [short]), OJS)["references_complete"] is True


def test_a_typed_number_closed_with_a_dash_or_no_space_is_still_a_number():
    numbered = [f"{n}. {entry}" for n, entry in enumerate(ENTRIES, 1)]
    numbered[2], numbered[4] = "3.-" + ENTRIES[2], "5." + ENTRIES[4]
    out = parse(ojs_list(numbered), OJS)
    assert [r["raw"] for r in out["references"]] == ENTRIES and out["references_complete"] is True


def test_a_templates_placeholder_reference_is_not_a_whole_list():
    head = '<meta name="citation_reference" content="....citação referencia 1....."/>'
    assert parse("", head, "http://aaai-asbai.org.br/detalhe_artigo.asp?id=710")["references_complete"] is False


def test_two_references_printed_as_one_are_not_a_whole_list():
    glued = ENTRIES[:5] + ["Blanc, E. (2012). The Impact of Climate Change on Crop Yields. American Journal of Climate "
                           "Change, 1(1), 1–13. https://doi.org/10.4236/ajcc.2012.11001Brini, R. (2021). Renewable and "
                           "non-renewable electricity consumption. Energy, 223, 120064."]
    out = parse(ojs_list(glued), OJS)
    assert out["references_complete"] is False
    assert out["references"][5]["doi"] == "10.4236/ajcc.2012.11001"


def test_springer_text_citing_a_number_past_the_end_of_the_list_means_entries_are_missing():
    items = "".join(sn_item(f"Author {n}: A title. Curr Biol 2003, 13: 925.", f"{n}.") for n in (1, 2, 3))
    body = '<p>We checked the sequences with the Rfam database [4] and the list [2].</p><ol>' + items + "</ol>"
    assert parse(body, url=SPRINGER)["references_complete"] is False
    cited_inside = body.replace("[4]", "[3]")
    assert parse(cited_inside, url=SPRINGER)["references_complete"] is True
