"""KoreaMed Synapse / XMLink journal pages (oxjob #2268). Markup cut down from stored pages of the template."""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.koreamed_xmlink import KoreaMedXMLink

URL = "https://doi.org/10.4055/jkoa.2011.46.1.42"


def _metas(names, affs=None):
    out = ""
    for i, n in enumerate(names):
        out += f'<meta name="citation_author" content="{n}"/>'
        out += f'<meta name="citation_author_institution" content="{(affs or [""] * len(names))[i]}"/>'
    return out + '<meta name="citation_title" content="A title"/><meta name="citation_doi" content="10.4055/x"/>'


SYNAPSE_BODY = """<div class="abody"><link rel="stylesheet" type="text/css" href="ViewNLM_m.css">
<table class="fm"><tr><td>
<span class="capture-id">Gwang Chul Lee, M.D.,<sup></sup></span>
<span class="capture-id">Jun-Young Lee, M.D.<sup><img src="image/icon_corresp.gif"></sup></span>
</td></tr>
<tr><td>Department of Orthopaedic Surgery, Chosun University, Gwangju, Korea.</td></tr>
<tr><td><span class="capture-id"><span class="gen"></span><sup><img src="image/icon_corresp.gif"></sup> Address reprint
requests to: Jun-Young Lee, M.D. Department of Orthopaedic Surgery, Chosun University Hospital.</span></td></tr>
<tr><td class="td-section"><div class="tl-main-part">Abstract</div></td></tr>
<tr><td><br/><div><span class="tl-default">Purpose</span><p>To analyze the long term follow up results of treatment
with posterolateral approach in trimalleolar fractures.</p></div>
<div><span class="tl-default">Results</span><p>Thirty four cases healed without complication during follow up.</p></div>
</td></tr></table>
<table width="100%"><tr><td class="td-section"><div class="tl-main-part">ACKNOWLEDGMENT</div></td></tr></table>
<p>This work was supported by the Inha University Research Grant.</p>
<table width="100%"><tr><td class="td-section"><div class="tl-main-part">References</div></td></tr></table>
<div class="bm">
<div class="ref-item"><div class="ref-label"><a href="#XREF_B1"><b><i>1. </i></b></a></div><div class="ref-data">Burwell HN,
Charnley AD. The treatment of displaced fractures at the ankle. J Bone Joint Surg Br 1965;47:634-660.<div>
<a href="https://pubmed.ncbi.nlm.nih.gov/5846764"><img src="image/ReficonPubmed.gif"></a></div></div></div>
<div class="ref-item"><div class="ref-label"><a href="#XREF_B2"><b><i>2. </i></b></a></div><div class="ref-data">Oh CM, Won YJ.
Cancer statistics in Korea. Cancer Res Treat 2016;48:436-450.<div><a href="https://doi.org/10.4143%2Fcrt.2016.089">
<img src="image/ReficonCrossRef.gif"></a></div></div></div>
</div></div>"""

SYN_NAMES = ["Lee, Gwang Chul", "Lee, Jun-Young"]
SYN_AFFS = ["Department of Orthopaedic Surgery, Chosun University, Gwangju, Korea"] * 2


def _page(metas, body):
    return f"<html><head>{metas}</head><body>{body}</body></html>"


def _synapse():
    return _page(_metas(SYN_NAMES, SYN_AFFS), SYNAPSE_BODY)


def test_synapse_viewer_abstract_is_read():
    out = parse_page(_synapse().encode(), "doi", URL)
    assert out["abstract"].startswith("Purpose: To analyze the long term")
    assert "Results: Thirty four cases" in out["abstract"]


def test_synapse_viewer_reprint_note_marks_the_iconed_author():
    out = parse_page(_synapse().encode(), "doi", URL)
    assert [a["name"] for a in out["authors"] if a["is_corresponding"]] == ["Lee, Jun-Young"]
    assert all(a["affiliations"] for a in out["authors"])


def test_synapse_viewer_references_and_acknowledgments():
    parsed = KoreaMedXMLink(BeautifulSoup(_synapse(), "lxml")).parse()
    refs = parsed["references"]
    assert [r["position"] for r in refs] == [1, 2]
    assert refs[0]["raw"].startswith("Burwell HN") and refs[0]["doi"] is None
    assert refs[1]["doi"] == "10.4143/crt.2016.089"
    assert parsed["references_complete"] is True
    assert parsed["acknowledgments"] == "This work was supported by the Inha University Research Grant."


