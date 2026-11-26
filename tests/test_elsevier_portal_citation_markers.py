"""
Citation markers in abstracts from Elsevier's journal portals (thelancet.com, cell.com and the other els-jbs sites).

oxjob #1052 step 7, Zendesk 8297: the Lancet Global Health Comment 10.1016/S2214-109X(21)00567-2 (W4288049398) served
"...internal political gridlock.1 Confidence in the UN agency..." and "...world politics,2 the failings...". A Comment has
no Summary, so its abstract is the page's og:description: the first paragraph with each citation marker flattened into
the text. The body holds the same paragraph with the markers as linked <sup>s, so they can be told apart from numbers
that are text. Fixtures are trimmed copies of the two page templates as stored by the harvester (pdf_candidate_html,
25 Nov 2026).
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from parseland_lib.publisher.parsers.elsevier_bv import ElsevierBV, citation_free_text, without_flattened_citations

HEAD = """
<link rel="canonical" href="https://www.thelancet.com/journals/langlo/article/PIIS2214-109X(21)00567-2/fulltext">
<meta name="citation_publisher" content="Elsevier"/>
<meta name="citation_author" content="Sample Author"/>
<meta name="citation_doi" content="10.1016/S2214-109X(21)00567-2"/>
"""

DESCRIPTION = (
    "Over the past decades, the political tensions that regularly plague WHO have undermined\n"
    "its authority. Every time an international public health emergency has arisen, WHO\n"
    "has faced internal political gridlock.1 Confidence in the UN agency has dwindled with\n"
    "every health crisis. Today, no one disputes that the political functioning of WHO\n"
    "is an impediment to fulfilling its role as a global health crisis coordinator and\n"
    "promoter of science-based standards. The UN system is still dependent on world politics,2\n"
    "the failings of which were far too evident during the first months of the COVID-19\n"
    "crisis."
)

FIXED = (
    "Over the past decades, the political tensions that regularly plague WHO have undermined its authority. Every "
    "time an international public health emergency has arisen, WHO has faced internal political gridlock. Confidence "
    "in the UN agency has dwindled with every health crisis. Today, no one disputes that the political functioning "
    "of WHO is an impediment to fulfilling its role as a global health crisis coordinator and promoter of "
    "science-based standards. The UN system is still dependent on world politics, the failings of which were far too "
    "evident during the first months of the COVID-19 crisis."
)


def _popup(n):
    """The older template's marker: the linked <sup> and the whole reference in a hidden pop-up."""
    return (
        f'<div class="dropBlock reference-citations"><sup><a href="#bib{n}" id="back-bib{n}" '
        f'data-db-target-for="bib{n}-d1e79" class="reference-citations__ctrl" aria-expanded="false" '
        f'aria-controls="bib{n}">{n}</a></sup><div data-db-target-of="bib{n}-d1e79" class="dropBlock__holder">'
        f'<div class="dropBlock__body"><ul title="list of authors" class="rlist reference-citations__loa">'
        f'<li class="loa__item">Author{n} A </li></ul><div class="reference-citations__detials">Reference title {n}.'
        f'<div class="popup-ref"><span class="ref__series"><i>Lancet.</i> <span class="ref__seriesDate">2020; '
        f'</span></span></div></div><div class="reference-citations__links"><ul class="rlist"><li>'
        f'<a class="google-scholar" href="http://scholar.google.com/scholar_lookup?title=Reference+{n}">Google Scholar'
        f'</a></li></ul></div></div><a href="#" class="dropBlock__ctrl--close" title="Close info"></a></div></div>'
    )


# Body paragraphs longer than 5x the description, so parse() keeps the description (the noisy-body rule).
TAIL = " ".join(["The paragraph goes on about governance and its reform."] * 60)

OLDER_TEMPLATE = f"""
<html><head>{HEAD}<meta property="og:description" content="{DESCRIPTION}" /></head><body>
<div class="col-md-7 col-lg-9 article__sections">
<div class="section-paragraph">Over the past decades, the political tensions that regularly plague WHO have undermined
its authority. Every time an international public health emergency has arisen, WHO has faced internal political
gridlock.{_popup(1)} Confidence in the UN agency has dwindled with every health crisis. Today, no one disputes that the
political functioning of WHO is an impediment to fulfilling its role as a global health crisis coordinator and promoter
of science-based standards. The UN system is still dependent on world politics,{_popup(2)} the failings of which were
far too evident during the first months of the COVID-19 crisis. {TAIL}</div>
<div class="section-paragraph">A second paragraph with 10<sup>5</sup> cells per m<sup>2</sup>.{_popup(3)} {TAIL}</div>
</div></body></html>
"""

