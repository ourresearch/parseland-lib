"""Bionika Media journal pages (DOI prefix 10.18565): lib.medvestnik.ru, aig-journal.ru and the older journal sites
(oxjob #2339). Markup cut down from stored pages of the three layouts the parser reads."""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.medvestnik import Medvestnik

WS = ('<meta name="ws" content="{&quot;app&quot;:&quot;lib&quot;,&quot;url&quot;:{&quot;websocket&quot;:'
      '&quot;wss:\\/\\/sock.bionika-digital.ru\\/connection\\/websocket&quot;}}">')
WS_AIG = ('<meta name="ws" content="{&quot;app&quot;:&quot;aig&quot;,&quot;url&quot;:'
          '&quot;https:\\/\\/sock.bionika-digital.ru\\/connection\\/sockjs&quot;}">')
OLD_HEAD = "<script>head.js('https://services.bionika-digital.ru/uid/lib.js', '/includes/b2a9473a.js');</script>"

LIB = f"""<html><head>{WS}<meta property="og:url" content="https://lib.medvestnik.ru/articles/x.html"></head><body>
<div class="article"><div class="header"><h1 class="ui header title">Псиллиум как метаболический корректор</h1></div>
<div class="c-basic-content-tracker"><div class="content"><div class="blocks-vertical text preview">
<p class="base">1) Омский государственный медицинский университет, Омск, Россия;<br />
2) Майкопский государственный медицинский университет, Майкоп, Россия</p>
<div class="c-typography-lead"><p>Цель обзора: оценить данные об эффективности псиллиума при ожирении и сахарном диабете
2 типа.<br />Материалы и методы: нарративный несистематический обзор с использованием источников PubMed и PMC.<br />
Заключение: псиллиум снижает гликемию натощак.</p>
<p>Для цитирования: Друк И.В., Нагоева З.М. Псиллиум. Фарматека. 2025;32(8):18-25.</p>
<p>Вклад авторов: Концепция – И.В. Друк.<br />Конфликт интересов: Авторы декларируют отсутствие конфликтов.<br />
Финансирование: Работа выполнена без спонсорской поддержки.</p></div>
<div class="c-typography-text"><h3>Введение</h3><p>Ожирение – хроническое заболевание...</p></div></div>
<div class="doi"><span class="title">DOI: </span><a href="https://dx.doi.org/10.18565/pharmateca.2025.8.18-25">x</a></div>
<div class="authors"><span class="author">Друк И.В.</span>, <span class="author">Нагоева З.М.</span></div></div></div>
</div></body></html>"""

AIG = f"""<html><head>{WS_AIG}</head><body><div id="main-content" class="ui segment">
<h1 class="ui header page">Редкий случай артериовенозной мальформации матки</h1><div class="article-wrapper">
<div class="ui segment secondary compact"><a class="ui" href="https://dx.doi.org/10.18565/aig.2021.12.182-186">doi</a></div>
<blockquote><div class="quote"><h3 class="ui header">Сыркашев Е.М., Акинфиев Д.М., Быченко\xa0В.Г.</h3></div>
<div class="author">ФГБУ «НМИЦ акушерства, гинекологии и перинатологии им. В.И. Кулакова» Минздрава России, Москва, Россия</div>
</blockquote>Актуальность: Артерио-венозная мальформация матки – достаточно редкое заболевание у женщин.<br/>
Описание: Пациентка С., 1971 г.р., поступила для органосберегающего лечения АВМ сосудов матки.<br/>
Заключение: ЭМА является приоритетным методом лечения АВМ матки.<h2 class="ui header">Ключевые слова</h2>
<div class="ui label">АВМ</div><h2 class="ui header">Список литературы</h2><div class="italic"><div><ol>
<li>Peitsidis P. Uterine arteriovenous malformations. Arch. Gynecol. Obstet. 2011; 284(5): 1137-51. https://dx.doi.org/10.1007/s00404-011-2067-7.</li>
<li>Леваков С.А. Опыт эмболизации маточных артерий. Клиническая практика. 2010; 3(3): 103-10.</li>
</ol><p>Поступила 08.07.2021</p></div></div><h2 class="ui header">Об авторах / Для корреспонденции</h2>
Сыркашев Егор Михайлович, НМИЦ АГиП, <a href="mailto:e@x.ru">e@x.ru</a>.<br/>
Финансирование: Исследование проведено без финансовой поддержки.<br/></div></div></body></html>"""