def test_reference_list_with_a_gap_is_not_whole():
    html = _synapse().replace("XREF_B2\"><b><i>2. ", "XREF_B2\"><b><i>3. ")
    assert KoreaMedXMLink(BeautifulSoup(html, "lxml")).parse()["references_complete"] is False


JATS_BODY = """<div class="metadata-group author_layer">
<a href="/articles/search_result.php?term=author&amp;f_name=Sang-Wuk&amp;l_name=Sohn">Sang-Wuk Sohn, MD</a><sup>a</sup>,
<a href="/articles/search_result.php?term=author&amp;f_name=Gwang-Dong&amp;l_name=Choi">Gwang-Dong Choi, MD</a><sup>b</sup>,
<a href="/articles/search_result.php?term=author&amp;f_name=Sang-Ho&amp;l_name=Kim">Sang-Ho Kim, MD</a><sup></sup><sup>a</sup>
</div>
<div class="metadata-group aff_layer">
<p class="metadata-entry"><a id="af1"></a><sup>a</sup>Department of Neurology, Dong-A University College of Medicine, Busan, Korea</p>
<p class="metadata-entry"><a id="af2"></a><sup>b</sup>Department of Neurology, Pusan National University, Busan, Korea</p>
</div>
<div class="corresp">Address for correspondence: Sang-Ho Kim, MD Department of Neurology, Dong-A University College of
Medicine, Busan, Korea E-mail: <a href="mailto:x@dau.ac.kr">x@dau.ac.kr</a></div>
<h4 class="link-target" id="sec07">ACKNOWLEDGEMENTS</h4>
<div>The authors thank the laboratory staff.</div>
<dl class="txt"><h4 class="link-target">REFERENCES</h4><ul class="reference">
<li id="B1" name="jats-ref-pub" class="ref_layer"><span>1. Bernardon JK, Ferrari P. Treatment time versus patient
satisfaction. J Prosthet Dent 2015;114:826-830.</span><a href="https://doi.org/10.1016/j.prosdent.2015.05.014">[CrossRef]</a></li>
<li id="B2" name="jats-ref-pub" class="ref_layer"><span>2. Joiner A. The bleaching of teeth. J Dent 2006;34:412-419.</span></li>
</ul></dl>"""
JATS_NAMES = ["Sang-Wuk Sohn", "Gwang-Dong Choi", "Sang-Ho Kim"]


def _jats():
    return _page(_metas(JATS_NAMES), JATS_BODY)


def test_jats_view_lettered_affiliations_fill_blank_meta_tags():
    out = parse_page(_jats().encode(), "doi", URL)
    affs = [[x["name"] for x in a["affiliations"]] for a in out["authors"]]
    assert affs == [["Department of Neurology, Dong-A University College of Medicine, Busan, Korea"],
                    ["Department of Neurology, Pusan National University, Busan, Korea"],
                    ["Department of Neurology, Dong-A University College of Medicine, Busan, Korea"]]


def test_jats_view_address_for_correspondence_marks_one_author():
    out = parse_page(_jats().encode(), "doi", URL)
    assert [a["name"] for a in out["authors"] if a["is_corresponding"]] == ["Sang-Ho Kim"]


def test_jats_view_references_and_acknowledgments():
    parsed = KoreaMedXMLink(BeautifulSoup(_jats(), "lxml")).parse()
    assert [r["raw"][:12] for r in parsed["references"]] == ["Bernardon JK", "Joiner A. Th"]
    assert parsed["references"][0]["doi"] == "10.1016/j.prosdent.2015.05.014"
    assert parsed["references_complete"] is True
    assert parsed["acknowledgments"] == "The authors thank the laboratory staff."


def test_lookalike_page_from_another_template_is_not_claimed():
    # an INFOrang-hosted Korean journal page (the census lumped some with this template): its own byline classes,
    # "Correspondence to" note and reference list, but none of XMLink's marks
    html = _page(_metas(["Moon Sil Choi"]), """<div class="article_author">Moon Sil Choi</div>
<div class="aff">Department of Dental Hygiene, Songwon University</div>
<p>Correspondence to: Moon Sil Choi</p><ol class="reference"><li class="ref_layer">1. A ref. 2020.</li></ol>
<p>Powered by INFOrang Co., Ltd</p>""")
    parser = KoreaMedXMLink(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
