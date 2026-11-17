"""Bauman Moscow State Technical University journals (BaumanPress, bmstu.ru, DOI prefix 10.18698), oxjob #2339.
Markup cut down from stored pages of the CMS's two layouts: the <header> one (Инженерный журнал) and the table.mini
one (Вестник МГТУ and the other journals)."""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.bmstu import Bmstu

URL = "https://doi.org/10.18698/2308-6033-2012-8-447"

HEADER = """<!DOCTYPE HTML><html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<title>Моделирование раскрытия солнечных батарей | Инженерный журнал: наука и инновации</title>
<link href="/css/style.css" rel="stylesheet" type="text/css"></head><body><section class="mainContent">
<section class="block article open"><h3>Моделирование раскрытия солнечных батарей</h3>
<header><div class="date"><strong>Опубликовано:</strong> 30.12.2012</div><p> <strong>Авторы:</strong>
<a href="/authors/771.html">Борзых&nbspС.В.</a>, <a href="/authors/777.html">Ильясова&nbspИ.Р.</a></p>
<p><b>Опубликовано в выпуске: </b><a href="/issues/8.html">#8(8)/2012</a></p>
<p><b>DOI: </b><a href='http://dx.doi.org/10.18698/2308-6033-2012-8-447'>10.18698/2308-6033-2012-8-447</a></p>
<p><strong>Раздел:</strong> <a href="/catalog/machin/">Машиностроение</a></p></header>
<section><p>Приведены результаты экспериментального и теоретического моделирования динамики раскрытия солнечных батарей
различных кинематических схем.</p>
<br /><b>Литература</b><br /><b>[1]</b> Докучаев Л.В. Нелинейная динамика летательных аппаратов. – М.: Машиностроение,
1987. – 261 с.<br /><b>[2]</b> Daniel J., Soucek P. On the effect of the substrate. Surface and Coatings Technology, 2017,
vol. 328, pp. 462–468. DOI: 10.1016/j.surfcoat.2017.06.076<br />
<script type="text/javascript" src="//yandex.st/share/share.js"></script><div class="yashare-auto-init"></div>
</section><nav class="tags"><ul><a href="/search/keyword/1780/page1.html">эксперимент</a></ul></nav></section>
</section><footer><span>Copyright ©BaumanPress 2012-2018.</span></footer></body></html>"""

TABLE = """<html><head><title>Vapor-liquid equilibrium study | Herald of the Bauman Moscow State Technical University.
Series Natural Sciences</title></head><body><div id="main"><div class="article">
<h1>Vapor-liquid equilibrium study in the alcohol binary solutions using the cluster model</h1>
<table class="mini" width="920px" border="0" cellspacing="0" cellpadding="0">
<tr><td><strong>Authors:</strong> <a href="/eng/authors/3001.html">Mitrofanov&nbspM.S.</a>, <a href="/eng/authors/3002.html">Ananyeva&nbspE.A.</a></td>
<td width="200px"><strong>Published:</strong> 14.02.2023 </td></tr>
<tr><td><strong>Published in issue: </strong><a href="/eng/issues/150.html">#1(106)/2023</a> </td><td>&nbsp;</td></tr>
<tr><td><p><b>DOI: </b><a href='http://dx.doi.org/10.18698/1812-3368-2023-1-161-172'>10.18698/1812-3368-2023-1-161-172</a></p> </td></tr>
</table>
<p><strong>Abstract</strong></p>
<p>The vapor-liquid equilibrium was analyzed for infinitely miscible binary solutions of alcohols on the basis of the
cluster model.</p>
<p>The research was carried out with the financial support of the Russian Science Foundation (RSF grant no. 17-71-10254)</p>
<p><strong>Please cite this article in English as:</strong></p>
<p>Mitrofanov M.S., Ananyeva E.A. Vapor-liquid equilibrium study. Herald of the BMSTU, 2023, no. 1, pp. 161--172.</p>
<h2><b>References</b></h2><p><b>[1]</b> Rudakov A.M. Molecular association in binary mixtures. Inzhenernaya fizika, 2007,
no. 2, pp. 32--35 (in Russ.).</p><p><b>[2]</b> Hornig G., Priest E.R. Evolution of magnetic flux. Phys. Plasmas, 2003, vol. 10,
pp. 2712--2721. DOI: <a href="https://doi.org/10.1063/1.1580120">https://doi.org/10.1063/1.1580120</a></p>
<p><b>[4]</b> Ohnhauser F. Analog-digital converters. Berlin, Springer-Verlag, 2015. 333 p.</p>
<div class="hr"><div class="sharebuttons"><a href="/articles/1078/1078.pdf">PDF</a></div></div>
</div></div></body></html>"""

