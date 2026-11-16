"""Corresponding authors on Springer Link articles: the byline's data-corresp-id mark, and names whose role or
other-script form sits in parentheses (oxjob #2247; markup cut down from stored link.springer.com pages)."""
from parseland_lib.parse import parse_page

URL = "https://link.springer.com/article/10.1007/s11767-005-0200-0"


def _page(people, aff_names=None, extra=""):
    """people: (byline text, data-author-search, corresponding?) per author; aff_names: the affiliation block's
    authors-list text (one affiliation for everybody)."""
    metas = "".join(f'<meta name="citation_author" content="{s}"/>' for _, s, _ in people)
    byline = "".join(
        f'<li class="c-article-author-list__item"><a data-test="author-name" data-author-search="{s}"'
        f'{" data-corresp-id=\"c1\"" if c else ""} href="#auth-{i}">{t}</a></li>'
        for i, (t, s, c) in enumerate(people, 1))
    names = aff_names or ", ".join(t for t, _, _ in people)
    affs = ('<ol class="c-article-author-affiliation__list"><li id="Aff1">'
            '<p class="c-article-author-affiliation__address">Southeast University, Nanjing, China</p>'
            f'<p class="c-article-author-affiliation__authors-list">{names}</p></li></ol>')
    return (f'<html><head><link rel="canonical" href="{URL}"/>{metas}'
            '<meta name="citation_title" content="A title"/></head><body>'
            f'<ul class="c-article-author-list">{byline}</ul>{affs}{extra}</body></html>')


def _authors(html):
    return [(a["name"], bool(a["is_corresponding"])) for a in parse_page(html.encode(), "doi", URL)["authors"]]


def test_surname_first_byline_name_is_marked():
    people = [("Meng Qingmin", "Meng, Qingmin", True), ("You Xiaohu", "You, Xiaohu", False),
              ("John Boyer", "Boyer, John", False)]
    html = _page(people, aff_names="Meng Qingmin (male, Ph.D. candidate)\xa0&\xa0You Xiaohu, John Boyer")
    assert _authors(html) == [("Meng Qingmin", True), ("You Xiaohu", False), ("John Boyer", False)]


def test_role_in_parentheses_is_not_an_author():
    people = [("Hong-ying Sun", "Sun, Hong-ying", False), ("Zhang-jian Zhou", "Zhou, Zhang-jian", True),
              ("Man Wang", "Wang, Man", False)]
    html = _page(people, aff_names="Hong-ying Sun (Doctor Candidate, Engineer),\xa0Zhang-jian Zhou (Doctor, Professor)"
                                   "\xa0&\xa0Man Wang")
    assert _authors(html) == [("Hong-ying Sun", False), ("Zhang-jian Zhou", True), ("Man Wang", False)]


def test_name_in_another_script_in_parentheses():
    people = [("Yadgar I. Abdulkarim", "Abdulkarim, Yadgar I.", False),
              ("Lian-wen Deng\xa0\n ( 邓联文 )", "Deng, Lian-wen", False), ("Heng Luo\xa0\n ( 罗衡 )", "Luo, Heng", True)]
    html = _page(people, aff_names="Yadgar I. Abdulkarim,\xa0Lian-wen Deng\xa0\n (邓联文)\xa0&\xa0Heng Luo\xa0\n (罗衡)")
    assert _authors(html) == [("Yadgar I. Abdulkarim", False), ("Lian-wen Deng", False), ("Heng Luo", True)]


def test_two_marks_mark_both():
    people = [("Anna Berg", "Berg, Anna", True), ("Carl Dahl", "Dahl, Carl", True), ("Eva Falk", "Falk, Eva", False)]
    assert _authors(_page(people)) == [("Anna Berg", True), ("Carl Dahl", True), ("Eva Falk", False)]


def test_no_mark_marks_no_one():
    people = [("Anna Berg", "Berg, Anna", False), ("Carl Dahl", "Dahl, Carl", False)]
    assert _authors(_page(people)) == [("Anna Berg", False), ("Carl Dahl", False)]


def test_correspondence_note_keeps_its_choice():
    people = [("Anna Berg", "Berg, Anna", True), ("Carl Dahl", "Dahl, Carl", False)]
    note = '<p>Correspondence to Carl Dahl.</p>'
    assert _authors(_page(people, extra=note)) == [("Anna Berg", False), ("Carl Dahl", True)]


