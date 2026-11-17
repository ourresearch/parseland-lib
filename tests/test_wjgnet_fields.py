"""Baishideng Publishing Group article pages on wjgnet.com (World Journal of Gastroenterology and its sister World
Journal titles, 世界华人消化杂志): authors, affiliations, corresponding author, abstract and back matter (oxjob #2338).

Markup is cut down from stored wjgnet.com pages (17 Nov 2026). The meta tags give the authors only as one comma-joined
citation_authors tag, so before this parser Parseland read no authors on the site. The header is a fixed set of ids:
#dpauthors (byline), #dpaff ("<b>Name, Name, </b>Affiliation" per line), #dpfn (labelled notes: "Corresponding
author" / "Correspondence to" / "通讯作者", "Co-corresponding authors", "Supported by"), #dpabstract; Chinese-language
pages repeat it in English (#dpabstracten, #dpfnen).
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.wjgnet import Wjgnet

URL = "https://www.wjgnet.com/1007-9327/full/v30/i43/4677.htm"
PUBLISHER = '<meta name="dc.publisher" content="Baishideng Publishing Group Inc." />'
ABSTRACT = ("Despite advancements in the field, early diagnosis of multiple endocrine neo<Hypen />plasia type 1 (MEN1) "
            "remains unachievable. This letter to the editor highlighted the importance of carefully assessing "
            "gastrointestinal symptoms, hypercalcemia, and elevated serum gastrin levels, as suggested by Yuan "
            "<i>et al</i> in their paper.")


def _link(name):
    first, last = name.rsplit(" ", 1)
    return (f'<a href="javascript:void(0);" class="author-name-link" data-f-name="{first}" data-l-name="{last}" '
            f'data-name="{name}" target="_self">{name}</a>')


def _page(byline, affs, notes, abstract=ABSTRACT, extra="", publisher=PUBLISHER, english=""):
    aff = "".join(f"<div><b>{who}, </b>{text}</div>" for who, text in affs)
    fn = "".join(f"<div><b>{label}</b>:  {text}</div>" for label, text in notes)
    return (f'<html><head><meta charset="utf-8" />{publisher}'
            '<meta name="citation_authors" content="A, B" /><meta name="citation_title" content="A title" />'
            '<meta name="citation_doi" content="10.3748/wjg.v30.i43.4677" /></head><body>'
            '<div id="dptitle">A title</div>'
            f'<div id="dpauthors">{byline}</div><div id="dpaff">{aff}</div><div id="dpfn">{fn}'
            '<div><b>Received:</b> August 17, 2024<br /><b>Published online:</b> November 21, 2024<br /></div></div>'
            '<div class="article-section-title-0" id="secabs"><span>Abstract</span></div>'
            f'<div id="dpabstract"><div><p>{abstract}</p></div>'
            '<div class="article-abstract-item"><b>Key Words: </b><span>Hypercalcemia; Early diagnosis</span></div>'
            '<div class="article-abstract-item"><span><p><b>Core Tip:</b> Early diagnosis is critical.</p></span></div>'
            f'{english}</div>{extra}</body></html>')


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _raw(html):
    return Wjgnet(BeautifulSoup(html, "lxml")).parse()


LINKED = ", ".join(_link(n) for n in ("Tsvetelina Velikova", "Velik Lazarov"))
AFFS = [("Tsvetelina Velikova", "Medical Faculty, Sofia University St. Kliment Ohridski, Sofia 1407, Bulgaria"),
        ("Velik Lazarov", "Obstetrics and Gynaecology, Second Specialised Hospital, Sofia 1504, Bulgaria")]
CORR = [("Corresponding author", "Velik Lazarov, MD, Chief Doctor, Obstetrics and Gynaecology, Sofia 1504, Bulgaria. "
                                 '<a href="mailto:x@example.com">x@example.com</a>')]


def test_linked_byline_with_affiliations_and_corresponding_author():
    out = _parse(_page(LINKED, AFFS, CORR))
    assert [a["name"] for a in out["authors"]] == ["Tsvetelina Velikova", "Velik Lazarov"]
    assert [[x["name"] for x in a["affiliations"]] for a in out["authors"]] == [[AFFS[0][1]], [AFFS[1][1]]]
    assert [a["is_corresponding"] for a in out["authors"]] == [False, True]


def test_older_plain_byline_shared_affiliation_line_and_correspondence_to():
    byline = "\n        Ying-Fang Fan, Zong-Hai Huang, Wei Li\n    "
    affs = [("Ying-Fang Fan, Zong-Hai Huang", "Department of Surgery,  Zhujiang Hospital,  Guangzhou 510282,  China"),
            ("Wei Li", "Department of Pathology, Zhujiang Hospital, Guangzhou 510282, China")]
    notes = [("Correspondence to", "Dr. Ying-Fang Fan, Department of Surgery, Zhujiang Hospital, Guangzhou 510282, "
                                   "China. <email>fyfnj@example.com</email>"),
             ("Telephone", "+86-20-61641234")]
    out = _parse(_page(byline, affs, notes))
    assert [a["name"] for a in out["authors"]] == ["Ying-Fang Fan", "Zong-Hai Huang", "Wei Li"]
    shared = "Department of Surgery, Zhujiang Hospital, Guangzhou 510282, China"
    assert [[x["name"] for x in a["affiliations"]] for a in out["authors"]] == [[shared], [shared], [affs[1][1]]]
    assert [a["is_corresponding"] for a in out["authors"]] == [True, False, False]


def test_an_author_with_two_affiliation_lines_gets_both():
    affs = AFFS + [("Velik Lazarov", "Faculty of Medicine, Medical University Sofia, Sofia 1431, Bulgaria")]
    out = _parse(_page(LINKED, affs, CORR))
    assert [x["name"] for x in out["authors"][1]["affiliations"]] == [AFFS[1][1], affs[2][1]]


def test_co_corresponding_authors_are_both_marked():
    names = ("Sathish Muthu", "Naveen Jeyaraman", "Madhan Jeyaraman")
    notes = [("Co-corresponding authors", "Sathish Muthu and Madhan Jeyaraman."),
             ("Corresponding author", "Madhan Jeyaraman, Department of Orthopaedics, Chennai 600077, India.")]
    out = _parse(_page(", ".join(_link(n) for n in names), [(n, "A Hospital, Chennai, India") for n in names], notes))
    assert [a["is_corresponding"] for a in out["authors"]] == [True, False, True]


def test_a_corresponding_name_not_in_the_byline_marks_no_one():
    notes = [("Corresponding author", "Someone Else, MD, Sofia 1504, Bulgaria.")]
    out = _parse(_page(LINKED, AFFS, notes))
    assert not any(a["is_corresponding"] for a in out["authors"])


def test_abstract_joins_soft_hyphen_tags_and_leaves_out_keywords_and_core_tip():
    abstract = _parse(_page(LINKED, AFFS, CORR))["abstract"]
    assert abstract.startswith("Despite advancements in the field, early diagnosis of multiple endocrine neoplasia")
    assert "Yuan et al in their paper." in abstract
    assert "Key Words" not in abstract and "Core Tip" not in abstract


def test_chinese_page_byline_corresponding_and_english_abstract():
    byline = "陈杏苑, 杨元生, 陈垦"
    affs = [("陈杏苑, 陈垦", "广东药学院临床学院内科学教研室 广东省广州市 510310"),
            ("杨元生", "广东药学院附属第二医院消化内科 广东省广州市 510300"),
            ("陈杏苑", "在读硕士,  主要从事急性胰腺炎的发病机制及治疗研究.")]
    notes = [("基金项目", "广东省科技计划项目, No. 2012B060300029"),
             ("通讯作者", "陈垦, 教授, 主任医师, 510310, 广东省广州市. <email>c@example.com</email>")]
    english = ('</div><div id="dpfnen"><div><b>Supported by</b>: Science and Technology Planning Project of '
               'Guangdong Province, No. 2012B060300029.</div><div><b>Correspondence to</b>:  Ken Chen, Professor.</div>'
               '</div><div class="article-section-title-0"><label>Abstract</label></div><div id="dpabstracten"><div>'
               '<p><b>AIM</b>:  To observe the effect of piperlonguminine on peroxidoxin-4.</p>'
               '<p><b>METHODS</b>:  Thirty SD rats were randomly divided into three groups.</p></div>')
    chinese = "<b>目的</b>:  探讨荜茇宁对胰腺组织硫氧还蛋白过氧化物酶-4表达的影响机制."
    html = _page(byline, affs, notes, abstract=chinese, english=english)
    out = _parse(html)
    assert [a["name"] for a in out["authors"]] == ["陈杏苑", "杨元生", "陈垦"]
    # the closing biography line ("主要从事 ...", "研究方向为 ...") is not an affiliation
    assert [len(a["affiliations"]) for a in out["authors"]] == [1, 1, 1]
    assert [a["is_corresponding"] for a in out["authors"]] == [False, False, True]
    assert out["abstract"] == ("AIM: To observe the effect of piperlonguminine on peroxidoxin-4.\n"
                               "METHODS: Thirty SD rats were randomly divided into three groups.")
    assert _raw(html)["funding_statement"] == "Science and Technology Planning Project of Guangdong Province, No. " \
                                              "2012B060300029."


def _ref(n, authors, rest, doi=None, num_tag="a"):
    links = ('<span>&nbsp;[<a href="https://referencecitationanalysis.com/x" target="_blank"><em>RCA</em></a>]</span>'
             '<span style="display:inline">&nbsp;[<a href="http://www.ncbi.nlm.nih.gov/pubmed/1" pub-id-type="pubmed" '
             'pub-id="1">PubMed</a>]</span>')
    if doi:
        links += (f'<span style="display:inline">&nbsp;[<a href="https://dx.doi.org/{doi}" pub-id-type="doi" '
                  f'pub-id="{doi}" target="_blank">DOI</a>]</span>')
    links += ('<span class="ref-count">&nbsp;<span class="ref-count-sep">[</span><a href="javascript:void(0);">'
              'Reference Citation Analysis (0)</a><span class="ref-count-sep">]</span></span>')
    return (f'<div class="article-ref" id="B{n}"><table><tr><td style="vertical-align:top;width:30px;">'
            f'<{num_tag} class="article-ref-vol">{n}.&nbsp;</{num_tag}></td><td>'
            f'<span>{authors}</span><span><em><a href="javascript:void(0);" name="refsource">{rest[0]}</a></em>'
            f'.&nbsp;{rest[1]}</span>{links}</td></tr></table></div>')


REFS = [_ref(1, "<b>Yuan JH</b>,&nbsp;Luo S,&nbsp;Wang LS.&nbsp;Early detection of MEN1: A case report.",
             ("World J Gastroenterol", "2024;<b>30</b>:3247-3252."), doi="10.3748/wjg.v30.i26.3247"),
        _ref(2, "<b>Newey PJ</b>,&nbsp;Newell-Price J.&nbsp;MEN1 Surveillance Guidelines.",
             ("J Endocr Soc", "2022;<b>6</b>:bvac001."), num_tag="span")]
BACK = ('<div id="article-main-container"><div id="sec11"><div id="sec11title" class="article-section-title-0">'
        'INTRODUCTION</div><p class="article-section-content">Body text.</p></div>'
        '<div id="sec12"><div id="sec12title" class="article-section-title-0">ACKNOWLEDGEMENTS</div>'
        '<p class="article-section-content">We thank Dr. Rajagopalan for his editorial assistance.</p></div></div>'
        '<div class="article-section-title-0" id="secref"><span>References</span></div><div>{refs}</div>')
FUNDED = CORR + [("Supported by", "<grant-sponsor>the European Union-Next Generation EU</grant-sponsor>, through "
                                  "the National Recovery and Resilience Plan, No. BG-RRP-2.004-0008.")]


def test_reference_list_is_whole_when_numbers_run_one_to_n():
    raw = _raw(_page(LINKED, AFFS, CORR, extra=BACK.format(refs="".join(REFS))))
    assert raw["references"] == [
        {"position": 1, "raw": "Yuan JH, Luo S, Wang LS. Early detection of MEN1: A case report. "
                               "World J Gastroenterol. 2024;30:3247-3252.", "doi": "10.3748/wjg.v30.i26.3247"},
        {"position": 2, "raw": "Newey PJ, Newell-Price J. MEN1 Surveillance Guidelines. J Endocr Soc. 2022;6:bvac001.",
         "doi": None}]
    assert raw["references_complete"] is True


def test_reference_list_with_a_numbering_gap_is_not_whole():
    gap = REFS[0] + REFS[1].replace(">2.&nbsp;<", ">3.&nbsp;<")
    raw = _raw(_page(LINKED, AFFS, CORR, extra=BACK.format(refs=gap)))
    assert len(raw["references"]) == 2 and raw["references_complete"] is False


def test_funding_sentence_and_acknowledgments_section():
    raw = _raw(_page(LINKED, AFFS, FUNDED, extra=BACK.format(refs="".join(REFS))))
    assert raw["funding_statement"] == ("the European Union-Next Generation EU, through the National Recovery and "
                                        "Resilience Plan, No. BG-RRP-2.004-0008.")
    assert raw["acknowledgments"] == "We thank Dr. Rajagopalan for his editorial assistance."


def test_no_back_matter_keys_when_the_page_shows_none():
    raw = _raw(_page(LINKED, AFFS, CORR))
    assert raw["acknowledgments"] is None and raw["funding_statement"] is None
    assert raw["references"] is None and raw["references_complete"] is False


def test_look_alike_pages_are_not_claimed():
    # same header ids under another publisher's meta tag, and no publisher meta tag at all
    for publisher in ('<meta name="dc.publisher" content="Another Press Ltd." />', ""):
        parser = Wjgnet(BeautifulSoup(_page(LINKED, AFFS, CORR, publisher=publisher), "lxml"))
        assert not parser.is_publisher_specific_parser() and not parser.authors_found()
    # a Baishideng page without the article header (a journal or listing page) is not read
    listing = f"<html><head>{PUBLISHER}</head><body><div id='content'>Issue contents</div></body></html>"
    parser = Wjgnet(BeautifulSoup(listing, "lxml"))
    assert parser.is_publisher_specific_parser() and not parser.authors_found()
