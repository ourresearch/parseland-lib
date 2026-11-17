"""IOS Press article pages on content.iospress.com (oxjob #2330).

Markup is cut down from stored iospress.nl pages (17 Nov 2026). The byline, affiliations, correspondence notes and
abstract sit in div.front-meta-data as p.metadata-entry rows labelled "Authors:", "Affiliations:", "Correspondence:",
"Note:" and "Abstract:". ios.py read only one of the template's variants and crashed on the others (affiliation anchors
named "a" rather than "aff1", a note-only correspondent, no starred author), so the meta-tag parser won those pages:
names only, no affiliations, no corresponding author, and the meta description's 250-character cut as the abstract.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.ios import IOSPress

URL = "https://content.iospress.com/articles/journal/x1"
HEAD = ('<meta name="citation_publisher" content="IOS Press"/><meta name="citation_title" content="A title"/>'
        '<meta name="citation_doi" content="10.3233/X-1"/>')


def _page(rows, head=HEAD, names=()):
    metas = "".join(f'<meta name="citation_author" content="{n}"/>' for n in names)
    entries = "".join(f'<p class="metadata-entry"><span class="generated">{label}: </span>{body}</p>' for label, body in rows)
    return (f"<html><head>{head}{metas}</head><body><div class=\"main col\"><header class=\"article-header\"><h1>A title</h1>"
            f"<div class=\"front-meta-data\" id=\"article1-front-metadata\">{entries}</div></header></div></body></html>")


def _author(name, *targets):
    links = "; ".join(f'<a href="#{t}">{t}</a>' if t else '<a href="#"></a>' for t in (targets or ("",)))
    return (f'<a href="https://content.iospress.com:443/search?q=author%3A%28%22{name}%22%29">{name}</a>'
            f'<sup>{links}</sup>')


def _byline(*authors):
    return " | ".join(authors)


def _affs(*items, labelled=True):
    out = []
    for anchor, label, text in items:
        mark = (f'<span class="generated">[</span>{label}<span class="generated">] </span>' if labelled else "")
        out.append(f'<a id="{anchor}"><!-- named anchor --></a>{mark}{text}')
    return " | ".join(out)


def _out(html):
    return parse_page(html.encode(), "doi", URL)


def _corr(out):
    return [a["name"] for a in out["authors"] if a["is_corresponding"]]


def test_lettered_affiliations_and_starred_author():
    html = _page([
        ("Authors", _byline(_author("Schofield, Jonathon S.", "a"), _author("Dawson, Michael R.", "b"),
                            _author("Hebert, Jacqueline S.", "b", "c", "*"))),
        ("Affiliations", _affs(("a", "a", "Department of Mechanical Engineering, University of Alberta, Edmonton, Canada"),
                               ("b", "b", "Glenrose Rehabilitation Hospital, Edmonton, Canada"),
                               ("c", "c", "Faculty of Medicine, University of Alberta, Edmonton, Canada"))),
        ("Correspondence", '<span id="*"> [*] Corresponding author: Jacqueline S. Hebert, Faculty of Medicine.</span>'),
    ])
    out = _out(html)
    assert [a["name"] for a in out["authors"]] == ["Schofield, Jonathon S.", "Dawson, Michael R.", "Hebert, Jacqueline S."]
    assert [[x["name"] for x in a["affiliations"]] for a in out["authors"]] == [
        ["Department of Mechanical Engineering, University of Alberta, Edmonton, Canada"],
        ["Glenrose Rehabilitation Hospital, Edmonton, Canada"],
        ["Glenrose Rehabilitation Hospital, Edmonton, Canada", "Faculty of Medicine, University of Alberta, Edmonton, Canada"]]
    assert _corr(out) == ["Hebert, Jacqueline S."]


def test_aff_anchor_names_map_through_their_printed_letters():
    html = _page([
        ("Authors", _byline(_author("Perig, Alexander V.", "a", "*"), _author("Zavdoveev, Anatoliy V.", "b"))),
        ("Affiliations", _affs(("aff1", "a", "Donbass State Engineering Academy, Kramatorsk, Ukraine"),
                               ("aff2", "b", "Paton Electric Welding Institute NASU, Kiev, Ukraine"))),
        ("Correspondence", '<span id="*"> [*] Address for correspondence: Dr. Alexander V. Perig, Kramatorsk.</span>'),
    ])
    out = _out(html)
    assert [[x["name"] for x in a["affiliations"]] for a in out["authors"]] == [
        ["Donbass State Engineering Academy, Kramatorsk, Ukraine"], ["Paton Electric Welding Institute NASU, Kiev, Ukraine"]]
    assert _corr(out) == ["Perig, Alexander V."]


def test_unlinked_affiliations_go_to_every_author_but_not_a_guest_editors():
    html = _page([
        ("Guest editors", 'Jack C. de la Torre<a href="#x"></a>'),
        ("Authors", _byline(_author("Morley, John E."), _author("Banks, William A.", "", "*"))),
        ("Affiliations", _affs(("a", "", "GRECC, VA Medical Center, St. Louis, MO, USA"),
                               ("x", "", "Banner Sun Health Research Institute, Sun City, AZ, USA"), labelled=False)),
        ("Correspondence", '<span id="*"> [*] Correspondence to: William A. Banks, MD, Seattle, WA, USA.</span>'),
    ])
    out = _out(html)
    assert [[x["name"] for x in a["affiliations"]] for a in out["authors"]] == [
        ["GRECC, VA Medical Center, St. Louis, MO, USA"], ["GRECC, VA Medical Center, St. Louis, MO, USA"]]
    assert _corr(out) == ["Banks, William A."]


def test_note_names_the_correspondent_when_no_author_is_starred():
    html = _page([
        ("Authors", _byline(_author("Tass, P.A.", "", ""), _author("Hauptmann, C."))),
        ("Affiliations", _affs(("a", "", "Research Center Jülich, Jülich, Germany"),
                               ("b", "", "University of Cologne, Cologne, Germany"), labelled=False)),
        ("Note", '<span id="">[] Corresponding author: Peter A. Tass, Institute of Neuroscience, Jülich, Germany.</span>'),
    ])
    assert _corr(_out(html)) == ["Tass, P.A."]


def test_address_for_correspondence_note_matches_the_surname():
    html = _page([
        ("Authors", _byline(_author("Yousif, M.A.", "", ""), _author("Nizar, S."))),
        ("Affiliations", _affs(("a", "", "Faculty of Pharmacy, University of Gezira, Sudan"), labelled=False)),
        ("Note", '<span id="">[] Address for correspondence: Mirghani A. Yousif, Professor in Pharmacy Practice.</span>'),
    ])
    assert _corr(_out(html)) == ["Yousif, M.A."]


def test_a_star_pointing_at_a_funding_note_is_not_a_corresponding_mark():
    html = _page([
        ("Authors", _byline(_author("Lutz, Neil", "a", "**"), _author("Stull, D.M.", "b", "*"))),
        ("Affiliations", _affs(("affa", "a", "Swarthmore College, Swarthmore, PA, USA"),
                               ("affb", "b", "Northwestern University, Evanston, IL, USA"))),
        ("Correspondence", '<span id="**"> [**] Corresponding author. E-mail: x.</span>'),
        ("Note", '<span id="*">[*] Research supported in part by National Science Foundation Grants 1247051.</span>'),
    ])
    assert _corr(_out(html)) == ["Lutz, Neil"]


def test_unnamed_correspondence_note_marks_no_one():
    html = _page([
        ("Authors", _byline(_author("Sawyer, Benjamin D."), _author("Hancock, P.A."))),
        ("Affiliations", _affs(("a", "", "University of Central Florida, Orlando, FL"), labelled=False)),
        ("Note", '<span id="">[] Corresponding author. E-mail: x Tel.: (01)407-823-4344.</span>'),
    ])
    assert _corr(_out(html)) == []


def test_note_with_only_an_email_is_not_a_corresponding_mark():
    html = _page([
        ("Authors", _byline(_author("Noomen, Jeroen", "a", "1"), _author("Uiterwijk, Jos", "b"))),
        ("Affiliations", _affs(("aff1", "a", "Apeldoorn, The Netherlands"), ("aff2", "b", "Maastricht, The Netherlands"))),
        ("Note", '<span id="1">[1] Apeldoorn, The Netherlands. Email: x</span>'),
    ])
    assert _corr(_out(html)) == []


def test_abstract_joins_the_folded_part_without_a_break():
    html = _page([
        ("Authors", _byline(_author("Kamada, Hiroki"))),
        ("Abstract", '<span>Background:Strategic vibration elicits illusions. Literature shows little consistency in the v'
                     '</span><span class="below-fold" data-below-fold="thc00879">ibration parameters used. '
                     'Objective:To characterize the effects.</span>'),
    ])
    assert _out(html)["abstract"] == ("Background:Strategic vibration elicits illusions. Literature shows little consistency "
                                      "in the vibration parameters used. Objective:To characterize the effects.")


def test_book_review_citation_is_not_an_abstract():
    soup = BeautifulSoup(_page([
        ("Article type", "Book Review"),
        ("Authors", _byline(_author("Anjewierden, Anjo"))),
        ("Affiliations", _affs(("aff1", "", "University of Amsterdam"), labelled=False)),
        ("Abstract", "<span>The Craft of Prolog, by Richard A. O'Keefe, MIT Press 1990, ISBN 0 262 15039 5, 387 pp. </span>"),
    ]), "lxml")
    assert IOSPress(soup).parse()["abstract"] is None


def test_ebook_chapter_page_without_the_front_matter_block_is_not_read():
    html = (f"<html><head>{HEAD}<meta name=\"citation_author\" content=\"Dayé, Christian\"/></head><body>"
            "<div class=\"chapter\"><h1>A title</h1><p>Authors Christian Dayé</p></div></body></html>")
    assert not IOSPress(BeautifulSoup(html, "lxml")).authors_found()


def test_lookalike_metadata_entry_page_from_another_publisher_is_not_claimed():
    head = ('<meta name="citation_publisher" content="SAGE Publications"/><meta name="citation_title" content="A title"/>')
    html = _page([("Authors", _byline(_author("Doe, Jane", "a"))),
                  ("Affiliations", _affs(("a", "a", "Some University")))], head=head)
    parser = IOSPress(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
