"""Article pages of the IRBIS journal system on the Vernadsky National Library of Ukraine's Drupal sites (oxjob #2338).

Markup cut down from stored pages of np.nbuv.gov.ua, rksu.nbuv.gov.ua and kraieznavstvo.history.org.ua (DOI prefix
10.15407, swarm site kiev.ua). The page opens with a broken doctype ("<DOCTYPE ...", no "!"), which lxml reads as a
<doctype> element holding the whole page; IRBIS prints its citation_* meta tags inside the article block, with the
authors in Ukrainian ("Потіха, А."). The visible byline is English, and its "Author(s) citation:" list gives each
author's affiliation in brackets, followed by an e-mail address on some pages; the references are one <ol>.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.nbuv_irbis import NbuvIrbis

URL = "https://doi.org/10.15407/np.43.239"
HEAD = ('<DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">\n'
        '<head profile="http://www.w3.org/1999/xhtml/vocab">\n'
        '<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />\n'
        '<meta name="Generator" content="Drupal 7 (http://drupal.org)" />\n'
        '<link rel="canonical" href="/uk/archive" />\n</head>\n<body>\n<div id="content"><div id="main">')
IRBIS_META = ('<meta name="citation_abstract_html_url" content="http://np.nbuv.gov.ua/cgi-bin/np/jrn.exe?I21DBN=LINK'
              '&P21DBN=NP&S21REF=10&S21FMT=ASP_meta&C21COM=S&2_S21STR=npnbuimviv_2016_43_18" />\n')
ABSTRACT = ("Study of the functioning and place in modern society of the party mass media is important, because "
            "researchers took up these problems not so long ago. The vast majority of research concerns periodicals "
            "and partially electronic media, and the number of serious studies of the mass media grows every year.")


def _li(name, aff_html):
    return ('<li><a style="font-size : 14px;" href="http://scholar.google.com.ua/scholar?as_sauthors=x">'
            f'{name}</a><span style="font-size : 12px;"> (<i>{aff_html}</i>) </li></span>\n')


def _page(names_uk, lis, refs="", irbis_meta=IRBIS_META, head=HEAD):
    metas = "".join(f'<meta name="citation_author" content="{n}" />\n' for n in names_uk)
    return (head + '<meta name="citation_title" content="Дослідження партійних засобів" />\n' + metas + irbis_meta
            + '<table><tr><td><p style="text-align:justify;font-size:14px;"><b>Byline</b><br><h4>Study of Party '
              'Mass Media</h4><p/><p style="text-align:justify;font-size:12px;"><i><b>Abstract: </b></i>'
            + ABSTRACT + '<p/><p><i><b>Keywords: </b></i>historiography, mass media.<p/><hr/>'
              '<span style="margin-top:6pt;"><i><b>Author(s) citation:</b></i></span><ul>' + "".join(lis)
            + '</ul><hr/><p><i><b>Cite:</b></i><br/>A citation.</p>' + refs
            + '</td></tr></table></div></div>\n<div id="footer">Texts are available under Creative Commons</div>'
              '</body></html>')


REFS = ('<hr><p style="text-align:justify;font-size:12px;"><i><b>References:</b></i><ol>'
        '<li style="font-size:10px;"><a href="http://nbuv.gov.ua/UJRN/Polzap_2013_7_10">Ahafonova, H. S. (2013) '
        'Dotsilnist vykorystannia SMM. Politolohichni zapysky, no.7. [in Ukrainian].</a></li>\n'
        '<li style="font-size:10px;">Swyripa, F. (1978). Ukrainian Canadians: a survey of their portrayal in '
        'English-language wo<font color=#8B4513>rks</font></b>. Edmonton, 169 p. [In English].</li>\n'
        '<li style="font-size:10px;">Osborne, B. (1991). Non-preferred people. Toronto, pp. 81-102. doi: '
        '<a href="https://doi.org/10.3138/9781442683235-008">https://doi.org/10.3138/9781442683235-008</a></li>\n'
        '</ol>')


def _out(html):
    return parse_page(html.encode(), "doi", URL)


def _parse(html):
    return NbuvIrbis(BeautifulSoup(html.encode(), parser="lxml", features="lxml")).parse()


def test_english_byline_with_its_affiliation_and_no_email():
    html = _page(["Дзира, О. І."], [_li("Dzyra Olesia", 'V.&nbsp;I.&nbsp;Vernadskyi National Library of Ukraine, '
                                    'Ukraine, Kyiv, <a href="mailto:"dzyraolesya@gmail.com">dzyraolesya@gmail.com</a>')])
    authors = _out(html)["authors"]
    assert [a["name"] for a in authors] == ["Dzyra Olesia"]
    assert [x["name"] for x in authors[0]["affiliations"]] == [
        "V. I. Vernadskyi National Library of Ukraine, Ukraine, Kyiv"]
    # an e-mail address shown for every author is no corresponding-author mark (label-v1)
    assert not authors[0]["is_corresponding"]


def test_each_author_keeps_their_own_affiliation():
    html = _page(["Потіха, А.", "Клименко, О."],
                 [_li("Potikha Andrii", "V. I. Vernadsky National Library of Ukraine, Ukraine, Kyiv"),
                  _li("Klymenko Oksana", "Institute of History of Ukraine of National Academy of Sciences of Ukraine, "
                                         "Ukraine, Kyiv")])
    authors = _out(html)["authors"]
    assert [a["name"] for a in authors] == ["Potikha Andrii", "Klymenko Oksana"]
    assert [[x["name"] for x in a["affiliations"]] for a in authors] == [
        ["V. I. Vernadsky National Library of Ukraine, Ukraine, Kyiv"],
        ["Institute of History of Ukraine of National Academy of Sciences of Ukraine, Ukraine, Kyiv"]]


def test_author_without_affiliation_gets_none():
    html = _page(["Потіха, А."], [_li("Potikha Andrii", "")])
    authors = _out(html)["authors"]
    assert [a["name"] for a in authors] == ["Potikha Andrii"]
    assert authors[0]["affiliations"] == []


def test_abstract_is_the_generic_readers():
    html = _page(["Потіха, А."], [_li("Potikha Andrii", "V. I. Vernadsky National Library of Ukraine, Ukraine, Kyiv")])
    assert _out(html)["abstract"].startswith("Study of the functioning and place in modern society")


def test_references_are_the_whole_ordered_list():
    html = _page(["Дзира, О. І."], [_li("Dzyra Olesia", "V. I. Vernadskyi National Library of Ukraine, Ukraine, Kyiv")],
                 refs=REFS)
    parsed = _parse(html)
    refs = parsed["references"]
    assert [r["position"] for r in refs] == [1, 2, 3]
    assert refs[0]["raw"].startswith("Ahafonova, H. S. (2013)")
    assert "English-language works." in refs[1]["raw"]  # the site's search highlight splits words in <font>
    assert [r["doi"] for r in refs] == [None, None, "10.3138/9781442683235-008"]
    assert parsed["references_complete"] is True
    assert parsed["acknowledgments"] is None and parsed["funding_statement"] is None


def test_page_without_references_has_none():
    parsed = _parse(_page(["Потіха, А."], [_li("Potikha Andrii", "V. I. Vernadsky National Library of Ukraine")]))
    assert parsed["references"] is None and parsed["references_complete"] is False


def test_same_drupal_theme_without_irbis_is_not_claimed():
    # scinn-eng.org.ua and visnyk-nanu.org.ua run the same Drupal theme with a proper doctype and no IRBIS block
    head = ('<!DOCTYPE html><html><head><meta name="Generator" content="Drupal 7 (http://drupal.org)" />'
            '<style>@import url("http://scinn-eng.org.ua/sites/all/themes/corporateclean/style.css");</style>'
            '</head><body><div id="content">')
    html = _page(["Kobets, VM"], [_li("Kobets VM", "Some Institute, Kyiv")], head=head)
    soup = BeautifulSoup(html.encode(), parser="lxml", features="lxml")
    assert not NbuvIrbis(soup).is_publisher_specific_parser()
    assert not NbuvIrbis(soup).authors_found()
    assert [a["name"] for a in _out(html)["authors"]] == ["Kobets, VM"]


def test_broken_doctype_page_of_another_system_is_not_claimed():
    # the same doctype typo on a page with no IRBIS meta tag (an OJS or WordPress journal) stays with the other readers
    other_meta = '<meta name="citation_abstract_html_url" content="https://journal.example.org/article/view/12" />\n'
    html = _page(["Potikha, A."], [_li("Potikha Andrii", "Some Institute, Kyiv")], irbis_meta=other_meta)
    soup = BeautifulSoup(html.encode(), parser="lxml", features="lxml")
    assert not NbuvIrbis(soup).is_publisher_specific_parser()
    assert not NbuvIrbis(soup).authors_found()
    authors = _out(html)["authors"]
    assert [a["name"] for a in authors] == ["Potikha, A."] and authors[0]["affiliations"] == []
