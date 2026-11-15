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