def test_nested_parentheses_keep_the_author():
    """A role with its own parenthesis inside ("(Fellow of the ... (CIC) ...)") must not drop the author it follows
    (dev page 23648d0d, 10.1007/BF01290660)."""
    people = [("V. de la Mota", "de la Mota, V.", False), ("E. S. Hernández", "Hernández, E. S.", False)]
    html = _page(people, aff_names="V. de la Mota (Fellow of the Comisión de Investigaciones Cientificas (CIC) de la "
                                   "Provincia de Buenos Aires)\xa0&\xa0E. S. Hernández (Member of the Scientific Research "
                                   "Career)")
    assert _authors(html) == [("V. de la Mota", False), ("E. S. Hernández", False)]


def test_page_with_only_og_url_still_gets_the_mark():
    """No canonical link: springer.py does not claim the page and the meta-tag parser wins (10.1007/BF03185563)."""
    people = [("A. V. Sidorov", "Sidorov, A. V.", True), ("M. V. Tokarev", "Tokarev, M. V.", True)]
    html = _page(people).replace(f'<link rel="canonical" href="{URL}"/>', f'<meta property="og:url" content="{URL}"/>')
    assert [c for _, c in _authors(html)] == [True, True]


def test_other_hosts_are_left_alone():
    people = [("Anna Berg", "Berg, Anna", True), ("Carl Dahl", "Dahl, Carl", False)]
    html = _page(people).replace(URL, "https://www.example.org/article/1")
    assert not any(c for _, c in _authors(html))


def _emailed(people, emails):
    """Meta tags as Springer writes them: citation_author_email right after its author's citation_author."""
    return "".join(f'<meta name="citation_author" content="{s}"/>'
                   + (f'<meta name="citation_author_email" content="{emails[s]}"/>' if s in emails else "")
                   for _, s, _ in people)


def test_note_name_across_a_line_break_clears_emailed_coauthors():
    """10.1007/s11595-011-0350-x: both first authors have an e-mail meta; the byline and the note name An Cheng only,
    and the note's name spans a line break before its Chinese form."""
    people = [("Weiting Lin\xa0\n ( 林威廷 )", "Lin, Weiting", False), ("An Cheng\xa0\n ( 鄭安 )", "Cheng, An", True),
              ("Ran Huang", "Huang, Ran", False)]
    note = ('<p id="corresponding-author-list">Correspondence to\n                <a id="corresp-c1" '
            'href="mailto:ancheng@niu.edu.tw">An Cheng\xa0\n            (<span>鄭安</span>)</a>.</p>')
    html = _page(people, aff_names="Weiting Lin (林威廷), An Cheng (鄭安) & Ran Huang", extra=note)
    metas = _emailed(people, {"Lin, Weiting": "wtlin@iner.gov.tw", "Cheng, An": "ancheng@niu.edu.tw"})
    html = html.replace('<meta name="citation_author" content="Lin, Weiting"/><meta name="citation_author" '
                        'content="Cheng, An"/><meta name="citation_author" content="Huang, Ran"/>', metas)
    assert _authors(html) == [("Weiting Lin", False), ("An Cheng", True), ("Ran Huang", False)]


def test_note_with_two_names_across_line_breaks():
    """10.1007/s11595-026-3313-y: three authors carry e-mail metas; the note names Wenbing Li or Wenxin Xiang."""
    people = [("Lin Chen\xa0\n ( 陈林 )", "Chen, Lin", False), ("Zujie Wu\xa0\n ( 吴祖杰 )", "Wu, Zujie", False),
              ("Wenbing Li\xa0\n ( 李文兵 )", "Li, Wenbing", True), ("Jiaxuan Li", "Li, Jiaxuan", False),
              ("Wenxin Xiang\xa0\n ( 项文信 )", "Xiang, Wenxin", True)]
    note = ('<p id="corresponding-author-list">Correspondence to\n <a id="corresp-c1" href="mailto:liwenbing@wust.edu.cn">'
            'Wenbing Li\xa0\n (<span lang="zh">李文兵</span>)</a> or <a id="corresp-c2" href="mailto:enyaz9@163.com">'
            'Wenxin Xiang\xa0\n (<span lang="zh">项文信</span>)</a>.</p>')
    html = _page(people, aff_names="Lin Chen (陈林), Zujie Wu (吴祖杰), Wenbing Li (李文兵), Jiaxuan Li & Wenxin Xiang (项文信)",
                 extra=note)
    metas = _emailed(people, {"Chen, Lin": "1239107464@qq.com", "Wu, Zujie": "6871464@qq.com",
                              "Li, Wenbing": "liwenbing@wust.edu.cn"})
    old = "".join(f'<meta name="citation_author" content="{s}"/>' for _, s, _ in people)
    html = html.replace(old, metas)
    assert [c for _, c in _authors(html)] == [False, False, True, False, True]
