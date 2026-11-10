"""World Scientific's own abstract block fills pages the winning parser left without one (oxjob #2145)."""
from parseland_lib.parse import parse_page

_CONTEXT = '<meta name="pbContext" content=";website:website:wspc-site;article:article:10.1142/S0000;">'


def _old(text, context=_CONTEXT):
    return (f'<html><head>{context}<title>A chapter | Some Book</title></head><body><div class="article__body ">'
            f'<div class="NLM_abstract"><strong>Abstract:</strong> <p>{text}</p></div></div></body></html>').encode()


def _new(paras):
    body = "".join(f"<p> {p}</p>" for p in paras)
    return (f'<html><head>{_CONTEXT}</head><body><div class="article__body "><div class="sectionInfo '
            f'abstractSectionHeading"><h2>Abstract</h2></div><div class="hlFld-Abstract"><div class="abstractSection '
            f'abstractInFull">{body}</div></div></div></body></html>').encode()


REAL = ("The power spectrum of the density fluctuations in the solar wind and its relationship with the spectra of the "
        "velocity and the magnetic field fluctuations is investigated.")


def _abstract(html):
    return parse_page(html, "doi", "https://doi.org/10.1142/S0000")["abstract"]


def test_old_template_abstract_is_read():
    assert _abstract(_old(REAL)) == REAL


def test_new_template_abstract_is_read():
    assert _abstract(_new(["Background:", REAL])) == "Background:\n" + REAL


def test_section_list_stand_in_is_not_an_abstract():
    assert _abstract(_old("The following sections are included: Introduction Air Pollutants Sulfur dioxide")) is None
    assert _abstract(_old("The following section is included: Index")) is None
    assert _abstract(_old("The Table of Contents for the book is as follows: PREFACE COMMITTEES Position papers")) is None


def test_headings_and_notices_are_not_abstracts():
    for text in ("Index", "Author Index.", "CONTENTS", "No abstract received."):
        assert _abstract(_old(text)) is None, text


def test_chapter_preview_cut_off_is_not_an_abstract():
    assert _abstract(_old("Two friends hoisted Milne out of his abyss of sad inertia. Chandra judged that…")) is None
    assert _abstract(_old("Our first task is to make these concepts precise….")) is None
    assert _abstract(_old("Let A and B be n×n matrices. Then we define the commutator of A and B as")) is None


def test_other_sites_are_not_read():
    other = '<meta name="pbContext" content=";website:website:other-site;">'
    assert _abstract(_old(REAL, context=other)) is None
