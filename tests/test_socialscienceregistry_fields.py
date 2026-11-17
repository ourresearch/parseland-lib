"""AEA RCT Registry (socialscienceregistry.org) trial pages (oxjob #2338).

Markup is cut down from stored trial pages (current-version and history-version pages share one layout; older pages
head each fieldset with <legend> instead of <h3>). Label-v1 (both blind labellers, 6 of 6 build pages) reads the
Primary Investigator and Other Primary Investigator(s) as the authors, in page order, each with its one affiliation
field, and the trial's "Abstract" field as the abstract. The "Contact Primary Investigator" button is not a
corresponding-author mark. The "Relevant Paper(s)" block prints a later paper's own abstract: never the trial's.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.socialscienceregistry import AEARCTRegistry

URL = "https://www.socialscienceregistry.org/trials/1519/history/10514"
TAGLINE = "The American Economic Association's registry for randomized controlled trials"


def _field(label, value, q="'"):
    return (f"<div class={q}row{q}><div class={q}span8{q}><div class={q}field-label{q}>{label}</div>"
            f"<div class={q}field{q}>{value}</div></div></div>")


def _page(pis, abstract, heading="h3", q="'", tagline=TAGLINE, related_abstract=None, title="AEA RCT Registry"):
    """pis: [(name, affiliation)], the first one the Primary Investigator."""
    (name, aff), others = pis[0], pis[1:]
    link = '<a href="/trials/search?search%5Binvestigator_name%5D=x">{}</a>'
    primary = (f"<fieldset><{heading}>Primary Investigator</{heading}>" + _field("Name", link.format(name), q)
               + _field("Affiliation", aff, q)
               + '<div class="row"><div class="span8"><div class="field"><a class="btn" '
                 'href="/trials/1519/investigators/1660/messages/new">Contact Primary Investigator</a></div></div></div>'
               + "</fieldset>")
    items = "".join(f"<div class={q}trial-collection-item{q}>" + _field("PI Name", link.format(n), q)
                    + _field("PI Affiliation", a, q)
                    + '<div class="field"><a class="btn" href="/trials/1519/other_investigators/2481/messages/new">'
                      'Contact Investigator</a></div></div>' for n, a in others)
    other = f"<fieldset><{heading}>Other Primary Investigator(s)</{heading}>{items}</fieldset>"
    info = (f"<fieldset><{heading}>Additional Trial Information</{heading}>" + _field("Status", "Completed", q)
            + f"<div class={q}row abstract{q}><div class={q}span8{q}><div class={q}field-label{q}>Abstract</div>"
              f"<div class={q}field{q}>{abstract}</div></div></div>"
            + f"<h3>Registration Citation</h3>" + _field("Citation", "Khincha, Roshni. 2016. AEA RCT Registry.", q)
            + "</fieldset>")
    papers = ""
    if related_abstract:
        papers = (f"<fieldset><{heading}>Relevant Paper(s)</{heading}>" + _field("Abstract", related_abstract, q)
                  + _field("Citation", "Barsbai, Toman (2024). Information and Immigrant Settlement.", q)
                  + "</fieldset>")
    header = (f"<div class='container-fluid' id='header'><div class='container header-wrapper'>"
              f"<a class=\"logo\" href=\"/\"><div class='aea-logo'></div><div class='logo-type-wrapper'>"
              f"<p class='tagline'>{tagline}</p></div></a></div></div>")
    return (f"<!DOCTYPE html><html lang='en'><head><title>{title}</title>"
            f'<link rel="stylesheet" media="all" href="/assets/legacy-af28.css" /></head><body>{header}'
            f"<div class='container' id='main'><h1>Improving Job Search Efficiency</h1>"
            f"<div class='trial-form accordion'>{primary}{other}{info}{papers}</div></div></body></html>")


PIS = [("Roshni Khincha", "Abdul Latif Jameel Poverty Action lab"),
       ("Christopher Ksoll", "Mathematica Policy Research"),
       ("Jeremy Magruder", "University of California, Berkeley")]
ABSTRACT = ("India is in the paradoxical situation of both identifying unemployment among the yearly graduates of "
            "technical colleges as a major problem and employers complaining that they cannot fill positions. <br>"
            "Job Shikari is a new job information platform that aims to fill this void, by matching recent graduates "
            "with employers in emerging industrial clusters. <br>")
RELATED = ("We study a randomly-assigned program providing information on U.S. settlement for new Filipino immigrants. "
           "The intervention has no effect on employment, settlement, and subjective wellbeing.")


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def test_investigators_are_the_authors_in_page_order():
    out = _parse(_page(PIS, ABSTRACT))
    assert [a["name"] for a in out["authors"]] == [n for n, _ in PIS]


def test_each_investigator_has_its_affiliation():
    out = _parse(_page(PIS, ABSTRACT))
    assert [[x["name"] for x in a["affiliations"]] for a in out["authors"]] == [[a] for _, a in PIS]


def test_empty_affiliation_field_gives_none():
    out = _parse(_page([("Christopher Hoy", ""), ("Franziska Mager", " ")], ABSTRACT))
    assert [a["name"] for a in out["authors"]] == ["Christopher Hoy", "Franziska Mager"]
    assert all(a["affiliations"] == [] for a in out["authors"])


def test_contact_button_is_not_a_corresponding_mark():
    out = _parse(_page(PIS, ABSTRACT))
    assert not any(a["is_corresponding"] for a in out["authors"])


def test_abstract_is_the_trial_field_with_paragraphs():
    out = _parse(_page(PIS, ABSTRACT))
    assert out["abstract"].startswith("India is in the paradoxical situation")
    assert out["abstract"].endswith("emerging industrial clusters.")
    assert "\nJob Shikari" in out["abstract"]


def test_related_paper_abstract_is_not_the_trials():
    out = _parse(_page(PIS, ABSTRACT, related_abstract=RELATED))
    assert out["abstract"].startswith("India is in the paradoxical situation")
    assert "Filipino" not in out["abstract"]


def test_one_sentence_abstract_is_kept():
    out = _parse(_page(PIS, "We study if increased competition leads to decreased effort provision."))
    assert out["abstract"] == "We study if increased competition leads to decreased effort provision."


def test_older_layout_with_legend_headings():
    out = _parse(_page([("James Riccio", "MDRC"), ("Cynthia Miller", "MDRC")], ABSTRACT, heading="legend", q='"'))
    assert [(a["name"], [x["name"] for x in a["affiliations"]]) for a in out["authors"]] == [
        ("James Riccio", ["MDRC"]), ("Cynthia Miller", ["MDRC"])]
    assert out["abstract"].startswith("India is in the paradoxical situation")


def test_newest_layout_titled_by_the_trial_is_claimed():
    out = _parse(_page(PIS, ABSTRACT, title="Cooperation and Spillovers under Group-Level Regulatory Allocation"))
    assert [a["name"] for a in out["authors"]] == [n for n, _ in PIS]


def test_parse_has_no_back_matter_keys():
    parsed = AEARCTRegistry(BeautifulSoup(_page(PIS, ABSTRACT), "lxml")).parse()
    assert set(parsed) == {"authors", "abstract"}


def test_look_alike_page_is_not_claimed():
    # same field-label markup and a #header, but another site's tagline (and an AEA journal page has no such header)
    other = _page(PIS, ABSTRACT, tagline="A registry for clinical trials")
    parser = AEARCTRegistry(BeautifulSoup(other, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    aea_journal = ('<html><head><title>Tax-Motivated Trading - American Economic Association</title>'
                   '<meta name="citation_publisher" content="American Economic Association"/></head><body>'
                   '<div id="header"><p class="tagline">American Economic Association</p></div>'
                   '<section class="primary"><h1>Tax-Motivated Trading</h1></section></body></html>')
    assert not AEARCTRegistry(BeautifulSoup(aea_journal, "lxml")).authors_found()
