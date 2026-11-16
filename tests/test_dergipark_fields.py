"""DergiPark (TUBITAK ULAKBIM's journal platform, meta generator "uds") article pages (oxjob #2268).

Markup cut down from stored DergiPark pages (16 Nov 2026, #2268 template sample). The citation_author tags carry the
byline and, on newer pages, citation_author_institution; the corresponding author is marked only in the "Yazarlar /
Authors" row of the details table, three ways over the years: "<small>(Sorumlu Yazar)</small>" after the name, a star
icon inside a name link titled "Sorumlu Yazar", or (2024 on) every name link titled "Sorumlu Yazar" with the star on the
real one only. English-interface pages print "Primary Author" in the same places; label-v1's labellers do not read that
as a corresponding-author mark, so the parser does not either. Funding and thanks sit in the details table
("Destekleyen Kurum", "Proje Numarası", "Teşekkür") or, on newer pages, in their own sections.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.dergipark import DergiPark

URL = "https://doi.org/10.33689/spormetre.673957"
GENERATOR = '<meta name="generator" content="uds" />'
NAMES = ["Metin ARGAN", "Caner ÖZGEN", "Rüstem DOĞAN"]


def _page(entries, rows="", sections="", names=NAMES, generator=GENERATOR, institutions=None):
    metas = ""
    for i, n in enumerate(names):
        metas += f'<meta name="citation_author" content="{n}" />'
        if institutions:
            metas += f'<meta name="citation_author_institution" content="{institutions[i]}" />'
    return (f'<html lang="tr"><head>{generator}{metas}<meta name="citation_title" content="Bir başlık" />'
            '<meta name="citation_abstract" content="' + "Bu çalışmada bir şey incelendi. " * 12 + '" />'
            '</head><body><div class="article-abstract data-section"><h3>Öz</h3><p>Bir öz.</p></div>' + sections +
            '<table class="record_properties table"><tr><th>Bölüm</th><td>Araştırma Makalesi</td></tr>'
            '<tr><th>Yazarlar</th><td><a name="article-authors-list"></a>' + "<hr>".join(entries) +
            '</td></tr>' + rows + '<tr><th>Yayımlanma Tarihi</th><td>30 Aralık 2020</td></tr></table></body></html>')


def _old_entry(i, name, mark=""):
    return (f'<p id="author13507{i}"><a href="/tr/pub/@x{i}" style="font-weight: 600">{name}></a> {mark} <br> '
            'Eskişehir Teknik Üniversitesi <br> <a href="https://orcid.org/0000-0002-5083-026X">0000-0002-5083-026X</a>'
            '<br> Türkiye </p>')


def _new_entry(i, name, star=False, label="Sorumlu Yazar"):
    icon = '<span class="fa fa-star-of-life primary-author-icon m-0"></span>' if star else ""
    return (f'<p id="author29571{i}"><a href="/tr/pub/@x{i}" style="font-weight: 600" data-toggle="tooltip" '
            f'title="{label}" aria-label="{label}: {name}">{name} {icon}</a> <span class="row no-space-row">'
            '<label class="m-0 p-0" aria-label="Kurum : GAZİANTEP ÜNİVERSİTESİ"><label aria-hidden="true">'
            'GAZİANTEP ÜNİVERSİTESİ</label></label></span> <span class="row no-space-row"><label class="m-0 p-0" '
            'aria-label="Ülke : Türkiye"><label aria-hidden="true">Türkiye</label></label></span></p>')


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _corr(html):
    return [a["name"] for a in _parse(html)["authors"] if a["is_corresponding"]]


def _raw(html):
    return DergiPark(BeautifulSoup(html, "lxml")).parse()


def test_small_sorumlu_yazar_marks_that_author():
    entries = [_old_entry(i, n, "<small>(Sorumlu Yazar)</small>" if i == 1 else "") for i, n in enumerate(NAMES)]
    assert _corr(_page(entries)) == ["Caner ÖZGEN"]


def test_star_in_link_titled_sorumlu_yazar_marks_that_author():
    entries = [_new_entry(i, n, star=(i == 2)) for i, n in enumerate(NAMES)]  # every link titled, one star
    assert _corr(_page(entries)) == ["Rüstem DOĞAN"]


def test_titles_without_a_star_mark_no_one():
    entries = [_new_entry(i, n) for i, n in enumerate(NAMES)]
    assert _corr(_page(entries)) == []


def test_primary_author_on_english_pages_is_not_a_mark():
    entries = [_old_entry(i, n, "<small>(Primary Author)</small>" if i == 0 else "") for i, n in enumerate(NAMES)]
    assert _corr(_page(entries)) == []
    entries = [_new_entry(i, n, star=(i == 1), label="Primary Author") for i, n in enumerate(NAMES)]
    assert _corr(_page(entries)) == []


def test_mark_matches_a_differently_written_name():
    names = ["Fatih PULAT", "Murat YAKAR", "Ali ULVİ"]  # the table prints "Fatih PULAT>"
    entries = [_old_entry(i, n.upper(), "<small>(Sorumlu Yazar)</small>" if i == 2 else "") for i, n in enumerate(names)]
    assert _corr(_page(entries, names=names)) == ["Ali ULVİ"]


def test_authors_affiliations_and_abstract_stay_as_the_meta_tags_give_them():
    entries = [_old_entry(i, n, "<small>(Sorumlu Yazar)</small>" if i == 1 else "") for i, n in enumerate(NAMES)]
    out = _parse(_page(entries, institutions=["ESKİŞEHİR TEKNİK", "ESKİŞEHİR TEKNİK", "ANADOLU"]))
    assert [a["name"] for a in out["authors"]] == NAMES
    assert [[f["name"] for f in a["affiliations"]] for a in out["authors"]] == [["ESKİŞEHİR TEKNİK"]] * 2 + [["ANADOLU"]]
    assert out["abstract"].startswith("Bu çalışmada")
    # no institution tags: no affiliations, as before (the table's are not read: under 1,000 works lack them)
    assert all(a["affiliations"] == [] for a in _parse(_page(entries))["authors"])


def test_funding_and_thanks_rows_in_the_details_table():
    rows = ('<tr><th>Destekleyen Kurum</th><td>Mersin Üniversitesi</td></tr>'
            '<tr><th>Proje Numarası</th><td>2021-2-TP2-4530</td></tr>'
            '<tr><th>Teşekkür</th><td>Bu çalışma, Mersin Üniversitesi tarafından desteklenmiştir.</td></tr>')
    raw = _raw(_page([_old_entry(0, NAMES[0])], rows=rows, names=NAMES[:1]))
    assert raw["funding_statement"] == "Mersin Üniversitesi\n2021-2-TP2-4530"
    assert raw["acknowledgments"] == "Bu çalışma, Mersin Üniversitesi tarafından desteklenmiştir."


def test_funding_and_thanks_sections_on_newer_pages():
    sections = ('<div class="article-supporting-institution data-section"><h3>Supporting Institution</h3>'
                '<p>Süleyman Demirel Üniversitesi</p></div>'
                '<div class="data-section"><h3>Project Number</h3><p>FYL-2023-9096</p></div>'
                '<div class="article-thanks-letter data-section"><h3>Thanks</h3><p>We thank the reviewers.</p>'
                '<p>And the editors.</p></div>')
    raw = _raw(_page([_new_entry(0, NAMES[0], star=True)], sections=sections, names=NAMES[:1]))
    assert raw["funding_statement"] == "Süleyman Demirel Üniversitesi\nFYL-2023-9096"
    assert raw["acknowledgments"] == "We thank the reviewers.\nAnd the editors."


def test_placeholder_funding_is_none_and_a_bare_project_number_is_not_a_statement():
    sections = ('<div class="article-supporting-institution data-section"><h3>Destekleyen Kurum</h3><p>yok</p></div>'
                '<div class="data-section"><h3>Proje Numarası</h3><p>51-40</p></div>')
    raw = _raw(_page([_new_entry(0, NAMES[0], star=True)], sections=sections, names=NAMES[:1]))
    assert raw["funding_statement"] is None
    assert raw["acknowledgments"] is None


def test_no_back_matter_rows_gives_none():
    raw = _raw(_page([_old_entry(0, NAMES[0])], names=NAMES[:1]))
    assert raw["funding_statement"] is None and raw["acknowledgments"] is None
    assert "references" not in raw  # the reference list is left to parse.py's readers


def test_look_alike_ojs_page_is_not_claimed():
    # an Open Journal Systems page of a Turkish journal: same words, numbered author paragraphs, no "uds" generator
    entries = [_old_entry(i, n, "<small>(Sorumlu Yazar)</small>" if i == 1 else "") for i, n in enumerate(NAMES)]
    html = _page(entries, generator='<meta name="generator" content="Open Journal Systems 3.3.0.13" />')
    assert not DergiPark(BeautifulSoup(html, "lxml")).is_publisher_specific_parser()
    assert _corr(html) == []


def test_uds_generator_without_the_details_table_is_not_claimed():
    html = (f"<html><head>{GENERATOR}<meta name=\"citation_author\" content=\"A B\" /></head><body>"
            '<p id="author1">A B <small>(Sorumlu Yazar)</small></p></body></html>')
    assert not DergiPark(BeautifulSoup(html, "lxml")).is_publisher_specific_parser()
