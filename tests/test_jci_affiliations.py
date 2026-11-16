"""Affiliations on jci.org article pages (oxjob #2252; ticket 25794 via #1062).

Markup is cut down from stored JCI pages (16 Nov 2026, #2252 EXPLORE § 5): the byline links open per-author pop-ups,
and every pop-up holds the article's whole affiliation list, numbered (10.1172/JCI30024, JCI24921) or not
(JCI104548, JCI105082). jci.org writes no citation_author_institution tags, so the meta-tag parser, which wins these
pages, gave every author none.
"""
from parseland_lib.parse import parse_page

URL = "https://www.jci.org/articles/view/30024"


def _page(byline, block, metas=""):
    """byline: (name, labels or ""); block: the inner HTML of each pop-up's p.affiliations (None: an empty pop-up)."""
    links = "".join(
        f'<a class="author-affiliation show-more" href="javascript:void(0);" data-dropdown="author-affiliation-{i}">'
        f' {name}{f"<sup>{labels}</sup>" if labels else ""} </a>' for i, (name, labels) in enumerate(byline))
    box = '<p class="affiliations">' + block + "</p>" if block is not None else "<p></p>"
    boxes = "".join(
        f'<div class="f-dropdown content large" data-dropdown-content id="author-affiliation-{i}"><p>{box}'
        f'<p> Find articles by {name} in: <a href="/search/results">JCI</a></p></div>' for i, (name, _) in
        enumerate(byline))
    tags = "".join(f'<meta name="citation_author" content="{name.removesuffix(", and").strip(" ,")}"/>'
                   for name, _ in byline)
    return (f'<html><head><link rel="canonical" href="https://www.jci.org/articles/view/30024"/><meta name="citation_journal_title" content="The Journal of Clinical Investigation"/>'
            f'<meta name="citation_title" content="A title"/>{tags}{metas}'
            f'<meta name="citation_doi" content="10.1172/JCI30024"/></head><body>'
            f'<h4 class="author-list">{links}</h4>{boxes}</body></html>')


def _affs(html):
    return {a["name"]: [x["name"] for x in a["affiliations"]] for a in parse_page(html.encode(), "doi", URL)["authors"]}


NUMBERED = ("<sup>1</sup>Angiogenesis Core Facility, NCI, NIH, Gaithersburg, Maryland, USA. "
            "<sup>2</sup>Department of Microbiology, University of Maryland, Baltimore, Maryland, USA. "
            "<sup>3</sup>Genetics Branch, NCI, and <sup>4</sup>NIDDK, NIH, Bethesda, Maryland, USA.")


def test_numbered_list_by_byline_labels():
    html = _page([("Enrique Zudaire,", "1"), ("Natalia Cuesta,", "2"), ("Karen Woodson,", "3"),
                  ("Deborah Novack, and", "1,4")], NUMBERED)
    assert _affs(html) == {
        "Enrique Zudaire": ["Angiogenesis Core Facility, NCI, NIH, Gaithersburg, Maryland, USA."],
        "Natalia Cuesta": ["Department of Microbiology, University of Maryland, Baltimore, Maryland, USA."],
        "Karen Woodson": ["Genetics Branch, NCI"],
        "Deborah Novack": ["Angiogenesis Core Facility, NCI, NIH, Gaithersburg, Maryland, USA.",
                           "NIDDK, NIH, Bethesda, Maryland, USA."],
    }


def test_one_unnumbered_affiliation_is_everyones():
    html = _page([("Nils U. Bang,", ""), ("Anthony P. Fletcher", "")],
                 "Department of Medicine, Washington University School of Medicine, St. Louis, Mo.")
    aff = ["Department of Medicine, Washington University School of Medicine, St. Louis, Mo."]
    assert _affs(html) == {"Nils U. Bang": aff, "Anthony P. Fletcher": aff}


def test_affiliation_set_in_superscript_is_not_a_label():
    html = _page([("Munsey S. Wheby,", ""), ("LeeRoy G. Jones", "")],
                 " <sup>Department of Gastroenterology, Walter Reed Army Institute of Research, Washington, D. C.</sup> ")
    aff = ["Department of Gastroenterology, Walter Reed Army Institute of Research, Washington, D. C."]
    assert _affs(html) == {"Munsey S. Wheby": aff, "LeeRoy G. Jones": aff}


def test_several_unnumbered_affiliations_go_to_no_one_of_several():
    block = ('<sup>Department of Physiology, U. S. Naval Submarine Base, New London, Conn.</sup></p>'
             '<p class="affiliations"><sup>Department of Pediatrics, Johns Hopkins University, Baltimore, Md.</sup>')
    html = _page([("K. E. Schaefer,", ""), ("M. E. Avery", "")], block)
    assert _affs(html) == {"K. E. Schaefer": [], "M. E. Avery": []}


def test_several_unnumbered_affiliations_are_a_sole_authors():
    block = ('Department of Physiology, U. S. Naval Submarine Base, New London, Conn.</p>'
             '<p class="affiliations">Department of Pediatrics, Johns Hopkins University, Baltimore, Md.')
    assert _affs(_page([("K. E. Schaefer", "")], block)) == {"K. E. Schaefer": [
        "Department of Physiology, U. S. Naval Submarine Base, New London, Conn.",
        "Department of Pediatrics, Johns Hopkins University, Baltimore, Md."]}


def test_empty_popups_give_no_affiliation():
    assert _affs(_page([("Amie S. Corbin,", ""), ("Brian J. Druker", "")], None)) == {
        "Amie S. Corbin": [], "Brian J. Druker": []}


def test_institution_tags_win_over_the_popups():
    metas = ('<meta name="citation_author" content="Ann Lee"/>'
             '<meta name="citation_author_institution" content="Tag University"/>')
    html = _page([], "").replace("</head>", metas + "</head>")
    html = html.replace('<h4 class="author-list"></h4>', '<h4 class="author-list"><a class="author-affiliation" '
                        'data-dropdown="author-affiliation-0"> Ann Lee </a></h4><div id="author-affiliation-0">'
                        '<p class="affiliations">Pop-up University</p></div>')
    assert _affs(html) == {"Ann Lee": ["Tag University"]}


def test_lookalike_popups_off_jci_org_are_left_alone():
    html = _page([("Nils U. Bang,", ""), ("Anthony P. Fletcher", "")], "Department of Medicine, Example University")
    html = html.replace("www.jci.org", "journal.example.org")
    assert _affs(html) == {"Nils U. Bang": [], "Anthony P. Fletcher": []}
