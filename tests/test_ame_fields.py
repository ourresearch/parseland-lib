"""AME Publishing Company article pages (jtd.amegroups.org and its sister journals), oxjob #2338 (Parseland swarm).

Markup is cut down from stored amegroups.org pages (17 Nov 2026). ame.py read the numbered byline but crashed on pages
that print their one affiliation without a number (19 of 58 sampled full-text pages), so those pages fell to the
generic reader and lost their corresponding author; names without a <sup> ran together into one; one <aff> holding
every affiliation behind <target> marks was read as one affiliation. The parser now also returns the
acknowledgments, the "Funding:" paragraph and the reference list (#2215's contract).
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.ame import AMEPublishing

URL = "https://jtd.amegroups.org/article/view/12345"


def _page(byline, affs, corr="", body="", publisher="AME Publishing Company"):
    return (f'<html><head><meta name="citation_publisher" content="{publisher}"/>'
            '<meta name="citation_title" content="A title"/><meta name="citation_doi" content="10.21037/jtd-20-1"/>'
            '</head><body><div class="article"><h1 class="title">A title</h1>'
            f'<p class="authors">{byline}</p><p class="affiliation">{affs}</p>{corr}<hr/>'
            '<div id="abstract"><p><strong>Background: </strong>We asked a question about patients.</p>'
            '<p><strong>Methods: </strong>We enrolled 27 patients and followed them.</p></div>'
            f'{body}</div></body></html>')


def _corr(name):
    return (f'<div class="correspond-author"><corresp id="cor1"><em>Correspondence to:</em> {name}, MD. '
            'Department of Medical Oncology, Dalian, China. Email: <email>x@163.com</email>.</corresp></div>')


SINGLE = _page('Kui Jiang<sup>#</sup>, Guangyan Gao<sup>#</sup>, Xiangyong Kong, Lulu Yao',
               '<aff id="aff1"><institution content-type="dept">Department of Medical Oncology</institution>, '
               '<institution>The Second Affiliated Hospital of Dalian Medical University</institution>, '
               '<addr-line>Dalian 116027</addr-line>, <country>China</country></aff>', _corr("Lulu Yao"))
NUMBERED = _page('Vivian Thimsen<sup>1</sup>, Miguel Goncalves<sup>2,10#</sup>, Mirco Schapher<sup>1</sup>',
                 '<aff id="aff1"><sup>1</sup>Department of Otorhinolaryngology, Erlangen, <country>Germany</country>; '
                 '</aff><aff id="aff2"><sup>2</sup>University of Aachen, Aachen, Germany</aff>'
                 '<aff id="aff10"><sup>10</sup>RWTH, Aachen, Germany</aff>', _corr("Mirco Schapher"))
TARGETS = _page('Jun An<sup>1*</sup>, Meijun Long<sup>2*</sup>, Ye Jiang<sup>3</sup>',
                '<aff><target id="aff1" target-type="aff"><sup>1</sup></target>Department of Cardiothoracic Surgery, '
                '<country>China</country>; <target id="aff2" target-type="aff"><sup>2</sup></target>Breast Cancer '
                'Center, Chongqing, China; <target id="aff3" target-type="aff"><sup>3</sup></target>Department of '
                'Pathology, Chongqing, China</aff>', _corr("Ye Jiang"))


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _soup(html):
    return BeautifulSoup(html, "lxml")


def test_unnumbered_affiliation_goes_to_every_author_and_names_split_at_commas():
    authors = _parse(SINGLE)["authors"]
    assert [a["name"] for a in authors] == ["Kui Jiang", "Guangyan Gao", "Xiangyong Kong", "Lulu Yao"]
    aff = ("Department of Medical Oncology, The Second Affiliated Hospital of Dalian Medical University, "
           "Dalian 116027, China")
    assert all([x["name"] for x in a["affiliations"]] == [aff] for a in authors)


def test_correspondence_note_marks_its_author_on_an_unnumbered_page():
    assert [a["name"] for a in _parse(SINGLE)["authors"] if a["is_corresponding"]] == ["Lulu Yao"]


def test_numbered_affiliations_follow_the_superscripts_including_two_digit_numbers():
    authors = {a["name"]: [x["name"] for x in a["affiliations"]] for a in _parse(NUMBERED)["authors"]}
    assert authors["Vivian Thimsen"] == ["Department of Otorhinolaryngology, Erlangen, Germany"]
    assert authors["Miguel Goncalves"] == ["University of Aachen, Aachen, Germany", "RWTH, Aachen, Germany"]
    assert [a["name"] for a in _parse(NUMBERED)["authors"] if a["is_corresponding"]] == ["Mirco Schapher"]


def test_one_aff_tag_with_target_marks_is_split_into_its_affiliations():
    authors = {a["name"]: [x["name"] for x in a["affiliations"]] for a in _parse(TARGETS)["authors"]}
    assert authors == {"Jun An": ["Department of Cardiothoracic Surgery, China"],
                       "Meijun Long": ["Breast Cancer Center, Chongqing, China"],
                       "Ye Jiang": ["Department of Pathology, Chongqing, China"]}


def test_departments_before_a_shared_institution_get_its_institution_and_address():
    # cut down from jtd 10.21037/jtd.2018.01.101 (fresh set, 17 Nov): two departments of one hospital, and a ';'
    # closing a group whose segments each name their own place
    html = _page('Lijun Qian<sup>1</sup>, Jing Yao<sup>2</sup>, Di Xu<sup>1,3</sup>',
                 '<aff><target id="aff1" target-type="aff"><sup>1</sup></target>Department of Geriatrics, '
                 '<target id="aff2" target-type="aff"><sup>2</sup></target>Department of Cardiology, '
                 '<institution>The First Affiliated Hospital of Nanjing Medical University</institution>, '
                 '<addr-line>Nanjing 210029</addr-line>, <country>China</country>; '
                 '<target id="aff3" target-type="aff"><sup>3</sup></target>Division of Radiology, '
                 '<country>China</country>;</aff>', _corr("Di Xu"))
    authors = {a["name"]: [x["name"] for x in a["affiliations"]] for a in _parse(html)["authors"]}
    hospital = "The First Affiliated Hospital of Nanjing Medical University, Nanjing 210029, China"
    assert authors == {"Lijun Qian": [f"Department of Geriatrics, {hospital}"],
                       "Jing Yao": [f"Department of Cardiology, {hospital}"],
                       "Di Xu": [f"Department of Geriatrics, {hospital}", "Division of Radiology, China"]}


def test_a_department_tagged_as_an_institution_still_shares_its_groups_address():
    # cut down from a stored amegroups.org page: the first department sits in an <institution> tag of its own
    html = _page('Wei Li<sup>1</sup>, Min Wang<sup>2</sup>',
                 '<aff><target id="aff1" target-type="aff"><sup>1</sup></target><institution>Department of Thoracic '
                 'Surgery</institution>, <target id="aff2" target-type="aff"><sup>2</sup></target><institution '
                 'content-type="dept">Department of Nephrology, The First Affiliated Hospital</institution>, '
                 '<institution>Zhengzhou University</institution>, <addr-line>Zhengzhou 450052</addr-line>, '
                 '<country country="cn">China</country>; </aff>', _corr("Min Wang"))
    authors = {a["name"]: [x["name"] for x in a["affiliations"]] for a in _parse(html)["authors"]}
    assert authors == {
        "Wei Li": ["Department of Thoracic Surgery, Zhengzhou University, Zhengzhou 450052, China"],
        "Min Wang": ["Department of Nephrology, The First Affiliated Hospital, Zhengzhou University, Zhengzhou 450052, "
                     "China"]}


def test_correspondence_name_must_be_a_whole_name():
    html = _page('Li Li<sup>1</sup>, Beili Lin<sup>1</sup>', '<aff id="aff1"><sup>1</sup>Fudan University</aff>',
                 _corr("Beili Lin"))
    assert [a["name"] for a in _parse(html)["authors"] if a["is_corresponding"]] == ["Beili Lin"]


def test_abstract_keeps_paragraphs_and_labels():
    assert _parse(SINGLE)["abstract"] == ("Background: We asked a question about patients.\n"
                                          "Methods: We enrolled 27 patients and followed them.")


def test_parsing_leaves_the_soup_as_it_was():
    soup = _soup(NUMBERED)
    AMEPublishing(soup).parse()
    assert soup.select_one("p.affiliation aff sup").get_text() == "1"


def test_a_lookalike_page_from_another_publisher_is_not_claimed():
    html = _page('Ann Smith<sup>1</sup>, Bo Jones', '<aff id="aff1"><sup>1</sup>Notre Dame University</aff>',
                 _corr("Bo Jones"), publisher="University of Notre Dame Press")
    parser = AMEPublishing(_soup(html))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


BACK = ('<h2 id="acknowledgments" class="section-title color-bg">Acknowledgments</h2>'
        '<p>The authors would like to thank Dave Primm for his help in editing this manuscript.</p>'
        '<p><em>Funding</em>: This work was supported by the Natural Science Foundation of Wuhan (No. WX20A03).</p>'
        '<hr/><h2 id="Footnote" class="section-title color-bg">Footnote</h2>'
        '<p><em>Conflicts of Interest:</em> The authors have no conflicts of interest to declare.</p><hr/>'
        '<h2 id="references" class="section-title color-bg">References</h2><ol class="ref-item">'
        '<li id="B1">Spiro RH. Salivary neoplasms: overview of a 35-year experience. Head Neck Surg 1986;8:177-84. '
        '[<a href="http://dx.doi.org/10.1002/hed.2890080309">Crossref</a>] '
        '[<a href="http://www.ncbi.nlm.nih.gov/pubmed/3744850">PubMed</a>]</li>'
        '<li id="B2">Seethala RR, Stenman G. Update from the 4th Edition of the WHO Classification. '
        'Head Neck Pathol 2017;11:55-67. [Epub ahead of print]</li></ol>')


def test_acknowledgments_without_the_funding_paragraph_and_funding_without_its_label():
    out = AMEPublishing(_soup(_page('Ann Smith', '<aff id="aff1">Fudan University</aff>', body=BACK))).parse()
    assert out["acknowledgments"] == "The authors would like to thank Dave Primm for his help in editing this manuscript."
    assert out["funding_statement"] == "This work was supported by the Natural Science Foundation of Wuhan (No. WX20A03)."


def test_an_acknowledgments_section_saying_none_and_funding_in_the_footnote_section():
    body = ('<h2 id="acknowledgments" class="section-title color-bg">Acknowledgments</h2><p>None.</p><hr/>'
            '<h2 id="Footnote" class="section-title color-bg">Footnote</h2>'
            '<p><em>Reporting Checklist:</em> The authors have completed the STROBE checklist.</p>'
            '<p><em>Funding:</em> None.</p><hr/>')
    out = AMEPublishing(_soup(_page('Ann Smith', '<aff id="aff1">Fudan University</aff>', body=body))).parse()
    assert out["acknowledgments"] is None
    assert out["funding_statement"] == "None."


def test_reference_list_without_link_buttons_with_dois_and_whole():
    out = AMEPublishing(_soup(_page('Ann Smith', '<aff id="aff1">Fudan University</aff>', body=BACK))).parse()
    assert [r["raw"] for r in out["references"]] == [
        "Spiro RH. Salivary neoplasms: overview of a 35-year experience. Head Neck Surg 1986;8:177-84.",
        "Seethala RR, Stenman G. Update from the 4th Edition of the WHO Classification. Head Neck Pathol "
        "2017;11:55-67. [Epub ahead of print]"]
    assert [r["doi"] for r in out["references"]] == ["10.1002/hed.2890080309", None]
    assert out["references_complete"] is True


def test_reference_list_with_a_gap_in_its_numbering_is_not_whole():
    body = BACK.replace('<li id="B2">', '<li id="B3">')
    out = AMEPublishing(_soup(_page('Ann Smith', '<aff id="aff1">Fudan University</aff>', body=body))).parse()
    assert len(out["references"]) == 2 and out["references_complete"] is False
