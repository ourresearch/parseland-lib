"""AME Publishing (amegroups.org, amegroups.com, theajo.com, annalscts.com ...): the reference list, funding statement
and acknowledgments (#2215's contract), and a claim cheap enough to run on every page (oxjob #2289, template
"ojs-like": OJS-style URLs on AME's own platform). Below them, oxjob #2338's cases (amegroups.org, Parseland swarm):
the correspondence note on whole names, one <aff> split at its <target> marks, departments before a shared
institution, the claim on the word AME, and the soup left as it was.

Markup is cut down from stored AME article pages (17 Nov 2026). Every AME journal loads its styles and scripts from
cdn.amegroups.cn and prints the back matter the same way: an "Acknowledgments" h2 whose paragraphs may include a run-in
"<em>Funding:</em>" paragraph, a "Footnote" h2 whose paragraphs may hold it instead, and a "References" h2 followed by
<ol class="ref-item"> with one <li id="B1">, <li id="B2"> ... per entry and [Crossref] [PubMed] buttons.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.ame import AMEPublishing

URL = "https://aes.amegroups.org/article/view/8145/html"
HEAD = ('<link rel="stylesheet" href="//cdn.amegroups.cn/journals/aes/styles/most.css?v=1"/>'
        '<script src="//cdn.amegroups.cn/journals/aes/js/common.js?v=1"></script>'
        '<meta name="citation_journal_title" content="Annals of Eye Science"/>'
        '<meta name="citation_publisher" content="AME Publishing Company"/>'
        '<meta name="citation_author" content="Sabrina Poonja"/><meta name="citation_author" content="John J. Chen"/>'
        '<meta name="citation_title" content="A title"/><meta name="citation_doi" content="10.21037/aes-24-38"/>')
BYLINE = ('<div class="meta"><p class="authors">Sabrina Poonja<sup>1</sup>, John J. Chen<sup>1,2</sup></p>'
          '<p class="affiliation"><aff id="aff1"><sup>1</sup><institution>Department of Ophthalmology</institution>, '
          '<institution>Mayo Clinic</institution>, <country>USA</country>;</aff><aff id="aff2"><sup>2</sup>'
          '<institution>Department of Neurology</institution>, <institution>Mayo Clinic</institution>, '
          '<country>USA</country></aff></p>'
          '<div class="correspond-author"><corresp id="cor1"><em>Correspondence to:</em> John J. Chen, MD, PhD. '
          'Department of Ophthalmology, Mayo Clinic. Email: <email>chen.john@mayo.edu</email>.</corresp></div></div>')
REF1 = ('<li id="B1">Berry S, Lin WV, Sadaka A, <em>et al</em>. Nonarteritic anterior ischemic optic neuropathy: cause, '
        'effect, and management. Eye Brain 2017;9:23-8. [<a href="http://dx.doi.org/10.2147/EB.S125311" '
        'target="_blank">Crossref</a>] [<a href="http://www.ncbi.nlm.nih.gov/pubmed/29033621" '
        'target="_blank">PubMed</a>]</li>')
REF2 = '<li id="B2">NICE. Menopause: diagnosis and management. NG23. 2015.</li>'
REF3 = ('<li id="B3">Foster RC, Bhatti MT, Crum OM, <em>et al</em>. Reexamining the Incidence of Nonarteritic Anterior '
        'Ischemic Optic Neuropathy. J Neuroophthalmol 2024;44:337-41. [<a href="http://www.ncbi.nlm.nih.gov/pubmed/'
        '38358828" target="_blank">PubMed</a>]</li>')
FUNDING_TEXT = "This study was supported by the Guangdong Basic and Applied Basic Research Foundation (No. 2023A1515)."
ACK_TEXT = "The authors would like to acknowledge Dr. A for preparing the histopathology slides."


def _page(ack="<p>None.</p>", footnote="<p><em>Funding:</em> None.</p>", refs=REF1 + REF2 + REF3, head=HEAD,
          ol='<ol class="ref-item">'):
    body = (f'<section>{BYLINE}<h2 id="introduction" class="section-title color-bg">Introduction</h2><p>Text.</p>'
            f'<hr/><h2 id="acknowledgments" class="section-title color-bg">Acknowledgments</h2>{ack}'
            f'<hr/><h2 id="Footnote" class="section-title color-bg">Footnote</h2>'
            f'<p><em>Conflicts of Interest:</em> The authors have no conflicts of interest to declare.</p>{footnote}'
            f'<hr/><h2 id="references" class="section-title color-bg">References</h2>{ol}{refs}</ol>'
            f'<div><p>Cite this article as: Poonja S, Chen JJ. A title. Ann Eye Sci 2025;10:5.</p></div></section>')
    return f"<html><head>{head}</head><body>{body}</body></html>"


def _parse(html):
    return AMEPublishing(BeautifulSoup(html, "lxml")).parse()


def test_byline_fields_unchanged():
    out = parse_page(_page().encode(), "doi", URL)
    assert [a["name"] for a in out["authors"]] == ["Sabrina Poonja", "John J. Chen"]
    assert out["authors"][0]["affiliations"] == [{"name": "Department of Ophthalmology, Mayo Clinic, USA;"}]
    assert [a["is_corresponding"] for a in out["authors"]] == [None, True]


def test_reference_list_in_page_order_without_buttons():
    refs = _parse(_page())["references"]
    assert [r["position"] for r in refs] == [1, 2, 3]
    assert refs[0]["raw"] == ("Berry S, Lin WV, Sadaka A, et al. Nonarteritic anterior ischemic optic neuropathy: "
                              "cause, effect, and management. Eye Brain 2017;9:23-8.")
    assert refs[0]["doi"] == "10.2147/EB.S125311"  # the entry's own Crossref button
    assert refs[1] == {"position": 2, "raw": "NICE. Menopause: diagnosis and management. NG23. 2015.", "doi": None}
    assert refs[2]["doi"] is None and refs[2]["raw"].endswith("2024;44:337-41.")  # a PubMed button is no DOI


def test_ids_running_one_to_n_make_the_list_whole():
    assert _parse(_page())["references_complete"] is True
    out = parse_page(_page().encode(), "doi", URL)
    assert len(out["references"]) == 3 and out["references_complete"] is True


def test_a_gap_in_the_entry_ids_is_not_whole():
    assert _parse(_page(refs=REF1 + REF3))["references_complete"] is False


def test_a_list_that_starts_later_is_not_whole():
    assert _parse(_page(ol='<ol class="ref-item" start="4">'))["references_complete"] is False


def test_funding_in_the_footnote_and_real_acknowledgments():
    out = _parse(_page(ack=f"<p>{ACK_TEXT}</p>", footnote=f"<p><em>Funding:</em> {FUNDING_TEXT}</p>"))
    assert out["funding_statement"] == FUNDING_TEXT
    assert out["acknowledgments"] == ACK_TEXT


def test_funding_paragraph_under_the_acknowledgments_heading_is_the_funding_statement():
    out = _parse(_page(ack=f"<p><em>Funding</em>: {FUNDING_TEXT}</p>", footnote=""))
    assert out["funding_statement"] == FUNDING_TEXT
    assert out["acknowledgments"] is None  # the section holds nothing but the funding paragraph


def test_none_is_no_statement():
    out = _parse(_page(ack="<p><em>Funding:</em> None.</p>", footnote=""))
    assert out["funding_statement"] is None and out["acknowledgments"] is None
    out = _parse(_page())
    assert out["funding_statement"] is None and out["acknowledgments"] is None


def test_a_page_without_the_platform_marks_is_not_read():
    """SciEngine and elpub pages print a <p class="authors"> byline too: never AME's to read."""
    look_alike = _page(head='<link rel="stylesheet" href="https://www.sciengine.com/static/css/article.css"/>'
                            '<meta name="citation_publisher" content="Science China Press"/>'
                            '<meta name="citation_author" content="Sabrina Poonja"/>')
    parser = AMEPublishing(BeautifulSoup(look_alike, "lxml"))
    assert not parser.authors_found()
    assert not parser.is_publisher_specific_parser()


