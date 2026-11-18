"""ABEPRO proceedings pages (abepro.org.br publicacoes/artigo.asp and proceedings/artigo.asp; DOI prefix 10.14488),
oxjob #2339.

Markup is cut down from stored pages of the ENEGEP, ICIEOM and CNEG paper pages: one div#resultado with
"<b>RESUMO:</b><BR> text <BR><BR><b>PALAVRAS-CHAVE:</b>" in the left column and "<b>AUTORES:</b>" in the right one,
each author a text line followed by <small><i>...</i></small>. Newer pages add citation_author / citation_title meta
tags inside the body; older ones have none. The generic parser reads the meta-tag names and nothing else. Affiliations
are not read (the parser's docstring says why), so the <small> slot never becomes a name or an affiliation. The journals ABEPRO also hosts (Produção Online, BJOPM) run Open Journal Systems and
are not this template.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.abepro import Abepro

URL = "https://abepro.org.br/publicacoes/artigo.asp?e=enegep&a=2023&c=46156"
ABSTRACT = ("No contexto atual de mercado, as organizacoes sao compelidas a demonstrar seu desempenho. "
            "Este artigo analisa os efeitos sobre o desempenho de um sistema de medicao arquitetado.")


def _author(name, aff, meta=True):
    tag = f'<meta name="citation_author" content= "{name}">' if meta else ""
    return f"{name}<BR><small><i>{aff}</i></small>\n{tag}\n"


def _page(authors, abstract=ABSTRACT, title="Anais Enegep | Proceedings ICIEOM", meta=True, head=""):
    byline = "<BR><BR>".join(_author(n, a, meta) for n, a in authors)
    return f"""<html><head><meta name="viewport" content="width=device-width, initial-scale=1">{head}
