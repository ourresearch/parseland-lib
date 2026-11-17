"""Universum journals (7universum.com) article pages (oxjob #2339).

Markup cut down from stored 7universum.com pages (17 Nov 2026): the byline `div.authors_article`, the body
`div.article_content` (АННОТАЦИЯ / ABSTRACT headings, keywords, "Список литературы:" and an <ol>) and the
`div.author_information` block with one item per author and one `div.information` per language.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.universum7 import Universum7

URL = "https://7universum.com/ru/tech/archive/item/21498"


def _info(name, post):
    return f'<div class="information"><div class="name"><a href="/ru/tech/authors/item/x">{name}</a></div>' \
           f'<div class="post"><p>{post}</p></div></div>'


def _page(byline, items, content, canonical=URL):
    links = "".join(f'<a href="/ru/tech/authors/item/x">{n}</a>' for n in byline)
    people = "".join(f'<div class="item"><div class="avatar"><img src="/images/no_photo.png"></div>{"".join(i)}</div>'
                     for i in items)
    return (f'<html><head><meta charset="UTF-8"><title>T</title><meta name="description" content="{byline[0]} T // '
            f'Universum: технические науки : электрон. научн. журн. 2025. 12(141). URL: {canonical}">'
            f'<link rel="canonical" href="{canonical}"><link rel="stylesheet" href="/css/style.css?v=1.93"></head>'
            f'<body><main><article><div class="info_article"><div class="authors_article"><i class="fa fa-user"></i>'
            f'{links}</div></div><div class="doi_block"><strong>DOI - 10.32743/UniTech.2025.141.12.21498</strong></div>'
            f'<div class="article_content">{content}</div>'
            f'<div class="author_information"><div class="title">Информация об авторах</div>{people}</div>'
            f'</article></main></body></html>')


RU_EN = ('<p style="text-align:center"><strong>АННОТАЦИЯ</strong></p><p>Приведены результаты исследований.</p>'
         '<p style="text-align:center"><strong>ABSTRACT</strong></p><p>The results of research are given.</p>'
         '<p>The granules are stronger.</p>'
         '<p><strong>Ключевые слова:</strong> фосфориты.</p><p><strong>Keywords:</strong> phosphorites.</p>'
         '<p>Введение. Агрохимический комплекс.</p>'
         '<p><strong>Список литературы:</strong></p><ol><li>Беглов Б.М. Нетрадиционные методы. – Ташкент, 2009.</li>'
         '<li>Shamshidinov I. Phosphorites // Chem. J. 2021. DOI: 10.1234/abc.5.</li></ol>')

ITEMS = [[_info("Шамшидинов Исраилжон Тургунович", "д-р. техн. наук, проф. Наманганского инженерно-строительного "
                "института, Республика Узбекистан, г.&nbsp;Наманган"),
          _info("Shamshidinov Israiljon", "Doctor of Technical Sciences, Professor of Namangan engineering-construction "
                "institute, Republic of Uzbekistan, Namangan")],
         [_info("Усманов Илхам Икрамович", "канд. техн. наук, доцент, Каршинский государственный технический "
                "университет, Узбекистан, г. Карши"),
          _info("Usmanov Ilham", "PhD, Associate Professor, Karshi State Technical University, Uzbekistan, Karshi")]]


def _parse(html):
    return Universum7(BeautifulSoup(html, "lxml")).parse()


def test_authors_full_names_and_affiliations_without_degrees():
    out = parse_page(_page(["Шамшидинов И.Т.", "Усманов И.И."], ITEMS, RU_EN).encode(), "doi", URL)
    assert [a["name"] for a in out["authors"]] == ["Шамшидинов Исраилжон Тургунович", "Усманов Илхам Икрамович"]
    assert [[x["name"] for x in a["affiliations"]] for a in out["authors"]] == [
        ["Наманганского инженерно-строительного института, Республика Узбекистан, г. Наманган"],
        ["Каршинский государственный технический университет, Узбекистан, г. Карши"]]
    assert not any(a["is_corresponding"] for a in out["authors"])


def test_latin_byline_takes_the_english_author_block():
    out = parse_page(_page(["Shamshidinov I.", "Usmanov I."], ITEMS, RU_EN).encode(), "doi", URL)
    assert [a["name"] for a in out["authors"]] == ["Shamshidinov Israiljon", "Usmanov Ilham"]
    assert [x["name"] for x in out["authors"][1]["affiliations"]] == [
        "Karshi State Technical University, Uzbekistan, Karshi"]


def test_english_abstract_not_the_citation_in_the_meta_description():
    out = parse_page(_page(["Шамшидинов И.Т.", "Усманов И.И."], ITEMS, RU_EN).encode(), "doi", URL)
    assert out["abstract"] == "The results of research are given.\nThe granules are stronger."


def test_russian_abstract_when_no_english_one_and_stop_at_other_language():
    content = ('<p><strong>АННОТАЦИЯ</strong></p><p>Рассмотрено движение сооружения.</p>'
               '<p>This sentence is the English abstract without its heading.</p><p>Введение.</p>')
    assert _parse(_page(["Шамшидинов И.Т.", "Усманов И.И."], ITEMS, content))["abstract"] == \
        "Рассмотрено движение сооружения."


def test_english_abstract_stops_where_the_russian_text_begins():
    content = ('<h2>Аннотация</h2><p>В статье рассмотрены аспекты.</p><h2>A BSTRACT</h2><p>The article considers it.</p>'
               '<p>Основной объем текущих запасов природного газа.</p>')
    assert _parse(_page(["Шамшидинов И.Т.", "Усманов И.И."], ITEMS, content))["abstract"] == "The article considers it."


def test_reference_list_in_an_ol_is_whole():
    out = _parse(_page(["Шамшидинов И.Т.", "Усманов И.И."], ITEMS, RU_EN))
    assert out["references"] == [
        {"position": 1, "raw": "Беглов Б.М. Нетрадиционные методы. – Ташкент, 2009.", "doi": None},
        {"position": 2, "raw": "Shamshidinov I. Phosphorites // Chem. J. 2021. DOI: 10.1234/abc.5.", "doi": "10.1234/abc.5"}]
    assert out["references_complete"] is True
    assert out["acknowledgments"] is None and out["funding_statement"] is None


def test_numbered_paragraph_list_then_its_transliteration_is_whole():
    content = ('<h2>Abstract</h2><p>Text.</p><h2>Список литературы</h2><div><p>1. Бурлов В.Г. Управление.</p>'
               '<p>2. Вишняков Я.Д. Безопасность.</p></div><h2>References</h2><div><p>1. Burlov V.G. Management.</p>'
               '<p>2. Vishnyakov Ya.D. Safety.</p></div>')
    out = _parse(_page(["Шамшидинов И.Т.", "Усманов И.И."], ITEMS, content))
    assert [r["raw"] for r in out["references"]] == ["Бурлов В.Г. Управление.", "Вишняков Я.Д. Безопасность."]
    assert out["references_complete"] is True


def test_text_after_the_list_or_a_gap_is_not_whole():
    content = RU_EN + '<div><p>[1] Закон был описан в 1908 году.</p></div>'
    assert _parse(_page(["Шамшидинов И.Т.", "Усманов И.И."], ITEMS, content))["references_complete"] is False
    gap = '<p>Список литературы:</p><p>1. Один.</p><p>3. Три.</p>'
    assert _parse(_page(["Шамшидинов И.Т.", "Усманов И.И."], ITEMS, gap))["references_complete"] is False


def test_issue_contents_page_is_not_read():
    html = _page(["Шамшидинов И.Т.", "Усманов И.И."], ITEMS, RU_EN,
                 canonical="https://7universum.com/ru/tech/archive/category/4121")
    parser = Universum7(BeautifulSoup(html, "lxml"))
    assert not parser.authors_found()


def test_look_alike_page_of_another_site_is_not_claimed():
    # internauka.org (the same publisher's conference site) and any page without the canonical link
    for canonical in ("https://www.internauka.org/conf/economy/lxi-lxii/344399", ""):
        parser = Universum7(BeautifulSoup(_page(["Шамшидинов И.Т.", "Усманов И.И."], ITEMS, RU_EN, canonical), "lxml"))
        assert not parser.is_publisher_specific_parser()
        assert not parser.authors_found()
