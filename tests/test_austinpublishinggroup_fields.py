"""austinpublishinggroup.com (Austin Publishing Group) article pages (oxjob #2210).

Markup is cut down from stored pages of the site (13 Nov 2026). The full-text page prints the byline as one
<p class="subline"> (names split by ";", "," or "and", affiliation numbers in <sup> or as Unicode superscripts, "*"
for the corresponding author), one <p class="affl"> per affiliation, a "*Corresponding author:" note, the abstract
under an <h2> "Abstract" (or "Summary"), and the references in one <ol id="ref">.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.austinpublishinggroup import AustinPublishingGroup

URL = "https://austinpublishinggroup.com/hematology/fulltext/hematology-v10-id1443.php"
HEAD = ('<link rel="canonical" href="https://austinpublishinggroup.com/hematology/fulltext/hematology-v10-id1443.php"/>'
        '<meta name="citation_title" content="A title">'
        '<meta name="citation_publisher" content="Austin Publishing Group">')
ABSTRACT = ('<h2 class="ash"><a name="Abstract"></a> <a id="Abstract"></a>Abstract</h2>'
            '<p><strong>Background:</strong> Light chain or AL amyloidosis is a systemic disease that occasionally\n'
            'involves the gastrointestinal tract.</p>'
            '<p><strong>Conclusion:</strong> The diagnosis of amyloidosis should be considered in adult patients.</p>'
            '<p><strong>Keywords:</strong> Amyloidosis; Bleeding</p>'
            '<h2 class="ash"><a name="Background"></a>Background</h2><p>Body text.</p>')
REFS = ('<h2 class="ash"><a name="References"></a><a id="References"></a>References</h2>'
        '<p id="last"><!-- References --><p style="clear:both;"><ol id="ref">'
        '<li class="refbul"><a href="https://pubmed.ncbi.nlm.nih.gov/1/" target="_blank">Oakland K. Changing '
        'epidemiology. Best Pract Res Clin Gastroenterol. 2019; 42: 101610.</a></li>'
        '<li class="refbul"><a href="https://doi.org/10.1016/j.x.2020.01.002" target="_blank">Merlini G. Molecular '
        'mechanisms of amyloidosis. N Engl J Med. 2003; 349: 583-96.</a></li>'
        '</ol></p>')


def _page(header, body="", head=HEAD):
    return (f'<html><head>{head}</head><body><div id="content"><p class="atp">Case Report</p>'
            f'<h1><a name="Title"></a>A title</h1>{header}'
            f'<p class="affl"><strong>Received: </strong>November 28, 2023</p>'
            f'<div class="article">{body}</div></div></body></html>')


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _raw(html):
    return AustinPublishingGroup(BeautifulSoup(html, "lxml")).parse()


def _affs(out):
    return [[a["name"] for a in au["affiliations"]] for au in out["authors"]]


def _corr(out):
    return [au["name"] for au in out["authors"] if au["is_corresponding"]]


NUMBERED = ('<p class="subline">Eilam Rabina<sup>1</sup>; Timna Naftali<sup>2,3</sup>; '
            'Osnat Jarchowsky Dolberg<sup>1,3</sup></p>'
            '<p class="affl"><sup>1</sup>Internal medicine A ward, Meir Medical Center, Kfar Saba Israel</p>'
            '<p class="affl"><sup>2</sup>Gastroenterology Institute, Meir Medical Center, Kfar Saba Israel</p>'
            '<p class="affl"><sup>3</sup>Tel Aviv University, Israel</p>'
            '<p class="affl" id="ref"><strong>*Corresponding author: </strong>Osnat Jarchowsky Dolberg Internal '
            'medicine A ward, Meir Medical Center, Kfar Saba, Israel. Email: o@example.org</p>')


def test_names_and_numbered_affiliations():
    out = _parse(_page(NUMBERED))
    assert [a["name"] for a in out["authors"]] == ["Eilam Rabina", "Timna Naftali", "Osnat Jarchowsky Dolberg"]
    assert _affs(out) == [["Internal medicine A ward, Meir Medical Center, Kfar Saba Israel"],
                          ["Gastroenterology Institute, Meir Medical Center, Kfar Saba Israel",
                           "Tel Aviv University, Israel"],
                          ["Internal medicine A ward, Meir Medical Center, Kfar Saba Israel",
                           "Tel Aviv University, Israel"]]


def test_corresponding_note_names_the_author_when_the_byline_has_no_star():
    assert _corr(_parse(_page(NUMBERED))) == ["Osnat Jarchowsky Dolberg"]
    header = ('<p class="subline">Guerra-Bulnes CM; Mercado-Flores HE; Lopez-Moran JA</p>'
              '<p class="affl">Department of Family Medicine, General Hospital Zone with Family Medicine, Mexico</p>'
              '<p class="affl" id="ref"><strong>*Corresponding author: </strong>Guerra-Bulnes Cristian Michel '
              'Department of Family Medicine, Mexico</p>')
    assert _corr(_parse(_page(header))) == ["Guerra-Bulnes CM"]


def test_unicode_superscripts_stars_and_and():
    header = ('<p class="subline">&Ouml;kkas KERETLI&sup1;, Emine Tuba &Ccedil;IFTCI&sup1; and Sefa L&Ouml;K&sup2;*</p>'
              '<p class="affl"><sup>1</sup>Selcuk University Institute of Health Sciences, Konya, Turkey</p>'
              '<p class="affl">²Selcuk University Faculty of Sport Sciences, Konya, Turkey</p>'
              '<p class="affl" id="ref"><strong>*Corresponding author: </strong>Sefa L&Ouml;KSelcuk University</p>')
    out = _parse(_page(header))
    assert [a["name"] for a in out["authors"]] == ["Ökkas KERETLI", "Emine Tuba ÇIFTCI", "Sefa LÖK"]
    assert _affs(out) == [["Selcuk University Institute of Health Sciences, Konya, Turkey"]] * 2 + [
        ["Selcuk University Faculty of Sport Sciences, Konya, Turkey"]]
    assert _corr(out) == ["Sefa LÖK"]


def test_two_starred_authors_and_equal_contribution_note():
    header = ('<p class="subline">Zhu D<sup>1#</sup>, Qiqi Z<sup>2#</sup>, Wang T<sup>2</sup>* and Lv C<sup>1,2</sup>*</p>'
              '<p class="affl"><sup>1</sup>Sichuan Agricultural University, Chengdu, China</p>'
              '<p class="affl"><sup>2</sup>Changchun Veterinary Research Institute, Changchun, PR China</p>'
              '<p class="affl"><sup>#</sup>Contributed Equally to this work</p>'
              '<p class="affl" id="ref"><strong>*Corresponding author: </strong>Tiecheng Wang, Changchun</p>'
              '<p class="affl" id="ref">Chaoxiang Lv, Changchun Veterinary Research Institute</p>')
    out = _parse(_page(header))
    assert _corr(out) == ["Wang T", "Lv C"]
    assert _affs(out)[0] == ["Sichuan Agricultural University, Chengdu, China"]
    assert all("Contributed" not in a for affs in _affs(out) for a in affs)


def test_one_unnumbered_affiliation_belongs_to_every_author():
    header = ('<p class="subline">Ahmed R*; Kalita JC</p>'
              '<p class="affl">Department of Zoology, Gauhati University, India</p>'
              '<p class="affl" id="ref"> <strong>*Corresponding author: </strong>Ahmed R Department of Zoology</p>')
    out = _parse(_page(header))
    assert _affs(out) == [["Department of Zoology, Gauhati University, India"]] * 2
    assert _corr(out) == ["Ahmed R"]


def test_star_without_a_corresponding_note_is_no_mark():
    header = ('<p class="subline">Yokoyama K, Ikeda T and Kawakami T*</p>'
              '<p class="affl">Division of Dermatology, Tohoku Medical and Pharmaceutical University, Sendai, Japan</p>')
    assert _corr(_parse(_page(header))) == []


def test_abstract_under_its_heading_without_keywords():
    out = _parse(_page(NUMBERED, ABSTRACT))
    assert out["abstract"] == ("Background: Light chain or AL amyloidosis is a systemic disease that occasionally "
                               "involves the gastrointestinal tract.\nConclusion: The diagnosis of amyloidosis "
                               "should be considered in adult patients.")


def test_summary_heading_with_trailing_comma_is_the_abstract():
    body = ('<h2 class="ash"><a name="Summary"></a>Summary,</h2><p>Introduction: Persistent COVID is considered the '
            'lack of return to a usual state of health after an acute illness due to COVID-19, in a cohort of 138 '
            'patients residing in Havana and Artemisa who were followed for one year.</p>'
            '<h2 class="ash">Introduction</h2><p>Body.</p>')
    assert _parse(_page(NUMBERED, body))["abstract"].startswith("Introduction: Persistent COVID")


def test_clinical_image_has_no_abstract():
    body = ('<h2 class="ash">Clinical Image</h2><p>UPS is a minimally invasive endoscopic procedure using a single '
            'Ethibond suture to attach the anterior cervix or vaginal vault unilaterally to the pectineal ligament.</p>')
    assert _raw(_page(NUMBERED, body))["abstract"] is None


def test_acknowledgments_and_funding_under_headings():
    body = ABSTRACT + ('<h2 class="assh"><a name="Acknowledgments"></a>Acknowledgments</h2>'
                       '<p>We thank the participants\r\r\nof this study.</p>'
                       '<h2 class="assh"><a name="Funding"></a>Funding</h2>'
                       '<p>This research received no specific grant.</p>') + REFS
    raw = _raw(_page(NUMBERED, body))
    assert raw["acknowledgments"] == "We thank the participants of this study."
    assert raw["funding_statement"] == "This research received no specific grant."


def test_acknowledgments_and_funding_as_bold_labels():
    body = ABSTRACT + ('<p><strong>Funding:</strong> Institutional funds from Italian Minister of Health</p>'
                       '<p><strong>Acknowledgements:</strong> The manuscript is dedicated to Dr. Balato.</p>')
    raw = _raw(_page(NUMBERED, body))
    assert raw["funding_statement"] == "Institutional funds from Italian Minister of Health"
    assert raw["acknowledgments"] == "The manuscript is dedicated to Dr. Balato."


def test_combined_acknowledgment_and_funding_heading_goes_to_acknowledgments():
    body = ('<h2 class="assh">Acknowledgment and Funding</h2><p>No acknowledgement nor funding to be declared.</p>')
    raw = _raw(_page(NUMBERED, body))
    assert raw["acknowledgments"] == "No acknowledgement nor funding to be declared."
    assert raw["funding_statement"] is None


def test_reference_list_is_whole_and_keeps_dois():
    raw = _raw(_page(NUMBERED, ABSTRACT + REFS))
    assert [r["position"] for r in raw["references"]] == [1, 2]
    assert raw["references"][0]["raw"].startswith("Oakland K. Changing epidemiology.")
    assert raw["references"][0]["doi"] is None
    assert raw["references"][1]["doi"] == "10.1016/j.x.2020.01.002"
    assert raw["references_complete"] is True


def test_empty_or_continued_list_is_not_complete():
    raw = _raw(_page(NUMBERED, ABSTRACT + '<h2 class="ash">References</h2><ol id="ref"></ol>'))
    assert raw["references"] is None and raw["references_complete"] is False
    raw = _raw(_page(NUMBERED, ABSTRACT + REFS.replace('<ol id="ref">', '<ol id="ref" start="5">')))
    assert raw["references_complete"] is False


def test_same_markup_on_another_site_is_not_claimed():
    head = '<link rel="canonical" href="https://example-journals.org/x/fulltext/x-v1-id1.php"/>'
    html = _page(NUMBERED, ABSTRACT, head=head)
    parser = AustinPublishingGroup(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    assert all(not au["affiliations"] for au in parse_page(html.encode(), "doi", "https://example-journals.org/x")["authors"])


def test_degree_after_a_comma_stays_with_its_name():
    header = ('<p class="subline">Tessy L&oacute;pez-Goerne, PhD<sup>1,2</sup>*; Rafael Valiente<sup>2</sup>; '
              'Xin Su, MD*</p>'
              '<p class="affl"><sup>1</sup>Department of Health Care, Autonomous Metropolitan University, Mexico</p>'
              '<p class="affl"><sup>2</sup>Tulane University, USA</p>'
              '<p class="affl" id="ref"><strong>*Corresponding author: </strong>Tessy L&oacute;pez-Goerne, Mexico</p>')
    out = _parse(_page(header))
    assert [a["name"] for a in out["authors"]] == ["Tessy López-Goerne", "Rafael Valiente", "Xin Su"]
    assert _affs(out)[0] == ["Department of Health Care, Autonomous Metropolitan University, Mexico",
                             "Tulane University, USA"]
    assert _corr(out) == ["Tessy López-Goerne", "Xin Su"]
