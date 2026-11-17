"""SciScan Publishing (三仓出版社 / 世刊出版平台, sciscanpub.com) article pages (oxjob #2339).

The site runs its own CMS. Every article page prints a `ul.article_abstract` list of labelled rows inside
`div.Main_articlescontents`: the byline ("作者：" / "Authors:", or an `h3.citation_author` above the list on the newest
pages), the affiliations ("单位：" / "Information:", numbered "1．..." when the byline carries ¹/² marks), keywords and
the abstract in Chinese and English. Full-text pages add the article body with one `p.ref` per reference. Older pages
carry no citation_* tags at all, and newer pages put every author into one romanized citation_author tag, so the
generic parser read one author or none and no affiliations. Markup below is cut down from stored pages; names are
placeholders.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.sciscanpub import SciScanPub

URL = "https://doi.org/10.35534/xx.0101001"
OLD_HEAD = '<head><title>某标题_译道_三仓出版社_开源期刊_期刊发表_快速发表_发表论文_见刊快</title></head>'
NEW_HEAD = ('<head><title>Some Title - Education Study - Full-Text HTML - SciScan</title>'
            '<meta name="citation_author" content="Zhang San Li Si" />'
            '<meta name="citation_publisher" content="SCISCAN PUBLISHING LIMITED" /></head>')
EN_ABSTRACT = ("This paper studies the discourse mode and the narrative function in the translations of classical "
               "poetry and shows that both strengthen the vitality of the translated poems.")
ZH_ABSTRACT = "本文从话语模式和叙述者功能两方面内容切入，考察译者对话语模式的运筹。"


def _page(head, inner, byline_h3=""):
    return (f'<html>{head}<body><div class="Main"><div class="Main_articlescontents">'
            f'<h2 class="article_title">某标题</h2>{byline_h3}'
            f'<ul class="article_abstract">{inner}</ul></div></div>'
            '<div class="footer_info"><p>邮箱：service@sciscanpub.com</p></div></body></html>')


def _row(label, content, tag="span"):
    return (f'<li><span class="abstract_title">{label}</span>'
            f'<{tag} class="abstract_content">{content}</{tag}></li>')


def _old_author(name):
    return (f'<a href="/index/index/serach?nkey={name}">{name}'
            '<span class="autor_num"> &nbsp;&nbsp;&nbsp;&nbsp;</span></a>')


def _new_author(name):
    return f'<a class="author_name" href="/index/index/serach?nkey={name}">{name}</a>'


OLD = _page(OLD_HEAD,
            _row("作者：", _old_author("张三¹") + _old_author("李四²*"))
            + _row("单位：", '<pre style="font-family:unset;">1．某某大学外国语学院，南京；\r\n2．某某科技大学外国语学院，太原</pre>')
            + _row("关键词：", "翻译；话语模式") + _row("", "Translation; Discourse Mode")
            + _row("摘要：", ZH_ABSTRACT) + _row("", EN_ABSTRACT.replace("narrative ", "narrative\r\n"))
            + _row("DOI：", " https://doi.org/10.35534/xx.0101001") + _row("引用：", "-"))

REFS = ('<div class="article_content"><p>正文。</p><h2>参考文献</h2>'
        '<p class="ref"><span class="ref-label">[1]</span> 王五．某某研究［J］．教育现代化，2018（25）：201-203．</p>'
        '<p class="ref"><span class="ref-label">[2]</span> Doe J. A study. Journal, 2020. https://doi.org/10.1234/abc.5678.</p>'
        '<p class="ref">［3］赵六．另一研究［J］．中国高等教育，2016（23）：4-6．</p></div>')

NEW = _page(NEW_HEAD,
            _row("Authors: ", _new_author("Zhang San¹²") + _new_author("Li Si¹") + _new_author("³"))
            + _row("Information: ", '<pre style="font-family:unset;">1. School of Economics, Some University, Yibin; '
                                    '2. Some Committee, Zigong; 3. Some Institute, Guangzhou</pre>')
            + _row("Keywords: ", '<span class="keyword">Meat rabbit industry</span>', tag="div")
            + '<li><span class="abstract_title">Abstract: </span>'
              f'<span class="abstract_content">{ZH_ABSTRACT}</span><span class="abstract_content">{EN_ABSTRACT}</span></li>'
            + _row("DOI: ", '<a href="https://doi.org/10.35534/xx.0101001">https://doi.org/10.35534/xx.0101001</a>')
            + _row("Cite: ", "Zhang, S., Li, S. (2025). Some Title.")) .replace("</ul></div></div>", "</ul>" + REFS + "</div></div>")

H3 = _page(NEW_HEAD.replace("Full-Text HTML - SciScan", "Full-Text HTML - SCISCAN PUBLISHING LIMITED"),
           _row("Information: ", '<pre style="font-family:unset;">某某医科大学，泸州</pre>')
           + '<li><span class="abstract_title">Abstract: </span>'
             f'<span class="abstract_content">{EN_ABSTRACT}</span><span class="abstract_content">{ZH_ABSTRACT}</span></li>',
           byline_h3=('<h3 class="citation_author"><span class="author_content">'
                      + _new_author("张三") + ",  " + _new_author("李四") + ",  " + _new_author("王五") + '</span></h3>'))


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _own(html):
    return SciScanPub(BeautifulSoup(html, parser="lxml", features="lxml")).parse()


def _affs(author):
    return [a["name"] for a in author["affiliations"]]


def test_old_page_byline_numbered_affiliations_and_english_abstract():
    out = _parse(OLD)
    assert [a["name"] for a in out["authors"]] == ["张三", "李四"]
    assert _affs(out["authors"][0]) == ["某某大学外国语学院，南京"]
    assert _affs(out["authors"][1]) == ["某某科技大学外国语学院，太原"]
    assert out["abstract"] == EN_ABSTRACT


def test_unexplained_asterisk_is_no_corresponding_mark():
    out = _parse(OLD)
    assert [a["is_corresponding"] for a in out["authors"]] == [False, False]


def test_new_page_marks_link_affiliations_and_a_stray_mark_joins_the_author_before():
    out = _parse(NEW)
    assert [a["name"] for a in out["authors"]] == ["Zhang San", "Li Si"]
    assert _affs(out["authors"][0]) == ["School of Economics, Some University, Yibin", "Some Committee, Zigong"]
    assert _affs(out["authors"][1]) == ["School of Economics, Some University, Yibin", "Some Institute, Guangzhou"]
    assert out["abstract"] == EN_ABSTRACT


def test_h3_byline_and_one_unlinked_affiliation_for_every_author():
    out = _parse(H3)
    assert [a["name"] for a in out["authors"]] == ["张三", "李四", "王五"]
    assert all(_affs(a) == ["某某医科大学，泸州"] for a in out["authors"])
    assert out["abstract"] == EN_ABSTRACT


def test_references_whole_numbered_list():
    out = _own(NEW)
    refs = out["references"]
    assert [r["position"] for r in refs] == [1, 2, 3]
    assert refs[0]["raw"] == "王五．某某研究［J］．教育现代化，2018（25）：201-203．"
    assert refs[1]["doi"] == "10.1234/abc.5678"
    assert refs[2]["raw"].startswith("赵六")
    assert out["references_complete"] is True
    assert out["acknowledgments"] is None and out["funding_statement"] is None


def test_references_with_a_gap_are_not_complete():
    out = _own(NEW.replace('<span class="ref-label">[2]</span>', '<span class="ref-label">[4]</span>'))
    assert len(out["references"]) == 3
    assert out["references_complete"] is False


def test_page_without_references():
    out = _own(OLD)
    assert out["references"] is None and out["references_complete"] is False


def test_look_alike_page_of_another_site_is_not_claimed():
    other = OLD.replace("_三仓出版社_", "_某某出版社_")
    soup = BeautifulSoup(other, parser="lxml", features="lxml")
    parser = SciScanPub(soup)
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_sciscan_title_without_the_article_list_is_not_claimed():
    listing = ('<html><head><title>Journal Index - SciScan</title></head><body><div class="Main">'
               '<ul class="journal_list"><li>Education Study</li></ul></div></body></html>')
    parser = SciScanPub(BeautifulSoup(listing, parser="lxml", features="lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
