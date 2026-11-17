"""PUC-Rio's Maxwell digital library record pages (maxwell.vrac.puc-rio.br, DOI prefix 10.17771; oxjob #2338).

Markup is cut down from stored record pages (theses, dissertations, articles). The page has no citation_* meta tags:
the byline is the "Autor(es):" value, each name a link that opens a pop-up card listing the person's role and unit at
PUC-Rio. Both blind labellers take the card's unit and institution as the author's affiliation; a card that lists
several roles (a biography) gives none. Advisors ("Colaborador(es): ... - Orientador") are not authors.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.puc_rio_maxwell import PucRioMaxwell

URL = "https://www.maxwell.vrac.puc-rio.br/colecao.php?strSecao=resultado&nrSeq=25327&idi=1"
HEAD = ('<head><title>Maxwell</title>'
        '<link href="https://www.maxwell.vrac.puc-rio.br/css/novocss.css" rel="stylesheet" type="text/css">'
        '<link href="https://www.maxwell.vrac.puc-rio.br/css/novocss_interno.css" rel="stylesheet" type="text/css">'
        '</head>')
SEARCH_FORM = ('<form id="frmBus" action="colecao.php" method="GET"><label for="strAut">'
               '<span class="txtformFont2 txtformNormal">Autor:</span></label><input type="text" name="strAut"></form>')
ABSTRACT = ("Nesta tese, analisamos a mitigação da culpa coconstruída, discursiva e interacionalmente, por inspetores "
            "de polícia, suspeitos e vítimas em interrogatórios policiais de uma Delegacia da Mulher. ") * 3


def _card(n, lines):
    body = "\n<BR>".join(lines)
    return (f'<center><div id="autor_{n}" class="colecao_tematicas" style="text-align: left; display:none;">'
            f'<div style="display: inline; float: right;"><a href="colecao.php?strSecao=autor&nrSeq=1@1&nrseqaut={n}"'
            f' class="linkNormal linkFont2">Veja mais</a></div><img src="./img/FOTO/FOTO.JPG" width="118">'
            f'<pre style="line-height: 0.8;"><span class="menlatNormal menlatFont2"><strong>{body}\n<BR></strong>'
            f'</span></pre><div id="links"><a href="http://lattes.cnpq.br/1">CURRICULO LATTES</a></div></div></center>')


def _author(n, name, lines):
    return (f'<a href="#" onclick="openCloseMenu(\'autor_{n}\');" class="linkNormal linkFont2">{name}</a><BR>'
            + _card(n, lines))


def _page(authors, label="Autor(es):", head=HEAD, search_form=SEARCH_FORM):
    return (f'<html>{head}<body><div id="corpo">{search_form}'
            '<div style="border-color:#C3B79B; border-width:1px; border-style: solid;">'
            '<span class="txtformNormal txtformFont2" width="130px">T&iacute;tulo:</span>&nbsp;'
            '<span class="txtNormal txtFont2">UM TÍTULO</span><br>'
            '<span class="txtformNormal txtformFont2" width="130px">Institui&ccedil;&atilde;o:</span>&nbsp;'
            '<span class="txtNormal txtFont2">PONTIFÍCIA UNIVERSIDADE CATÓLICA DO RIO DE JANEIRO - PUC-RIO</span><br>'
            f'<span class="txtformNormal txtformFont2" width="110px" valign="top">{label}</span>'
            f'<span bgcolor="#E6E0CF" class="txtNormal txtFont2">{"".join(authors)}</span><br>'
            '<span class="txtformNormal txtformFont2" width="130px">Colaborador(es):</span>&nbsp;'
            '<span class="txtNormal txtFont2"><a href="colecao.php?strSecao=autor&nrSeq=1@1&nrseqaut=2266" '
            'class="linkNormal linkFont2">LILIANA CABRAL BASTOS</a> - Orientador<br></span>'
            '<span class="txtformNormal txtformFont2" colspan="4">Resumo:</span><center>'
            f'<div style="overflow: auto;" class="txtNormal txtFont2">{ABSTRACT}</div></center>'
            '</div></div></body></html>')


STUDENT = _author(14375, "DEBORA MARQUES", ["Marques, Débora", "19-", "Aluna de Pós-Graduação",
                                            "Programa de Pós-Graduação em Estudos da Linguagem", "PUC-Rio"])


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _parse_raw(html):
    return PucRioMaxwell(BeautifulSoup(html, parser="lxml", features="lxml"))


def test_byline_name_and_card_affiliation():
    out = _parse(_page([STUDENT]))
    assert [a["name"] for a in out["authors"]] == ["DEBORA MARQUES"]
    assert out["authors"][0]["affiliations"] == [
        {"name": "Programa de Pós-Graduação em Estudos da Linguagem, PUC-Rio"}]
    assert not out["authors"][0]["is_corresponding"]


def test_advisor_is_not_an_author():
    out = _parse(_page([STUDENT]))
    assert "LILIANA CABRAL BASTOS" not in [a["name"] for a in out["authors"]]


def test_several_authors_each_with_their_own_card():
    second = _author(21546, "TOMAS BONADIU PELOSI", ["Pelosi, Tomas Bonadiu", "19-", "Aluno de Graduação",
                                                     "Curso de Graduação em Engenharia de Produção", "PUC-Rio"])
    out = _parse(_page([STUDENT, second], label="Autor:"))
    assert [a["name"] for a in out["authors"]] == ["DEBORA MARQUES", "TOMAS BONADIU PELOSI"]
    assert out["authors"][1]["affiliations"] == [{"name": "Curso de Graduação em Engenharia de Produção, PUC-Rio"}]


def test_professor_card_and_outside_institution():
    prof = _author(1, "CRISTINA VIANA TENENBAUM", ["Tenenbaum, Cristina Viana", "19-", "Professora",
                                                   "Departamento de Arte e Design", "PUC-Rio"])
    other = _author(2, "GUTEMBERG HESPANHA BRASIL", ["Brasil, Gutemberg Hespanha", "19-", "Professor",
                                                     "Universidade Federal do Espírito Santo", "UFES"])
    out = _parse(_page([prof, other]))
    assert [a["affiliations"] for a in out["authors"]] == [
        [{"name": "Departamento de Arte e Design, PUC-Rio"}],
        [{"name": "Universidade Federal do Espírito Santo, UFES"}]]


def test_card_with_several_roles_is_a_biography_not_an_affiliation():
    bio = _author(7, "MARCELO FERNANDES PEREIRA", [
        "Pereira, Marcelo Fernandes", "19-", "Professor de Especialização",
        "Curso de Especialização na área de Arte e Design", "Ex-Aluno de Pós-Graduação",
        "Programa de Pós-Graduação em Design", "PUC-Rio"])
    out = _parse(_page([bio]))
    assert [a["name"] for a in out["authors"]] == ["MARCELO FERNANDES PEREIRA"]
    assert out["authors"][0]["affiliations"] == []


def test_journal_credited_as_author_gets_no_affiliation():
    journal = _author(9, "REVISTA ATUALIDADE TEOLÓGICA", ["Revista Atualidade Teológica", "2011",
                                                         "Departamento de Teologia", "PUC-Rio"])
    out = _parse(_page([journal]))
    assert [a["name"] for a in out["authors"]] == ["REVISTA ATUALIDADE TEOLÓGICA"]
    assert out["authors"][0]["affiliations"] == []


def test_empty_card_keeps_the_author():
    bare = ('<a href="#" onclick="openCloseMenu(\'autor_5\');" class="linkNormal linkFont2">ADRIANA DACACHE</a><BR>'
            '<center><div id="autor_5" class="colecao_tematicas" style="display:none;"></div></center>')
    out = _parse(_page([bare]))
    assert [(a["name"], a["affiliations"]) for a in out["authors"]] == [("ADRIANA DACACHE", [])]


def test_parser_leaves_the_abstract_to_parse_page():
    parser = _parse_raw(_page([STUDENT]))
    assert parser.is_publisher_specific_parser() and parser.authors_found()
    assert parser.parse()["abstract"] is None


def test_session_check_shell_is_not_claimed():
    shell = f'<html>{HEAD}<body><div id="corpo">{SEARCH_FORM}Verificando sua sessão…</div></body></html>'
    parser = _parse_raw(shell)
    assert parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_look_alike_page_from_another_site_is_not_claimed():
    # The same label/value markup and pop-up cards, served from another library's stylesheet
    other_head = ('<head><title>Biblioteca</title><link href="https://biblioteca.example.br/css/novocss.css" '
                  'rel="stylesheet" type="text/css"></head>')
    parser = _parse_raw(_page([STUDENT], head=other_head))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_search_form_label_without_a_label_tag_is_passed_over():
    # Some record pages print the search box's "Autor:" with no <label> around it, before the record's own byline
    form = ('<div id="advopt" style="display:none;"><span class="txtformFont2 txtformNormal">Autor:</span>&nbsp;'
            '<input type="text" name="strAut" class="campotxtFont2"><br><button>OK</button></div>')
    out = _parse(_page([STUDENT], search_form=form))
    assert [a["name"] for a in out["authors"]] == ["DEBORA MARQUES"]
