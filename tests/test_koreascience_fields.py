"""KoreaScience article pages (koreascience.or.kr, KISTI's platform for Korean society journals; oxjob #2289).

Markup is cut down from stored KoreaScience pages (17 Nov 2026, #2289 template koreascience). The DOIs of hundreds of
Korean society journals resolve to one KoreaScience article page. Its only author tag is a single citation_author
holding every name joined by ';' ("Nam, Seung-Min;Kim, Ki-Woong;"), so the generic parser read one "author" made of all
of them and no affiliation. The page prints the byline twice under the title: in English, each name linked to its
doi.or.kr person record and followed by "(affiliation)", then in Korean with the same links; when the English byline
has no affiliations the Korean one has them. The reference list is an <ol> of li#ref-N under an "References" box.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.koreascience import KoreaScience

URL = "https://doi.org/10.5351/kjas.2008.21.5.835"

ABSTRACT = ("In this paper, we investigate a Bayesian inference for software reliability models based on mean value "
            "functions which take the form of the mixture of beta distribution functions. The posterior simulation via "
            "the Markov chain Monte Carlo approach is used to produce estimates of posterior properties.")


def _head(title="Bayesian Inferences for Software Reliability Models -The Korean Journal of Applied Statistics",
          authors="Nam, Seung-Min;Kim, Ki-Woong;Cho, Sin-Sup;"):
    return (f"<head><title>\n\t\t\t\t{title}\n\t\t\t | Korea Science</title>"
            '<meta name="citation_journal_title" content="The Korean Journal of Applied Statistics">'
            '<meta name="citation_publisher" content="The Korean Statistical Society">'
            '<meta name="citation_title" content="Bayesian Inferences for Software Reliability Models">'
            f'<meta name="citation_author" content="{authors}">'
            '<meta name="citation_pdf_url" content="http://koreascience.or.kr:80/article/JAKO200801440609400.pdf">'
            f'<meta name="description" content="\n\n{ABSTRACT}"></head>')


def _li(name, aff=None, psn="ADPER0000073146", sep=True, extra=""):
    who = f'<a target="_blank" href="http://doi.or.kr/10.PSN/{psn}">{name}</a>' if psn else name
    return (f'<li class="list-inline-item">\n\t\t{who}{extra}\n\t\t' + (f"({aff})\n\t\t" if aff else "")
            + (";\n" if sep else "") + "</li>")


def _byline(*lines):
    first = '<ul class="list-inline g-color-gray-dark-v2 m0">' + "".join(lines[0]) + "</ul>"
    rest = "".join('<ul class="list-inline g-color-gray-dark-v2">' + "".join(line) + "</ul>" for line in lines[1:])
    return first + rest


REFS = """
<div class="article-box"><h4 class="h4 g-mb-15 article-con-title">References</h4>
<ol class="ml0 pl25" style="word-break:unset">
<li class="g-color-gray-dark-v2 mb10" id="ref-1"><span class="ref-text">Achcar, J. A., Dey, D. K. and Niverthi, M.
 (1997). A Bayesian approach using nonhomogeneous Poisson process for software reliability models</span></li>
<li class="g-color-gray-dark-v2 mb10" id="ref-2"><span class="ref-text">Basu, S. and Ebrahimi, N. (2003). Bayesian
 software reliability models based on Martingale processes, Technometrics, 45, 150-158</span>
 <a href="https://doi.org/10.1198/004017003188618788" target="_blank" class="doi-link">https://doi.org/10.1198/004017003188618788</a></li>
<li class="g-color-gray-dark-v2 mb10" id="ref-3"><span class="ref-text">Cox, D. R. and Lewis, P. A. (1966).
 Statistical Analysis of Series of Events, Chapman &amp; Hall/CRC, London</span></li>