OLD = f"""<html><head><title>Терапия » Острое почечное повреждение</title>{OLD_HEAD}</head><body>
<div id="page-archive-article" class="page-identifier"><h3 class="compact">Острое почечное повреждение</h3><br/>
<p>DOI: <a href="https://dx.doi.org/10.18565/therapy.2022.9.44-52">https://dx.doi.org/10.18565/therapy.2022.9.44-52</a></p>
<blockquote><p>Р.М. Мамина (1, 2), Б.И. Кантемирова (1), В.В. Белопасов (2)</p>
<small>1) ФГБОУ ВО «Астраханский государственный медицинский университет», Астрахань;
2) ГБУЗ АО «Городская поликлиника № 3», Астрахань</small></blockquote>
<div class="well">Аннотация. В экспериментах установлено, что клетки врожденного иммунитета участвуют в развитии острого
почечного повреждения.<br/>Цель – оценка особенностей макрофагального состава в тканях почек.</div>
<div class="well">Ключевые слова: макрофаги, воспаление</div>
<h3>Литература</h3><hr class='no-top'><p><em><div><p>1. Wang C., Pei Y.Y. Risk factors for acute kidney injury. Chin Med J. 2019; 132(14): 1660–65. https://dx.doi.org/10.1097/CM9.0000000000000293.</p><br />
<p>2. Межонов Е. М. Прогностическое значение острого кардиоренального синдрома. Кардиология. 2019; 59(8S): 44–55.</p></div></em></p>
<br /><h3>Об авторах / Для корреспонденции</h3><hr class='no-top'><p><em><p>А в т о р  д л я  с в я з и: Б. И. Кантемирова – д.м.н.,
профессор; e-mail: b@mail.ru</p></em></p><h3>Похожие статьи</h3></div></body></html>"""


def _soup(html):
    return BeautifulSoup(html, "lxml")


def test_lib_byline_unlinked_affiliations_and_abstract():
    out = parse_page(LIB.encode(), "doi", "https://lib.medvestnik.ru/articles/x.html")
    assert [a["name"] for a in out["authors"]] == ["Друк И.В.", "Нагоева З.М."]
    affs = [x["name"] for x in out["authors"][1]["affiliations"]]
    assert affs == ["Омский государственный медицинский университет, Омск, Россия",
                    "Майкопский государственный медицинский университет, Майкоп, Россия"]
    assert out["abstract"].startswith("Цель обзора: оценить")
    assert out["abstract"].endswith("снижает гликемию натощак.")
    assert "Для цитирования" not in out["abstract"]
    assert not any(a["is_corresponding"] for a in out["authors"])


def test_lib_funding_statement():
    parsed = Medvestnik(_soup(LIB)).parse()
    assert parsed["funding_statement"] == "Работа выполнена без спонсорской поддержки."
    assert parsed["references"] is None and parsed["references_complete"] is False


def test_lib_layout_needs_the_library_app():
    news = LIB.replace("&quot;lib&quot;", "&quot;mv&quot;")
    assert not Medvestnik(_soup(news)).is_publisher_specific_parser()


def test_journal_app_byline_abstract_and_ordered_references():
    out = parse_page(AIG.encode(), "doi", "https://aig-journal.ru/articles/x.html")
    assert [a["name"] for a in out["authors"]] == ["Сыркашев Е.М.", "Акинфиев Д.М.", "Быченко В.Г."]
    assert all(len(a["affiliations"]) == 1 for a in out["authors"])
    assert out["abstract"].startswith("Актуальность: Артерио-венозная")
    assert out["abstract"].endswith("методом лечения АВМ матки.")
    parsed = Medvestnik(_soup(AIG)).parse()
    assert [r["position"] for r in parsed["references"]] == [1, 2]
    assert parsed["references"][0]["doi"] == "10.1007/s00404-011-2067-7"
    assert parsed["references"][1]["doi"] is None
    assert parsed["references_complete"] is True
    assert parsed["funding_statement"] == "Исследование проведено без финансовой поддержки."
    assert not any(a["is_corresponding"] for a in parsed["authors"])  # the "Для корреспонденции" heading is no mark


def test_journal_app_affiliation_list_where_the_abstract_goes_is_not_an_abstract():
    page = AIG.replace("Актуальность: Артерио-венозная мальформация матки – достаточно редкое заболевание у женщин.",
                       "1) Academician V.I. Kulakov National Medical Research Center for Obstetrics, Moscow;")
    page = page.replace("Описание:", "2) The Far Eastern State Medical University. Описание:")
    assert Medvestnik(_soup(page)).parse()["abstract"] is None


