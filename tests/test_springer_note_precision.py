"""Springer Link's "Correspondence to" note names its authors exactly (oxjob #2352; markup cut down from stored
link.springer.com pages).

Until #2352 the note matched any author sharing 2 tokens with the whole note, so a shared given name and surname,
"Prof. Dr." on everyone, or one name inside another ("Jie Wang" in "Zhengjie Wang") flagged a co-author the note does
not name. And a Springer page that cites an Elsevier book or a ScienceDirect article says "Elsevier" in its
citation_reference tags, which made the Elsevier parser claim it ahead of springer.py and flag every author with an
e-mail tag.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.elsevier_bv import ElsevierBV

URL = "https://link.springer.com/article/10.1007/s10443-023-10186-w"


def _page(people, note, metas=""):
    """people: (byline text, corresponding per the byline mark) per author; one affiliation for everybody."""
    byline = "".join(
        f'<li class="c-article-author-list__item"><a data-test="author-name"'
        f'{" data-corresp-id=\"c1\"" if c else ""} href="#auth-{i}">{t}</a></li>'
        for i, (t, c) in enumerate(people, 1))
    names = ", ".join(t for t, _ in people)
    affs = ('<ol class="c-article-author-affiliation__list"><li id="Aff1">'
            '<p class="c-article-author-affiliation__address">University of Porto, Porto, Portugal</p>'
            f'<p class="c-article-author-affiliation__authors-list">{names}</p></li></ol>')
    return (f'<html><head><link rel="canonical" href="{URL}"/>{metas}'
            '<meta name="citation_title" content="A title"/></head><body>'
            f'<ul class="c-article-author-list">{byline}</ul>{affs}'
            f'<p id="corresponding-author-list">Correspondence to {note}.</p></body></html>')


def _flags(html):
    return [(a["name"], bool(a["is_corresponding"])) for a in parse_page(html.encode(), "doi", URL)["authors"]]


def _corresponding(html):
    return [name for name, c in _flags(html) if c]


def test_shared_given_name_and_surname_is_not_the_noted_author():
    """10.1186/s13098-026-02266-1: 'Yung-Chih Chen' shares 'Chih' and 'Chen' with 'Solomon Chih-Cheng Chen'."""
    people = [("Yung-Chih Chen", False), ("Solomon Chih-Cheng Chen", True)]
    assert _corresponding(_page(people, '<a href="mailto:s@x.org">Solomon Chih-Cheng Chen</a>')) == [
        "Solomon Chih-Cheng Chen"]


def test_a_name_inside_another_name_is_not_a_match():
    """10.1186/s13550-026-01382-3: 'Jie Wang' is a substring of 'Zhengjie Wang'."""
    people = [("Jie Wang", False), ("Hua Pang", True), ("Zhengjie Wang", True)]
    note = '<a href="mailto:a@x.org">Hua Pang</a> or <a href="mailto:b@x.org">Zhengjie Wang</a>'
    assert _corresponding(_page(people, note)) == ["Hua Pang", "Zhengjie Wang"]


def test_titles_everyone_carries_do_not_match():
    """10.1007/978-3-658-05046-7_9: every author is 'Prof. Dr.'; the note names Manfred Bruhn."""
    people = [("Heribert Meffert Prof. Dr. Dr. h.c.", False), ("Manfred Bruhn Prof. Dr.", True),
              ("Karsten Hadwich Prof. Dr.", False)]
    assert _corresponding(_page(people, '<a href="mailto:m@x.org">Manfred Bruhn Prof. Dr.</a>')) == [
        "Manfred Bruhn Prof. Dr."]


def test_tokens_taken_from_two_noted_names_do_not_match():
    """10.1007/s11030-026-11471-z: 'Yu-Qiang Xiang' takes 'Yu' from Yu-Li Dang and 'Qiang' from Sheng-Qiang Guo."""
    people = [("Yu-Li Dang", True), ("Cao-Yuan Niu", True), ("Sheng-Qiang Guo", True), ("Yu-Qiang Xiang", False)]
    note = ('<a href="mailto:a@x.org">Yu-Li Dang</a> , <a href="mailto:b@x.org">Cao-Yuan Niu</a> or '
            '<a href="mailto:c@x.org">Sheng-Qiang Guo</a>')
    assert _corresponding(_page(people, note)) == ["Yu-Li Dang", "Cao-Yuan Niu", "Sheng-Qiang Guo"]


def test_shared_particle_and_surname_is_not_the_noted_author():
    """10.1007/s40819-021-01073-8: 'Gustavo Ribeiro dos Santos' shares 'dos Santos' with the noted author."""
    people = [("Matheus dos Santos Guzella", True), ("Gustavo Ribeiro dos Santos", False), ("Antonio Campo", False)]
    assert _corresponding(_page(people, '<a href="mailto:m@x.org">Matheus dos Santos Guzella</a>')) == [
        "Matheus dos Santos Guzella"]


def test_noted_names_still_match_through_titles_initials_and_order():
    """The note and the byline write one person differently: a title the note leaves out, a degree, a middle initial,
    a surname-first name."""
    people = [("StB Univ.-Prof. Dr. Rolf Uwe Fülbier", True), ("Christina Scharf M.Sc.", True), ("Anna Berg", False)]
    note = '<a href="mailto:a@x.org">Rolf Uwe Fülbier</a> or <a href="mailto:b@x.org">Christina Scharf M.Sc.</a>'
    assert _corresponding(_page(people, note)) == ["StB Univ.-Prof. Dr. Rolf Uwe Fülbier", "Christina Scharf M.Sc."]
    people = [("Robert Wright", True), ("Carl Dahl", False)]
    assert _corresponding(_page(people, '<a href="mailto:r@x.org">Robert J. Wright</a>')) == ["Robert Wright"]
    people = [("Qingmin Meng", True), ("Xiaohu You", False)]
    assert _corresponding(_page(people, '<a href="mailto:m@x.org">Meng Qingmin</a>')) == ["Qingmin Meng"]


def test_springer_page_citing_elsevier_stays_springers():
    """10.1007/s10443-023-10186-w: a reference to an Elsevier book in the citation_reference tags made the Elsevier
    parser claim the page; it flagged both authors with an e-mail tag, where the note names one."""
    people = [("Afshin Zeinedini", True), ("Yazdan Hosseini", False), ("Ahmed Sahib Mahdi", False)]
    metas = ('<meta name="citation_author" content="Zeinedini, Afshin"/>'
             '<meta name="citation_author_email" content="zeinedini@iauksh.ac.ir"/>'
             '<meta name="citation_author_institution" content="Islamic Azad University, Kermanshah, Iran"/>'
             '<meta name="citation_author" content="Hosseini, Yazdan"/>'
             '<meta name="citation_author_institution" content="Islamic Azad University, Kermanshah, Iran"/>'
             '<meta name="citation_author" content="Mahdi, Ahmed Sahib"/>'
             '<meta name="citation_author_email" content="ahmed.altaei@stu.edu.iq"/>'
             '<meta name="citation_author_institution" content="Southern Technical University, Alnasiriyah, Iraq"/>'
             '<meta name="citation_reference" content="Levy, S.M.: Construction calculations manual. Elsevier Inc. '
             '(2012)"/>')
    html = _page(people, '<a href="mailto:zeinedini@iauksh.ac.ir">Afshin Zeinedini</a>', metas=metas)
    assert not ElsevierBV(BeautifulSoup(html, "lxml")).is_publisher_specific_parser()
    assert _flags(html) == [("Afshin Zeinedini", True), ("Yazdan Hosseini", False), ("Ahmed Sahib Mahdi", False)]


def test_elsevier_signal_outside_references_still_dispatches():
    html = ('<html><head><meta name="citation_reference" content="A. Author, J. Other. 12 (2001)"/>'
            '<meta name="citation_publisher" content="Elsevier Masson"/></head><body/></html>')
    assert ElsevierBV(BeautifulSoup(html, "lxml")).is_publisher_specific_parser()
    html = '<html><head><meta name="dc.relation" content="https://www.sciencedirect.com/x"/></head><body/></html>'
    assert not ElsevierBV(BeautifulSoup(html, "lxml")).is_publisher_specific_parser()
