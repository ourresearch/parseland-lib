"""OAE Publishing Inc. article pages (oaepublish.com, DOI prefix 10.20517) (oxjob #2339).

Markup cut down from stored pages of both templates: the older per-journal sites (an <em> byline, div.Affs_con,
"Correspondence Address:") and the Nuxt site (the whole byline in the embedded state, div.author_box, "*Correspondence
to:"). The citation_* tags carry no affiliations or corresponding mark, so the generic parser read neither.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.oaepublish import OAEPublish

URL = "https://www.oaepublish.com/articles/x.2026.01"
HEAD = ('<meta name="citation_publisher" content="OAE Publishing Inc."><meta name="citation_title" content="A title">'
        '<meta name="citation_author" content="Ann Lee"><meta name="citation_author" content="Bo Chen">'
        '<meta name="citation_author" content="Cy Park">')

DECLARATIONS = ('<div class="article-Section article-declarations"><h2>DECLARATIONS</h2>'
                '<h3>Acknowledgments</h3><p>We thank the reviewers for their helpful comments.</p>'
                '<h3>Authors’ contributions</h3><p>Wrote the draft: Lee A</p>'
                '<h3>Financial support and sponsorship</h3><p>This work was supported by the National Natural Science '
                'Foundation of China (21975214).</p><h3>Conflicts of interest</h3><p>None.</p></div>')

OLD_BODY = ('<div id="authorString" class="article-authors"><em>Ann Lee<sup>1</sup>&nbsp;</em>, '
            '<em>Bo Chen<sup>1,2</sup></em>, <em>Cy Park<sup>2</sup>&nbsp;<a href="mailto:c@x.org">'
            '<i class="fas fa-envelope"></i></a></em></div>'
            '<div class="Aff_current"><div class="Affs_con"><p><sup>1</sup>Department of Biology, '
            '<institution>Alpha University</institution>, Rome 00185, Italy.</p><p><sup>2</sup>Beta Institute, '
            'Oslo 0313, Norway.</p></div><div class="CorrsAdd"><p>Correspondence Address: Prof. Cy Park, Beta '
            'Institute, Oslo 0313, Norway. E-mail: c@x.org</p></div></div>'
            '<div class="CorrsAdd"><p>© The Author(s) 2019. Open Access.</p></div>')

NUXT_STATE = ('window.__NUXT__=(function(a,b){return {data:[{article:{doi:"10.20517\\u002Fx.2026.01",author:['
              '{base:"Ann  Lee\\u003Csup\\u003E1\\u003C\\u002Fsup\\u003E",email:a,orcid:a,collab:a},'
              '{base:"Bo  Chen\\u003Csup\\u003E1,2,*\\u003C\\u002Fsup\\u003E",email:a,orcid:a,collab:a},'
              '{base:"Cy  Park\\u003Csup\\u003E2\\u003C\\u002Fsup\\u003E",email:a,orcid:"https:\\u002F\\u002F'
              'orcid.org\\u002F0000-0001-0000-0000",collab:a}],editor:[]}}]}}(null,""));')
NEW_BODY = ('<div id="authorString"><span class="authors_item"><span class="author_name">Ann Lee<sup>1</sup></span>'
            '</span> ... <span class="authors_item"><span class="author_name">Cy Park<sup>2</sup></span></span></div>'
            '<div class="author_box" style="display:none;"><div><div><sup>1</sup>Department of Biology, Alpha '
            'University, Rome 00185, Italy.</div></div><div><div><sup>2</sup>Beta Institute, Oslo 0313, Norway.'
            '</div></div><div class="CorrsPlus"><div><span id="cirrsMail"><sup>*</sup>Correspondence to: Prof. '
            'Bo Chen, Dr. Cy Park, Beta Institute, Oslo 0313, Norway. E-mail: b@x.org</span></div></div></div>'
            f'<script>{NUXT_STATE}</script>')


def _page(body, head=HEAD):
    return f"<html><head>{head}</head><body>{body}{DECLARATIONS}</body></html>"


def _authors(html):
    return parse_page(html.encode(), "doi", URL)["authors"]


def test_old_template_byline_affiliations_and_corresponding():
    authors = _authors(_page(OLD_BODY))
    assert [a["name"] for a in authors] == ["Ann Lee", "Bo Chen", "Cy Park"]
    assert [[x["name"] for x in a["affiliations"]] for a in authors] == [
        ["Department of Biology, Alpha University, Rome 00185, Italy."],
        ["Department of Biology, Alpha University, Rome 00185, Italy.", "Beta Institute, Oslo 0313, Norway."],
        ["Beta Institute, Oslo 0313, Norway."]]
    assert [a["is_corresponding"] for a in authors] == [False, False, True]


def test_nuxt_template_reads_the_whole_byline_from_the_page_state():
    authors = _authors(_page(NEW_BODY))
    assert [a["name"] for a in authors] == ["Ann Lee", "Bo Chen", "Cy Park"]
    assert [len(a["affiliations"]) for a in authors] == [1, 2, 1]
    # Bo Chen is starred and named in the note, Cy Park only named in it
    assert [a["is_corresponding"] for a in authors] == [False, True, True]


def test_unnumbered_affiliation_goes_to_every_author():
    body = ('<div id="authorString"><em>Ann Lee<sup></sup></em>, <em>Bo Chen<sup></sup></em></div>'
            '<div class="Affs_con"><p>Department of Biophysics, Panjab University, Chandigarh 160014, India.</p></div>'
            '<div class="CorrsAdd"><p>Correspondence Address: Dr. Ann Lee, Panjab University. E-mail: a@x.org</p></div>')
    authors = _authors(_page(body))
    assert all([x["name"] for x in a["affiliations"]] == ["Department of Biophysics, Panjab University, Chandigarh "
                                                           "160014, India."] for a in authors)
    assert [a["is_corresponding"] for a in authors] == [True, False]


def test_no_correspondence_note_marks_no_one():
    body = OLD_BODY.replace("Correspondence Address: Prof. Cy Park, Beta Institute, Oslo 0313, Norway. E-mail: c@x.org",
                            "")
    assert [a["is_corresponding"] for a in _authors(_page(body))] == [None, None, None]


def test_declarations_give_acknowledgments_and_funding():
    out = OAEPublish(BeautifulSoup(_page(OLD_BODY), "lxml")).parse()
    assert out["acknowledgments"] == "We thank the reviewers for their helpful comments."
    assert out["funding_statement"].startswith("This work was supported by the National Natural Science Foundation")
    assert "references" not in out


def test_none_funding_is_no_statement():
    page = _page(OLD_BODY).replace("This work was supported by the National Natural Science Foundation of China "
                                   "(21975214).", "None.")
    out = OAEPublish(BeautifulSoup(page, "lxml")).parse()
    assert "funding_statement" not in out


def test_claimed_by_doi_prefix_without_publisher_tag():
    head = '<meta name="citation_doi" content="10.20517/2394-5079.2019.013"><meta name="citation_author" content="Ann Lee">'
    assert OAEPublish(BeautifulSoup(_page(OLD_BODY, head), "lxml")).is_publisher_specific_parser()


def test_look_alike_page_of_another_publisher_is_not_claimed():
    head = ('<meta name="citation_publisher" content="Another Press"><meta name="citation_doi" content="10.1234/ab.1">'
            '<meta name="citation_author" content="Ann Lee">')
    parser = OAEPublish(BeautifulSoup(_page(OLD_BODY, head), "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_equal_contribution_note_is_not_an_affiliation_and_middle_initial_still_matches():
    body = ('<div id="authorString"><em>Ann Lee<sup>#</sup></em>, <em>Bo Q. Chen<sup>#</sup></em></div>'
            '<div class="Affs_con"><p>Beta Institute, Oslo 0313, Norway.</p><p><sup>#</sup>Authors contributed '
            'equally.</p></div><div class="CorrsAdd"><p>Correspondence Address: Dr. Bo Chen, Beta Institute. '
            'E-mail: b@x.org</p></div>')
    authors = _authors(_page(body))
    assert [[x["name"] for x in a["affiliations"]] for a in authors] == [["Beta Institute, Oslo 0313, Norway."]] * 2
    assert [a["is_corresponding"] for a in authors] == [False, True]


def test_affiliation_number_in_a_label_wrapper_links_by_number():
    # 2024-2025 Nuxt pages (ir.2025.06, ces.2024.67): "<label><sup>1</sup></label><addr-line>...</addr-line>"
    body = NEW_BODY.replace('<div><div><sup>1</sup>Department of Biology, Alpha University, Rome 00185, Italy.</div>',
                            '<div><div><label><sup>1</sup></label><addr-line>Department of Biology, Alpha University, '
                            'Rome 00185, Italy.</addr-line></div>').replace(
        '<div><div><sup>2</sup>Beta Institute, Oslo 0313, Norway.</div>',
        '<div><div><label><sup>2</sup></label><addr-line>Beta Institute, Oslo 0313, Norway.</addr-line></div>')
    assert "<label><sup>2</sup></label>" in body
    authors = _authors(_page(body))
    assert [[x["name"] for x in a["affiliations"]] for a in authors] == [
        ["Department of Biology, Alpha University, Rome 00185, Italy."],
        ["Department of Biology, Alpha University, Rome 00185, Italy.", "Beta Institute, Oslo 0313, Norway."],
        ["Beta Institute, Oslo 0313, Norway."]]


def test_correspondence_note_names_authors_by_initials():
    # "Correspondence to: Chambers MR, DVM, MD, ..." (jtgg.2021.31), "Dr. Kenneth KW To, ...; Dr. William CS Cho, ..."
    # (cdr.2022.38), "Dr. V Nithya, ..." (ces.2024.67)
    body = ('<div id="authorString"><em>M. R. Chambers<sup>1</sup></em>, <em>Kenneth K. W. To<sup>1</sup></em>, '
            '<em>Venkatesan Nithya<sup>1</sup></em>, <em>Ann Lee<sup>1</sup></em></div>'
            '<div class="Affs_con"><p><sup>1</sup>Beta Institute, Oslo 0313, Norway.</p></div>'
            '<div class="CorrsAdd"><p>Correspondence to: Chambers MR, DVM, MD, Beta Institute. E-mail: m@x.org; '
            'Dr. Kenneth KW To, Beta Institute. E-mail: k@x.org; Dr. V Nithya, Beta Institute. E-mail: v@x.org</p>'
            '</div>')
    assert [a["is_corresponding"] for a in _authors(_page(body))] == [True, True, True, False]


def test_initials_inside_another_authors_name_do_not_mark_that_author():
    # "Correspondence Address: Luiz A. Auersvald, ..." names Luiz, not André Auersvald ("A. Auersvald")
    body = ('<div id="authorString"><em>Luiz A. Auersvald<sup></sup></em>, <em>André Auersvald<sup></sup></em></div>'
            '<div class="Affs_con"><p>Department of Plastic Surgery, Clínica Auersvald, Curitiba 80430-000, Brazil.</p>'
            '</div><div class="CorrsAdd"><p>Correspondence Address: Luiz A. Auersvald, Department of Plastic Surgery, '
            'Clínica Auersvald, Curitiba 80430-000, Brazil. E-mail: l@x.org</p></div>')
    assert [a["is_corresponding"] for a in _authors(_page(body))] == [True, False]