def test_archive_numbered_byline_links_affiliations():
    out = parse_page(OLD.encode(), "doi", "https://doi.org/10.18565/therapy.2022.9.44-52")
    assert [a["name"] for a in out["authors"]] == ["Р.М. Мамина", "Б.И. Кантемирова", "В.В. Белопасов"]
    affs = [[x["name"] for x in a["affiliations"]] for a in out["authors"]]
    assert affs[0] == ["ФГБОУ ВО «Астраханский государственный медицинский университет», Астрахань",
                       "ГБУЗ АО «Городская поликлиника № 3», Астрахань"]
    assert affs[1] == ["ФГБОУ ВО «Астраханский государственный медицинский университет», Астрахань"]
    assert affs[2] == ["ГБУЗ АО «Городская поликлиника № 3», Астрахань"]


def test_archive_abstract_without_its_label_and_keywords():
    out = parse_page(OLD.encode(), "doi", "https://doi.org/10.18565/therapy.2022.9.44-52")
    assert out["abstract"].startswith("В экспериментах установлено")
    assert "Ключевые слова" not in out["abstract"]


def test_archive_contact_author_is_corresponding():
    out = parse_page(OLD.encode(), "doi", "https://doi.org/10.18565/therapy.2022.9.44-52")
    assert [a["name"] for a in out["authors"] if a["is_corresponding"]] == ["Б.И. Кантемирова"]


def test_archive_numbered_paragraph_references_are_whole():
    parsed = Medvestnik(_soup(OLD)).parse()
    assert [r["raw"][:10] for r in parsed["references"]] == ["Wang C., P", "Межонов Е."]
    assert parsed["references"][0]["doi"] == "10.1097/CM9.0000000000000293"
    assert parsed["references_complete"] is True


def test_archive_gap_in_numbering_is_not_whole():
    page = OLD.replace("<p>2. Межонов", "<p>3. Межонов")
    assert Medvestnik(_soup(page)).parse()["references_complete"] is False


def test_lookalike_without_the_platform_mark_is_not_claimed():
    # Same byline markup, no bionika-digital.ru in <head>: another site's page.
    for page in (LIB.replace("bionika-digital.ru", "example.org"), AIG.replace("bionika-digital.ru", "example.org"),
                 OLD.replace("bionika-digital.ru", "example.org")):
        parser = Medvestnik(_soup(page))
        assert not parser.is_publisher_specific_parser()
        assert not parser.authors_found()


def test_journal_app_page_without_a_doi_ribbon_is_not_claimed():
    page = AIG.replace("https://dx.doi.org/10.18565/aig.2021.12.182-186", "/news/1")
    page = page.replace("https://dx.doi.org/10.1007/s00404-011-2067-7", "")
    assert not Medvestnik(_soup(page)).is_publisher_specific_parser()


def test_archive_citation_line_in_the_abstract_block_is_cut():
    page = OLD.replace("в тканях почек.</div>", "в тканях почек.<br/><p>Для цитирования: Мамина Р.М. Терапия. "
                       "2022; 9: 44-52. DOI: https://dx.doi.org/10.18565/therapy.2022.9.44-52</p></div>")
    out = Medvestnik(_soup(page)).parse()
    assert out["abstract"].endswith("в тканях почек.")


def test_affiliations_numbered_on_one_line_and_broken_before_the_city():
    one_line = OLD.replace("""<small>1) ФГБОУ ВО «Астраханский государственный медицинский университет», Астрахань;
2) ГБУЗ АО «Городская поликлиника № 3», Астрахань</small>""", "<small>1 ФГБОУ ВО АГМУ, Барнаул, Россия; 2 ФГБУ «НМИЦ "
                       "гематологии», Барнаул, Россия</small>")
    authors = Medvestnik(_soup(one_line)).parse()["authors"]
    assert authors[0]["affiliations"] == ["ФГБОУ ВО АГМУ, Барнаул, Россия", "ФГБУ «НМИЦ гематологии», Барнаул, Россия"]
    broken = AIG.replace("Минздрава России, Москва, Россия</div>", "Минздрава России, \r\nг. Москва, Россия</div>")
    authors = Medvestnik(_soup(broken)).parse()["authors"]
    assert authors[0]["affiliations"][0].endswith("Минздрава России, г. Москва, Россия")