NEWER_TEMPLATE = f"""
<html><head>{HEAD}<meta property="og:description" content="{DESCRIPTION}" /></head><body>
<section id="bodymatter"><div id="para10" role="paragraph">Over the past decades, the political tensions that regularly
plague WHO have undermined its authority. Every time an international public health emergency has arisen, WHO has faced
internal political gridlock.<a id="cecref10" href="#bib1" role="doc-biblioref" data-xml-rid="bib1"><sup>1</sup></a>
Confidence in the UN agency has dwindled with every health crisis. Today, no one disputes that the political functioning
of WHO is an impediment to fulfilling its role as a global health crisis coordinator and promoter of science-based
standards. The UN system is still dependent on world politics,<a id="cecref20" href="#bib2" role="doc-biblioref"
data-xml-rid="bib2"><sup>2</sup></a> the failings of which were far too evident during the first months of the
COVID-19 crisis. We describe what should change.</div></section>
</body></html>
"""


def _soup(html):
    return BeautifulSoup(html, "lxml")


def test_older_template_description_loses_flattened_markers():
    assert ElsevierBV(_soup(OLDER_TEMPLATE)).parse()["abstract"] == FIXED


def test_newer_template_description_loses_flattened_markers():
    assert ElsevierBV(_soup(NEWER_TEMPLATE)).parse()["abstract"] == FIXED


def test_body_text_drops_markers_and_hidden_references_but_keeps_unlinked_superscripts():
    soup = _soup(OLDER_TEMPLATE)
    first, second = soup.select("div.section-paragraph")
    text = citation_free_text(first)
    assert "gridlock. Confidence" in text and "politics, the failings" in text
    assert "Google Scholar" not in text and "Reference title" not in text
    # an unlinked superscript is text, as tag.text has it
    assert citation_free_text(second).startswith("A second paragraph with 105 cells per m2. ")
    # the page itself is not changed
    assert "Google Scholar" in first.text


def test_unlinked_numbers_in_meta_text_are_kept():
    """CO2, m2 and the like stay when the body shows them as text, not as citation links."""
    html = f"""<html><head>{HEAD}</head><body><div class="article__sections"><div class="section-paragraph">
    Emissions of CO<sub>2</sub> rose by 5% per m<sup>2</sup> of floor area.<sup><a href="#bib4">4</a></sup>
    The trend held.</div></div></body></html>"""
    soup = _soup(html)
    text = "Emissions of CO2 rose by 5% per m2 of floor area.4 The trend held."
    assert without_flattened_citations(text, soup) == "Emissions of CO2 rose by 5% per m2 of floor area. The trend held."
    # text that isn't a stretch of the page's paragraphs is left alone
    other = "A different text that ends with a number like area.4 Then more."
    assert without_flattened_citations(other, soup) == other


def test_adjacent_markers_leave_no_separator():
    """Two pop-up markers with a comma between them ("established.1, 2 Some") leave no stray ", "."""
    html = f"""<html><body><div class="article__sections"><div class="section-paragraph">Its value is yet to be
    established. {_popup(1)}, {_popup(2)} Some of the trials say so.</div></div></body></html>"""
    text = citation_free_text(_soup(html).select_one("div.section-paragraph"))
    assert " ".join(text.split()) == "Its value is yet to be established. Some of the trials say so."


def test_line_break_before_marker_and_a_range_of_markers():
    """Step 7b (3,361 Lancet pages kept their numbers after the first fix): the older template breaks the line before
    each pop-up marker ("children.\\n <div class="dropBlock ...">"), and the meta writes the run of markers "1", "2", "3"
    as "1–3". Shape of 10.1016/S0140-6736(18)32325-0 as stored."""
    html = f"""<html><head>{HEAD}</head><body><div class="article__sections"><div class="section-paragraph">Increasing
      rates of caesarean section are debated because of worse outcomes for mothers and their children.
      {_popup(1)} As Ties Boerma and colleagues
      {_popup(2)} report in this Series on optimising caesarean section use,
      {_popup(1)},{_popup(2)},{_popup(3)} there are unacceptable disparities in 2015 data.</div></div></body></html>"""
    soup = _soup(html)
    text = ("Increasing rates of caesarean section are debated because of worse outcomes for mothers\nand their "
            "children.1 As Ties Boerma and colleagues2 report in this Series on optimising caesarean section use,1–3\n"
            "there are unacceptable")
    assert without_flattened_citations(text, soup) == (
        "Increasing rates of caesarean section are debated because of worse outcomes for mothers and their children. "
        "As Ties Boerma and colleagues report in this Series on optimising caesarean section use, there are "
        "unacceptable")
    assert without_flattened_citations(text + "...", soup).endswith("there are unacceptable...")


def test_number_in_meta_that_is_not_the_markers_label_is_kept():
    """A number in the meta where the page has a marker, but not the marker's own label, means the meta is not this
    paragraph's flattened text: leave it alone. A number right after a marker that the page prints as text stays."""
    html = f"""<html><body><div class="article__sections"><div class="section-paragraph">Cases rose in the north,
    {_popup(4)} 2014 saw more.</div></div></body></html>"""
    soup = _soup(html)
    assert without_flattened_citations("Cases rose in the north,4 2014 saw more.", soup) == (
        "Cases rose in the north, 2014 saw more.")
    assert without_flattened_citations("Cases rose in the north,7 2014 saw more.", soup) == (
        "Cases rose in the north,7 2014 saw more.")
