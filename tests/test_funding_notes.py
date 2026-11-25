"""oxjob #2630: funding printed outside a "Funding" heading: a footnote or author note that says who funded the work,
or a paragraph that opens with a funding label. Markup as each template prints it (stored pages in #2630 EXPLORE § 1)."""
from parseland_lib.parse import parse_page


def parse(body, url="https://example.org/article/1"):
    return parse_page(f"<html><head></head><body>{body}</body></html>".encode(), "doi", url)


def test_sciencedirect_article_footnote():
    body = ('<div class="Footnotes"><dl class="footnote"><dt class="footnote-label"><sup><a href="#baep-article-'
            'footnote-id1">☆</a></sup></dt><dd class="u-margin-xxl-left"><p>This study supported by U.S. Public Health '
            'service Grant H-1999</p></dd></dl></div>')
    out = parse(body, "https://www.sciencedirect.com/science/article/pii/0024320566902839")
    assert out["funding_statement"] == "This study supported by U.S. Public Health service Grant H-1999"


def test_wiley_header_note():
    body = ('<div class="epub-sections"><div class="article-header__references-container no-truncate" id="nss">'
            '<sup>†</sup><div class="header-note-content"><p>This work was partly supported by the Special Postdoctoral '
            'Researchers Program at RIKEN.</p></div></div></div>')
    out = parse(body, "https://onlinelibrary.wiley.com/doi/10.1002/anie.200500777")
    assert out["funding_statement"] == "This work was partly supported by the Special Postdoctoral Researchers Program at RIKEN."


def test_note_that_also_thanks_someone_is_an_acknowledgment():
    body = ('<div class="header-note-content"><p>This work was supported by the C.N.R. (Rome). We thank Professor '
            '<i>F. Calderazzo</i> for helpful discussions.</p></div>')
    out = parse(body)
    assert out["acknowledgments"] == ("This work was supported by the C.N.R. (Rome). We thank Professor F. Calderazzo "
                                      "for helpful discussions.")
    assert out["funding_statement"] is None


def test_springer_additional_information():
    body = ('<section data-title="Additional information"><div class="c-article-section" id="additional-information-'
            'section"><h2 class="c-article-section__title">Additional information</h2><div class="c-article-section__'
            'content" id="additional-information-content"><p><i>Dedicated to J. Céa on his 60th birthday</i></p><p>The '
            'study is supported by the Swedish Medical Research Council, project no. B81-21X-4803-6A.</p></div></div>'
            '</section>')
    out = parse(body, "https://link.springer.com/article/10.1007/BF00343996")
    assert out["funding_statement"] == "The study is supported by the Swedish Medical Research Council, project no. B81-21X-4803-6A."


def test_lww_author_notes_and_heading():
    body = ('<section id="ejp-article-authors-info"><div class="ejp-article-authors-info-holder"><p>The authors have no '
            'personal or proprietary interest in any of the techniques used in this study.</p><p>This study was '
            'supported in part by an unrestricted grant from Research to Prevent Blindness, Inc., New York, NY.</p>'
            '</div></section>')
    out = parse(body)
    assert out["funding_statement"] == ("This study was supported in part by an unrestricted grant from Research to "
                                        "Prevent Blindness, Inc., New York, NY.")
    out = parse('<h3>Financial support and sponsorship</h3><p>This work was supported by Ministry of Science and '
                'Technology (MOST) of China.</p><h3>Conflicts of interest</h3><p>None.</p>')
    assert out["funding_statement"] == "This work was supported by Ministry of Science and Technology (MOST) of China."


def test_highwire_footnote_label_without_colon():
    body = ('<div class="section fn-group"><ul><li class="fn-financial-disclosure"><p>Funding The R L Gardner Cancer '
            'Research Fund (North Manchester).</p></li><li class="fn-conflict"><p>Conflict of interest None.</p></li>'
            '</ul></div>')
    assert parse(body)["funding_statement"] == "The R L Gardner Cancer Research Fund (North Manchester)."


def test_run_in_label_and_label_block():
    body = ('<div class="articleinfo"><p><strong>Funding:</strong> This work was supported by the Finnish Funding '
            'Agency for Technology and Innovation.</p></div>')
    assert parse(body)["funding_statement"] == ("This work was supported by the Finnish Funding Agency for Technology "
                                                "and Innovation.")
    body = ('<section class="sec"><div class="title">Funding</div><p>JDRF (2-SRA-2018-666-M-R); Children’s Diabetes '
            'Foundation</p></section>')
    assert parse(body)["funding_statement"] == "JDRF (2-SRA-2018-666-M-R); Children’s Diabetes Foundation"
    assert parse('<p><b>Funding</b>: JDRF</p>')["funding_statement"] == "JDRF"


def test_not_funding_notes():
    # an endnote's argument, a disclosure list, a conflict of interest, a note that there was none, a glossary line
    assert parse('<div class="footnote"><p>This view is supported by Smith (1990).</p></div>')["funding_statement"] is None
    assert parse('<div class="disclosures"><p><strong>Research Funding:</strong> Roche (Inst)</p></div>')[
        "funding_statement"] is None
    assert parse('<div class="Footnotes"><dl class="footnote"><dd><p>Dr. Smith has received consulting fees from '
                 'Pfizer.</p></dd></dl></div>')["funding_statement"] is None
    assert parse('<div class="Footnotes"><dl class="footnote"><dd><p>This work received no funding from any '
                 'agency.</p></dd></dl></div>')["funding_statement"] is None
    assert parse('<p><b>Funding</b>: Foundation</p>')["funding_statement"] is None


def test_funding_the_acknowledgments_already_print_stays_there():
    body = ('<section><h2>Acknowledgments</h2><p>We thank A. Jones. This work was supported by NIH grant R01 GM12345.'
            '</p></section><div class="Footnotes"><dl class="footnote"><dd><p>This work was supported by NIH grant R01 '
            'GM12345.</p></dd></dl></div>')
    out = parse(body)
    assert out["acknowledgments"] == "We thank A. Jones. This work was supported by NIH grant R01 GM12345."
    assert out["funding_statement"] is None
