"""Media Sphera (mediasphera.ru) article pages (oxjob #2338).

Markup is cut down from stored mediasphera.ru pages (Russian medical journals on a 1C-Bitrix site, template
"MediaSphera"). Most pages carry no citation_* meta tags, so no parser read their byline: each author's name and
affiliations sit in the byline pop-up (div.author__list-item), an ORCID / SPIN list beside them. The reference list is
one <ol> under "Список литературы:" / "References:".
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.mediasphera import MediaSphera

URL = "https://doi.org/10.17116/hirurgia202207133"
HEAD = ('<head><meta charset="utf-8"><link rel="icon" href="/local/templates/MediaSphera/favicon.ico" '
        'type="image/vnd.microsoft.icon"><title>Мобилизация селезеночного изгиба</title>{meta}</head>')


def _item(name, aff_html, ids=""):
    return (f'<div class="author__list-item"><div class="author__list-item-name"><p>{name}</p></div>'
            f'<div class="author__list-item-info"><p>{aff_html}</p></div>'
            f'<div class="author__list-item-info" style="margin-top: 2rem;"><ul>{ids}</ul></div></div>')


def _page(items, bibliography="", meta="", head=HEAD):
    return ("<!DOCTYPE html><html lang=\"ru\">" + head.format(meta=meta) + "<body>"
            '<section class="articlePage-main"><div class="container"><div class="articlePage-main-block">'
            '<div class="articlePage-main-block-author__list">' + "".join(items) + "</div>"
            '<div class="articlePage-main-block-info"><div class="name"><p>Мобилизация селезеночного изгиба</p></div>'
            "</div></div></div></section>"
            '<section class="articlePage-metadoc"><div class="container"><div class="articlePage-metadoc-bottom">'
            '<div class="text"><p>Оценка безопасности и эффективности.</p></div>' + bibliography +
            "</div></div></section></body></html>")


RU_ITEMS = [
    _item("Половинкин&nbsp;В.В.", "ГБУЗ «НИИ — Краевая клиническая больница №1&nbsp;им.&nbsp;проф. С.В.&nbsp;Очаповского»"),
    _item("Домрачев&nbsp;С.А.", "ГБУЗ Москвы «Московский клинический научный центр им.&nbsp;А.С.&nbsp;Логинова»;<br/>"
          "ФГБОУ ВО&nbsp;«Московский государственный медико-стоматологический университет»",
          ids='<li>ORCID: <span><a href="https://orcid.org/0000-0002-7169-2724">0000-0002-7169-2724</a></span></li>'),
    _item("Адамян Л.В.", "ФГБУ «НМИЦ акушерства им. акад. В.И. Кулакова» Минздрава России; "
          "Академия женского здоровья и эндоскопической хирургии"),
]


def _bibliography(items, title="Список литературы:", ol_attrs=""):
    lis = "".join(f'<li style="margin-top: 20px;">\t{i}</li>' for i in items)
    return (f'<div class="bibliography"><div class="title"><p>{title}</p></div>'
            f"<ol{ol_attrs}>{lis}</ol></div>")


REFS = [
    "Александров В.Б.&nbsp;Рак&nbsp;прямой кишки. М.: Вузовская книга; 2001. "
    '<a target="_blank" href=" "> </a>',
    "Araujo SE, Seid VE.&nbsp;Assessing the&nbsp;extent of&nbsp;colon lengthening. Arquivos de&nbsp;Gastroenterologia. "
    '2012;49(3):219-222.&nbsp;<a target="_blank" href=" https://doi.org/10.1590/s0004-28032012000300010 "> '
    "https://doi.org/10.1590/s0004-28032012000300010</a>",
    "Иванов А.С. <em>Руководство по лазертерапии.</em> СПб. 2000.",
]


def _parsed(html):
    return parse_page(html.encode(), "doi", URL)


def _raw(html):
    return MediaSphera(BeautifulSoup(html, "lxml")).parse()


def test_byline_names_and_affiliations():
    authors = _parsed(_page(RU_ITEMS))["authors"]
    assert [a["name"] for a in authors] == ["Половинкин В.В.", "Домрачев С.А.", "Адамян Л.В."]
    assert authors[0]["affiliations"] == [{"name": "ГБУЗ «НИИ — Краевая клиническая больница №1 им. проф. С.В. Очаповского»"}]


def test_affiliations_split_one_string_each():
    authors = _parsed(_page(RU_ITEMS))["authors"]
    assert [x["name"] for x in authors[1]["affiliations"]] == [
        "ГБУЗ Москвы «Московский клинический научный центр им. А.С. Логинова»",
        "ФГБОУ ВО «Московский государственный медико-стоматологический университет»"]
    assert [x["name"] for x in authors[2]["affiliations"]] == [
        "ФГБУ «НМИЦ акушерства им. акад. В.И. Кулакова» Минздрава России",
        "Академия женского здоровья и эндоскопической хирургии"]


def test_orcid_list_is_not_an_affiliation():
    authors = _parsed(_page(RU_ITEMS))["authors"]
    assert all("ORCID" not in x["name"] for a in authors for x in a["affiliations"])


def test_no_corresponding_mark():
    # the generic "Связаться с автором" (contact the author) button is tied to no author
    assert not any(a["is_corresponding"] for a in _parsed(_page(RU_ITEMS))["authors"])


def test_byline_beats_citation_meta_tags():
    # English pages carry citation_author tags with an institution on the first author only; the byline gives all four
    meta = ('<meta name="citation_author" content="Pavlova I.E."/>'
            '<meta name="citation_author_institution" content="RosNIIGT FMBA of Russia"/>'
            '<meta name="citation_author" content="Bubnova L.N."/>')
    items = [_item("Pavlova I.E.", "RosNIIGT FMBA of Russia"), _item("Bubnova L.N.", "RosNIIGT FMBA of Russia")]
    authors = _parsed(_page(items, meta=meta))["authors"]
    assert [(a["name"], [x["name"] for x in a["affiliations"]]) for a in authors] == [
        ("Pavlova I.E.", ["RosNIIGT FMBA of Russia"]), ("Bubnova L.N.", ["RosNIIGT FMBA of Russia"])]


def test_reference_list_whole():
    out = _raw(_page(RU_ITEMS, _bibliography(REFS)))
    refs = out["references"]
    assert [r["position"] for r in refs] == [1, 2, 3]
    assert refs[0] == {"position": 1, "raw": "Александров В.Б. Рак прямой кишки. М.: Вузовская книга; 2001.", "doi": None}
    assert refs[1]["doi"] == "10.1590/s0004-28032012000300010"
    assert refs[1]["raw"].startswith("Araujo SE, Seid VE. Assessing the extent of colon lengthening.")
    assert refs[2]["raw"] == "Иванов А.С. Руководство по лазертерапии. СПб. 2000."
    assert out["references_complete"] is True


def test_reference_list_with_start_is_not_whole():
    out = _raw(_page(RU_ITEMS, _bibliography(REFS, ol_attrs=' start="4"')))
    assert len(out["references"]) == 3 and out["references_complete"] is False


def test_empty_reference_list():
    out = _raw(_page(RU_ITEMS, _bibliography([])))
    assert out["references"] is None and out["references_complete"] is False


def test_no_acknowledgments_or_funding():
    out = _raw(_page(RU_ITEMS, _bibliography(REFS)))
    assert out["acknowledgments"] is None and out["funding_statement"] is None


def test_lookalike_bitrix_page_not_claimed():
    # another 1C-Bitrix site with the same byline class names but not the MediaSphera template
    head = HEAD.replace("/local/templates/MediaSphera/", "/local/templates/main/")
    html = _page(RU_ITEMS, _bibliography(REFS), head=head)
    parser = MediaSphera(BeautifulSoup(html, "lxml"))
    assert not parser.authors_found() and not parser.is_publisher_specific_parser()
    assert _parsed(html)["authors"] == []


def test_empty_shell_page_not_read():
    # about half the stored pages are an empty "Просмотр статьи" shell with no template mark and no byline
    html = ('<html><head><title>Просмотр статьи</title></head><body><div><div></div></div>'
            '<script src="/bitrix/js/main/core/core.js"></script></body></html>')
    parser = MediaSphera(BeautifulSoup(html, "lxml"))
    assert not parser.authors_found()
