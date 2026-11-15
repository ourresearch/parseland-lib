"""oxjob #2239 round 6: reference lists, acknowledgments and funding statements from the page's own template, filled
where the winning parser returned none; an image or archive link is never the PDF."""
from parseland_lib.parse import parse_page


def parse(body, head="", url="https://example.org/article/1"):
    return parse_page(f"<html><head>{head}</head><body>{body}</body></html>".encode(), "doi", url)


def sn_item(text, counter=None, doi=None):
    counter = f' data-counter="{counter}"' if counter else ""
    button = f'<p class="c-article-references__links"><a data-doi="{doi}" href="https://doi.org/{doi}">Article</a></p>' \
        if doi else ""
    return (f'<li class="c-article-references__item"{counter}><p class="c-article-references__text">{text}</p>'
            f'{button}</li>')


def test_springer_nature_references_acknowledgments_and_funding():
    body = (f'<section data-title="References"><ol class="c-article-references">'
            f'{sn_item("Darnell, J. E. Transcription factors. <i>Nat. Rev. Cancer</i> 2, 740 (2002).", "1.", "10.1038/nrc906")}'
            f'{sn_item("Bar-On YM. The biomass distribution on earth. PNAS. 2018;115:6506.", "2.")}</ol></section>'
            '<section data-title="Acknowledgements"><div class="c-article-section__content"><p>We thank the reviewers.</p>'
            '</div></section><section data-title="Funding"><div class="c-article-section__content">'
            '<p>Open Access funding enabled and organized by Projekt DEAL.</p></div></section>')
    out = parse(body, url="https://www.nature.com/articles/s41698-022-00278-4")
    assert [(r["raw"], r["doi"]) for r in out["references"]] == [
        ("Darnell, J. E. Transcription factors. Nat. Rev. Cancer 2, 740 (2002).", "10.1038/nrc906"),
        ("Bar-On YM. The biomass distribution on earth. PNAS. 2018;115:6506.", None)]
    assert out["references_complete"] is True
    assert out["acknowledgments"] == "We thank the reviewers."
    assert out["funding_statement"] == "Open Access funding enabled and organized by Projekt DEAL."


def test_springer_endnotes_numbered_with_gaps_are_not_a_whole_list():
    body = ('<ol class="c-article-references">' + sn_item("Note two.", "2.") + sn_item("Note three.", "3.")
            + sn_item("Note eight.", "8.") + "</ol>")
    out = parse(body, url="https://link.springer.com/chapter/10.1057/9781137291967_3")
    assert len(out["references"]) == 3 and out["references_complete"] is False


def test_taylor_francis_references_take_the_cited_doi_not_the_citing_one():
    entry = ('<li id="CIT0001"><span> Hogg J C, Pare P D. The nature of small-airway obstruction. '
             '<span class="citation_source-journal">New Engl J Med</span> 2004; 350: 2645–2653 '
             '<span class="xlinks-container"><a href="/servlet/linkout?suffix=e_1&amp;dbid=16&amp;'
             'doi=10.1080%2F15412550902835168&amp;key=10.1056%2FNEJMoa032158">[Crossref]</a></span></span></li>')
    body = ('<div class="pb-dropzone" data-pb-dropzone="x"></div><div id="references-Section">'
            f'<ul class="references numeric-ordered-list">{entry}</ul></div>')
    out = parse(body, '<meta name="dc.Identifier" scheme="doi" content="10.1080/15412550902835168"/>',
                "https://www.tandfonline.com/doi/full/10.1080/15412550902835168")
    assert out["references"][0]["doi"] == "10.1056/NEJMoa032158"
    assert out["references"][0]["raw"].startswith("Hogg J C, Pare P D. The nature of small-airway obstruction. New")
    assert "[Crossref]" not in out["references"][0]["raw"]


