"""DKS Center's own article pages (nayka.com.ua's older journal sites: Ефективна економіка, Економіка та держава,
Агросвіт, Інвестиції: практика та досвід, Державне управління; oxjob #2339).

Markup cut down from stored pages (17 Nov 2026). Each page prints its reference list twice: under "Література" in the
article's language and under "References" in English and transliteration, both numbered "1." to "n.". The parser
returns the "References" version (the page's English one) and leaves authors and abstract to the generic reader,
whose output it passes on unchanged. The journals' Open Journal Systems pages (#2267) are not claimed.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.nayka import Nayka

URL = "https://doi.org/10.32702/2307-2105-2021.3.74"
HEAD = ('<meta name="citation_journal_title" content="Ефективна економіка" />'
        '<meta name="citation_doi" content="10.32702/2307-2105-2021.3.74" />'
        '<meta name="citation_title" content="УПРАВЛІННЯ АСОРТИМЕНТНОЮ ПОЛІТИКОЮ" />'
        '<meta name="citation_author" content="О. В. Петренко" /><meta name="citation_author" content="Г. С. Коваль" />'
        '<meta name="citation_abstract_html_url" content="http://www.economy.nayka.com.ua?op=1&amp;z=8744" />'
        '<meta name="citation_pdf_url" content="http://www.economy.nayka.com.ua/pdf/3_2021/76.pdf" />'
        '<meta name="DC.Description" xml:lang="en" content="The peculiarities of retail trade in a pandemic in 2020 are '
        'considered. The changes that have taken place in the nature of retail trade are analyzed, and the sales '
        'volumes of the main categories of goods in 2019-2020 are compared with inflation and wages." />')
ORIGINAL = ["1. Левченко М. Роздрібна торгівля. Київ: Лібра, 2006. 720 с.",
            "2. Марков Б.М. Генезис поняття «роздрібна торгівля». Науковий вісник. 2016. С. 27-30",
            "3. Індекс інфляції. URL: https://index.minfin.com.ua/ua/economy/index/inflation/2019/"]
ENGLISH = ["1.\tLevchenko, M. (2006), Rozdribna torhivlia [Retail trade], Libra, Kyiv, Ukraine.",
           "2.\tMarkov, B.M. (2016), “Genesis of the concept “retail trading””, Naukovyi visnyk, vol. 18, pp. 27-30. "
           "DOI: 10.32702/2307-2105-2021.4.3.",
           "3.\tMinistry of Finance of Ukraine (2020), “Index of inflation”, available at: "
           "https://index.minfin.com.ua/ua/economy/index/inflation/2019/ (Accessed 05 March 2021)."]


def _list(heading, lines):
    return f'<p class="bold m_top10">{heading}</p><p class="rezume">{"<br />".join(lines)}</p>'


def _page(original=ORIGINAL, english=ENGLISH, head=HEAD, original_heading="Література"):
    body = ('<p class="bold italic m_top10">О. В. Петренко, Г. С. Коваль</p>'
            '<h1 class="article_title">УПРАВЛІННЯ АСОРТИМЕНТНОЮ ПОЛІТИКОЮ</h1>'
            '<p class="bold m_top10">Анотація</p><p class="rezume">У статті розглянуто особливості торгівлі.</p>')
    if original is not None:
        body += _list(original_heading, original)
    body += '<p class="bold italic m_top10">O. Petrenko, H. Koval</p><p class="bold m_top10">Summary</p>' \
            '<p class="rezume">The peculiarities of retail trade in a pandemic in 2020 are considered.</p>'
    if english is not None:
        body += _list("References", english)
    side = ('<div class="plashka"><p>Відомості про авторів</p></div><div class="ramka">'
            '<p class="bold text-left">О. В. Петренко</p><p class="text-right"><i>к. е. н., доцент, Львівський '
            'національний університет імені Івана Франка</i></p></div>')
    return (f'<html lang="uk"><head><meta charset="utf-8" />{head}</head><body><div class="container"><div class="row">'
            f'<div class="col-md-8"><article class="article">{body}</article></div><div class="col-md-4">{side}</div>'
            f'</div></div></body></html>')


def _parsed(html):
    return Nayka(BeautifulSoup(html, "lxml")).parse()


def test_claims_its_own_pages():
    parser = Nayka(BeautifulSoup(_page(), "lxml"))
    assert parser.is_publisher_specific_parser()
    assert parser.authors_found()


def test_references_are_the_english_list_without_numbers():
    parsed = _parsed(_page())
    assert [r["position"] for r in parsed["references"]] == [1, 2, 3]
    assert parsed["references"][0]["raw"] == "Levchenko, M. (2006), Rozdribna torhivlia [Retail trade], Libra, Kyiv, Ukraine."
    assert parsed["references"][1]["doi"] == "10.32702/2307-2105-2021.4.3"
    assert parsed["references"][0]["doi"] is None
    assert parsed["references_complete"] is True


def test_parse_page_serves_the_whole_list():
    out = parse_page(_page().encode(), "doi", URL)
    assert len(out["references"]) == 3 and out["references_complete"] is True
    assert out["acknowledgments"] is None and out["funding_statement"] is None


def test_authors_and_abstract_are_the_generic_readers():
    html = _page()
    parsed = _parsed(html)
    generic = GenericPublisherParser(BeautifulSoup(html, "lxml")).parse()
    assert parsed["authors"] == generic["authors"]
    assert parsed["abstract"] == generic["abstract"]
    out = parse_page(html.encode(), "doi", URL)
    assert [a["name"] for a in out["authors"]] == ["О. В. Петренко", "Г. С. Коваль"]
    assert all(a["affiliations"] == [] for a in out["authors"])


def test_a_number_typed_with_a_tab_only_still_counts():
    english = ENGLISH[:2] + ["3\t" + ENGLISH[2][3:]]
    parsed = _parsed(_page(english=english))
    assert parsed["references"][2]["raw"].startswith("Ministry of Finance")
    assert parsed["references_complete"] is True


def test_a_gap_in_the_numbering_is_not_whole():
    english = [ENGLISH[0], ENGLISH[2].replace("3.", "4.", 1)]
    parsed = _parsed(_page(original=ORIGINAL[:1] + ORIGINAL[2:], english=english))
    assert len(parsed["references"]) == 2
    assert parsed["references_complete"] is False


def test_an_entry_broken_across_lines_is_not_whole():
    english = [ENGLISH[0], ENGLISH[1][:40], ENGLISH[1][40:], ENGLISH[2]]
    assert _parsed(_page(english=english))["references_complete"] is False


def test_lists_of_different_lengths_are_not_whole():
    assert _parsed(_page(original=ORIGINAL[:2]))["references_complete"] is False


def test_the_original_list_when_there_is_no_english_one():
    parsed = _parsed(_page(english=None, original_heading="Литература"))
    assert parsed["references"][0]["raw"].startswith("Левченко М.")
    assert parsed["references_complete"] is True


def test_no_list_no_reference_keys():
    parsed = _parsed(_page(original=None, english=None))
    assert "references" not in parsed and "references_complete" not in parsed
    assert parsed["authors"]


def test_a_journal_site_whose_pages_carry_no_doi_tag():
    head = HEAD.replace('<meta name="citation_doi" content="10.32702/2307-2105-2021.3.74" />', "")
    head = head.replace("http://www.economy.nayka.com.ua?op=1&amp;z=8744", "http://www.agrosvit.info/?op=1&amp;z=3492&amp;i=2")
    parsed = _parsed(_page(head=head))
    assert len(parsed["references"]) == 3 and parsed["references_complete"] is True


def test_not_the_same_journals_ojs_pages():
    ojs = HEAD.replace("http://www.economy.nayka.com.ua?op=1&amp;z=8744",
                       "https://nayka.com.ua/index.php/ee/article/view/5527")
    ojs = '<meta name="generator" content="Open Journal Systems 3.3.0.11" />' + ojs
    parser = Nayka(BeautifulSoup(_page(head=ojs), "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_not_a_look_alike_page_of_another_publisher():
    other = HEAD.replace("10.32702/", "10.15407/").replace("www.economy.nayka.com.ua", "www.example.kiev.ua")
    parser = Nayka(BeautifulSoup(_page(head=other), "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    assert parse_page(_page(head=other).encode(), "doi", URL)["references"] is None


def test_not_the_same_address_form_on_another_host():
    other = HEAD.replace("www.economy.nayka.com.ua?op=1", "www.economy.example.com.ua/?op=1")
    assert not Nayka(BeautifulSoup(_page(head=other), "lxml")).is_publisher_specific_parser()
    other = HEAD.replace("www.economy.nayka.com.ua?op=1", "nayka.com.ua.example.org/?op=1")
    assert not Nayka(BeautifulSoup(_page(head=other), "lxml")).is_publisher_specific_parser()


def test_a_page_with_no_head():
    parser = Nayka(BeautifulSoup("<p>References</p>", "lxml"))
    assert not parser.is_publisher_specific_parser()
