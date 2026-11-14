"""psyjournals.ru (Portal of Russian Psychological Publications, MSUPE) article pages (oxjob #2210).

Markup is cut down from stored pages of the site (13 Nov 2026). The site runs its own CMS: a byline of author links,
then <section aria-labelledby="..."> blocks for the abstract, "General Information" (funding and acknowledgements as
bold-labelled paragraphs), the reference list (<ol>) and "Information About the Authors" (one prose paragraph per
author: degree, position, institutions, ORCID, e-mail). Russian pages carry the same markup with Russian labels.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.psyjournals import PsyJournals

URL = "https://psyjournals.ru/en/journals/pse/archive/2026_n3/Morozova_Stopkina"


def _page(body, og_url=URL, names=("O.V. Morozova", "E.V. Kokhanovich")):
    metas = "".join(f'<meta name="citation_author" content="{n}">' for n in names)
    return (f'<html lang="en"><head><meta name="citation_title" content="A title">{metas}'
            f'<meta property="og:url" content="{og_url}"><link href="{og_url}" rel="canonical"></head>'
            f'<body><main><article class="publicationarticles journalarticles view content">{body}</article></main>'
            f'</body></html>')


BYLINE = ('<div class="authors"><p><span itemprop="author"><a class="author" href="/en/authors/15711" rel="author">'
          '<span itemprop="name">O.V. Morozova</span></a></span>, <span itemprop="author"><a class="author" '
          'href="/en/authors/1313" rel="author"><span itemprop="name">E.V. Kokhanovich</span></a></span></p></div>')

ABSTRACT = ('<section aria-labelledby="abstract"><h2 id="abstract">Abstract</h2><div style="text-align: justify;">'
            '<p><strong>Context and relevance.</strong> Mastering experimentation skills is a key outcome. '
            '<strong>Objective.</strong> To determine whether second-graders discover a method.</p></div></section>')

GENERAL = ('<section aria-labelledby="generalinfo"><h2 id="generalinfo">General Information</h2>'
           '<p><strong>Keywords:</strong> <span>experimentation</span></p>'
           '<p> <strong>Funding.</strong> The study was funded by a grant from the Russian Science Foundation '
           '(project № 19-18-00271). </p>'
           '<p> <strong>Acknowledgements.</strong> The authors thank the participating students. </p>'
           '<p><strong>DOI:</strong> <a href="https://doi.org/10.17759/pse.2026310302">x</a></p></section>')

REFS = ('<section aria-labelledby="references"><h2 id="references">References</h2><div><ol>'
        '<li>Ахутин, А.В. (1976). <em>История принципов</em>. М.: Наука.<br>Akhutin, A.V. (1976). History of the '
        'principles. Moscow: Nauka (In Russ.).</li>'
        '<li>Рубцов, В.В. (2024). Школа. <em>Культурно-историческая психология</em>, 20(1), 16–26. '
        '<a href="https://doi.org/10.17759/chp.2024200104" class="refitem-link">https://doi.org/10.17759/chp.2024200104</a>'
        '<br>Rubtsov, V.V. (2024). School. <em>Cultural-Historical Psychology</em>, 20(1), 16–26. '
        '<a href="https://doi.org/10.17759/chp.2024200104" class="refitem-link">https://doi.org/10.17759/chp.2024200104</a></li>'
        '<li>Степин, В.С. (2000). <em>Теоретическое знание</em>. М.: Прогресс-Традиция.</li>'
        '</ol></div></section>')

AUTHORS_INFO = (
    '<section aria-labelledby="authorsinfo"><h2 id="authorsinfo">Information About the Authors</h2><div class="authors">'
    '<p><a href="/en/authors/15711" id="author-id-15711" class="author"><em>Olga V. Morozova,</em></a> Student, Faculty '
    'of Psychology, Lomonosov Moscow State University, Moscow, Russian Federation, ORCID: '
    '<a href="https://orcid.org/0000-0003-0380-1113">https://orcid.org/0000-0003-0380-1113</a>, e-mail: a@example.com</p>'
    '<p><a href="/en/authors/1313" id="author-id-1313" class="author"><em>Ellena V. Kokhanovich,</em></a> Candidate of '
    'Science (Psychology), Leading Researcher, Federal Scientific Centre for Psychological and Interdisciplinary '
    'Research (Psychological Institute of the Russian Academy of Education), Moscow, Russian Federation, ORCID: '
    '<a href="https://orcid.org/0000-0002-3923-781X">https://orcid.org/0000-0002-3923-781X</a>, e-mail: b@example.com</p>'
    '</div></section>')

FULL = _page(BYLINE + ABSTRACT + GENERAL + REFS + AUTHORS_INFO)


def _parsed(html):
    return PsyJournals(BeautifulSoup(html, "lxml")).parse()


def test_authors_come_from_the_byline_with_affiliations_from_author_info():
    out = parse_page(FULL.encode(), "doi", URL)
    assert [a["name"] for a in out["authors"]] == ["O.V. Morozova", "E.V. Kokhanovich"]
    affs = [[x["name"] for x in a["affiliations"]] for a in out["authors"]]
    assert affs == [["Faculty of Psychology, Lomonosov Moscow State University, Moscow, Russian Federation"],
                    ["Federal Scientific Centre for Psychological and Interdisciplinary Research (Psychological "
                     "Institute of the Russian Academy of Education), Moscow, Russian Federation"]]
    assert not any(a["is_corresponding"] for a in out["authors"])


def test_russian_author_info_drops_degree_and_position_and_splits_institutions():
    info = ('<section aria-labelledby="authorsinfo"><h2 id="authorsinfo">Информация об авторах</h2><div class="authors">'
            '<p><a href="/authors/2538" id="author-id-2538" class="author"><em>Валуева Екатерина Александровна,</em></a> '
            'кандидат психологических наук, научный сотрудник лаборатории психологии творчества, ФГБУН «Институт '
            'психологии Российской академии наук» (ИПРАН), ведущий научный сотрудник, Центр прикладных исследований, '
            'Московский государственный психолого-педагогический университет (ФГБОУ ВО МГППУ), Москва, Россия, ORCID: '
            '<a href="https://orcid.org/0000-0003-3637-287X">https://orcid.org/0000-0003-3637-287X</a>, e-mail: '
            'c@example.ru</p></div></section>')
    byline = '<div class="authors"><p><a href="/authors/2538" class="author">Валуева Е.А.</a></p></div>'
    html = _page(byline + info, og_url="https://psyjournals.ru/journals/exppsy/archive/2024_n4/Valueva",
                 names=("Валуева Е.А.",))
    author = _parsed(html)["authors"][0]
    assert author["name"] == "Валуева Е.А."
    assert author["affiliations"] == [
        "лаборатории психологии творчества, ФГБУН «Институт психологии Российской академии наук» (ИПРАН)",
        "Центр прикладных исследований, Московский государственный психолого-педагогический университет "
        "(ФГБОУ ВО МГППУ), Москва, Россия"]


def test_abstract_is_the_abstract_section_text():
    out = parse_page(FULL.encode(), "doi", URL)
    assert out["abstract"] == ("Context and relevance. Mastering experimentation skills is a key outcome. Objective. "
                               "To determine whether second-graders discover a method.")


def test_funding_and_acknowledgements_from_general_information():
    out = _parsed(FULL)
    assert out["funding_statement"] == ("The study was funded by a grant from the Russian Science Foundation "
                                        "(project № 19-18-00271).")
    assert out["acknowledgments"] == "The authors thank the participating students."


def test_russian_funding_label():
    general = ('<section aria-labelledby="generalinfo"><h2 id="generalinfo">Общая информация</h2>'
               '<p> <strong>Финансирование.</strong> Исследование выполнено при поддержке РНФ, проект № 24-18-00130. </p>'
               '</section>')
    out = _parsed(_page(BYLINE + general))
    assert out["funding_statement"] == "Исследование выполнено при поддержке РНФ, проект № 24-18-00130."
    assert out["acknowledgments"] is None


def test_no_funding_or_acknowledgements_when_the_page_has_none():
    out = _parsed(_page(BYLINE + ABSTRACT))
    assert out["funding_statement"] is None and out["acknowledgments"] is None


def test_reference_list_in_order_with_dois_and_complete():
    out = _parsed(FULL)
    refs = out["references"]
    assert [r["position"] for r in refs] == [1, 2, 3]
    assert refs[0]["raw"].startswith("Ахутин, А.В. (1976). История принципов. М.: Наука. Akhutin, A.V. (1976).")
    assert refs[0]["doi"] is None
    assert refs[1]["doi"] == "10.17759/chp.2024200104"
    assert out["references_complete"] is True


def test_nested_list_counts_each_reference_once():
    refs = REFS.replace("<ol>", "<ol><ol>").replace("</ol>", "</ol></ol>")
    out = _parsed(_page(BYLINE + refs))
    assert len(out["references"]) == 3 and out["references_complete"] is True


def test_empty_reference_section_gives_no_list():
    empty = '<section aria-labelledby="references"><h2 id="references">Литература</h2><div><p> </p></div></section>'
    out = _parsed(_page(BYLINE + empty))
    assert out["references"] is None and out["references_complete"] is False


def test_list_with_a_show_more_marker_is_not_complete():
    more = REFS.replace("</ol>", '</ol><button class="refs-more">Show all references</button>')
    out = _parsed(_page(BYLINE + more))
    assert len(out["references"]) == 3 and out["references_complete"] is False


def test_same_markup_on_another_site_is_not_claimed():
    html = _page(BYLINE + ABSTRACT + GENERAL + REFS + AUTHORS_INFO,
                 og_url="https://notpsyjournals.example.org/journals/x/archive/2026_n3/Morozova")
    parser = PsyJournals(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
