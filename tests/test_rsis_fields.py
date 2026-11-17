"""RSIS International pages (rsisinternational.org: IJRISS, IJRSI, IJRIAS), oxjob #2338.

Markup is cut down from stored pages of the site's two templates. The WordPress theme lists the authors in
ul.sj-articles_info and prints the byline, affiliations and reference list in the pasted full text
(div.sj-article-detail_content); it has no citation_* meta tags. The 2026 PHP template has citation_author tags, one
card per author in an "Authors" section, and a "References" section of numbered paragraphs.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.rsis import RSISInternational

WP_URL = "https://rsisinternational.org/journals/ijriss/articles/a-study-of-something/"
PHP_URL = "https://rsisinternational.org/journals/ijriss/article.php?id=5213"
TITLE = "A Study of Something in Rural Communities"
ABSTRACT = ("This study examines how rural community cooperatives organise tourism products and how their members "
            "share the income. Data from 120 households were analysed with descriptive statistics and regression.")
REFS = ("<li>Abraham, B. (2016). The Colonial Origins. <em>Economic and Political Weekly</em>, 51(9), 15–18.</li>"
        "<li>Agyemang, E. F. (2024). Anomaly detection. Scientific African. "
        "<a href=\"https://doi.org/10.1016/j.sciaf.2024.e02386\">https://doi.org/10.1016/j.sciaf.2024.e02386</a></li>"
        "<li>Baxi, U. (2008). The Indian Supreme Court and Politics. Eastern Book Company.</li>")


def _wp_page(info, front, refs=f"<ol>{REFS}</ol>", og_url=WP_URL, after_refs=""):
    lis = "".join(f'<li><span><i class="icon icon-user"></i>{name}</span></li>' for name in info)
    return (f'<html><head><meta property="og:url" content="{og_url}" />'
            f'<meta property="og:site_name" content="International Journal of Research and Innovation in Social '
            f'Science" /><meta name="description" content="This study examines how rural community ..." /></head>'
            f'<body><div class="sj-article-detail"><div class="sj-article-detail_title"><h1 class="h2">{TITLE}</h1>'
            f'</div><ul class="sj-articles_info">{lis}<li><span><i class="icon icon-calendar"></i>May 3, 2025</span>'
            f'</li></ul><div class="sj-article-detail_content">'
            f'<p style="text-align: center;"><strong>{TITLE}</strong></p>{front}'
            f'<p style="text-align: center;"><strong>DOI: </strong><a href="https://dx.doi.org/10.47772/IJRISS.2025'
            f'.90400158">https://dx.doi.org/10.47772/IJRISS.2025.90400158</a></p>'
            f'<p style="text-align: center;"><strong>Received: 27 March 2025; Published: 03 May 2025</strong></p>'
            f'<h3 style="text-align: justify;"><strong>ABSTRACT</strong></h3><p>{ABSTRACT}</p>'
            f'<h3><strong>INTRODUCTION</strong></h3><p>Tourism is a growing sector.</p>'
            f'<h3><strong>REFERENCES</strong></h3>{refs}<p><em>&nbsp;</em></p>{after_refs}'
            f'</div></div></body></html>')


def _p(html):
    return f'<p style="text-align: center;"><strong>{html}</strong></p>'


def _parse(html, url=WP_URL):
    return parse_page(html.encode(), "doi", url)


def _authors(html, url=WP_URL):
    return [(a["name"], [x["name"] for x in a["affiliations"]], a["is_corresponding"])
            for a in _parse(html, url)["authors"]]


def _raw(html):
    return RSISInternational(BeautifulSoup(html, parser="lxml", features="lxml")).parse()


def test_numbered_byline_links_each_author_to_their_affiliations():
    html = _wp_page(["Wale Sammie Chombo", "Orach-Meza Faustino L", "Mwirumubi Richard"],
                    _p("Wale Sammie Chombo<sup>1</sup>, Orach-Meza Faustino L<sup>2</sup><sub>,</sub> and "
                       "Mwirumubi Richard<sup>2,3</sup>")
                    + _p("<sup>1</sup></strong><strong>Nkumba University, Entebbe, Uganda.")
                    + _p("<sup>2</sup></strong><strong>Makerere University, Kampala, Uganda.")
                    + _p("<sup>3</sup></strong><strong>Kyambogo University, Kampala, Uganda."))
    assert _authors(html) == [
        ("Wale Sammie Chombo", ["Nkumba University, Entebbe, Uganda."], False),
        ("Orach-Meza Faustino L", ["Makerere University, Kampala, Uganda."], False),
        ("Mwirumubi Richard", ["Makerere University, Kampala, Uganda.", "Kyambogo University, Kampala, Uganda."],
         False)]


def test_numbers_printed_before_the_names_and_a_line_continued_after_a_break():
    html = _wp_page(["Donath Asiimire.", "Robert Mugabe.", "Dr. Nuwatuhaire Benard."],
                    _p("<sup>1</sup></strong><strong>Donath Asiimire., <sup>1</sup>Robert Mugabe., "
                       "<sup>2</sup>Dr. Nuwatuhaire Benard.")
                    + _p("<sup>1</sup>Bishop Stuart University, P.O. Box 9,<br/>Mbarara – Uganda")
                    + _p("<sup>2</sup></strong><strong>Ankole Western University"))
    assert _authors(html) == [("Donath Asiimire", ["Bishop Stuart University, P.O. Box 9, Mbarara – Uganda"], False),
                              ("Robert Mugabe", ["Bishop Stuart University, P.O. Box 9, Mbarara – Uganda"], False),
                              ("Nuwatuhaire Benard", ["Ankole Western University"], False)]


def test_unnumbered_affiliation_is_every_authors_and_family_given_names_turn_round():
    html = _wp_page(["Alejandro, David T.", "Dela Cruz, Fiona Faith", "JAMES L. PAGLINAWAN, PhD"],
                    _p("Alejandro, David T., Dela Cruz, Fiona Faith, James L. Paglinawan, Phd")
                    + _p("Harlal School of Law, Greater Noida"))
    assert _authors(html) == [("David T. Alejandro", ["Harlal School of Law, Greater Noida"], False),
                              ("Fiona Faith Dela Cruz", ["Harlal School of Law, Greater Noida"], False),
                              ("JAMES L. PAGLINAWAN", ["Harlal School of Law, Greater Noida"], False)]


def test_star_explained_as_corresponding_author_marks_that_author():
    html = _wp_page(["Vekneswary Krishnan", "Hafiz Zaini"],
                    _p("Vekneswary Krishnan, Hafiz Zaini*")
                    + _p("Faculty of Education, Universiti Kebangsaan Malaysia, Bangi, Selangor, Malaysia")
                    + _p("*Correspondent Author"))
    assert _authors(html) == [
        ("Vekneswary Krishnan", ["Faculty of Education, Universiti Kebangsaan Malaysia, Bangi, Selangor, Malaysia"],
         False),
        ("Hafiz Zaini", ["Faculty of Education, Universiti Kebangsaan Malaysia, Bangi, Selangor, Malaysia"], True)]


def test_star_in_a_numbered_mark_with_a_note_and_without_one():
    byline = _p("W. </strong><strong>Isuru Dananjana<sup>1</sup>, D. L. Isuri Yasara</strong><strong>*</strong>"
                "<strong><sup>2</sup>")
    affs = _p("<sup>1</sup></strong><strong>Institute of Chemistry Ceylon, Rajagiriya") + _p(
        "<sup>2</sup></strong><strong>Open University, Nawala, Sri Lanka")
    names = ["W. Isuru Dananjana", "D. L. Isuri Yasara"]
    noted = _authors(_wp_page(names, byline + affs + _p("*Corresponding author")))
    assert [c for _, _, c in noted] == [False, True]
    assert noted[1][1] == ["Open University, Nawala, Sri Lanka"]
    # an unexplained star is no corresponding-author mark (label-v1)
    assert [c for _, _, c in _authors(_wp_page(names, byline + affs))] == [False, False]


def test_title_in_another_language_before_the_byline_and_a_degree_programme_line():
    html = _wp_page(["Thierry Dong"],
                    _p("(La reconstruction de l’intimité sexuelle)") + _p("Thierry Dong")
                    + _p("Bachelor of Science in Psychology (BSPsy)"))
    assert _authors(html) == [("Thierry Dong", [], False)]


def test_abstract_is_still_read():
    html = _wp_page(["Thierry Dong"], _p("Thierry Dong") + _p("University of Dschang, Cameroon"))
    assert _parse(html)["abstract"] == ABSTRACT


def test_reference_list_is_whole_and_keeps_dois():
    out = _raw(_wp_page(["Thierry Dong"], _p("Thierry Dong")))
    assert out["references_complete"] is True
    assert [r["position"] for r in out["references"]] == [1, 2, 3]
    assert out["references"][0]["raw"].startswith("Abraham, B. (2016). The Colonial Origins.")
    assert [r["doi"] for r in out["references"]] == [None, "10.1016/j.sciaf.2024.e02386", None]
    assert out["acknowledgments"] is None and out["funding_statement"] is None


def test_reference_text_outside_the_list_or_a_list_starting_later_is_not_whole():
    stray = _raw(_wp_page(["Thierry Dong"], _p("Thierry Dong"),
                          after_refs="<p>Zulu, K. (2020). A reference typed after the list.</p>"))
    assert len(stray["references"]) == 3 and stray["references_complete"] is False
    later = _raw(_wp_page(["Thierry Dong"], _p("Thierry Dong"), refs=f'<ol start="4">{REFS}</ol>'))
    assert later["references_complete"] is False


def _php_page(cards, refs, og_url=PHP_URL):
    metas = "".join(f'<meta name="citation_author" content="{name}">' for name, _ in cards)
    body = "".join(f'<div><p class="font-semibold"><a href="author.php?id={i}" class="text-blue-700">{name}</a></p>'
                   f'<p class="text-sm text-gray-600">{aff}</p></div>' for i, (name, aff) in enumerate(cards))
    ref_ps = "".join(f'<p>{ref} <a class="text-blue-700" href="https://scholar.google.com/scholar?q=x">'
                     f'[Google Scholar]</a> <a class="text-blue-700" href="https://search.crossref.org/?q=x">'
                     f'[Crossref]</a></p>' for ref in refs)
    return (f'<html><head><meta name="citation_title" content="{TITLE}">{metas}'
            f'<meta name="citation_publisher" content="RSIS International">'
            f'<meta property="og:url" content="{og_url}"></head><body><main><article>'
            f'<h1 class="text-3xl font-bold mb-4">{TITLE}</h1>'
            f'<section aria-labelledby="authors-heading"><h2 id="authors-heading">Authors</h2>'
            f'<div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">{body}</div></section>'
            f'<section aria-labelledby="abstract-heading"><h2 id="abstract-heading">Abstract</h2>'
            f'<div class="bg-white p-4 rounded shadow"><p>{ABSTRACT}</p></div></section>'
            f'<section aria-labelledby="references-heading"><h2 id="references-heading">References</h2>'
            f'<div class="bg-white p-4 rounded shadow">{ref_ps}</div></section></article></main></body></html>')


PHP_CARDS = [("Angelica A. Delos Reyes", "Northern Iloilo State University (Philippines)"),
             ("Maria Kristina C. Ortiz", "Capiz State University (Philippines)")]
PHP_REFS = ["1. Ali, S. A. (2025). Banking in the digital era. Indus Journal, 3(2), 1–9. "
            "https://doi.org/10.1234/indus.2025.12.", "2. Ibid., p. 4.", "3. Yoshino, N. (2018). The role of SMEs in Asia."]


def test_php_template_cards_give_each_author_an_affiliation():
    assert _authors(_php_page(PHP_CARDS, PHP_REFS), PHP_URL) == [
        ("Angelica A. Delos Reyes", ["Northern Iloilo State University (Philippines)"], False),
        ("Maria Kristina C. Ortiz", ["Capiz State University (Philippines)"], False)]
    assert _parse(_php_page(PHP_CARDS, PHP_REFS), PHP_URL)["abstract"] == ABSTRACT


def test_php_template_references_drop_numbers_and_search_links():
    out = _raw(_php_page(PHP_CARDS, PHP_REFS))
    assert out["references_complete"] is True
    assert [r["raw"] for r in out["references"]] == [
        "Ali, S. A. (2025). Banking in the digital era. Indus Journal, 3(2), 1–9. https://doi.org/10.1234/indus.2025.12.",
        "Ibid., p. 4.", "Yoshino, N. (2018). The role of SMEs in Asia."]
    assert out["references"][0]["doi"] == "10.1234/indus.2025.12"
    gap = _raw(_php_page(PHP_CARDS, [PHP_REFS[0], PHP_REFS[2]]))
    assert gap["references_complete"] is False
    # a URL printed as an entry of its own: the list isn't one entry per reference
    split = _raw(_php_page(PHP_CARDS, PHP_REFS + ["4. https://documents.worldbank.org/en/publication/report"]))
    assert len(split["references"]) == 4 and split["references_complete"] is False


def test_same_theme_on_another_site_is_not_claimed():
    other = _wp_page(["Thierry Dong"], _p("Thierry Dong") + _p("University of Dschang, Cameroon"),
                     og_url="https://example-journals.org/journals/ijxx/articles/a-study-of-something/")
    soup = BeautifulSoup(other, parser="lxml", features="lxml")
    parser = RSISInternational(soup)
    assert not parser.is_publisher_specific_parser() and not parser.authors_found()
    assert _authors(other) == []
    php_other = _php_page(PHP_CARDS, PHP_REFS, og_url="https://example-journals.org/article.php?id=5")
    assert not RSISInternational(BeautifulSoup(php_other, parser="lxml", features="lxml")).authors_found()
    assert [a for a, _, _ in _authors(php_other, PHP_URL)] == [n for n, _ in PHP_CARDS]  # the generic meta-tag reader
