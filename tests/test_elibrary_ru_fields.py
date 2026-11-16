"""eLIBRARY.RU item pages (elibrary.ru/item.asp?id=N), oxjob #2268.

Many Russian journals' DOIs resolve to their eLIBRARY.RU record. The page has no citation_* meta tags; it prints the
Russian byline as table markup (name in a dark-blue <font>, affiliation numbers in <sup>), numbered affiliation lines
under it, the abstract in div#abstract1 (cut, with the whole text in a hidden div#abstract2), an "ОПИСАНИЕ НА
АНГЛИЙСКОМ ЯЗЫКЕ" section with the English byline and abstract (div#eabstract1/2), and a funding label
("ИНФОРМАЦИЯ О ФИНАНСОВОЙ ПОДДЕРЖКЕ"). Markup cut down from stored pages (#2268 sample).
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.elibrary_ru import ELibraryRu

URL = "https://doi.org/10.54068/00394580_2021_5_48"

RU_ABS = ("О комплексе исследований по определению технической готовности корабля, новой методике планирования и "
          "учета трудоемкости, работоспособной системе обмена информацией в реальном масштабе времени.")
EN_ABS = ("The authors hereby describe a battery of studies related to determination of ship's technical readiness, "
          "new labour planning and accounting method, operable real-time data exchange system on product's "
          "technical readiness between engaged parties.")


def _author(name, sups="1", tooltip=True, star=""):
    sup = f"<font color=#000000><sup>{sups}</sup></font>" if sups else ""
    inner = f"<b><font color=#00008f>{name}</font></b>"
    if star:
        sup = f"<span class='astmd help' title='{star}'>*</span>" + sup
    if tooltip:
        inner = f"<span class='help pointer' title='<b>{name}</b><br>Профиль автора'>{inner}</span>"
    return f"<div style='display: inline-block; white-space: nowrap'>{inner}{sup},</div> "


def _aff(num, name, tail=""):
    return (f"<font color=#000000><sup>{num}</sup></font>&nbsp;<span class='help1 pointer' title='<b>{name} full</b>'>"
            f"<font color=#00008f>{name}</font></span>{tail}<br>")


def _section(label, body):
    return (f"<table width=550 border=0 cellspacing=0 cellpadding=3><tr><td colspan=2 align=left>"
            f"<font color=#000000>{label}:</font></td></tr><tr><td width=34>&nbsp;</td>"
            f"<td width=504 align=left valign=middle>{body}</td></tr></table>")


def _page(authors="", affs="", abstracts="", english="", funding="", logo=True, header="ИНФОРМАЦИЯ О ПУБЛИКАЦИИ"):
    logo_img = ('<img id="elibrary_logo" src="/images/elibrary_logo2.svg" width=150 height=39 border=0 '
                'title="eLIBRARY.RU - НАУЧНАЯ ЭЛЕКТРОННАЯ БИБЛИОТЕКА">') if logo else ""
    return f"""<!DOCTYPE html><html><head>
