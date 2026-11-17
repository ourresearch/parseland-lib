"""oxjob #2239 phase 2, class newkeys-r7: back-matter texts the round-7 junk tripwire found wrong. A funding section
ends at a bold label that heads another section ("Declaration of conflicting interests", "Patient consent",
"Provenance and peer review"); BioMed Central's "pre-publication history" notice is not a reference. (OSTI's record
rows "Sponsoring Org." / "DOE Contract Number" are metadata, not a funding statement: tests/test_osti_fields.py.)"""
from parseland_lib.parse import parse_page


def parse(body, head="", url="https://example.org/article/1"):
    return parse_page(f"<html><head>{head}</head><body>{body}</body></html>".encode(), "doi", url)


# ---------------------------------------------------------------- a funding section with sub-sections under bold labels

NO_GRANT = ("This research received no specific grant from any finding agency in the public, commercial or not for "
            "profit sectors.")


def funding_section(paragraphs, heading="Funding"):
    """auctoresonline.org's article template: an <h4> heading, then a block of <p>s (cut from a stored page)."""
    return ('<h4 class="article-det-header" id="conclusion">Conclusion</h4>'
            '<div class="parent-cls"><p>We conclude.</p></div>'
            f'<h4 class="article-det-header" id="funding">{heading}</h4><div class="parent-cls" data-for="funding">'
            + "".join(paragraphs) + '</div><h4 id="references">References</h4>')


BMJ_STYLE_TAIL = ['<p><span><strong>Declaration of conflicting interests </strong></span></p>',
                  "<p><span>The authors declared no potential conflicts of interest.</span></p>",
                  "<p><span><strong>Patient consent</strong></span></p><p><span>Obtained.</span></p>",
                  "<p><span><strong>Provenance and peer review</strong></span></p>",
                  "<p><span>Not commissioned; externally peer reviewed.</span></p>"]


def test_funding_section_ends_at_a_bold_label_heading_another_section():
    out = parse(funding_section([f"<p><span>{NO_GRANT}</span></p>", *BMJ_STYLE_TAIL]))
    assert out["funding_statement"] == NO_GRANT


def test_funding_section_ends_at_patient_consent_or_provenance_labels_too():
    for label in ("Patient consent", "Provenance and peer review", "Ethics approval", "Competing interests",
                  "Author contributions", "Data availability statement"):
        paragraphs = [f"<p>{NO_GRANT}</p>", f"<p><b>{label}</b></p>", "<p>Something else entirely.</p>"]
        assert parse(funding_section(paragraphs))["funding_statement"] == NO_GRANT, label


def test_funding_section_keeps_all_its_own_paragraphs():
    paragraphs = [f"<p>{NO_GRANT}</p>", "<p>Publication support was provided by the Open Access Publishing Fund.</p>"]
    assert parse(funding_section(paragraphs))["funding_statement"] == (
        NO_GRANT + "\nPublication support was provided by the Open Access Publishing Fund.")


def test_funding_section_keeps_text_after_a_bold_label_that_is_not_another_sections():
    # a bold funder name or funding label inside the funding section is part of it
    for label in ("National Institutes of Health", "Open Access funding", "Funding information"):
        paragraphs = [f"<p>{NO_GRANT}</p>", f"<p><b>{label}</b></p>", "<p>Grant R01 GM123456.</p>"]
        assert parse(funding_section(paragraphs))["funding_statement"] == (
            f"{NO_GRANT}\n{label}\nGrant R01 GM123456."), label


def test_bold_sentence_in_the_funding_section_is_text_not_a_label():
    paragraphs = [f"<p>{NO_GRANT}</p>", "<p><b>Ethics approval was not needed for this study.</b></p>"]
    assert parse(funding_section(paragraphs))["funding_statement"] == (
        NO_GRANT + "\nEthics approval was not needed for this study.")


def test_acknowledgments_section_is_unchanged_by_the_funding_rule():
    paragraphs = ["<p>We thank the nurses of the unit for their help.</p>", "<p><b>Conflict of interest</b></p>",
                  "<p>None declared.</p>"]
    out = parse(funding_section(paragraphs, heading="Acknowledgments"))
    assert out["acknowledgments"] == ("We thank the nurses of the unit for their help.\nConflict of interest\n"
                                      "None declared.")


# ---------------------------------------------------------------- BioMed Central's pre-publication history notice

BMC = "https://bmcmedgenet.biomedcentral.com/articles/10.1186/1471-2350-14-38"
PREPUB = ('<h3 class="c-article-references__heading u-h3">Pre-publication history</h3>'
          '<ul class="c-article-references">'
          '<li class="c-article-references__item js-c-reading-companion-references-item">'
          '<p class="c-article-references__text" id="ref-CR16">The pre-publication history for this paper can be '
          'accessed here:<a href="http://www.biomedcentral.com/1471-2350/14/38/prepub">'
          'http://www.biomedcentral.com/1471-2350/14/38/prepub</a> </p></li></ul>')


def sn_item(text, counter):
    return (f'<li class="c-article-references__item" data-counter="{counter}"><p class="c-article-references__text">'
            f'{text}</p></li>')


ENTRIES = [("Brock DJ, Shrimpton AE: Non-paternity and prenatal genetic screening. Lancet. 1991, 338: 1151.", "1."),
           ("Wolf M, Musch J: Estimating the Prevalence of Nonpaternity in Germany. Hum Nat. 2012, 23: 208-217.", "2.")]


def bmc_page(entries, tail=PREPUB):
    items = "".join(sn_item(text, counter) for text, counter in entries)
    return parse(f'<section data-title="References"><ol class="c-article-references">{items}</ol>{tail}</section>',
                 url=BMC)


def test_bmc_pre_publication_history_notice_is_not_a_reference_and_the_list_stays_whole():
    out = bmc_page(ENTRIES)
    assert [r["raw"] for r in out["references"]] == [text for text, _ in ENTRIES]
    assert out["references_complete"] is True


def test_bmc_list_with_a_gap_is_still_not_whole_without_the_notice():
    out = bmc_page([ENTRIES[0], (ENTRIES[1][0], "3.")])
    assert len(out["references"]) == 2 and out["references_complete"] is False


def test_a_reference_that_cites_a_pre_publication_history_is_kept():
    cited = ("Smith J: The pre-publication history of open peer review. BMC Med. 2015, 13: 1.", "3.")
    out = bmc_page([*ENTRIES, cited], tail="")
    assert out["references"][-1]["raw"] == cited[0] and out["references_complete"] is True