<title>{title}</title></head><body><div class="container">
<div class="row"><div class="col col-md-12" style="padding:0px 50px"><div id="resultado">
<small><i>ENEGEP2017_TN_STO_240_391_31241</i></small>
<h3 style="color:#FF6600">COMBINANDO TOYOTA KATA E PERFORMANCE ALIGNMENT MATRIX</h3><BR>
<div class="row"><div class="col col-sm-8">
<b>ÁREA:</b> 01. GESTÃO DA PRODUÇÃO<BR><BR>
<b>RESUMO:</b><BR>
{abstract}<BR><BR>
<b>PALAVRAS-CHAVE:</b><BR> <i>desempenho; toyota kata.</i>
<BR><BR>DOI: <a href="http://dx.doi.org/10.14488/ENEGEP2017_TN_STO_240_391_31241">10.14488/enegep2017_tn_sto_240_391_31241</a>
</div>
<div class="col col-sm-4"><b>AUTORES:</b><BR><BR>
{byline}
</div></div>
<div class="text-center"><a href="http://www.abepro.org.br/biblioteca/TN_STO_240_391_31241.pdf"><h3>Clique aqui</h3></a></div>
</div></div></div>
<center><b>ISSN ENEGEP:</b> 23183349 / <b>ISSN ICIEOM:</b> 23178000</center></div></body></html>"""


def _parser(html):
    return Abepro(BeautifulSoup(html, parser="lxml", features="lxml"))


def test_authors_from_the_byline():
    out = parse_page(_page([("VITOR LUIS ALVES DOS SANTOS", "FEI"), ("GABRIELA SCUR", "UNIVERSIDADE FEDERAL DA PARAÍBA/PPGEPS")]).encode(), "doi", URL)
    assert [a["name"] for a in out["authors"]] == ["VITOR LUIS ALVES DOS SANTOS", "GABRIELA SCUR"]
    assert all(a["affiliations"] == [] for a in out["authors"])
    assert not any(a["is_corresponding"] for a in out["authors"])
    assert out["abstract"] == ABSTRACT


def test_older_page_without_meta_tags():
    html = _page([("ADRIANO PEREIRA DA SILVA", "UFBA"), ("FRANCISCO FREIRES", "UFBA")], meta=False,
                 title="Proceedings ICIEOM")
    out = parse_page(html.encode(), "doi", URL)
    assert [a["name"] for a in out["authors"]] == ["ADRIANO PEREIRA DA SILVA", "FRANCISCO FREIRES"]
    assert out["abstract"] == ABSTRACT


def test_numbered_or_empty_slot_is_never_a_name():
    out = _parser(_page([("FERNANDA ROCHA", "441"), ("SELMA REGINA MARTINS OLIVEIRA", "")])).parse()
    assert [a["name"] for a in out["authors"]] == ["FERNANDA ROCHA", "SELMA REGINA MARTINS OLIVEIRA"]
    assert all(a["affiliations"] == [] for a in out["authors"])


def test_abstract_stops_before_keywords():
    out = parse_page(_page([("GABRIELA SCUR", "FEI")]).encode(), "doi", URL)
    assert out["abstract"] == ABSTRACT
    assert "PALAVRAS" not in out["abstract"] and "toyota kata." not in out["abstract"]


def test_cp1252_control_character_becomes_its_letter():
    text = ABSTRACT.replace("organizacoes", "specialists\u0092 organizacoes")
    out = _parser(_page([("GABRIELA SCUR", "FEI")], abstract=text)).parse()
    assert "specialists’ organizacoes" in out["abstract"]


def test_empty_abstract_is_none():
    out = _parser(_page([("GABRIELA SCUR", "FEI")], abstract="")).parse()
    assert out["abstract"] is None
    assert out["authors"][0]["name"] == "GABRIELA SCUR"


def test_new_fields_are_absent():
    out = _parser(_page([("GABRIELA SCUR", "FEI")])).parse()
    assert out["acknowledgments"] is None and out["funding_statement"] is None
    assert out["references"] is None and out["references_complete"] is False


def test_claims_every_event_title():
    for title in ("Anais Enegep | Proceedings ICIEOM", "Proceedings IJCIEOM", "Proceedings ICIEOM", "Anais CNEG"):
        assert _parser(_page([("GABRIELA SCUR", "FEI")], title=title)).is_publisher_specific_parser(), title


def test_look_alike_page_is_not_claimed():
    # Another Brazilian site with the same Portuguese labels and a div#resultado, under its own title.
    p = _parser(_page([("GABRIELA SCUR", "FEI")], title="Anais do Congresso Brasileiro de Custos"))
    assert not p.is_publisher_specific_parser()
    assert not p.authors_found()
    # ABEPRO's own OJS journal (Produção Online): its title names the journal, never the event pages' title.
    ojs = ('<html><head><title>Evoluindo da cadeia de valor | Revista Produção Online</title>'
           '<meta name="generator" content="Open Journal Systems 3.3.0.13"></head><body>'
           '<div class="pkp_structure_page"><b>AUTORES:</b> Marciano Silva Santos</div></body></html>')
    assert not _parser(ojs).is_publisher_specific_parser()


def test_page_without_the_frame_is_not_claimed():
    html = ('<html><head><title>Anais Enegep | Proceedings ICIEOM</title></head><body>'
            '<div id="resultado_pesquisa"><div class="div_trabalho">listing</div></div></body></html>')
    p = _parser(html)
    assert not p.is_publisher_specific_parser()
    assert not p.authors_found()


def test_line_ends_in_markup_are_not_paragraphs():
    first, second = ABSTRACT.split(". ", 1)
    out = _parser(_page([("GABRIELA SCUR", "FEI")], abstract=f"{first}.\n   {second}<BR>Segundo paragrafo do resumo.")).parse()
    assert out["abstract"] == f"{first}. {second}\nSegundo paragrafo do resumo."


def test_utf8_letter_read_as_latin1_is_repaired():
    out = _parser(_page([("LUCKAS STEPHANIO REIS DE ARAÃ\u009aJO", "UFPA")])).parse()
    assert out["authors"][0]["name"] == "LUCKAS STEPHANIO REIS DE ARAÚJO"
