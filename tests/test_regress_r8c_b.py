"""Abstract regressions found measuring round 8's head 5cd21b8 against production ec20266 (oxjob #2239, phase 2, round 8c).

- Springer Link: once #2352 stopped the Elsevier parser claiming Springer pages that cite Elsevier, springer.py read
  their abstracts, and it took the graphical abstract's (visually hidden) figure caption from the Abstract section, and
  the JSON-LD description where that runs on into the next section (EMBO's Synopsis) because it was longer.
- Cochrane Library: a protocol's abstract is shown as "This is a protocol for a Cochrane Review (Intervention). The
  objectives are as follows: <objectives>"; the label-v2 gold keeps that line (both labelled protocol pages), so it is
  not cut.

Markup is cut down from the stored pages.
"""
import json

from parseland_lib.not_abstract import clean_abstract
from parseland_lib.parse import parse_page

URL = "https://link.springer.com/article/10.1007/s10840-024-01853-4"

INTRO = ("Pulsed-field energy (PFA) and very high-power short-duration radiofrequency (vHPSD-RF) are two novel ablation "
         "methods for pulmonary vein isolation (PVI). Both show promise for improving efficacy and safety.")
METHODS = ("Retrospective analysis of 82 patients with symptomatic AF. Of these, 52 patients received PFA and 30 received "
           "vHPSD-RF as index procedure. At the 6-month follow-up, AF recurrence occurred in 4 and 5 patients.")
CONCL = "PFA and vHPSD-RF were associated with similar effectiveness and safety profiles."
CAPTION = ("Summarizing the study methods and results. PFA has been found to be associated with shorter procedure "
           "durations (A) and longer fluoroscopy times (B). Abbreviations: PFA, pulsed-field ablation")


def _springer(abstract_content, description=None, after=""):
    ld = ""
    if description is not None:
        ld = ('<script type="application/ld+json">'
              + json.dumps({"mainEntity": {"headline": "A title", "description": description}}) + "</script>")
    return (f'<html><head><link rel="canonical" href="{URL}"/><meta name="citation_title" content="A title"/>'
            '<meta name="citation_publisher" content="Springer US"/>'
            f'{ld}</head><body><section aria-labelledby="Abs1" data-title="Abstract" lang="en">'
            '<div class="c-article-section" id="Abs1-section"><h2 class="c-article-section__title" id="Abs1">Abstract'
            f'</h2><div class="c-article-section__content" id="Abs1-content">{abstract_content}</div></div></section>'
            f'{after}</body></html>').encode()


def _sub(label):
    return f'<h3 class="c-article__sub-heading" data-test="abstract-sub-heading">{label}</h3>'


GRAPHICAL = (_sub("Graphical Abstract") + '<div class="c-article-section__figure" data-test="figure"><figure>'
             '<div class="c-article-section__figure-content"><div class="c-article-section__figure-item"><picture>'
             '<img alt="" src="//media.springernature.com/lw685/x.png"/></picture></div>'
             '<div class="c-article-section__figure-description u-visually-hidden" id="figure-a-desc">'
             f'<p>{CAPTION}</p></div></div></figure></div>')

STRUCTURED = (_sub("Introduction") + f"<p>{INTRO}</p>" + _sub("Methods and results") + f"<p>{METHODS}</p>"
              + _sub("Conclusion") + f"<p>{CONCL}</p>")


def _abstract(html):
    return parse_page(html, "doi", URL)["abstract"]


# --- Springer: a graphical abstract's caption is not abstract text ---------------------------------------------------

def test_graphical_abstract_caption_is_left_out():
    abstract = _abstract(_springer(STRUCTURED + GRAPHICAL))
    assert CAPTION[:40] not in abstract
    assert INTRO in abstract and CONCL in abstract


def test_graphical_abstract_caption_left_out_beside_its_json_ld_description():
    # the JSON-LD description is the three parts without their labels (and Springer's trailing whitespace)
    description = f"{INTRO} {METHODS} {CONCL} \n\n                \n                  \n              "
    abstract = _abstract(_springer(STRUCTURED + GRAPHICAL, description))
    assert CAPTION[:40] not in abstract
    assert " ".join(abstract.split()) == f"{INTRO} {METHODS} {CONCL}"


def test_paragraphs_without_a_figure_are_all_kept():
    # look-alike: an abstract of several plain paragraphs keeps every one
    abstract = _abstract(_springer(f"<p>{INTRO}</p><p>{METHODS}</p><p>{CONCL}</p>"))
    assert abstract == f"{INTRO}\n{METHODS}\n{CONCL}"


# --- Springer: a JSON-LD description that runs past the Abstract section ---------------------------------------------

BODY = ("The maternal-to-zygotic transition (MZT) is a reprograming process encompassing zygotic genome activation and "
        "the clearance of maternally-provided mRNAs. Here, we have performed a proof-of-principle CRISPR-RfxCas13d "
        "maternal screen. This screen identified <i>Bckdk</i> as a novel post-translational regulator of MZT.")
BODY_TEXT = BODY.replace("<i>", "").replace("</i>", "")
SYNOPSIS = ("Post-translational regulation during the maternal-to-zygotic transition (MZT) remains largely unexplored. "
            "Using an optimized CRISPR-RfxCas13d screening strategy, this study identifies Bckdk as a kinase.")
SYNOPSIS_SECTION = (f'<section data-title="Synopsis"><div class="c-article-section"><h2>Synopsis</h2>'
                    f'<div class="c-article-section__content"><p>{SYNOPSIS}</p></div></div></section>')


def test_json_ld_description_running_into_the_synopsis_gives_way_to_the_section():
    description = f"{BODY_TEXT} \n                \n               {SYNOPSIS} \n                \n   "
    abstract = _abstract(_springer(f"<p>{BODY}</p>", description, after=SYNOPSIS_SECTION))
    assert abstract == BODY_TEXT


def test_longer_json_ld_description_with_text_of_the_section_still_wins():
    # look-alike: the description is longer because the section holds text the <p> reader does not take (a list):
    # that text is the abstract's own, so the description stays
    items = "First, the screen. Second, the kinase."
    content = f"<p>{BODY}</p><ul><li>First, the screen.</li><li>Second, the kinase.</li></ul>"
    description = f"{BODY_TEXT} {items}"
    assert _abstract(_springer(content, description)) == description


def test_json_ld_description_that_is_not_the_section_text_keeps_the_longer_rule():
    # look-alike: a description that does not start with the section's text is left to the longer-wins rule
    description = f"{SYNOPSIS} {BODY_TEXT}"
    assert _abstract(_springer(f"<p>{BODY}</p>", description, after=SYNOPSIS_SECTION)) == description


# --- Cochrane Library: a protocol's opening line is the site's template (round 8d reverses round 8c's keep) --------

OBJECTIVES = ("To evaluate the impact of the different GnRHa protocols as adjuncts to ovarian stimulation in women "
              "undergoing ART cycles.")


def test_cochrane_protocol_line_is_cut():
    # the rubric and the fresh-draw tripwire's judge call it site text (tests/test_tripwire_r8d.py); the label keeps it
    text = f"This is a protocol for a Cochrane Review (Intervention). The objectives are as follows: {OBJECTIVES}"
    assert clean_abstract(text) == OBJECTIVES


def test_other_leading_notices_are_still_cut():
    # look-alike: round 8's other leading notices stay cut
    notice = ("Correction: On 16th February 2017, the author K. Peiris was removed from this paper. This error is "
              "regretted. - Editor")
    assert clean_abstract(f"{notice} {OBJECTIVES}") == OBJECTIVES
