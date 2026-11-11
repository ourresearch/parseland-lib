"""Corresponding authors on scielo.br pages (oxjob #2149).

Markup is cut down from stored www.scielo.br pages sampled 11 Nov 2026 (#2149 EXPLORE § 1). SciELO marks the
corresponding author three ways, and Parseland read none of them: the author's own byline dropdown holds the JATS
corresp note (current template); converted older pages put a footnote on the byline name; or a correspondence note
names the author ("Correspondência: X", "Address for correspondence: X"). 91 of 199 sampled works with authors and no
corresponding author had one marked on their page.
"""
from parseland_lib.parse import parse_page

OG = '<meta property="og:url" content="https://www.scielo.br/j/rbz/a/AbCdEf123/?lang=en">'


def _dropdown(i, name, inner="Universidade Federal de Viçosa, Viçosa, MG, Brasil"):
    return (f'<span class="dropdown"><a id="contribGroupTutor{i}" class="dropdown-toggle" data-toggle="dropdown">'
            f'<span> {name} </span></a><ul class="dropdown-menu" role="menu"><strong></strong>{inner}</ul></span>')


def _page(dropdowns, body="", og=OG):
    group = "".join(_dropdown(i, *d) if isinstance(d, tuple) else _dropdown(i, d) for i, d in enumerate(dropdowns, 1))
    return (f'<html><head>{og}</head><body><h1 class="article-title">A title</h1>'
            f'<div class="contribGroup">{group}</div><article id="articleText"><div class="articleSection">'
            f'{body}</div></article></body></html>')


def _corr(html, url="https://doi.org/10.1590/s0103-84782008000900035"):
    return [a["name"] for a in parse_page(html.encode(), "doi", url)["authors"] if a["is_corresponding"]]


def test_corresp_note_in_the_authors_own_dropdown():
    html = _page(["Fernanda Jaqueline Menegusso",
                  ("Fabíola Villa", 'Unioeste, Brazil. fvilla2003@hotmail.com<div class="corresp">*Corresponding '
                                    'author: <a href="mailto:fvilla2003@hotmail.com">fvilla2003@hotmail.com</a></div>'),
                  "Daniel Fernandes da Silva"])
    authors = parse_page(html.encode(), "doi", "https://doi.org/10.1590/0034-737x202168060005")["authors"]
    assert [a["is_corresponding"] for a in authors] == [False, True, False]


def test_bare_corresponding_text_in_a_dropdown_marks_that_author_not_the_next():
    html = _page([("CATARINY CABRAL ALEMAN", 'Universidade Federal de Viçosa; catariny@ufv.br. '
                                             '<strong class="fn-title">*</strong> *Corresponding author'),
                  "PATRICIA ANGÉLICA ALVES MARQUES", "ANA CLAUDIA PACHECO"])
    assert _corr(html) == ["CATARINY CABRAL ALEMAN"]


def test_footnote_on_a_byline_name_with_glued_affiliation_numeral():
    body = ('<p>Tiago Tedeschi dos Santos<sup>I, </sup><span class="ref footnote"><sup class="xref">1</sup>'
            '<span class="refCtt closed"><span class="refCttPadding"> 1 Autor para correspondência. </span></span>'
            '</span>; Samuel Augusto dos Santos<sup>II</sup>; Alex Maiorka<sup>V</sup></p>')
    html = _page(["Tiago Tedeschi dos Santos", "Samuel Augusto dos Santos", "Alex Maiorka"], body)
    assert _corr(html) == ["Tiago Tedeschi dos Santos"]


def test_footnote_note_held_in_a_data_ref_attribute():
    body = ('<p>Otman, J.<sup><b>I</b></sup>; Perugini, M.E.<sup><b>II</b></sup>; Vidotto, M.C.I,<span class="ref '
            'footnote"><sup class="xref"><a href="#nota_ref" data-ref=" * Corresponding Author. Mailing address: '
            'Universidade Estadual de Londrina. Email: macarlos@uel.br "><b>*</b></a></sup></span></p>')
    html = _page(["J. Otman", "M.E. Perugini", "M.C. Vidotto"], body)
    assert _corr(html) == ["M.C. Vidotto"]


def test_one_email_footnote_marks_its_author_but_two_mark_no_one():
    one = ('<p>Tumoru Sera; Gustavo Hiroshi Sera<span class="ref footnote"><sup class="xref"> * </sup><span '
           'class="refCtt closed"> * E-mail: gustavosera@iapar.br </span></span></p>')
    assert _corr(_page(["Tumoru Sera", "Gustavo Hiroshi Sera"], one)) == ["Gustavo Hiroshi Sera"]
    two = ('<p>Ana Lima<span class="ref footnote"><sup class="xref">*</sup><span class="refCtt"> * E-mail: '
           'ana@usp.br </span></span>; Bruno Costa<span class="ref footnote"><sup class="xref">**</sup><span '
           'class="refCtt"> ** E-mail: bruno@usp.br </span></span>; Carla Dias</p>')
    assert _corr(_page(["Ana Lima", "Bruno Costa", "Carla Dias"], two)) == []


def test_correspondence_note_naming_the_author_by_initials():
    body = ('<p>Universidade do Estado do Rio de Janeiro, Brasil</p><p>Correspondência: E. B. B. D. Van Eyken '
            'Mestrado Profissional em Saúde da Família, Universidade Estácio de Sá. elisa.vaneyken@gmail.com</p>')
    html = _page(["Elisa Beatriz Braga Dell'Orto Van Eyken", "Claudia Leite Moraes"], body)
    assert _corr(html) == ["Elisa Beatriz Braga Dell'Orto Van Eyken"]


def test_correspondence_note_with_full_name_and_initials_listed_author():
    body = ('<p>Instituto Nacional de Pesquisas da Amazônia, Manaus, AM, Brazil</p><p>Correspondence to: Levy de '
            'Carvalho Gomes, Embrapa Amazônia Ocidental, Manaus, AM, Brazil e-mail: levy@cpaa.embrapa.br</p>')
    html = _page(["L. C. Gomes", "C. A. R. M. Araujo-Lima", "A. R. Chippari-Gomes"], body)
    assert _corr(html) == ["L. C. Gomes"]


def test_data_availability_line_is_no_mark():
    body = ('<p>Data Availability Statement: the datasets are available from the corresponding author upon '
            'reasonable request. Correspondence: Avenida Sete de Setembro, 817, Passo Fundo, RS.</p>')
    assert _corr(_page(["Rodrigo Arnold Tisot", "Juliano Silveira Luiz Vieira"], body)) == []


def test_same_note_on_every_author_marks_no_one():
    fn = ('<span class="ref footnote"><sup class="xref">1</sup><span class="refCtt"> 1 Autor para correspondência'
          '</span></span>')
    body = f'<p>Ana Lima{fn}; Bruno Costa{fn}</p>'
    assert _corr(_page(["Ana Lima", "Bruno Costa"], body)) == []


def test_only_scielo_br_pages_are_read():
    body = ('<p>Ana Lima; Bruno Costa<span class="ref footnote"><sup class="xref">1</sup><span class="refCtt"> 1 '
            'Autor para correspondência</span></span></p>')
    og = '<meta property="og:url" content="https://example.org/article/1">'
    html = (f'<html><head>{og}<meta name="citation_author" content="Lima, Ana"><meta name="citation_author" '
            f'content="Costa, Bruno"></head><body><a href="https://www.scielo.br/j/x">SciELO</a>{body}</body></html>')
    assert _corr(html, "https://example.org/article/1") == []
