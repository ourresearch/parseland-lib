"""nbpublish.com (NB-Media) article pages (oxjob #2338).

Markup cut down from stored pages: one <table class="article"> per author whose author_desc cell holds the Russian
block, then the English one, then an e-mail table; one citation_author tag holding the whole byline; reference lists
numbered as table rows (older pages) or as <a name="engN"> spans (newer pages, stored with the Cyrillic dropped).
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.nbpublish import NBPublish

URL = "https://nbpublish.com/library_read_article.php?id=28671"
HEAD = ('<head><meta name="citation_author" content="{byline}">'
        '<meta name="citation_title" content="Заголовок статьи">'
        '<meta name="citation_doi" content="10.7256/2454-0625.2019.1.28671">'
        '<meta name="citation_abstract_html_url" content="{home}/library_read_article.php?id=28671"></head>')


def _author(ru_name, ru_lines, en_name, en_lines, email="a@example.ru"):
    ru = "".join(f"<br>{line}<br>" for line in ru_lines)
    en = "".join(f"<br>{line}<br>" for line in en_lines)
    return (f'<table class="article"><tr><td valign="middle" class="author_desc" align="right">'
            f"<b >{ru_name}</b><br>{ru}<br><b >{en_name}</b><br>{en}<br>"
            f'<table><tr><td><img src="//www.e-notabene.ru/img/emailButton.png"></td><td>{email}</td></tr></table>'
            f'</td><td><img src="no_photo.png"></td></tr></table>')


AUTHOR_1 = _author("Рубин Владимир Александрович",
                   ["кандидат исторических наук",
                    'доцент кафедры истории и философии ФГБОУ ВО "Оренбургский государственный аграрный университет"',
                    "460014, Россия, Оренбургская область, г. Оренбург, ул. Челюскинцев, 18"],
                   "Rubin Vladimir Aleksandrovich",
                   ["PhD in History", "Docent, the department of History and Philosophy, Orenburg State Agricultural Academy",
                    "460014, Russia, Orenburgskaya oblast', g. Orenburg, ul. Chelyuskintsev, 18"])
AUTHOR_2 = _author("Спиридонова Екатерина Владимировна",
                   ["ORCID: 0000-0002-1825-0097", "доцент, , кафедра прикладной математики, Оренбургский государственный университет",
                    "460018, Россия, г. Оренбург, пр. Победы, 13"],
                   "Spiridonova Ekaterina Vladimirovna",
                   ["Docent, the department of Applied Mathematics, Orenburg State University", "460018, Russia, Orenburg"])
ABSTRACT = ('<span class="annotation" style="display:block"><p color="#FF6600"><b>Abstract:</b> The rationale of the '
            "research is caused by the lack of knowledge on the topic as well as the state policy that is taking shape in "
            "the post-Soviet space in perpetuating the memory of those who died defending the Fatherland, and the authors "
            "study the contribution of search organizations to the preservation of the military memorial heritage.</p>"
            "</span>")
OLD_REFS = ('<div class="subpart_title">Библиография</div><table>'
            '<tr><td><span class="annotation"><a name="1">1</a>.</span></td><td><div><span class="annotation">'
            "Боле Е.Н. Историческое значение поискового движения // Военная археология. 2009. № 1.</span></div></td></tr>"
            "</table>"
            '<div class="subpart_title">References</div><table>'
            '<tr><td><span class="annotation"><a name="1">1</a>.</span></td><td><div><span class="annotation">'
            "Bole E.N. Istoricheskoe znachenie poiskovogo dvizheniya // Voennaya arkheologiya. 2009. № 1.</span></div></td></tr>"
            '<tr><td><span class="annotation"><a name="2">2</a>.</span></td><td><div><span class="annotation">'
            "Ivanov I.I. A title // A journal. 2018. DOI: 10.1163/22116001_03501014.</span></div></td></tr>"
            "</table>")


def _page(authors, refs=OLD_REFS, extra="", home="http://nbpublish.com",
          byline="Рубин В.А., Спиридонова Е.В."):
    return (f"<html>{HEAD.format(byline=byline, home=home)}<body>"
            f'<h1 class="article_title">Заголовок статьи</h1>{"".join(authors)}{ABSTRACT}{refs}{extra}</body></html>')


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def test_each_author_from_the_byline_cells_not_the_joined_meta_tag():
    names = [a["name"] for a in _parse(_page([AUTHOR_1, AUTHOR_2]))["authors"]]
    assert names == ["Рубин Владимир Александрович", "Спиридонова Екатерина Владимировна"]


def test_affiliation_is_position_line_and_address_without_degree_orcid_or_email():
    authors = _parse(_page([AUTHOR_1, AUTHOR_2]))["authors"]
    assert authors[0]["affiliations"] == [{"name": 'доцент кафедры истории и философии ФГБОУ ВО "Оренбургский '
                                                   'государственный аграрный университет", 460014, Россия, Оренбургская '
                                                   "область, г. Оренбург, ул. Челюскинцев, 18"}]
    assert authors[1]["affiliations"] == [{"name": "доцент, кафедра прикладной математики, Оренбургский "
                                                   "государственный университет, 460018, Россия, г. Оренбург, пр. Победы, 13"}]


def test_email_for_every_author_is_not_a_corresponding_mark():
    assert not any(a["is_corresponding"] for a in _parse(_page([AUTHOR_1, AUTHOR_2]))["authors"])


def test_page_stored_without_cyrillic_reads_the_english_block():
    stripped = _author("", [", , ,", "1439813164, , , . , . , 1"], "Golami Hosein",
                       ["PhD in Philology", "Professor, Department of Russian Language and Literature, University of Tehran",
                        "1439813164, Iran, Tehran, Karegar str., 1"])
    authors = _parse(_page([stripped], byline=" .."))["authors"]
    assert [a["name"] for a in authors] == ["Golami Hosein"]
    assert authors[0]["affiliations"] == [{"name": "Professor, Department of Russian Language and Literature, "
                                                   "University of Tehran, 1439813164, Iran, Tehran, Karegar str., 1"}]


def test_abstract_is_still_the_printed_english_one():
    assert _parse(_page([AUTHOR_1]))["abstract"].startswith("The rationale of the research")


def test_page_with_reviews_block_is_left_to_the_generic_parser():
    # a review report's DOI resolves to this same page: its authors are not the article's
    reviews = '<div id="reviews"><span class="annotation 0"><a name="review_37244" id="review_37244"></a></span></div>'
    soup = BeautifulSoup(_page([AUTHOR_1], extra=reviews), "lxml")
    assert NBPublish(soup).is_publisher_specific_parser() and not NBPublish(soup).authors_found()


def test_english_reference_list_from_table_rows():
    out = NBPublish(BeautifulSoup(_page([AUTHOR_1]), "lxml")).parse()
    assert [r["raw"] for r in out["references"]] == [
        "Bole E.N. Istoricheskoe znachenie poiskovogo dvizheniya // Voennaya arkheologiya. 2009. № 1.",
        "Ivanov I.I. A title // A journal. 2018. DOI: 10.1163/22116001_03501014."]
    assert [r["doi"] for r in out["references"]] == [None, "10.1163/22116001_03501014"]
    assert out["references_complete"] is True


def test_reference_spans_on_new_pages_and_a_gap_is_not_complete():
    def span(n, text):
        return (f'<span class="annotation"><span style="font-style:normal"><a name="eng{n}">{n}</a>.&nbsp;{text}'
                "</span></span><br>")
    refs = '<div class="subpart_title">References</div><span class="annotation">' + span(1, "Savenkov, A.N. (2018). Arctic.") \
        + span(3, "Zudro, I.S. (2022). Arctic: Sustainable development.") + "</span>"
    out = NBPublish(BeautifulSoup(_page([AUTHOR_1], refs=refs), "lxml")).parse()
    assert [r["raw"] for r in out["references"]] == ["Savenkov, A.N. (2018). Arctic.",
                                                     "Zudro, I.S. (2022). Arctic: Sustainable development."]
    assert out["references_complete"] is False


def test_same_template_on_another_domain_is_not_claimed():
    # e-notabene.ru runs the same CMS; this parser claims nbpublish.com only
    soup = BeautifulSoup(_page([AUTHOR_1], home="https://e-notabene.ru"), "lxml")
    assert not NBPublish(soup).is_publisher_specific_parser()
    names = [a["name"] for a in _parse(_page([AUTHOR_1], home="https://e-notabene.ru"))["authors"]]
    assert names != ["Рубин Владимир Александрович"]