def test_platform_assets_alone_are_enough():
    """An AME page with no citation_publisher tag (actr.amegroups.org) is still read: its <head> loads AME's assets."""
    head = HEAD.replace('<meta name="citation_publisher" content="AME Publishing Company"/>', "")
    assert AMEPublishing(BeautifulSoup(_page(head=head), "lxml")).authors_found()


SINGLE_AFF_BYLINE = ('<div class="meta"><p class="authors">Taiyuan Liu<sup>^</sup>, Yonghao Liang, Sunil Kumar Lalwani, '
                     'Yingchao Zhang<sup>^</sup></p><p class="affiliation"><aff id="aff1"><institution>Department of '
                     'Breast Surgery</institution>, <institution>Second Hospital of Jilin University</institution>, '
                     '<country>China</country></aff></p><div class="correspond-author"><corresp id="cor1">'
                     '<em>Correspondence to:</em> Yingchao Zhang, MD. Department of Breast Surgery. Email: '
                     '<email>zyc@example.edu</email>.</corresp></div></div>')


def test_a_byline_with_one_unlabelled_affiliation():
    """One affiliation, no numbers: the names share one text node and the affiliation is everyone's (the parser used
    to crash here, so another parser's reading won and the back matter was lost)."""
    html = _page().replace(BYLINE, SINGLE_AFF_BYLINE)
    out = parse_page(html.encode(), "doi", URL)
    assert [a["name"] for a in out["authors"]] == ["Taiyuan Liu", "Yonghao Liang", "Sunil Kumar Lalwani",
                                                  "Yingchao Zhang"]
    assert all(a["affiliations"] == [{"name": "Department of Breast Surgery, Second Hospital of Jilin University, China"}]
               for a in out["authors"])
    assert [a["is_corresponding"] for a in out["authors"]] == [None, None, None, True]
    assert len(out["references"]) == 3


