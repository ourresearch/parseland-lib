"""Revista FT (revistaft.com.br) article pages (oxjob #2339).

Markup cut down from stored pages of the site (17 Nov 2026). The site is a WordPress blog: the byline is the first
right-aligned paragraph of the post body, each name followed by a footnote marker (<sup>1</sup>, a Word footnote link
"[1]", a Unicode superscript "¹" or "*"), and the footnotes sit in right-aligned paragraphs after the post's last
separator. No citation_author tags, so Parseland read no authors or affiliations before.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.revistaft import RevistaFT

URL = "https://revistaft.com.br/um-artigo/"
HEAD = ('<meta name="citation_journal_title" content="Revista ft" />'
        '<link rel="canonical" href="https://revistaft.com.br/um-artigo/" />')
HR = '<hr class="wp-block-separator"/>'
ABSTRACT = ("Este estudo teve como objetivo geral apresentar uma solução voltada à redução do tempo de ciclo no processo "
            "de usinagem realizada em uma empresa fabricante de motores a combustão interna localizada em Manaus.")


def _page(byline, notes="", refs="", head=HEAD):
    body = (f'<p>TITLE IN ENGLISH</p><p class="has-text-align-center">REGISTRO DOI: 10.69849/revistaft/x1</p>{HR}'
            f'<p class="has-text-align-right">{byline}</p>{HR}<p><strong>RESUMO</strong></p><p>{ABSTRACT}</p>'
            f'<p><strong>1 INTRODUÇÃO</strong></p><p>Texto.</p>{refs}{HR if notes else ""}{notes}')
    return (f'<html><head>{head}</head><body><article class="post"><header><h1 class="entry-title">TITULO</h1></header>'
            f'<div class="entry-content clear">{body}</div></article></body></html>')


def _authors(html):
    return [(a["name"], [x["name"] for x in a["affiliations"]]) for a in parse_page(html.encode(), "doi", URL)["authors"]]


def test_sup_markers_link_footnotes_and_degree_only_note_is_dropped():
    html = _page('Eduardo Antonio Tiodozio de França<sup>1</sup>, Orientador: Dyogo Bortot<sup>2</sup>',
                 '<p class="has-text-align-right"><sup>1</sup> Graduando em 2024 (UNIVEL 2022).<br><sup>2</sup> Mestre.</p>')
    assert _authors(html) == [("Eduardo Antonio Tiodozio de França", ["Graduando em 2024 (UNIVEL 2022)."]),
                              ("Dyogo Bortot", [])]


def test_honorifics_and_role_labels_are_stripped_and_emails_dropped():
    html = _page('Breno Saldanha<sup>1</sup><br>Dra. Siomara Rocha<sup>2</sup><br>'
                 'Orientador (a): Prof. (a) Dr. (a) Daniela Cristina Lopes de Abreu<sup>2</sup>',
                 '<p class="has-text-align-right"><sup>1 </sup>Bacharelando da Fundação Centro de Análise – FUCAPI, '
                 'Manaus/AM. E-mail: breno@example.com<br><sup>2</sup> Professora da Fundação Centro de Análise – FUCAPI. '
                 'ORCID: https://orcid.org/0000-0002-0650-5961</p>')
    got = _authors(html)
    assert [n for n, _ in got] == ["Breno Saldanha", "Siomara Rocha", "Daniela Cristina Lopes de Abreu"]
    assert got[0][1] == ["Bacharelando da Fundação Centro de Análise – FUCAPI, Manaus/AM."]
    assert got[1][1] == ["Professora da Fundação Centro de Análise – FUCAPI."]
    assert not any("@" in a or "orcid" in a.lower() for _, affs in got for a in affs)


def test_unicode_superscripts_and_shared_notes():
    html = _page('Raissa Oliveira Silva¹; Josiane Steil Siewert²; Bruna Lira Santos Ribeiro¹.',
                 '<p class="has-text-align-right">¹Centro Universitário do Norte de Minas.<br>'
                 '²Instituto Federal de Santa Catarina.</p>')
    assert _authors(html) == [("Raissa Oliveira Silva", ["Centro Universitário do Norte de Minas."]),
                              ("Josiane Steil Siewert", ["Instituto Federal de Santa Catarina."]),
                              ("Bruna Lira Santos Ribeiro", ["Centro Universitário do Norte de Minas."])]


def test_word_footnote_links_and_one_note_for_several_markers():
    html = _page('Thays Vitória Andrade dos Santos<a href="#_ftn1" id="_ftnref1">[1]</a><br>'
                 'Fabrícia Gomes da Silva<a href="#_ftn2" id="_ftnref2">[2]</a>',
                 '<p class="has-text-align-right"><a href="#_ftnref1" id="_ftn1">[1]</a> Docente da Universidade '
                 'Estadual do Piauí (UESPI). E-mail: a@b.br</p>'
                 '<p class="has-text-align-right"><a href="#_ftnref2" id="_ftn2">[2]</a> Mestre em Educação pela '
                 'Universidade Estadual do Ceará (UECE).</p>')
    assert _authors(html) == [("Thays Vitória Andrade dos Santos", ["Docente da Universidade Estadual do Piauí (UESPI)."]),
                              ("Fabrícia Gomes da Silva", ["Mestre em Educação pela Universidade Estadual do Ceará (UECE)."])]
    shared = _page('Tiago Cunha Berno Campos<sup>1</sup>,<br>Cezar Ernani Mancini<sup>2</sup>',
                   '<p class="has-text-align-right"><sup>1,2</sup>Discentes do Centro Universitário de Valença – UNIFAA.</p>')
    assert _authors(shared) == [("Tiago Cunha Berno Campos", ["Discentes do Centro Universitário de Valença – UNIFAA."]),
                                ("Cezar Ernani Mancini", ["Discentes do Centro Universitário de Valença – UNIFAA."])]
    one_word = _page('Leidiane Fernandes Moreira<sup>1</sup>',
                     '<p class="has-text-align-right"><sup>1</sup>Mestranda Unicarioca-Rio Comprido – ORCID nº '
                     '0009-0001-4310-3611 / E-mail: l@example.com – Link Lattes: https://lattes.cnpq.br/42258</p>')
    assert _authors(one_word) == [("Leidiane Fernandes Moreira", ["Mestranda Unicarioca-Rio Comprido"])]


def test_note_continuation_line_and_institution_label():
    html = _page('Paulo Rogério Cortêz Leal*<br>André Senna Andrade<sup>1</sup>',
                 '<p class="has-text-align-right">*Liga Acadêmica de Fisioterapia Desportiva – LAFDE<br>'
                 'Faculdade AGES, Jacobina -BA</p><p class="has-text-align-right"><sup>1</sup> Graduando em Medicina<br>'
                 'Instituição: Faculdade de Medicina Estácio (IDOMED) – Juazeiro-BA<br>E-mail: x@y.com</p>')
    assert _authors(html) == [
        ("Paulo Rogério Cortêz Leal", ["Liga Acadêmica de Fisioterapia Desportiva – LAFDE Faculdade AGES, Jacobina -BA"]),
        ("André Senna Andrade", ["Faculdade de Medicina Estácio (IDOMED) – Juazeiro-BA"])]


def test_unmarked_note_goes_to_every_author():
    html = _page('Felipe Rodrigues Ferreira;<br>Bruno Kilmer Nunes Saraiva;<br>Orientadora: Prof<sup>a</sup>. Diana Guerra',
                 '<p class="has-text-align-right">Curso de Odontologia, Faculdade Ideal Wyden</p>')
    got = _authors(html)
    assert [n for n, _ in got] == ["Felipe Rodrigues Ferreira", "Bruno Kilmer Nunes Saraiva", "Diana Guerra"]
    assert all(affs == ["Curso de Odontologia, Faculdade Ideal Wyden"] for _, affs in got)


def test_byline_without_notes_gives_authors_only_and_nobody_is_corresponding():
    html = _page('Jammylly Fonseca Silva;<br>Fabiana de Sá Ferreira.')
    out = parse_page(html.encode(), "doi", URL)
    assert [a["name"] for a in out["authors"]] == ["Jammylly Fonseca Silva", "Fabiana de Sá Ferreira"]
    assert not any(a["is_corresponding"] or a["affiliations"] for a in out["authors"])


def test_corresponding_note_is_not_an_affiliation():
    html = _page('Viviane Brito Andrade<sup><strong>1*</strong></sup>',
                 '<p class="has-text-align-right"><sup>1</sup> Discente do Instituto Federal de São Paulo – IFSP.</p>'
                 '<p class="has-text-align-right"><sup><strong>∗</strong></sup> Autor correspondente: v@example.com</p>')
    assert _authors(html) == [("Viviane Brito Andrade", ["Discente do Instituto Federal de São Paulo – IFSP."])]


def test_abstract_is_what_the_page_got_before():
    notes = '<p class="has-text-align-right"><sup>1</sup> Universidade X.</p>'
    ours = parse_page(_page('Breno Saldanha<sup>1</sup>', notes).encode(), "doi", URL)
    unclaimed = parse_page(_page('Breno Saldanha<sup>1</sup>', notes, head="").encode(), "doi", URL)
    assert ours["authors"] and not unclaimed["authors"]
    assert ours["abstract"] == unclaimed["abstract"] and ours["abstract"].startswith(ABSTRACT)


def test_reference_list():
    refs = ('<p><strong>REFERÊNCIAS</strong></p><p>AGUIAR, P. R. Análise. Revista, v. 33, 2021.</p>'
            '<p>BAKER, A. High-speed machining. J. Manuf. Sci. 2020. https://doi.org/10.1115/1.4045617.</p>')
    soup = BeautifulSoup(_page('Breno Saldanha<sup>1</sup>', '<p class="has-text-align-right"><sup>1</sup> Universidade X.</p>',
                               refs), "lxml")
    out = RevistaFT(soup).parse()
    assert [r["position"] for r in out["references"]] == [1, 2]
    assert out["references"][0]["raw"] == "AGUIAR, P. R. Análise. Revista, v. 33, 2021."
    assert out["references"][1]["doi"] == "10.1115/1.4045617"
    assert out["references_complete"] is False  # unnumbered paragraphs: no evidence the list is whole
    assert out["acknowledgments"] is None and out["funding_statement"] is None
    ol = '<p><strong>REFERÊNCIAS BIBLIOGRÁFICAS</strong></p><ol><li>Um. 2020.</li><li>Dois. 2021.</li></ol>'
    out = RevistaFT(BeautifulSoup(_page('Breno Saldanha', refs=ol), "lxml")).parse()
    assert [r["raw"] for r in out["references"]] == ["Um. 2020.", "Dois. 2021."] and out["references_complete"] is True


def test_reference_list_ends_at_an_appendix_heading_and_numbered_heading_is_found():
    refs = ('<p><strong>8 – REFERÊNCIAS:</strong></p><p>1 CALVO-LOBO, C. Nursing guidelines. 2023.</p>'
            '<p>2 ALI, A. Intervenção. 2022.</p><p class="has-text-align-center"><strong>ANEXO A – TERMO</strong></p>'
            '<p>Texto do anexo.</p>')
    out = RevistaFT(BeautifulSoup(_page('Breno Saldanha', refs=refs), "lxml")).parse()
    assert [r["raw"] for r in out["references"]] == ["1 CALVO-LOBO, C. Nursing guidelines. 2023.", "2 ALI, A. Intervenção. 2022."]
    assert out["references_complete"] is True  # numbered 1..n with no gap


def test_section_called_referencial_teorico_is_not_the_reference_list():
    refs = '<p><strong>REFERENCIAL TEÓRICO</strong></p><p>Texto do referencial.</p>'
    out = RevistaFT(BeautifulSoup(_page('Breno Saldanha', refs=refs), "lxml")).parse()
    assert out["references"] == [] and out["references_complete"] is False


def test_lookalike_wordpress_page_is_not_claimed():
    other = ('<meta name="citation_journal_title" content="Revista Ibero-Americana" />'
             '<link rel="canonical" href="https://periodicorease.pro.br/rease/article/x" />')
    html = _page('Breno Saldanha<sup>1</sup>', '<p class="has-text-align-right"><sup>1</sup> Universidade X.</p>', head=other)
    soup = BeautifulSoup(html, "lxml")
    assert not RevistaFT(soup).is_publisher_specific_parser()
    assert not RevistaFT(soup).authors_found()
    assert parse_page(html.encode(), "doi", URL)["authors"] == []
    # the journal title alone, on another host, is not enough
    copy_ = HEAD.replace("https://revistaft.com.br/", "https://mirror.example.org/")
    assert not RevistaFT(BeautifulSoup(_page('Breno Saldanha', head=copy_), "lxml")).is_publisher_specific_parser()


def test_biographies_are_not_affiliations_and_degrees_after_a_role_are_cut():
    # A role at an organisation keeps; the degrees after it (a sentence or a clause) are biography and go.
    html = _page('Anna Lara Chaves Oliveira Cruz<strong><sup>1</sup></strong><br>'
                 'Prof. Orientadora: Bianca Silva Oliveira<strong><sup>2</sup></strong><br>'
                 'Anna Kellssya Leite Filgueira<sup>3</sup>',
                 '<p class="has-text-align-right"><strong>1</strong> Alunas do Curso de Direito da Faculdade Independente '
                 'do Nordeste- FAINOR, e-mail: annalaracruz@gmail .com e brendamirandas123@gamail.com</p>'
                 '<p class="has-text-align-right"><strong>2 </strong>Docente do Curso de graduação em Direito da UNEB e '
                 'da Fainor, advogada Mestra em Direito pela Universidade Federal da Bahia (UFBA). Graduada em Direito '
                 'pela Universidade Estadual do Sudoeste da Bahia (UESB).</p>'
                 '<p class="has-text-align-right"><sup>3</sup> Docente do Curso Superior de Fisioterapia da Universidade '
                 'Estadual da Paraíba (UEPB) Campus I. Mestre em Ciências da Tecnologia em Saúde (UEPB/NUTES) e '
                 'doutoranda em Fisioterapia pela UFRN.</p>')
    assert _authors(html) == [
        ("Anna Lara Chaves Oliveira Cruz", ["Alunas do Curso de Direito da Faculdade Independente do Nordeste- FAINOR"]),
        ("Bianca Silva Oliveira", ["Docente do Curso de graduação em Direito da UNEB e da Fainor."]),
        ("Anna Kellssya Leite Filgueira", ["Docente do Curso Superior de Fisioterapia da Universidade Estadual da Paraíba "
                                          "(UEPB) Campus I."])]
    # A CV (three or more degrees) and a narrated biography give no affiliation; a lone degree note still does.
    cv = _page('Gustavo Araújo Vilas Boas<sup>1</sup><br>Mestre Único da Silva<sup>2</sup>',
               '<p class="has-text-align-right"><sup>1</sup> Graduado em Direito pela Universidade Ceuma. Pós-graduado em '
               'Direito Constitucional Aplicado pela Universidade Ceuma. Pós-graduado em Criminologia pela Faculdade de '
               'Tecnologia de Alagoas. Sócio do Escritório Moreira Gomes Vilas Boas Advogados Associados.</p>'
               '<p class="has-text-align-right"><sup>2</sup> Mestre em Gestão, Universidade Federal de Roraima</p>')
    assert _authors(cv) == [("Gustavo Araújo Vilas Boas", []),
                            ("Mestre Único da Silva", ["Mestre em Gestão, Universidade Federal de Roraima"])]
    narrated = _page('JESUS, Moisés de<sup>1</sup>',
                     '<p class="has-text-align-right"><sup>1</sup> Moisés de Jesus é formado em Administração pela '
                     'Universidade Federal de Mato Grosso (UFMT) e mestre pelo Programa de Pós-Graduação PROFNIT(UFMT)</p>')
    assert _authors(narrated) == [("Moisés de JESUS", [])]  # "FAMILY, Given" with no ";" is one name, not two


def test_star_runs_are_different_markers_and_address_notes_keep():
    html = _page('Sidinei Benedito*<br>Professora-Orientadora Ma. Josiane Luiz**',
                 '<p class="has-text-align-right">*Estudante do curso de Bacharelado em Administração da Faculdade Cristo '
                 'Rei de Cornélio Procópio. E-mail: s@example.com<br>** Docente do curso de Administração da Faculdade '
                 'Cristo Rei de Cornélio Procópio. E-mail: j@example.br</p>')
    assert _authors(html) == [
        ("Sidinei Benedito", ["Estudante do curso de Bacharelado em Administração da Faculdade Cristo Rei de Cornélio Procópio."]),
        ("Josiane Luiz", ["Docente do curso de Administração da Faculdade Cristo Rei de Cornélio Procópio."])]
    museum = _page('Marcos Pereira Magalhães<sup>1</sup><br>Lucila Nara Rambo<sup>2</sup>',
                   '<p class="has-text-align-right"><sup>1</sup>Museu Paraense Emílio Goeldi, Belém, PA, Brasil. '
                   'm@example.br<br><a href="https://orcid.org/0000-0003-1711-8235">https://orcid.org/0000-0003-1711-8235</a>'
                   '<br><sup>2</sup> Colaborating specialist in Biomagnetism, Curitiba, Paraná, Brazil</p>')
    assert _authors(museum) == [("Marcos Pereira Magalhães", ["Museu Paraense Emílio Goeldi, Belém, PA, Brasil."]),
                                ("Lucila Nara Rambo", ["Colaborating specialist in Biomagnetism, Curitiba, Paraná, Brazil"])]