<meta name="description" content='{RU_ABS}'>
<title>Об определении технической готовности строящихся кораблей</title>
<meta property="og:image" content="https://elibrary.ru/images/elibrary_fb.png">
<meta name="doi" content="10.54068/00394580_2021_5_48">
</head><body><table><tr><td id="leftcol"><a href="/defaultx.asp">{logo_img}</a></td><td>
<div class="header-panel"><div><font color=#5674b9><b>{header}</b></font></div></div>
<table width=550><tr><td>eLIBRARY ID:&nbsp;<font color=#00008f><a href="item.asp?id=46714716">46714716</a></font></td></tr></table>
<table width=550><tr align=center valign=middle><td width=4></td><td width=534><span><b>
<p class='bigtext' style='color: #F26C4F;'>ОБ ОПРЕДЕЛЕНИИ ТЕХНИЧЕСКОЙ ГОТОВНОСТИ СТРОЯЩИХСЯ КОРАБЛЕЙ</p></b></span></td></tr>
</table>
<div style="width:580px;"><div style="height:10px;"></div>
<table width=550 border=0 cellspacing=0 cellpadding=3><tr><td width=24></td>
<td width=514 valign=middle align=center>
{authors}
<div style="height:10px;"></div>
{affs}
</td></tr></table>
<table width=580><tr><td width=574 align=center>Тип:&nbsp;<font color=#00008f>статья в журнале - научная статья</font></td></tr></table>
{abstracts}
{funding}
{english}
</div></td></tr></table></body></html>"""


def _abstracts(text, full=None):
    out = _section("АННОТАЦИЯ", f'<div id="abstract1" style="width:504px;"><p align=justify>{text}</div>'
                   + (f'<div id="abstract2" style="width:504px; display:none;"><p align=justify>{full}</div>' if full else ""))
    return out


def _english(abstract1, abstract2=None, label="ОПИСАНИЕ НА АНГЛИЙСКОМ ЯЗЫКЕ"):
    byline = ("<div style='display: inline-block; white-space: nowrap'><font color=#00008f>POTRYAKHAYEV V.V.</font>"
              "<font color=#000000><sup>1</sup></font></div><br><font color=#000000><sup>1</sup></font>&nbsp;"
              "<span class='help1 pointer'><font color=#00008f>JSC SSTC</font></span><br>")
    body = f'<div id="eabstract1" style="width:504px;"><p align=justify>{abstract1}</div>'
    if abstract2:
        body += f'<div id="eabstract2" style="width:504px; display:none;"><p align=justify>{abstract2}</div>'
    return (f"<table width=550><tr><td colspan=2 align=left><font color=#000000>{label}:</font></td></tr>"
            f"<tr><td width=34>&nbsp;</td><td width=504 align=center valign=middle>{byline}</td></tr>"
            f"<tr><td width=34>&nbsp;</td><td width=504 align=left valign=middle>{body}</td></tr></table>")


def _out(html):
    return parse_page(html.encode(), "doi", URL)


def _raw(html):
    return ELibraryRu(BeautifulSoup(html, "lxml")).parse()


def _affs(out):
    return [[a["name"] for a in au["affiliations"]] for au in out["authors"]]


def test_byline_names_and_numbered_affiliations():
    html = _page(_author("ПОТРЯХАЕВ В.В.") + _author("ГРЕЧАНЮК&nbsp;А.Н.", tooltip=False), _aff(1, "АО «ЦТСС»"),
                 _abstracts(RU_ABS), _english(EN_ABS))
    out = _out(html)
    assert [a["name"] for a in out["authors"]] == ["ПОТРЯХАЕВ В.В.", "ГРЕЧАНЮК А.Н."]  # Russian byline, not English
    assert _affs(out) == [["АО «ЦТСС»"], ["АО «ЦТСС»"]]
    assert not any(a["is_corresponding"] for a in out["authors"])


def test_affiliation_line_keeps_its_place_after_the_name():
    html = _page(_author("ЯРЛЫЧЕНКО АЛЛА АЛЕКСАНДРОВНА"),
                 "<font color=#000000><sup>1</sup></font>&nbsp;<font color=#00008f>Приволжский филиал ПАО "
                 "«Промсвязьбанк»</font>, г. Казань, Россия<br>", _abstracts(RU_ABS))
    assert _affs(_out(html)) == [["Приволжский филиал ПАО «Промсвязьбанк», г. Казань, Россия"]]


def test_several_numbers_and_an_author_with_none():
    html = _page(_author("ЛОГИНОВ Д.А.", sups="") + _author("ГЛАВАТСКИХ А.Ю.", sups="1,2") + _author("ИВАНОВ И.И.", sups="2"),
                 _aff(1, "Вятский государственный университет") + _aff(2, "Институт философии РАН", ", Москва"),
                 _abstracts(RU_ABS))
    assert _affs(_out(html)) == [[], ["Вятский государственный университет", "Институт философии РАН, Москва"],
                                 ["Институт философии РАН, Москва"]]


def test_asterisk_explained_as_correspondence_marks_the_author():
    html = _page(_author("РОЗЕНФЕЛЬД С. Б.") + _author("ШЕРЕМЕТЬЕВ И. С.", star="Автор, отвечающий за переписку")
                 + _author("БАРАНЮК В. В."), _aff(1, "Институт проблем экологии и эволюции им. А.Н. Северцова РАН"),
                 _abstracts(RU_ABS))
    out = _out(html)
    assert [a["name"] for a in out["authors"] if a["is_corresponding"]] == ["ШЕРЕМЕТЬЕВ И. С."]
    assert out["authors"][1]["name"] == "ШЕРЕМЕТЬЕВ И. С."  # the asterisk is not part of the name


def test_asterisk_with_another_meaning_marks_no_one():
    html = _page(_author("РОЗЕНФЕЛЬД С. Б.", star="Автор умер") + _author("БАРАНЮК В. В."), _aff(1, "МГУ"),
                 _abstracts(RU_ABS))
    assert not any(a["is_corresponding"] for a in _out(html)["authors"])


def test_english_abstract_is_preferred():
    html = _page(_author("ПОТРЯХАЕВ В.В."), _aff(1, "АО «ЦТСС»"), _abstracts(RU_ABS), _english(EN_ABS))
    assert _out(html)["abstract"] == EN_ABS


def test_whole_abstract_over_its_cut_preview():
    cut, whole = EN_ABS[:80] + "...", EN_ABS + " A second sentence closes the whole abstract here."
    html = _page(_author("ПОТРЯХАЕВ В.В."), _aff(1, "АО «ЦТСС»"), _abstracts(RU_ABS[:60] + "...", RU_ABS),
                 _english(cut, whole))
    assert _out(html)["abstract"] == whole


def test_russian_abstract_when_no_english_one():
    html = _page(_author("ПОТРЯХАЕВ В.В."), _aff(1, "АО «ЦТСС»"), _abstracts(RU_ABS))
    assert _out(html)["abstract"] == RU_ABS


def test_main_abstract_in_english_beats_a_russian_other_language_one():
    html = _page(_author("OSIPOV D.V."), _aff(1, "Kazan State Medical University"), _abstracts(EN_ABS),
                 _english(RU_ABS, label="ОПИСАНИЕ НА ДРУГОМ ЯЗЫКЕ"))
    assert _out(html)["abstract"] == EN_ABS


def test_funding_statement_under_its_label():
    text = "Исследование выполнено за счет гранта Российского научного фонда № 22-18-00421"
    raw = _raw(_page(_author("ВЕРЕМЕНКО В.А."), _aff(1, "ЛГУ им. А. С. Пушкина"), _abstracts(RU_ABS),
                     funding=_section("ИНФОРМАЦИЯ О ФИНАНСОВОЙ ПОДДЕРЖКЕ", f'<div style="height:3px;"></div><p>{text}')))
    assert raw["funding_statement"] == text
    assert raw["acknowledgments"] is None
    assert raw["references"] is None and raw["references_complete"] is False


def test_no_funding_label_no_funding_statement():
    raw = _raw(_page(_author("ПОТРЯХАЕВ В.В."), _aff(1, "АО «ЦТСС»"), _abstracts(RU_ABS)))
    assert raw["funding_statement"] is None


def test_not_an_item_page_is_not_claimed():
    # an eLIBRARY issue page: same logo and item links, no publication-information header
    html = _page(_author("ПОТРЯХАЕВ В.В."), _aff(1, "АО «ЦТСС»"), _abstracts(RU_ABS), header="СОДЕРЖАНИЕ ВЫПУСКА")
    parser = ELibraryRu(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser() and not parser.authors_found()


def test_journal_page_linking_to_elibrary_is_not_claimed():
    # a journal's own article page (the nearest look-alike: OJS with an eLIBRARY badge and the same byline style)
    html = ("<html><head><meta name='citation_author' content='Ivanov, Ivan'><meta name='citation_title' content='T'>"
            "</head><body><a href='https://elibrary.ru/title_about.asp?id=8239'><img src='https://elibrary.ru/images/"
            "elibrary_logo2.svg' alt='eLIBRARY.RU'></a><p class='bigtext'>T</p><table><tr><td width=514>"
            + _author("ИВАНОВ И.И.") + _aff(1, "МГУ") + "</td></tr></table></body></html>")
    parser = ELibraryRu(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser() and not parser.authors_found()
    assert "МГУ" not in [aff for affs in _affs(_out(html)) for aff in affs]