def test_an_unlabelled_affiliation_after_a_labelled_one_continues_it():
    byline = ('<div class="meta"><p class="authors">Marco Chiarelli<sup>1</sup>, Angelo Guttadauro<sup>2</sup></p>'
              '<p class="affiliation"><aff id="aff1"><sup>1</sup>Department of General Surgery, Ospedale Manzoni, '
              '<country>Italy</country>;</aff><aff id="aff2"><sup>2</sup>Department of Surgery,</aff><aff id="aff3">'
              'University of Milan-Bicocca, Monza, <country>Italy</country></aff></p></div>')
    authors = _parse(_page().replace(BYLINE, byline))["authors"]
    assert authors[1].affiliations == ["Department of Surgery, University of Milan-Bicocca, Monza, Italy"]
    assert authors[0].affiliations == ["Department of General Surgery, Ospedale Manzoni, Italy;"]


def test_abstract_label_is_not_abstract_text():
    html = _page().replace(BYLINE, BYLINE + '<div id="abstract"><p><strong>Abstract:</strong> Advanced Practice '
                                            'Providers are fundamental to oncology care.</p></div>')
    assert _parse(html)["abstract"] == "Advanced Practice Providers are fundamental to oncology care."


# ---- oxjob #2338 (amegroups.org): markup cut down from stored amegroups.org pages (17 Nov 2026)

ARTICLE_URL = "https://jtd.amegroups.org/article/view/12345"


def _article(byline, affs, corr="", body="", publisher="AME Publishing Company"):
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


def _read(html):
    return parse_page(html.encode(), "doi", ARTICLE_URL)


def _affs_by_name(html):
    return {a["name"]: [x["name"] for x in a["affiliations"]] for a in _read(html)["authors"]}


SINGLE = _article('Kui Jiang<sup>#</sup>, Guangyan Gao<sup>#</sup>, Xiangyong Kong, Lulu Yao',
                  '<aff id="aff1"><institution content-type="dept">Department of Medical Oncology</institution>, '
                  '<institution>The Second Affiliated Hospital of Dalian Medical University</institution>, '
                  '<addr-line>Dalian 116027</addr-line>, <country>China</country></aff>', _corr("Lulu Yao"))
