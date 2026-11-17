"""SCIndeks (Serbian Citation Index, scindeks.ceon.rs and scindeks-zbornici.ceon.rs) article pages (oxjob #2338).

Markup is cut down from stored pages of CEON/CEES's index (DOI prefix 10.5937), which hosts most Serbian journals'
article pages. The meta tags give the byline (citation_author) and the abstract (citation_abstract) but no
affiliations; the page prints them under the byline, tied to authors by superscript letters or shared by all.
It also prints the work's funding projects under the label "Projekat" and its whole reference list in a table.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.scindeks import SCIndeks

URL = "https://doi.org/10.5937/vojdelo1901164M"
OG_IMAGE = '<meta property="og:image" content="https://scindeks.ceon.rs/images/scindeks-logo_fb_sr.png" />'
ABSTRACT = ("The relation of personalized religiosity and militaristic political culture is studied on the European "
            "Values Study data for Serbia, wave 2008, with a regression of religiosity on the preferred political "
            "order; militaristic political culture is a positive predictor of personalized religiosity.")


def _page(names, byline, afil, extra="", refs="", og=OG_IMAGE, abstract_meta=True):
    metas = "".join(f'<meta name="citation_author" content="{n}" />' for n in names)
    if abstract_meta:
        metas += f'<meta name="citation_abstract" content="{ABSTRACT}" />'
    ref_rows = "".join(
        f'<tr><td class="cl_reflink"><p><a id="inGS{i}" href="https://scholar.google.com/x">GS</a></p></td>'
        f'<td class="cl_ref{1 + i % 2}">{r}</td></tr>' for i, r in enumerate(refs or [], 1))
    ref_table = ('<tr id="ctl00_cph1_Details1_ReferencesCont"><td colspan="2"><table>'
                 '<tr><td></td><td><div class="cl_section cl_section_up">Reference</div></td></tr>'
                 f'{ref_rows}<tr><td class="cl_reflink">&nbsp;</td><td>&nbsp;</td></tr></table></td></tr>'
                 if refs else "")
    return (f'<html><head><title>Naslov</title><meta name="citation_title" content="A title" />{metas}{og}</head>'
            f'<body><table><tr><td colspan="2"><div class="cl_nas">Naslov</div>'
            f'<div class="cl_aut">{byline}</div><div class="cl_afil">{afil}</div>{extra}'
            '<div><div class="cl_section">Sažetak</div><div class="cl_saz cl_saz_ab">Srpski sažetak.</div></div>'
            '<div class="cl_other_ab hidden"><div class="cl_section">Abstract</div>'
            f'<div class="cl_saz cl_saz_ab">{ABSTRACT}</div></div></td></tr>{ref_table}</table></body></html>')


def _a(name, n):
    return f"<a href='Related.aspx?artaun={n}'>{name}</a>"


EMAIL = "<br /><span class='boldGrey'>e-adresa</span>:&nbsp;<a href='mailto:a.b@example.rs'>a.b@example.rs</a>"
CF_EMAIL = ("<br /><span class='cl_indent'><span class='boldGrey'>e-adresa</span>:&nbsp;<a href=\"/cdn-cgi/l/"
            "email-protection#12\"><span class=\"__cf_email__\" data-cfemail=\"12\">[email&#160;protected]</span></a>"
            "</span><div class=\"cl_other_cr hidden\"> </div>")


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _affs(out):
    return [[x["name"] for x in a["affiliations"]] for a in out["authors"]]


def test_lettered_affiliations_go_to_their_authors():
    byline = _a("Maksimović Andrijana", 1) + "<sup>a</sup>, " + _a("Milosavljević Zoran", 2) + "<sup>b</sup>"
    afil = ("<sup>a</sup>Državni univerzitet u Novom Pazaru, Srbija<br /><sup>b</sup>Institut za političke studije, "
            "Beograd, Srbija<br />" + EMAIL)
    out = _parse(_page(["Maksimović, Andrijana", "Milosavljević, Zoran"], byline, afil))
    assert [a["name"] for a in out["authors"]] == ["Maksimović, Andrijana", "Milosavljević, Zoran"]
    assert _affs(out) == [["Državni univerzitet u Novom Pazaru, Srbija"], ["Institut za političke studije, Beograd, Srbija"]]


def test_unlettered_affiliation_is_shared_and_email_is_not_an_affiliation_or_a_mark():
    byline = _a("Jovanović Stevan", 1) + ", " + _a("Jovčić Ljiljana", 2)
    afil = "Akademija strukovnih studija, Odsek visoka zdravstvena škola, Beograd<br />" + EMAIL
    out = _parse(_page(["Jovanović, Stevan", "Jovčić, Ljiljana"], byline, afil))
    assert _affs(out) == [["Akademija strukovnih studija, Odsek visoka zdravstvena škola, Beograd"]] * 2
    assert not any(a["is_corresponding"] for a in out["authors"])


def test_newer_markup_with_protected_email_and_two_affiliations_joined_by_plus():
    byline = _a("Momirović Anđela", 1)
    afil = ('<div class="cl_afil_mrg">Univerzitet u Beogradu, Geografski fakultet, Srbija + Univerzitet u Beogradu, '
            'Fakultet organizacionih nauka, Srbija<br /></div>' + CF_EMAIL)
    out = _parse(_page(["Momirović, Anđela"], byline, afil))
    assert _affs(out) == [["Univerzitet u Beogradu, Geografski fakultet, Srbija",
                           "Univerzitet u Beogradu, Fakultet organizacionih nauka, Srbija"]]


def test_none_placeholder_is_not_an_affiliation():
    byline = _a("Radovanović Radovan", 1) + "<sup>a</sup>, " + _a("Đokić Nebojša", 2) + "<sup>b</sup>"
    afil = "<sup>a</sup>Policijska akademija, Beograd<br /><sup>b</sup>nema<br />"
    out = _parse(_page(["Radovanović, Radovan", "Đokić, Nebojša"], byline, afil))
    assert _affs(out) == [["Policijska akademija, Beograd"], []]


def test_abstract_is_the_meta_tags_english_version():
    byline = _a("Mršević Zorica", 1)
    out = _parse(_page(["Mršević, Zorica"], byline, "Institut društvenih nauka, Beograd, Srbija<br />"))
    assert out["abstract"] == ABSTRACT


def _soup_parse(html):
    return SCIndeks(BeautifulSoup(html, "lxml")).parse()


def test_funding_project_both_markups():
    byline = _a("Živančev Dragan", 1)
    flex = ("<div><div style='display:flex'><div><span class='boldGrey'>Projekat</span>:</div>"
            "<div style='margin-left:3px'>Savremeno oplemenjivanje strnih žita (MPNTR - 31066)<br/>"
            "Second project (EU-HE - 101094070)</div></div><br/></div>")
    out = _soup_parse(_page(["Živančev, Dragan"], byline, "Institut, Novi Sad<br />", extra=flex))
    assert out["funding_statement"] == "Savremeno oplemenjivanje strnih žita (MPNTR - 31066)\nSecond project (EU-HE - 101094070)"
    indent = ("<div><span class='cl_indent'><span class='boldGrey'>Projekat</span>: The reported study was funded by "
              "the Russian Academy, project 1.1.6.2</span><br/></div>")
    out = _soup_parse(_page(["Živančev, Dragan"], byline, "Institut, Novi Sad<br />", extra=indent))
    assert out["funding_statement"] == "The reported study was funded by the Russian Academy, project 1.1.6.2"
    assert out["acknowledgments"] is None
    out = _soup_parse(_page(["Živančev, Dragan"], byline, "Institut, Novi Sad<br />"))
    assert out["funding_statement"] is None


REFS = ["Almond, G.A., Verba, S. (2000) Civilna kultura. Zagreb: Politička kultura",
        "Berger, P. (2008) Desekularizacija sveta. Novi Sad: Mediterran publishing",
        "Đukić, S. (2011) Uloga društvenih medija. <i>Marketing</i>, 42(1), 17-26. https://doi.org/10.5937/markt1101017D"]


def test_reference_list_in_order_with_printed_doi_and_whole():
    out = _soup_parse(_page(["Mršević, Zorica"], _a("Mršević Zorica", 1), "Institut<br />", refs=REFS))
    refs = out["references"]
    assert [r["position"] for r in refs] == [1, 2, 3]
    assert refs[0]["raw"] == "Almond, G.A., Verba, S. (2000) Civilna kultura. Zagreb: Politička kultura"
    assert refs[0]["doi"] is None
    assert refs[2]["raw"].endswith("17-26. https://doi.org/10.5937/markt1101017D")
    assert refs[2]["doi"] == "10.5937/markt1101017D"
    assert out["references_complete"] is True


def test_typed_numbers_with_a_gap_are_not_a_whole_list():
    typed = [f"{n}. Author{n}, A. (2010) Title {n}. Journal, 1, 1-2" for n in (1, 2, 3, 5)]
    out = _soup_parse(_page(["Mršević, Zorica"], _a("Mršević Zorica", 1), "Institut<br />", refs=typed))
    assert len(out["references"]) == 4
    assert out["references_complete"] is False


def test_no_reference_table():
    out = _soup_parse(_page(["Mršević, Zorica"], _a("Mršević Zorica", 1), "Institut<br />"))
    assert out["references"] is None and out["references_complete"] is False


def test_look_alike_markup_on_another_site_is_not_claimed():
    byline = _a("Maksimović Andrijana", 1) + "<sup>a</sup>"
    afil = "<sup>a</sup>Državni univerzitet u Novom Pazaru, Srbija<br />"
    other = '<meta property="og:image" content="https://anali.rs/wp-content/uploads/2020/09/thumb5G.jpg" />'
    for og in (other, ""):
        html = _page(["Maksimović, Andrijana"], byline, afil, og=og)
        parser = SCIndeks(BeautifulSoup(html, "lxml"))
        assert not parser.authors_found() and not parser.is_publisher_specific_parser()
        assert _affs(_parse(html)) == [[]]
