"""Karger's own article pages (www.karger.com/Article/FullText|Abstract/<id>), oxjob #2330.

Markup is cut down from stored karger.com pages (17 Nov 2026, #2330 sites/karger-com). The byline is
``span.autoren``: "Family I." names split by ``<span class="color">·</span>``, each with an optional ``<sup>`` of
affiliation labels, and a ``<br />`` after the last name. ``div#cAffi`` holds the affiliations (labelled by ``<sup>``,
or one unlabelled block for every author) and ``div#cAuthors`` the corresponding author's name and address.

karger.py appended an author only when a ``<sup>`` or a separator followed the name, so the last author of a byline
without labels was lost; a sole author always was, and with him the page's affiliation (1 in 10 of the site's works).
It never read ``div#cAuthors``. Silverchair-era karger.com pages (``.al-author-name``) are left to the parsers that read
them today, and so are other Silverchair publishers' pages: this parser's output there is unchanged.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.karger import Karger

URL = "https://www.karger.com/Article/FullText/519962"
SEP = ' <span class="color">·</span> '


def _page(byline, affs=None, contact=None, og="https://www.karger.com/Article/FullText/519962", metas=()):
    meta = "".join(f'<meta name="citation_author" content="{m}" />' for m in metas)
    aff_html = ('<p><a href="#" id="showAffi" class="AuthorAffiliations">Author affiliations</a>'
                f'<div id="cAffi">{affs}</div></p>') if affs is not None else ""
    contact_html = ('<p><a href="#" id="showContact" class="CorrespondingAuthor">Corresponding Author</a>'
                    f'<div id="cAuthors">{contact}</div></p>') if contact is not None else ""
    return (f'<html><head><meta property="og:url" content="{og}" />{meta}'
            '<meta name="citation_title" content="A title" /><meta name="citation_doi" content="10.1159/000519962" />'
            '<meta name="citation_publisher" content="Karger Publishers" /></head><body>'
            '<table class="articleTable"><tr><td valign="top" width="100%">'
            '<h1 class="abstractbig">A title</h1>'
            f'<span class="autoren">\r\n{byline}  \r\n                     <br />\r\n              </span>'
            f'{aff_html}{contact_html}</td></tr></table></body></html>')


def _authors(html):
    return parse_page(html.encode(), "doi", URL)["authors"]


def _names(html):
    return [a["name"] for a in _authors(html)]


def _affs(html):
    return [[aff["name"] for aff in a["affiliations"]] for a in _authors(html)]


def _corr(html):
    return [a["is_corresponding"] for a in _authors(html)]


def test_sole_author_is_kept_with_the_page_affiliation():
    html = _page("Ford D.H.", "State University of New York, Downstate Medical Center", metas=["Donald H. Ford"])
    assert _names(html) == ["Ford D.H."]
    assert _affs(html) == [["State University of New York, Downstate Medical Center"]]


def test_last_author_of_an_unlabelled_byline_is_kept():
    byline = SEP.join(["Stonehill E.", "Crisp A.H.", "Gould J."])
    html = _page(byline, "Department of Pharmacology, University of Leeds, UK")
    assert _names(html) == ["Stonehill E.", "Crisp A.H.", "Gould J."]
    assert _affs(html) == [["Department of Pharmacology, University of Leeds, UK"]] * 3


def test_labelled_byline_still_links_each_author_to_its_affiliations():
    byline = SEP.join(["Rust P.<sup>a</sup>", "Eichler I.<sup>b</sup>", "Elmadfa I.<sup>a</sup>"])
    affs = "<sup>a</sup>Institute of Nutritional Sciences, University of Vienna<br /><sup>b</sup>General Hospital Vienna"
    html = _page(byline, affs)
    assert _names(html) == ["Rust P.", "Eichler I.", "Elmadfa I."]
    assert _affs(html) == [["Institute of Nutritional Sciences, University of Vienna"], ["General Hospital Vienna"],
                           ["Institute of Nutritional Sciences, University of Vienna"]]


def test_labelled_byline_with_one_unlabelled_affiliation_block_reads():
    # e3362e68: labels in the byline, but the block prints them as "(a)" text: one block for every author (it crashed)
    byline = SEP.join(["Masumori N.<sup>a</sup>", "Kumamoto Y.<sup>a</sup>", "Takahashi S.<sup>b</sup>"])
    html = _page(byline, "Departments of\r\n(a) Urology and\r\n(b) Pathology, Sapporo Medical College,\r\nSapporo, Japan")
    assert _names(html) == ["Masumori N.", "Kumamoto Y.", "Takahashi S."]
    assert _affs(html) == [["Departments of (a) Urology and (b) Pathology, Sapporo Medical College, Sapporo, Japan"]] * 3


def test_corresponding_author_named_in_the_contact_block():
    byline = SEP.join(["Cherrad T.<sup>a</sup>", "Belabbes S.<sup>b</sup>", "Zejjari H.<sup>a</sup>"])
    affs = "<sup>a</sup>Department of Trauma, Meknes, Morocco<br /><sup>b</sup>Department of Radiology, Meknes, Morocco"
    html = _page(byline, affs, "<p>Taoufik Cherrad, taoufik@example.com</p>")
    assert _corr(html) == [True, False, False]


def test_corresponding_with_prefix_title_and_credentials():
    byline = SEP.join(["Mangodt E.A.", "Van Gasse A.L.", "Ebo D.G."])
    contact = ("<p>Correspondence to: Dr. Didier G. Ebo</p><p>Department of Immunology, University of Antwerp</p>"
               "<p>E-Mail immuno@example.be</p>")
    assert _corr(_page(byline, "University of Antwerp, Belgium", contact)) == [False, False, True]
    byline = SEP.join(["Fukasawa Y.", "Seki N."])
    assert _corr(_page(byline, "Teikyo University, Tokyo", "<p>Nobuhiko Seki, MD, PhD</p><p>Tokyo (Japan)</p>")) \
        == [False, True]


def test_corresponding_needs_the_family_name_and_first_initial():
    # fb0a7334: two Zhangs in the byline; the contact is Gui-Xiang, so only "Zhang G.-X."; "1" marks a co-corresponding
    byline = SEP.join(["Zheng L.-F.<sup>a</sup>", "Zhang J.-W.<sup>b</sup>", "Zhang G.-X.<sup>a</sup>",
                       "Xu Y.-Z.<sup>b, 1</sup>"])
    affs = "<sup>a</sup>Department of Radiology, Shanghai<br /><sup>b</sup>Department of Surgery, Shanghai"
    contact = ("<p>Gui-Xiang Zhang, Department of Radiology</p><p>Shanghai 200080 (China)</p>"
               "<p><sup>1</sup> Co-corresponding author</p>")
    assert _corr(_page(byline, affs, contact)) == [False, False, True, True]


def test_contact_naming_nobody_in_the_byline_marks_nobody():
    byline = SEP.join(["Kumar L.", "Gupta S."])
    assert _corr(_page(byline, "AIIMS, New Delhi", "<p>Editorial Office, Basel (Switzerland)</p>")) == [None, None]


def test_no_contact_block_leaves_correspondence_unknown():
    assert _corr(_page(SEP.join(["Kumar L.", "Gupta S."]), "AIIMS, New Delhi")) == [None, None]


def test_claim_is_unchanged():
    old = BeautifulSoup(_page("Ford D.H.", "Somewhere"), "lxml")
    assert Karger(old).authors_found() and Karger(old).is_publisher_specific_parser()
    # the Silverchair byline marker is still found anywhere in the page (its parse is unchanged)
    sc = BeautifulSoup('<html><body><div><p><strong class="x al-author-name y">A B</strong></p></div></body></html>',
                       "lxml")
    assert Karger(sc).authors_found()
    # neither marker: a div.autoren is not the byline span, and class names are whole words
    for body in ('<div class="autoren">Ford D.H.</div>', '<span class="autorenliste">x</span>',
                 '<span class="al-author-names">x</span>', "<p>Nothing</p>"):
        assert not Karger(BeautifulSoup(f"<html><body>{body}</body></html>", "lxml")).authors_found(), body


def test_look_alike_byline_on_another_site_is_not_claimed():
    # the same span.autoren markup under another domain is not Karger's page
    html = _page("Ford D.H.", "Somewhere", og="https://www.example-press.org/Article/FullText/1")
    assert not Karger(BeautifulSoup(html, "lxml")).is_publisher_specific_parser()
