"""De Gruyter's old-template corresponding-author note, IUPAC pop-ups that say "Corresponding author", bios in names,
and Brill parts whose only byline is the book's editors (oxjob #2251; markup cut down from stored pages)."""
from parseland_lib.parse import parse_page

DG_URL = "https://www.degruyter.com/document/doi/10.1515/BC.2006.182/html"


def _dg_page(people, notes=(), bio=""):
    """people: (name, popdown email, popdown affiliations) per author; notes: the authorNotes divs' inner HTML."""
    spans = "".join(
        f'<span class="contributor"><span class="displayName linkAnimation">{n}</span>'
        f'<contributor-popdown name="{n}" email="{e}" affiliations="{a}">{bio}</contributor-popdown></span>'
        for n, e, a in people)
    notes_html = "".join(f'<div class="correspondingAuthor">{n}</div>' for n in notes)
    return (f'<html><head><meta property="og:url" content="{DG_URL}"/>'
            '<meta name="citation_title" content="A title"/></head><body>'
            f'<li class="contributors-AUTHOR"><span class="metadataAndContributorsFont">{spans}</span></li>'
            f'<section class="authorNotes"><hr/>{notes_html}<hr/></section></body></html>')


def _authors(html, url=DG_URL):
    return [(a["name"], bool(a["is_corresponding"]), [aff["name"] for aff in a["affiliations"]])
            for a in parse_page(html.encode(), "doi", url)["authors"]]


def _marked(html):
    return [name for name, corr, _ in _authors(html) if corr]


PEOPLE = [("Andrey Damianov", "", "Justus-Liebig-Universität Giessen"),
          ("Michael Kann", "", "Justus-Liebig-Universität Giessen"),
          ("Albrecht Bindereif", "", "Justus-Liebig-Universität Giessen")]


def test_note_naming_the_author_marks_them():
    html = _dg_page(PEOPLE, ["Corresponding author: Dr Albrecht Bindereif, Heinrich-Buff-Ring 58, D-35392 Giessen"])
    assert _marked(html) == ["Albrecht Bindereif"]


def test_note_with_only_an_email_marks_its_owner():
    html = _dg_page(PEOPLE, ['Corresponding author <span class="email">abindereif@chemie.uni-giessen.de</span>'])
    assert _marked(html) == ["Albrecht Bindereif"]


def test_correspondence_address_with_surname_email():
    html = _dg_page(PEOPLE, ["* Correspondence address: Giessen, Deutschland, kann@uni-giessen.de"])
    assert _marked(html) == ["Michael Kann"]


def test_address_notes_without_corresponding_wording_single_no_one_out():
    html = _dg_page(PEOPLE[:2], ["Andrey Damianov is Professor, Giessen. E-mail: damianov@uni-giessen.de",
                                "Michael Kann is Lecturer, Giessen. E-mail: kann@uni-giessen.de"])
    assert _marked(html) == []


def test_an_email_naming_no_author_marks_no_one():
    html = _dg_page(PEOPLE, ["Corresponding author: prbchiefstaff@med.example.edu"])
    assert _marked(html) == []


def test_note_never_overrides_a_popdown_email():
    people = [("Andrey Damianov", "damianov@uni-giessen.de", "Giessen")] + PEOPLE[1:]
    html = _dg_page(people, ["Corresponding author: Dr Albrecht Bindereif, Giessen"])
    assert _marked(html) == ["Andrey Damianov"]


def test_iupac_popdown_corresponding_note_marks_that_author_and_leaves_affiliations():
    people = [("John H. Duffus", "", "The Edinburgh Centre for Toxicology, Edinburgh, Scotland, UK; Corresponding "
                                     "author: John H. Duffus, 43 Mansionhouse Road, Edinburgh; E-mail: jhd@example.co.uk"),
              ("Monica Nordberg", "", "Karolinska Institutet, Stockholm, Sweden")]
    authors = _authors(_dg_page(people), "https://www.degruyter.com/database/IUPAC/entry/iupac.79.1924/html")
    assert authors == [("John H. Duffus", True, ["The Edinburgh Centre for Toxicology, Edinburgh, Scotland, UK"]),
                       ("Monica Nordberg", False, ["Karolinska Institutet, Stockholm, Sweden"])]


def test_name_is_the_display_name_not_the_popdown_bio():
    html = _dg_page(PEOPLE[:1], bio="<p>Andrey Damianov MD, PhD currently works as an oncologist in Giessen.</p>")
    assert [name for name, _, _ in _authors(html)] == ["Andrey Damianov"]


def _brill_page(og_url, lines):
    """lines: (wrapper class suffix, label, names) per contributor line, Brill's 'contributor-details' markup."""
    html = ""
    for suffix, label, names in lines:
        people = '<span class="contributor-separator">, </span>'.join(
            f'<div class="contributor-details"><div class="contributor-details-block">'
            f'<span class="contributor-details-link">{n}</span><div class="contributor-details-pop-up">'
            f'<span class="institution">Leiden University</span></div></div></div>' for n in names)
        html += (f'<div class="content-contributor{suffix}"><div class="contributor-line text-subheading">'
                 f'<span class="creator-type-label">{label}</span>{people}</div></div>')
    return (f'<html><head><meta content="{og_url}" property="og:url"/>'
            f'<meta name="citation_title" content="A title"/></head><body>{html}</body></html>')


def test_brill_part_with_only_editors_has_no_authors():
    url = "https://brill.com/display/book/edcoll/9789047403012/back-1.xml"
    html = _brill_page(url, [("-editor", "Editors:", ["David Freestone", "Surya Subedi"])])
    assert parse_page(html.encode(), "doi", url)["authors"] == []


def test_brill_authors_line_is_read():
    url = "https://brill.com/view/journals/cr/96/1/article-p45_5.xml"
    html = _brill_page(url, [("-author", "Authors:", ["Yi-Jia Shih", "Peter K. L. Ng"])])
    assert [a["name"] for a in parse_page(html.encode(), "doi", url)["authors"]] == ["Yi-Jia Shih", "Peter K. L. Ng"]


def test_brill_whole_book_keeps_its_volume_editors():
    url = "https://brill.com/display/title/38492"
    html = _brill_page(url, [("-volume-editor", "Volume Editors:", ["Anna Smith", "Ben Jones"]),
                             ("", "Author:", ["Chapter Author"])])
    assert [a["name"] for a in parse_page(html.encode(), "doi", url)["authors"]] == ["Anna Smith", "Ben Jones"]