</ol></div>
<div class="article-box"><h4 class="h4 g-mb-15 article-con-title">Cited by</h4>
<ol><li>A later paper citing this one, vol.40, pp.1, 2017, https://doi.org/10.14697/jkase.2020.40.1.13</li></ol></div>
"""


def _page(byline, refs=REFS, head=None):
    return (f"<html>{head or _head()}<body><main role=\"main\"><div id=\"article-view\" class=\"container\">"
            '<div class="contenting"><div class="row contents-table article-title-row"><div class="col-md-12">'
            '<h1 class="h2 article-title" id="h-0">Bayesian Inferences for Software Reliability Models</h1>'
            '</div></div><div class="row"><div class="col-md-12">'
            f"{byline}"
            '<ul class="list-inline"><li class="list-inline-item">Published : 2008.10.31</li></ul>'
            '</div></div><hr><div class="row"><div class="col-12 col-lg-8">'
            '<div class="article-box"><h4 class="h4 g-mb-15 article-con-title">Abstract</h4>'
            f'<p class="g-color-gray-dark-v2 text-justify">{ABSTRACT}</p></div>'
            f"{refs}</div></div></div></div></main></body></html>")


ENGLISH_WITH_AFFS = [_li("Nam, Seung-Min", "Samsung Fire &amp; Marine Insurance Co.", "ADPER0000073146"),
                     _li("Kim, Ki-Woong", "Samsung Fire &amp; Marine Insurance Co.", "ADPER0000043345"),
                     _li("Cho, Sin-Sup", "Dept. of Statistics, Seoul National University", "ADPER0000000483",
                         sep=False)]


def _authors(html):
    return [(a["name"], [x["name"] for x in a["affiliations"]])
            for a in parse_page(html.encode(), "doi", URL)["authors"]]


def _parsed(html):
    return KoreaScience(BeautifulSoup(html, "lxml")).parse()


def test_byline_names_and_affiliations():
    assert _authors(_page(_byline(ENGLISH_WITH_AFFS))) == [
        ("Nam, Seung-Min", ["Samsung Fire & Marine Insurance Co."]),
        ("Kim, Ki-Woong", ["Samsung Fire & Marine Insurance Co."]),
        ("Cho, Sin-Sup", ["Dept. of Statistics, Seoul National University"])]


def test_english_affiliations_win_over_korean_ones():
    korean = [_li("남승민", "삼성화재", "ADPER0000073146"), _li("김기웅", "삼성화재", "ADPER0000043345"),
              _li("조신섭", "서울대학교 통계학과", "ADPER0000000483", sep=False)]
    assert [affs for _, affs in _authors(_page(_byline(ENGLISH_WITH_AFFS, korean)))] == [
        ["Samsung Fire & Marine Insurance Co."], ["Samsung Fire & Marine Insurance Co."],
        ["Dept. of Statistics, Seoul National University"]]


def test_korean_byline_gives_the_affiliation_the_english_one_leaves_out():
    english = [_li("Kwon, Hyuk-Jin", None, "ADPER0000301770"), _li("Lee, Kang-Seok", None, "ADPER0000127806", sep=False)]
    korean = [_li("권혁진", "국토교통부 항공보안과", "ADPER0000301770"),
              _li("이강석", "한국항공대학교 항공운항학과", "ADPER0000127806", sep=False)]
    assert _authors(_page(_byline(english, korean))) == [("Kwon, Hyuk-Jin", ["국토교통부 항공보안과"]),
                                                       ("Lee, Kang-Seok", ["한국항공대학교 항공운항학과"])]


def test_byline_without_person_links_and_nested_parentheses():
    english = [_li("Yang, Elizabeth J.", "Asian Liver Center at Stanford University", None),
               _li("Eom, Ki-Cheol", "Sejong Institute of Data Analysis (SEIDA)", None, sep=False)]
    assert _authors(_page(_byline(english))) == [("Yang, Elizabeth J.", ["Asian Liver Center at Stanford University"]),
                                                ("Eom, Ki-Cheol", ["Sejong Institute of Data Analysis (SEIDA)"])]


def test_isni_badge_is_not_part_of_name_or_affiliation():
    isni = ('<a target="_blank" href="http://nl.go.kr/isni/0000000465075935" title="ISNI:0000000465075935">'
            '<img src="/image/isni-logo2-xs.png"></a>')
    english = [_li("Yeo, In-Kwon", "Dept. of Statistics, Sookmyung Women's University", "ADPER0000009280",
                   sep=False, extra=isni)]
    assert _authors(_page(_byline(english))) == [("Yeo, In-Kwon", ["Dept. of Statistics, Sookmyung Women's University"])]


def test_no_author_is_marked_corresponding():
    out = parse_page(_page(_byline(ENGLISH_WITH_AFFS)).encode(), "doi", URL)
    assert not any(a["is_corresponding"] for a in out["authors"])


def test_abstract_is_the_english_one():
    assert parse_page(_page(_byline(ENGLISH_WITH_AFFS)).encode(), "doi", URL)["abstract"] == ABSTRACT


def test_reference_list_is_whole_and_keeps_printed_dois():
    parsed = _parsed(_page(_byline(ENGLISH_WITH_AFFS)))
    refs = parsed["references"]
    assert [r["position"] for r in refs] == [1, 2, 3]
    assert refs[0]["raw"] == ("Achcar, J. A., Dey, D. K. and Niverthi, M. (1997). A Bayesian approach using "
                              "nonhomogeneous Poisson process for software reliability models")
    assert refs[1]["raw"].endswith("Technometrics, 45, 150-158") and "doi.org" not in refs[1]["raw"]
    assert [r["doi"] for r in refs] == [None, "10.1198/004017003188618788", None]
    assert refs[2]["raw"].endswith("Chapman & Hall/CRC, London")
    assert parsed["references_complete"] is True


def test_gap_in_reference_numbers_is_not_a_whole_list():
    gapped = REFS.replace('id="ref-2"', 'id="ref-4"')
    parsed = _parsed(_page(_byline(ENGLISH_WITH_AFFS), refs=gapped))
    assert len(parsed["references"]) == 3 and parsed["references_complete"] is False


def test_page_without_reference_box_returns_no_references():
    parsed = _parsed(_page(_byline(ENGLISH_WITH_AFFS), refs=""))
    assert not parsed.get("references") and not parsed.get("references_complete")


def test_kci_landing_page_with_the_same_byline_markup_is_not_claimed():
    # KCI's landing template (kci_portal.py, the nearest other Korean template) under a look-alike byline
    head = ('<head><title>Korea Open Access Journals</title>'
            '<link rel="stylesheet" href="/kciportal/resources/landing/css/common.css" type="text/css"></head>')
    parser = KoreaScience(BeautifulSoup(_page(_byline(ENGLISH_WITH_AFFS), head=head), "lxml"))
    assert not parser.is_publisher_specific_parser() and not parser.authors_found()


def test_journal_named_for_korea_science_without_the_platform_title_is_not_claimed():
    head = _head().replace(" | Korea Science</title>", " - Journal of Korea Science</title>")
    assert not KoreaScience(BeautifulSoup(_page(_byline(ENGLISH_WITH_AFFS), head=head), "lxml")).authors_found()
