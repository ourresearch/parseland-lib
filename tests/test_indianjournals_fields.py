"""indianjournals.com article pages, the ijor.aspx template (oxjob #2330).

Markup cut down from stored pages of the site (17 Nov 2026). The page prints its byline as <p class="authorNames">,
names separated by commas, each linked to its affiliation (<a href="#aff001">) and, for the corresponding author, to
the correspondence note (<a href="#cor001">*</a>); the citation_* tags carry no affiliations and no parser read the
byline, so these works had no affiliations or corresponding author from the page.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.indianjournals import IndianJournals

URL = "https://www.indianjournals.com/ijor.aspx?target=ijor:aca&volume=7&issue=1&article=004"
HEAD = ('<html><head><link href="ijor_css/general.css" rel="stylesheet" type="text/css"/>'
        '<script src="ijor_css/filterlist.js"></script></head>')
ABSTRACT = ("Finance is the backbone of every business. No organization can run without finance. So, major financial "
            "decisions are always taken by the top management authorities. There are various techniques used by the "
            "experts to analyse the investment decisions and choose the best alternative.")


def _page(byline, after="", meta_abstract=ABSTRACT, abstract=None, head=HEAD):
    abstract = abstract if abstract is not None else f'<P class="abstract">{ABSTRACT}</P>'
    return (f'{head}<body><div id="DIVmain"><meta name="citation_title" content="A title">'
            f'<meta name="citation_abstract" content="{meta_abstract}"><table><tr><td>'
            f'<P class="articleTitle">A title</P><P class="authorNames">{byline}</P>{after}'
            f'<P class="authorNote"><i><b>Online published on 8 July, 2019</b>.</i></P>'
            f'<P class="sectionHeading1">Abstract</P>{abstract}<P class="linktotop"><A class="linktotop" href="#top">Top'
            f'</A></P><P class="sectionHeading1">Keywords</P><P class="keywords">NPV, IRR.</P></td></tr></table>'
            f'</div></body></html>')


def _aff(anchor, marker, text):
    return (f'<A name="{anchor}"></A>' if anchor else "") + f'<P class="authorAffiliation">{marker}{text}</P>'


def _cor(anchor, text):
    return (f'<A name="{anchor}"></A>' if anchor else "") + f'<P class="correspondingAuthorAffiliation">{text}<br></P>'


def _mail(addr):
    return (f'<A class="generallink" title="Click to send an e-mail" '
            f'href="mailto:{addr}?cc=gbehal@indianjournals.com">{addr}</A>')


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _authors(html):
    return [(a["name"], [x["name"] for x in a["affiliations"]], bool(a["is_corresponding"]))
            for a in _parse(html)["authors"]]


def test_byline_names_without_honorifics_and_linked_affiliations_without_email():
    html = _page('Ms Poonam<A href="#aff001"><SUP>1</SUP></A>, Dr. Aneja Harpreet<A href="#aff002"><SUP>2</SUP></A>',
                 _aff("aff001", "<SUP>1</SUP>", f"Research Scholar, IKG PTU, Jalandhar, India, Email id: "
                                                 f"{_mail('p@yahoo.co.in')}")
                 + _aff("aff002", "<SUP>2</SUP>", "Khalsa Institute of Management &amp; Technology for Women, "
                                                   "Ludhiana, India"))
    assert _authors(html) == [
        ("Poonam", ["Research Scholar, IKG PTU, Jalandhar, India"], False),
        ("Aneja Harpreet", ["Khalsa Institute of Management & Technology for Women, Ludhiana, India"], False)]


def test_star_markers_link_affiliations_not_correspondence():
    html = _page('Prakash N.<A href="#aff001"><SUP>*</SUP></A>, Somasundaram R.<A href="#aff002"><SUP>**</SUP></A>',
                 _aff("aff001", "", "*Kongu Engineering College, Erode, India")
                 + _aff("aff002", "", "**Anna University, Chennai, India"))
    assert _authors(html) == [("Prakash N.", ["Kongu Engineering College, Erode, India"], False),
                              ("Somasundaram R.", ["Anna University, Chennai, India"], False)]


def test_unlinked_affiliation_goes_to_every_author():
    html = _page("Lingaiah N, Raju Ch Surender, Sarla N.",
                 _aff(None, "", "Agricultural College, Mulugu Road, Warangal-506007, PJTSAU, Telangana, India"))
    aff = ["Agricultural College, Mulugu Road, Warangal-506007, PJTSAU, Telangana, India"]
    assert _authors(html) == [("Lingaiah N", aff, False), ("Raju Ch Surender", aff, False), ("Sarla N.", aff, False)]


def test_unmarked_affiliation_goes_to_authors_without_a_link():
    html = _page('Patel S.I., Patel G.M.<A href="#aff001"><SUP>1</SUP></A>, Patel A.A.',
                 _aff(None, "", "Centre of Excellence for Research on Wheat, S. D. Agricultural University, India")
                 + _aff("aff001", "<SUP>1</SUP>", "College of Basic Sciences, S. D. Agricultural University, India"))
    wheat = ["Centre of Excellence for Research on Wheat, S. D. Agricultural University, India"]
    assert _authors(html) == [("Patel S.I.", wheat, False),
                              ("Patel G.M.", ["College of Basic Sciences, S. D. Agricultural University, India"], False),
                              ("Patel A.A.", wheat, False)]


def test_job_title_dropped_only_when_an_organisation_remains():
    html = _page("Alimova Mahfuza",
                 _aff(None, "", "Associate Professor, Doctor of philosophy PhD, Department of the Religious Study and "
                                f"UNESCO, Uzbekistan, Email id: {_mail('m@iiau.uz')}"))
    assert _authors(html) == [("Alimova Mahfuza", ["Department of the Religious Study and UNESCO, Uzbekistan"], False)]
    html = _page("Tutor X", _aff(None, "", "Assistant Professor (Biochemistry), SUM Nursing College, Bhubaneswar"))
    assert _authors(html)[0][1] == ["SUM Nursing College, Bhubaneswar"]


def test_quoted_footnote_is_not_an_affiliation():
    html = _page('Mishra Ashutosh<A href="#aff001"><SUP>*</SUP></A>, Kumar Swatanter<A href="#aff002"><SUP>**</SUP></A>',
                 _aff("aff001", "", "*Faculty of Law, Delhi University")
                 + _aff("aff002", "", "**&#8220;Significance of Mediation&#8221;, Dispute Resolution Souvenir, 60 (2011)."))
    assert _authors(html) == [("Mishra Ashutosh", ["Faculty of Law, Delhi University"], False),
                              ("Kumar Swatanter", [], False)]


def test_orcid_note_is_not_part_of_the_affiliation():
    html = _page('Goel Garima<A href="#aff001"><SUP>1</SUP></A>',
                 _aff("aff001", "<SUP>1</SUP>", "National Dental College and Hospital, Mohali, Punjab, India "
                                                 "(ORCID ID 0000-0002-2709-8314)"))
    assert _authors(html)[0][1] == ["National Dental College and Hospital, Mohali, Punjab, India"]


def test_role_span_in_byline_is_not_an_author():
    html = _page('Maduri Rama Rao<A href="#aff1"><SUP>1</SUP></A>, <SPAN class="roledeg">Programme Coordinator</SPAN>',
                 _aff("aff1", "<SUP>1</SUP>", "Osmania University, Hyderabad, India"))
    assert [a[0] for a in _authors(html)] == ["Maduri Rama Rao"]


def test_starred_author_with_corresponding_note_is_marked():
    html = _page('Xu Yong-Jie<A href="#aff001"><SUP>1,</SUP></A><A href="#cor001">*</A>, '
                 'Wang Qi-Zhu<A href="#aff002"><SUP>2</SUP></A>',
                 _aff("aff001", "<SUP>1</SUP>", "Hubei Academy of Forestry, Wuhan, China")
                 + _aff("aff002", "<SUP>2</SUP>", "Yangtze University, Jingzhou, China")
                 + _cor("cor001", f"*Corresponding author: {_mail('49867@qq.com')}"))
    assert [a[2] for a in _authors(html)] == [True, False]


def test_only_the_note_that_says_corresponding_marks():
    html = _page('Pradhan Rubi<A href="#aff001"><SUP>1,</SUP></A><A href="#cor001"><SUP>*</SUP></A>, '
                 'Nayak Geeta Rani<A href="#aff001"><SUP>1,</SUP></A><A href="#cor002"><SUP>**</SUP></A>',
                 _aff("aff001", "<SUP>1</SUP>", "SUM Nursing College, Bhubaneswar")
                 + _cor("cor001", f"*Corresponding Author Email: {_mail('rp@gmail.com')}")
                 + _cor("cor002", f"**{_mail('gr@yahoo.com')}"))
    assert [a[2] for a in _authors(html)] == [True, False]


def test_one_starred_author_with_an_email_note_is_marked_but_not_a_lone_author():
    html = _page('Lingaiah N<A href="#cor001">*</A>, Raju Ch Surender, Sarla N.',
                 _aff(None, "", "Agricultural College, Warangal, India") + _cor("cor001", f"*E-mail: {_mail('n@g.com')}"))
    assert [a[2] for a in _authors(html)] == [True, False, False]
    html = _page('Kamat Pradeep V.<A href="#aff1"><SUP>1,</SUP></A><A href="#cor1">*</A>',
                 _aff("aff1", "<SUP>1</SUP>", "Business School, Mumbai, India") + _cor("cor1", f"*Email id: {_mail('p@y.com')}"))
    assert [a[2] for a in _authors(html)] == [False]


def test_unstarred_corresponding_note_matched_by_email_or_lone_author():
    html = _page('Sheik Ruksana<A href="#aff001"><SUP>1</SUP></A>, Dr. Nasim Iffat<A href="#aff002"><SUP>2</SUP></A>',
                 _aff("aff001", "<SUP>1</SUP>", "Saveetha Dental College, Chennai")
                 + _aff("aff002", "<SUP>2</SUP>", "Saveetha Dental College, Chennai")
                 + _cor("cor001", f"*Corresponding Author E-mail: {_mail('ruksana.sheik@gmail.com')}"))
    assert [a[2] for a in _authors(html)] == [True, False]
    html = _page("Hasan Hina", _aff(None, "", "MANUU, College of Teacher Education, Bidar, India")
                 + _cor(None, f"Corresponding author: {_mail('hina.manuu@rediffmail.com')}"))
    assert [a[2] for a in _authors(html)] == [True]


def test_structured_abstract_read_when_the_tag_is_empty():
    parts = ('<P class="sectionHeading2">Introduction</P><P class="section2paragraph">The diagnosis of sudden death '
             'due to acute myocardial infarction is difficult for the forensic expert and the pathologist alike.</P>'
             '<P class="sectionHeading2">Conclusion</P><P class="section2paragraph">The staining technique is more '
             'sensitive and efficient for detecting early ischemic changes in cases of sudden death.</P>')
    html = _page('Sheikh Mohammed Iliyas<A href="#aff001"><SUP>1</SUP></A>',
                 _aff("aff001", "<SUP>1</SUP>", "Surat Municipal Institute of Medical Education and Research, Surat"),
                 meta_abstract="", abstract=parts)
    abstract = _parse(html)["abstract"]
    assert abstract.startswith("Introduction: The diagnosis of sudden death")
    assert "Conclusion: The staining technique" in abstract


def test_tag_abstract_kept_when_present():
    html = _page("Save Vibhuti Aditya", _aff(None, "", "Bedekar Institute of Management Studies, Thane, India"))
    assert _parse(html)["abstract"] == ABSTRACT


def test_lookalike_byline_on_another_site_is_not_claimed():
    other_head = '<html><head><link href="/css/site.css" rel="stylesheet"/></head>'
    html = _page('Ms Poonam<A href="#aff001"><SUP>1</SUP></A>', _aff("aff001", "<SUP>1</SUP>", "IKG PTU, India"),
                 head=other_head)
    parser = IndianJournals(BeautifulSoup(html, parser="lxml", features="lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_new_indianjournals_template_is_not_claimed():
    html = ('<html><head><meta name="citation_author" content="S. Saran"/><meta name="citation_abstract_html_url" '
            'content="https://indianjournals.com/article/pmhe-29-2-008"/><link rel="stylesheet" '
            'href="/_next/static/css/a.css"/></head><body><ul class="publisher"><li><span class="me-3">S. Saran'
            '<sup>*</sup></span></li></ul></body></html>')
    parser = IndianJournals(BeautifulSoup(html, parser="lxml", features="lxml"))
    assert not parser.authors_found()


def test_error_page_of_the_template_is_not_read():
    html = (f'{HEAD}<body><div id="DIVmain"><P class="contentTitle">Content Page not found</P>'
            f'<P>Requested page could not be found.</P></div></body></html>')
    parser = IndianJournals(BeautifulSoup(html, parser="lxml", features="lxml"))
    assert parser.is_publisher_specific_parser()
    assert not parser.authors_found()