NUMBERED = _article('Vivian Thimsen<sup>1</sup>, Miguel Goncalves<sup>2,10#</sup>, Mirco Schapher<sup>1</sup>',
                    '<aff id="aff1"><sup>1</sup>Department of Otorhinolaryngology, Erlangen, <country>Germany</country>; '
                    '</aff><aff id="aff2"><sup>2</sup>University of Aachen, Aachen, Germany</aff>'
                    '<aff id="aff10"><sup>10</sup>RWTH, Aachen, Germany</aff>', _corr("Mirco Schapher"))
TARGETS = _article('Jun An<sup>1*</sup>, Meijun Long<sup>2*</sup>, Ye Jiang<sup>3</sup>',
                   '<aff><target id="aff1" target-type="aff"><sup>1</sup></target>Department of Cardiothoracic Surgery, '
                   '<country>China</country>; <target id="aff2" target-type="aff"><sup>2</sup></target>Breast Cancer '
                   'Center, Chongqing, China; <target id="aff3" target-type="aff"><sup>3</sup></target>Department of '
                   'Pathology, Chongqing, China</aff>', _corr("Ye Jiang"))


def test_hash_marks_are_no_labels_and_the_unnumbered_affiliation_is_everyones():
    authors = _read(SINGLE)["authors"]
    assert [a["name"] for a in authors] == ["Kui Jiang", "Guangyan Gao", "Xiangyong Kong", "Lulu Yao"]
    aff = ("Department of Medical Oncology, The Second Affiliated Hospital of Dalian Medical University, "
           "Dalian 116027, China")
    assert all([x["name"] for x in a["affiliations"]] == [aff] for a in authors)
    assert [a["name"] for a in authors if a["is_corresponding"]] == ["Lulu Yao"]


def test_numbered_affiliations_follow_the_superscripts_including_two_digit_numbers():
    authors = _affs_by_name(NUMBERED)
    assert authors["Vivian Thimsen"] == ["Department of Otorhinolaryngology, Erlangen, Germany;"]  # #2289 keeps the ';'
    assert authors["Miguel Goncalves"] == ["University of Aachen, Aachen, Germany", "RWTH, Aachen, Germany"]
    assert [a["name"] for a in _read(NUMBERED)["authors"] if a["is_corresponding"]] == ["Mirco Schapher"]


def test_one_aff_tag_with_target_marks_is_split_into_its_affiliations():
    assert _affs_by_name(TARGETS) == {"Jun An": ["Department of Cardiothoracic Surgery, China"],
                                      "Meijun Long": ["Breast Cancer Center, Chongqing, China"],
                                      "Ye Jiang": ["Department of Pathology, Chongqing, China"]}


def test_departments_before_a_shared_institution_get_its_institution_and_address():
    # cut down from jtd 10.21037/jtd.2018.01.101 (fresh set, 17 Nov): two departments of one hospital, and a ';'
    # closing a group whose segments each name their own place
    html = _article('Lijun Qian<sup>1</sup>, Jing Yao<sup>2</sup>, Di Xu<sup>1,3</sup>',
                    '<aff><target id="aff1" target-type="aff"><sup>1</sup></target>Department of Geriatrics, '
                    '<target id="aff2" target-type="aff"><sup>2</sup></target>Department of Cardiology, '
                    '<institution>The First Affiliated Hospital of Nanjing Medical University</institution>, '
                    '<addr-line>Nanjing 210029</addr-line>, <country>China</country>; '
                    '<target id="aff3" target-type="aff"><sup>3</sup></target>Division of Radiology, '
                    '<country>China</country>;</aff>', _corr("Di Xu"))
    hospital = "The First Affiliated Hospital of Nanjing Medical University, Nanjing 210029, China"
    assert _affs_by_name(html) == {"Lijun Qian": [f"Department of Geriatrics, {hospital}"],
                                   "Jing Yao": [f"Department of Cardiology, {hospital}"],
                                   "Di Xu": [f"Department of Geriatrics, {hospital}", "Division of Radiology, China"]}


