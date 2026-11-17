"""Tomsk State University's research library (VTLS Vital at vital.lib.tsu.ru) record pages reached by DOI (oxjob #2339).

Markup cut down from stored record pages of TSU journal articles and conference papers (DOI prefix 10.17223). The page
lists its creators in citation_authors tags, one person per tag as "Family, Given Patronymic", and again under
"Creator" in its metadata list; the meta author tag names the university, not a person. No parser read the byline on
the DOI path before, so conference papers whose works have no authors at all stayed without them.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.tsu_ru import TsuVital

URL = "https://doi.org/10.17223/978-5-907442-03-0-2021-083"
NAMES = ["Выродова, Анна Вячеславовна", "Сараева, Анастасия Александровна", "Киреева, Ирина Васильевна",
         "Чумляков, Юрий Иванович"]


def _page(names=NAMES, host="vital.lib.tsu.ru", record="koha:000720381", extra_head="", title="Механизмы деформации"):
    metas = "".join(f'<meta name="citation_authors" content="{n}" />' for n in names)
    creators = "".join(f"<dt>Creator</dt><dd><a href=\"/vital/access/manager/Repository?exact=sm_creator\">{n}</a>"
                       for n in names)
    return (f'<html><head><meta name="author" content="Томский государственный Университет" />'
            f'<meta name="language" content="ru" />'
            f'<meta name="citation_pdf_url" content="http://{host}/vital/access/services/Download/{record}/SOURCE1" />'
            f'<meta name="citation_doi" content="10.17223/978-5-907442-03-0-2021-083" />{metas}'
            f'<meta name="citation_title" content="{title}" /><meta name="dc.Title" content="{title}" />'
            f'<meta name="dc.Identifier" content="{record}; DOI:10.17223/978-5-907442-03-0-2021-083; '
            f'http://{host}/vital/access/manager/Repository/{record}" />{extra_head}'
            f'<title>{title} | Tomsk state university Research library</title></head>'
            f'<body><div class="metadata_display"><dl class="metadata"><dt>Title</dt>'
            f'<dd class="primary_title" id="title">{title}</dd>{creators}<dt>Date</dt><dd>2021</dd></dl></div>'
            f'</body></html>')


def _authors(html):
    return parse_page(html.encode(), "doi", URL)["authors"]


def test_creators_are_the_byline_in_page_order():
    assert [a["name"] for a in _authors(_page())] == NAMES


def test_single_author_with_initials():
    assert [a["name"] for a in _authors(_page(names=["Duleba, M."]))] == ["Duleba, M."]


def test_no_affiliation_and_no_corresponding_mark():
    authors = _authors(_page())
    assert all(a["affiliations"] == [] for a in authors)
    assert not any(a["is_corresponding"] for a in authors)


def test_university_in_the_author_tag_is_not_an_author():
    names = [a["name"] for a in _authors(_page())]
    assert "Томский государственный Университет" not in names


def test_collection_page_without_creators_is_not_read():
    parser = TsuVital(BeautifulSoup(_page(names=[], record="vital:14"), "lxml"))
    assert parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_another_vital_repository_is_not_claimed():
    html = _page(names=["Smith, John"], host="researchonline.federation.edu.au", record="vital:11142")
    parser = TsuVital(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_page_with_citation_authors_but_no_tsu_record_is_not_claimed():
    html = ('<html><head><meta name="citation_authors" content="Чалкова, Т. Ф." />'
            '<meta name="citation_title" content="Повесть" /></head><body><p>Авторы: Чалкова Т.Ф.</p></body></html>')
    parser = TsuVital(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