# An issue's table of contents on the same CMS: one table.mini per listed article, no DOI in them.
ISSUE = """<html><head><title>Выпуск 3 | Вестник МГТУ им. Н.Э. Баумана. Серия Естественные науки</title></head><body>
<div class="main"><a class="artname" href="/catalog/math/diff/692.html">К вопросу о симметричности решений</a>
<table class="mini"><tr><td><strong>Авторы:</strong> <a href="/authors/44.html">Фетисов Д.А.</a></td></tr></table></div>
<div class="main"><a class="artname" href="/catalog/math/diff/693.html">О стабилизации аффинных систем</a>
<table class="mini"><tr><td><strong>Авторы:</strong> <a href="/authors/732.html">Кавинов А.В.</a></td></tr></table></div>
</body></html>"""

# Another site's page with the same "Authors:" label and an article about Zygmunt Bauman: not this CMS.
LOOKALIKE = """<html><head><title>Liquid modernity revisited: reading Bauman today | Journal of Social Theory</title>
<meta name="citation_title" content="Liquid modernity revisited"></head><body><div class="article">
<table class="mini"><tr><td><strong>Authors:</strong> <a href="/authors/12.html">Smith&nbspJ.</a></td></tr>
<tr><td><b>DOI: </b><a href="https://doi.org/10.1234/jst.2020.5">10.1234/jst.2020.5</a></td></tr></table>
<p>This paper revisits Zygmunt Bauman's notion of liquid modernity and asks what it explains about platform work.</p>
</div></body></html>"""


def _parser(html):
    return Bmstu(BeautifulSoup(html, parser="lxml", features="lxml"))


def test_header_layout_authors_and_abstract():
    out = parse_page(HEADER.encode(), "doi", URL)
    assert [a["name"] for a in out["authors"]] == ["Борзых С.В.", "Ильясова И.Р."]
    assert all(a["affiliations"] == [] and not a["is_corresponding"] for a in out["authors"])
    assert out["abstract"].startswith("Приведены результаты экспериментального")
    assert "Литература" not in out["abstract"]


def test_header_layout_references():
    out = _parser(HEADER).parse()
    refs = out["references"]
    assert [r["position"] for r in refs] == [1, 2]
    assert refs[0]["raw"].startswith("Докучаев Л.В.") and refs[0]["raw"].endswith("261 с.")
    assert refs[0]["doi"] is None
    assert refs[1]["doi"] == "10.1016/j.surfcoat.2017.06.076"
    assert out["references_complete"] is True


def test_table_layout_abstract_skips_label_funding_and_citation():
    out = parse_page(TABLE.encode(), "doi", "https://doi.org/10.18698/1812-3368-2023-1-161-172")
    assert [a["name"] for a in out["authors"]] == ["Mitrofanov M.S.", "Ananyeva E.A."]
    assert out["abstract"].startswith("The vapor-liquid equilibrium was analyzed")
    for not_abstract in ("Abstract", "financial support", "Please cite", "References"):
        assert not_abstract not in out["abstract"]


def test_table_layout_references_with_a_gap_are_not_complete():
    out = _parser(TABLE).parse()
    refs = out["references"]
    assert len(refs) == 3
    assert refs[1]["doi"] == "10.1063/1.1580120"
    assert refs[2]["raw"].startswith("Ohnhauser F.") and "PDF" not in refs[2]["raw"]
    assert out["references_complete"] is False  # [1], [2], [4]: a number is missing


def test_issue_table_of_contents_not_claimed():
    parser = _parser(ISSUE)
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_lookalike_from_another_site_not_claimed():
    parser = _parser(LOOKALIKE)
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