def test_a_department_tagged_as_an_institution_still_shares_its_groups_address():
    # cut down from a stored amegroups.org page: the first department sits in an <institution> tag of its own
    html = _article('Wei Li<sup>1</sup>, Min Wang<sup>2</sup>',
                    '<aff><target id="aff1" target-type="aff"><sup>1</sup></target><institution>Department of Thoracic '
                    'Surgery</institution>, <target id="aff2" target-type="aff"><sup>2</sup></target><institution '
                    'content-type="dept">Department of Nephrology, The First Affiliated Hospital</institution>, '
                    '<institution>Zhengzhou University</institution>, <addr-line>Zhengzhou 450052</addr-line>, '
                    '<country country="cn">China</country>; </aff>', _corr("Min Wang"))
    assert _affs_by_name(html) == {
        "Wei Li": ["Department of Thoracic Surgery, Zhengzhou University, Zhengzhou 450052, China"],
        "Min Wang": ["Department of Nephrology, The First Affiliated Hospital, Zhengzhou University, Zhengzhou 450052, "
                     "China"]}


def test_correspondence_name_must_be_a_whole_name():
    html = _article('Li Li<sup>1</sup>, Beili Lin<sup>1</sup>', '<aff id="aff1"><sup>1</sup>Fudan University</aff>',
                    _corr("Beili Lin"))
    assert [a["name"] for a in _read(html)["authors"] if a["is_corresponding"]] == ["Beili Lin"]


def test_correspondence_note_matches_without_accents_and_a_suffix_stays_with_its_name():
    html = _article('José Pérez, Jr.<sup>1</sup>, <!-- co-first --> Ann Lee<sup>1</sup>',
                    '<aff id="aff1"><sup>1</sup>Fudan University</aff>', _corr("Jose Perez"))
    authors = _read(html)["authors"]
    assert [a["name"] for a in authors] == ["José Pérez, Jr.", "Ann Lee"]
    assert [a["is_corresponding"] for a in authors] == [True, None]


def test_abstract_keeps_paragraphs_apart_and_their_labels():
    assert _read(SINGLE)["abstract"] == ("Background: We asked a question about patients.\n"
                                         "Methods: We enrolled 27 patients and followed them.")


def test_parsing_leaves_the_soup_as_it_was():
    soup = BeautifulSoup(NUMBERED, "lxml")
    AMEPublishing(soup).parse()
    assert soup.select_one("p.affiliation aff sup").get_text() == "1"


def test_a_lookalike_page_from_another_publisher_is_not_claimed():
    html = _article('Ann Smith<sup>1</sup>, Bo Jones', '<aff id="aff1"><sup>1</sup>Notre Dame University</aff>',
                    _corr("Bo Jones"), publisher="University of Notre Dame Press")
    parser = AMEPublishing(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_acknowledgments_and_the_funding_paragraph_in_one_section():
    body = ('<h2 id="acknowledgments" class="section-title color-bg">Acknowledgments</h2>'
            '<p>The authors would like to thank Dave Primm for his help in editing this manuscript.</p>'
            '<p><em>Funding</em>: This work was supported by the Natural Science Foundation of Wuhan (No. WX20A03).</p>'
            '<hr/><h2 id="references" class="section-title color-bg">References</h2><ol class="ref-item">'
            '<li id="B1">Seethala RR, Stenman G. Update from the 4th Edition of the WHO Classification. '
            'Head Neck Pathol 2017;11:55-67. [Epub ahead of print]</li></ol>')
    out = AMEPublishing(BeautifulSoup(_article('Ann Smith', '<aff id="aff1">Fudan University</aff>', body=body),
                                      "lxml")).parse()
    assert out["acknowledgments"] == "The authors would like to thank Dave Primm for his help in editing this manuscript."
    assert out["funding_statement"] == "This work was supported by the Natural Science Foundation of Wuhan (No. WX20A03)."
    assert out["references"][0]["raw"].endswith("2017;11:55-67. [Epub ahead of print]")  # not a link button
