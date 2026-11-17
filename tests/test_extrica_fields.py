"""Extrica (JVE International: Journal of Vibroengineering and its sister titles) article pages (oxjob #2339).

Markup is cut down from stored extrica.com pages (17 Nov 2026). The site prints two templates, and on both the
citation_author tags give the byline in page order but no correspondence flag:
  - the older one: <h2 class="my-4"> with <strong>name</strong><sup>n</sup>, then <p class="mb-0"> lines
    "<sup>1, 2</sup>affiliation" and "<sup>2</sup>Corresponding author" (the number is the author's place);
  - the current one: div.single-author bylines and a div.corresponding-author block naming one author
    ("Corresponding Author:") or several ("Corresponding Authors: A, B").
The generic parser read no mark on the older template and only a single name on the current one.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.extrica import Extrica

URL = "https://www.extrica.com/article/19253"


def _head(names, publisher="JVE International Ltd.", og="https://www.extrica.com/article/19253"):
    metas = "".join(f'<meta name="citation_author" content="{n}">' for n in names)
    og_tag = f'<meta property="og:url" content="{og}">' if og else ""
    pub_tag = f'<meta name="citation_publisher" content="{publisher}">' if publisher else ""
    return (f'<head><meta charset="utf-8" />{og_tag}<meta name="citation_title" content="A title">{metas}'
            f'{pub_tag}<meta name="citation_doi" content="10.21595/jme.2017.19253">'
            '<meta name="citation_abstract" content="An analytical model based on energy balance is built to study '
            'high velocity impacts on woven Kevlar composite laminates by a cylindrical projectile."></head>')


OLD_META = ["Fangyu, Chen", "Li, Zhou", "Yihao, Tang", "Xiaoming, Zhou"]
OLD_BYLINE = ["Chen Fangyu", "Zhou Li", "Tang Yihao", "Zhou Xiaoming"]


def _old_page(corr_line='<p class="mb-0"><sup>2</sup>Corresponding author</p>', names=OLD_META, byline=OLD_BYLINE,
              **head):
    strongs = '<span>, </span>'.join(f"<strong>{n}</strong><sup>{i + 1}</sup>" for i, n in enumerate(byline))
    return (f"<html>{_head(names, **head)}<body><div class=\"journal-header\"><div class=\"container\">"
            f'<h1>An analytical modeling</h1><h2 class="my-4" style="font-size:medium">{strongs}</h2>'
            '<p class="mb-0"><sup>1, 2</sup>State Key Laboratory of Mechanics, Nanjing, China</p>'
            '<p class="mb-0"><sup>3, 4</sup>China Helicopter Research and Development Institute, Jingdezhen, China</p>'
            f"{corr_line}</div></div></body></html>")


NEW_META = ["Du, Qingsong", "Xu, Anhua", "Li, Guoyu"]
NEW_BYLINE = ["Qingsong Du", "Anhua Xu", "Guoyu Li"]
ORCID = ('<a href="https://orcid.org/0000-0003-3652-3957" title="ORCID page" target="_blank" rel="nofollow">'
         '<i class="fab fa-orcid"></i></a>')


def _new_page(label="Corresponding Authors:", value=f"Qingsong Du {ORCID}, Anhua Xu", names=NEW_META, **head):
    authors = "".join(f'<div class="single-author">{n}<sup>{i + 1}</sup>{ORCID if i == 0 else ""}</div>'
                      for i, n in enumerate(NEW_BYLINE))
    corr = (f'<div class="corresponding-author"><div class="label">{label}</div><div class="value">{value}</div></div>'
            if label else "")
    return (f"<html>{_head(names, **head)}<body><div class=\"title\"><h1>Ground deformation</h1></div>"
            f'<div class="list"><div class="list-title">{authors}</div><div class="list-content expanded">'
            '<div class="list-item"><sup>1, 2</sup>Qinghai Polytechnic University, Xining, China</div>'
            '<div class="list-item"><sup>3</sup>Chinese Academy of Sciences, Lanzhou, China</div>'
            f'{corr}</div></div><section class="about-section"><div class="about-row bordered"><div class="row-content">'
            '<div class="title">DOI</div><div class="content">https://doi.org/10.21595/jve.2026.26179</div></div></div>'
            "</section></body></html>")


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _corr(html):
    return [a["name"] for a in _parse(html)["authors"] if a["is_corresponding"]]


def _extrica(html):
    return Extrica(BeautifulSoup(html, parser="lxml", features="lxml"))


def test_older_template_numbered_corresponding_line():
    out = _parse(_old_page())
    assert [a["name"] for a in out["authors"]] == OLD_META  # the tags' names, as the generic parser reads them
    assert [a["is_corresponding"] for a in out["authors"]] == [False, True, False, False]


def test_older_template_corresponding_line_naming_two():
    assert _corr(_old_page('<p class="mb-0"><sup>1, 3</sup>Corresponding author</p>')) == ["Fangyu, Chen",
                                                                                          "Yihao, Tang"]


def test_older_template_without_a_corresponding_line_marks_no_one():
    assert _corr(_old_page(corr_line="")) == []


def test_byline_and_tags_that_name_different_people_mark_no_one():
    names = ["Fangyu, Chen", "Wang, Wei", "Yihao, Tang", "Xiaoming, Zhou"]
    assert _corr(_old_page(names=names)) == []


def test_current_template_several_corresponding_authors():
    assert _corr(_new_page()) == ["Du, Qingsong", "Xu, Anhua"]


def test_current_template_one_corresponding_author():
    out = _parse(_new_page(label="Corresponding Author:", value="Anhua Xu"))
    assert [a["is_corresponding"] for a in out["authors"]] == [False, True, False]


def test_abstract_and_authors_are_the_generic_readers():
    out = _parse(_old_page())
    assert out["abstract"].startswith("An analytical model based on energy balance")
    assert all(a["affiliations"] == [] for a in out["authors"])


def test_claims_extrica_pages_without_og_url():
    assert _extrica(_new_page(og=None, publisher="Extrica")).authors_found()
    assert _extrica(_old_page(og="https://www.jvejournals.com/article/19253")).authors_found()


def test_look_alike_page_from_another_site_is_not_claimed():
    html = _old_page(publisher="Some Other Press", og="https://journals.example.org/article/19253")
    parser = _extrica(html)
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    assert _corr(html) == []  # as before: the generic parser reads no mark from a bare numbered line


def test_extrica_page_without_either_byline_is_not_read():
    html = f"<html>{_head(NEW_META)}<body><h1>Journal of Vibroengineering</h1></body></html>"
    assert not _extrica(html).authors_found()
