"""John Libbey Eurotext (jle.com) article pages (oxjob #2210, Parseland swarm pilot).

Markup is cut down from stored jle.com pages (13 Nov 2026). The site's "Résumé" tab holds the byline
(``div.auteur``), numbered affiliations (``div.affiliation`` with ``a.xref_aff``), a starred correspondence note
(``a.xref_cor``) and the abstract paragraphs after ``ul.resume``. No publisher parser claimed the pages, so the
meta-tag parser won them: authors only, no affiliations, no corresponding author, no abstract.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.jle import JLE

URL = "https://www.jle.com/fr/revues/ejd/e-docs/a_title_314540/article.phtml"
HEAD = ('<meta name="citation_doi" content="10.1684/ejd.2019.3557">'
        '<meta name="citation_title" content="A title">'
        '<meta name="citation_fulltext_html_url" content="https://www.jle.com/fr/revues/ejd/e-docs/'
        'a_title_314540/article.phtml?tab=texte">'
        '<meta name="citation_pdf_url" content="https://www.jle.com/fr/revues/ejd/e-docs/a_title_314540/'
        'article.phtml?tab=download&pj_key=doc_attach_43095">')

PREVIEW = ("Over the last decade, immune checkpoint inhibitors have improved the overall survival of advanced-stage "
           "cancers [1]. They block CTLA-4, PD-1 or PD-L1. Modulation of T-cells may sometimes result in inflammatory "
           "side effects [1]. There is a high incidence of cutaneous toxicity, ranging from 47% to 68% [...]")
ABSTRACT = ("Atopic dermatitis is a worldwide prevalent chronic inflammatory skin disease. Although primarily "
            "recognized as a disease of children, there is increasing evidence that it is more common in adults.")


def _author(name, refs=(), cor=False):
    links = "".join(f' <a href="?tab=resume#xref_note_aff{n}" name="xref_cite_aff{n}"><sup>{n}</sup></a>' for n in refs)
    if cor:
        links += ' <a href="?tab=resume#xref_note_cor1" name="xref_cite_cor1">*</a>'
    return (f'<div class="auteur"><a href="/fr/recherche/recherche.phtml?dans=auteur&amp;texte={name}">{name}</a>'
            f'{links}</div>')


def _aff(n, text):
    return (f'<div class="affiliation"><a class="xref_aff" href="#xref_cite_aff{n}" name="xref_note_aff{n}">{n}</a> '
            f'{text}</div>')


def _page(byline, after="", head=HEAD):
    texte = ('<div class="texte"><big>Auteurs</big>' + byline +
             '<ul class="resume"><li><big>DOI :</big> <a href="/10.1684/ejd.2019.3557">10.1684/ejd.2019.3557</a></li>'
             '<li><big>Année de parution :</big> 2019</li></ul>' + after + '</div>')
    return (f'<html><head>{head}</head><body><div id="tabs"><section class="tab_content clearfix">{texte}'
            '</section></div></body></html>')


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _affs(out):
    return [[a["name"] for a in au["affiliations"]] for au in out["authors"]]


def test_numbered_affiliations_and_linked_corresponding_note():
    byline = (_author("Ana Lima", [1]) + _author("Rui Costa", [1, 2], cor=True) +
              _aff(1, "University of Porto, Porto, Portugal") + _aff(2, "Centro Hospitalar do Porto, Portugal") +
              '<div class="affiliation"><a class="xref_cor" name="xref_note_cor1">*</a> Reprints</div>')
    out = _parse(_page(byline, f"<p><p>{ABSTRACT}</p></p>"))
    assert [a["name"] for a in out["authors"]] == ["Ana Lima", "Rui Costa"]
    assert _affs(out) == [["University of Porto, Porto, Portugal"],
                          ["University of Porto, Porto, Portugal", "Centro Hospitalar do Porto, Portugal"]]
    assert [a["is_corresponding"] for a in out["authors"]] == [False, True]
    assert out["abstract"] == ABSTRACT


def test_affiliation_lines_split_by_br_are_joined():
    byline = _author("Ana Lima", [1]) + _aff(1, "APHM, Hôpital La Timone<br/> Laboratoire de toxicologie<br/> "
                                                "F-13005 Marseille<br/> France")
    out = _parse(_page(byline, f"<p>{ABSTRACT}</p>"))
    assert _affs(out) == [["APHM, Hôpital La Timone, Laboratoire de toxicologie, F-13005 Marseille, France"]]


def test_one_unmarked_affiliation_goes_to_every_author_of_an_old_byline():
    byline = ('<div class="auteur"><a href="/fr/recherche/recherche.phtml?dans=auteur&amp;texte=J+Laval">J Laval</a>, '
              '<a href="/fr/recherche/recherche.phtml?dans=auteur&amp;texte=C+Dumas+">C Dumas </a></div>'
              '<div class="affiliation">Inserm U923, CHU Côte de Nacre, Caen</div>')
    out = _parse(_page(byline, f"<p>{ABSTRACT}</p>"))
    assert [a["name"] for a in out["authors"]] == ["J Laval", "C Dumas"]
    assert _affs(out) == [["Inserm U923, CHU Côte de Nacre, Caen"]] * 2


def test_correspondence_note_naming_an_author_marks_that_author():
    byline = (_author("Pauline Marchal", [1]) + _author("Lucas Girard", [1]) +
              _aff(1, "CHU Lille, F-59000, Lille") +
              '<div class="affiliation"><a class="xref_cor" name="xref_note_cor1">*</a> Correspondant : P. Marchal, '
              '<email>p.marchal@example.fr</email></div>')
    out = _parse(_page(byline, f"<p>{ABSTRACT}</p>"))
    assert [a["is_corresponding"] for a in out["authors"]] == [True, False]
    assert _affs(out) == [["CHU Lille, F-59000, Lille"]] * 2


def test_reprints_note_naming_an_author_with_a_short_given_name():
    byline = _author("Paul Morel", [1]) + _author("Luc Garnier", [1]) + _aff(1, "Université de Bourgogne, Dijon")
    note = ('<div class="affiliation"><a class="xref_cor" name="xref_note_cor1">*</a> <b>Tirés à part\xa0:</b> '
            'L. Garnier</div>')
    out = _parse(_page(byline + note, f"<p>{ABSTRACT}</p>"))
    assert [a["is_corresponding"] for a in out["authors"]] == [False, True]


def test_email_only_note_marks_the_author_it_belongs_to():
    byline = (_author("Brandon Ce Hu", [1]) + _author("Senhong Lee", [1]) + _aff(1, "Monash Health, Australia") +
              '<div class="affiliation"><a class="xref_cor" name="xref_note_cor1">*</a> '
              '<email>brandonce.hu@example.com</email></div>')
    out = _parse(_page(byline, f"<p>{ABSTRACT}</p>"))
    assert [a["is_corresponding"] for a in out["authors"]] == [True, False]
    assert _affs(out) == [["Monash Health, Australia"]] * 2


def test_email_with_surname_beats_a_shared_first_name():
    byline = _author("Céline Pasian", [1]) + _author("Raymond Azar", [1]) + _author("Céline Nodimar", [1])
    note = ('<div class="affiliation"><a class="xref_cor" name="xref_note_cor1">*</a> Correspondance : '
            '<email>celine.pasian@example.fr</email></div>')
    out = _parse(_page(byline + _aff(1, "Hospices civils de Lyon, France") + note, f"<p>{ABSTRACT}</p>"))
    assert [a["is_corresponding"] for a in out["authors"]] == [True, False, False]


def test_reprints_line_naming_one_of_two_same_surname_authors():
    byline = ('<div class="auteur"><a href="/fr/recherche/recherche.phtml?dans=auteur&amp;texte=Meishui Wang">'
              'Meishui Wang</a></div><div class="auteur"><a href="/fr/recherche/recherche.phtml?dans=auteur&amp;'
              'texte=Biao Wang">Biao Wang</a></div>'
              '<div class="affiliation">Department of Plastic Surgery, Fujian Medical University, Fuzhou, China</div>'
              '<div class="affiliation"><b>Reprints:</b> Biao Wang</div>'
              '<div class="affiliation">&lt;<a href="mailto:x@example.com">x@example.com</a>&gt;</div>')
    out = _parse(_page(byline, f"<p>{ABSTRACT}</p>"))
    assert [a["is_corresponding"] for a in out["authors"]] == [False, True]
    assert _affs(out) == [["Department of Plastic Surgery, Fujian Medical University, Fuzhou, China"]] * 2


def test_unexplained_or_unnamed_note_marks_no_one():
    byline = (_author("Ana Lima", [1]) + _author("Rui Costa", [1]) + _aff(1, "University of Porto, Portugal") +
              '<div class="affiliation"><a class="xref_cor" name="xref_note_cor1">*</a> Tirés à part</div>')
    out = _parse(_page(byline, f"<p>{ABSTRACT}</p>"))
    assert [a["is_corresponding"] for a in out["authors"]] == [False, False]


def test_list_inside_the_abstract_is_kept():
    after = (f'<p>{ABSTRACT} Dans cet article, nous rappelons :</p><ul class="simple"><li><span class="label">–</span>'
             'les notions classiques de régulation ;</li><li><span class="label">–</span>le rôle du tonus.</li></ul>')
    out = _parse(_page(_author("Ana Lima"), after))
    assert out["abstract"].endswith("nous rappelons :\nles notions classiques de régulation ;\nle rôle du tonus.")


def test_notes_are_not_affiliations_and_emails_are_dropped():
    byline = (_author("Marie Durand", [1]) + _aff(1, "Laboratoire d'hématologie, CHU de Limoges, France.") +
              '<div class="affiliation"><a class="xref_cor" name="xref_note_cor1">*</a> Tirés à part : M. Durand '
              '&lt;<a href="mailto:m.durand@example.fr">m.durand@example.fr</a>&gt;</div>'
              '<div class="affiliation"><b>Liens d’intérêt :</b> Les auteurs déclarent n’avoir aucun lien.</div>')
    out = _parse(_page(byline, f"<p>{ABSTRACT}</p>"))
    assert _affs(out) == [["Laboratoire d'hématologie, CHU de Limoges, France."]]
    assert out["authors"][0]["is_corresponding"] is True


def test_body_preview_cut_with_brackets_is_not_an_abstract():
    out = _parse(_page(_author("Ana Lima"), f"<p>{PREVIEW}</p>"))
    assert out["abstract"] is None


def test_structured_abstract_keeps_labels_inline_and_drops_the_licence_line():
    after = ("<p></p><h4>Background</h4><p>Laser intervention is increasingly recognized as an effective approach to "
             "preventing scars.</p><h4>Conclusion</h4><p>The combination of two lasers is a safe and effective "
             "therapeutic modality for facial scarring.</p>"
             '<p><img alt="Licence" src="/library/images/common/icone_cc_by-nc-nd2.png"/> Cette œuvre est mise à '
             'disposition selon les termes de la <a href="https://creativecommons.org/licenses/by-nc-nd/4.0/">'
             'Licence Creative Commons</a></p>')
    out = _parse(_page(_author("Ana Lima"), after))
    assert out["abstract"] == ("Background: Laser intervention is increasingly recognized as an effective approach to "
                               "preventing scars.\nConclusion: The combination of two lasers is a safe and effective "
                               "therapeutic modality for facial scarring.")


def test_pdf_link_notice_is_not_an_abstract():
    after = ('<p>Pour lire le texte intégral, <a class="tool_PDF" href="/fr/revues/ipe/e-docs/x/article.phtml?'
             'tab=download&amp;pj_key=doc_attach_14753"> cliquer ici. </a></p>')
    out = _parse(_page(_author("Ana Lima"), after))
    assert out["abstract"] is None


def test_new_fields_are_not_claimed():
    # the Résumé tab shows no acknowledgments, funding or references (they sit on other tabs)
    soup = BeautifulSoup(_page(_author("Ana Lima"), f"<p>{ABSTRACT}</p>"), "lxml")
    parsed = JLE(soup).parse()
    assert not parsed.get("references") and not parsed.get("references_complete")


def test_other_site_with_the_same_markup_is_not_claimed():
    head = ('<meta name="citation_title" content="A title">'
            '<meta name="citation_pdf_url" content="https://www.example-libbey.org/revues/x/article.pdf">')
    soup = BeautifulSoup(_page(_author("Ana Lima", [1]) + _aff(1, "Somewhere"), f"<p>{ABSTRACT}</p>", head=head),
                         "lxml")
    assert not JLE(soup).is_publisher_specific_parser()