def test_ojs_references_one_per_paragraph_and_fragments_are_not_whole():
    head = '<meta name="generator" content="Open Journal Systems 3.3.0.13"/>'
    whole = ('<section class="item references"><h2 class="label">References</h2><div class="value">'
             '<p>Ali, A.S., (1981). Sandstone Diagenesis. Gulf Science.</p><p>Crow, C.W., (1989). Acid Fracturing.</p>'
             '</div></section>')
    out = parse(whole, head)
    assert [r["raw"] for r in out["references"]] == ["Ali, A.S., (1981). Sandstone Diagenesis. Gulf Science.",
                                                     "Crow, C.W., (1989). Acid Fracturing."]
    assert out["references_complete"] is True
    broken = whole.replace("<p>Crow, C.W., (1989). Acid Fracturing.</p>",
                           "<p>Crow, C.W., (1984). Precipitation of Hydrated</p><p>Silica from Spent Acid – How</p>"
                           "<p>much of a problem is it? Paper SPE 13083</p>")
    assert parse(broken, head)["references_complete"] is False


def test_headed_acknowledgments_in_div_paragraphs_and_not_in_navigation():
    body = ('<nav><h2>Acknowledgments</h2><p>Jump to the acknowledgments of this article</p></nav>'
            '<section id="aep-acknowledgment-id31"><h2 class="u-h4">Acknowledgments</h2>'
            '<div class="u-margin-s-bottom">This work is supported by the National Natural Science Foundation.</div>'
            '</section><div class="details-block"><h3>Funding</h3><div class="collapse"><a href="/f">+ Simons '
            'Foundation</a> <a href="/more">More from this funder</a></div></div>')
    out = parse(body, url="https://www.sciencedirect.com/science/article/pii/S0001")
    assert out["acknowledgments"] == "This work is supported by the National Natural Science Foundation."
    assert out["funding_statement"] is None


def test_an_image_link_is_never_the_pdf():
    head = '<meta name="citation_pdf_url" content="https://www.jstage.jst.go.jp/pub/pdfpreview/kds/60/6_60_1.jpg"/>'
    out = parse("", head, "https://www.jstage.jst.go.jp/article/kds/60/6/60_1/_article")
    assert not [u for u in out["urls"] if u["content_type"] == "pdf"]


def test_scielo_classic_references_follow_their_markers_without_numbers_or_link_buttons():
    body = "".join(f'<!-- ref --><p><font size="2">{n}. Author {n}. A title. J Med 2002; 22: 268. [ <a href="#">Links</a> ]'
                   f'</font></p><!-- end-ref -->' for n in (1, 2))
    url = "https://scielo.conicyt.cl/scielo.php?script=sci_arttext&pid=S0718"
    out = parse(body, f'<link rel="canonical" href="{url}"/>', url)
    assert [r["raw"] for r in out["references"]] == ["Author 1. A title. J Med 2002; 22: 268.",
                                                     "Author 2. A title. J Med 2002; 22: 268."]
    assert out["references_complete"] is True


def test_scielo_reference_list_is_the_references_section_not_a_footnote_list():
    notes = '<div class="ref-list"><ul class="refList"><li><sup class="xref">*</sup><div>Corresponding note.</div></li></ul></div>'
    refs = ('<div class="articleSection" data-anchor="References"><h1>REFERENCES</h1><div class="ref-list"><ul class="refList">'
            '<li><sup class="xref big">1</sup><div> Li TC. Recurrent miscarriage. Hum Reprod Update. 8: 463-81, 2002.</div></li>'
            '<li><sup class="xref big">2</sup><div> Rai R. Antiphospholipid syndrome. Lancet. 2010. '
            '&lt;https://doi.org/10.1359/jbmr.1999.14.7.1061/full&gt;.</div></li></ul></div></div>')
    url = "https://www.scielo.br/j/rbr/a/crWMcpXPZjPpSzdVbBHt"
    out = parse(notes + refs, f'<link rel="canonical" href="{url}"/>', url)
    assert [r["raw"][:20] for r in out["references"]] == ["Li TC. Recurrent mis", "Rai R. Antiphospholi"]
    assert out["references"][1]["doi"] == "10.1359/jbmr.1999.14.7.1061"
    assert out["references_complete"] is True


def test_plain_citation_reference_tags_are_a_reference_list_highwire_ones_are_not():
    plain = ('<meta name="citation_reference" content="Smith J. A study of things. J Things. 2001;1:1-2."/>'
             '<meta name="citation_reference" content="Doe A. More things. J Things. 2003;3:3-4."/>')
    out = parse("", plain)
    assert len(out["references"]) == 2 and out["references_complete"] is True
    highwire = '<meta name="citation_reference" content="citation_title=A study; citation_author=J. Smith"/>'
    assert parse("", plain + highwire)["references"] is None
