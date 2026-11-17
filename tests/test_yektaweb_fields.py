"""Yektaweb article pages (oxjob #2289): the journal platform of about 70 Iranian journal sites.

Markup is cut down from stored pages of the template's two layouts (17 Nov 2026): the older one prints the article in
table rows (td.abstract, td.abstractsmall, td.abstractmed), the newer one in div.yw_text_small blocks. Both print the
byline as search.php?...author= links with <sup> affiliation numbers and a <sup>*</sup> on one author, the numbered
affiliation lines in one <em> (the starred author's line ends with an e-mail address), the abstract under a bold
"Abstract:" row, and the references as div.text_med entries in .articles_ref.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.yektaweb import Yektaweb

URL = "https://journal.example.ac.ir/article-1-3235-en.html"
GENERATOR = '<meta name="GENERATOR" content="Yektaweb 4547" >'
NAMES = ["Azizi, Farnoush", "Amiri, Azadeh", "Paran, Maryam"]
AFFS = ["Department of Nursing, Shiraz University of Medical Sciences, Shiraz, Iran.",
        "Department of Operating Room, Shiraz University of Medical Sciences, Shiraz, Iran.",
        "School of Nursing and Midwifery, Shiraz University of Medical Sciences, Shiraz, Iran."]
ABSTRACT = ("<strong>Background and Objectives:</strong> Academic procrastination can have an adverse effect on "
            "students' educational, communicational, health, and career prospects.<br>\n<strong>Methods:</strong> This "
            "descriptive cross-sectional correlational study was performed on 95 operating room students.<br>\n"
            "<strong>Conclusion:</strong> Academic procrastination is less among students with higher self-efficacy.")
REFS = ("<div class='text_med' dir='ltr'>1. Xu P, Xiong ZH. State anxiety reduces procrastinating behavior. Motiv Emot. "
        "2016; 40(4):625-37. [DOI:10.1007/s11031-016-9554-x] [<a target=\"_blank\" href=\"https://doi.org/10.1007/"
        "s11031-016-9554-x\">DOI:10.1007/s11031-016-9554-x</a>] </div>"
        "<div class='text_med' dir='ltr'>2. Nasri S, Shahrokhi M. The prediction of academic procrastination. "
        "Res Sch Virtual Learn. 2013; 1(1):24-36. https://etl.journals.pnu.ac.ir/article_459.html</div>"
        "<div class='text_med' dir='ltr'>3. Klingsieck KB. Procrastination: When good things don't come to those who "
        "wait. Eur Psychol. 2013; 18(1):24-34. [<a target=\"_blank\" href=\"https://doi.org/10.1027/1016-9040/a000138\">"
        "DOI:10.1027/1016-9040/a000138</a>] </div>")


def _byline(names=("Farnoush Azizi", "Azadeh Amiri", "Maryam Paran"), star=2, numbered=True):
    parts = []
    for i, name in enumerate(names):
        mark = " <sup>*</sup>" if i == star else ""
        number = f"<sup>{i + 1}</sup>" if numbered else ""
        parts.append(f"<a href='search.php?sid=1&amp;slc_lang=en&author={name.split()[-1]}'> {name}</a>{mark}{number} "
                     f"<span dir='ltr' style='vertical-align:middle;'><a class='masterTooltip' href='http://orcid.org/"
                     f"0000-0002-1761-780{i}'><img src='./files/0allsites/images/orcid.png'></a></span>")
    return ", ".join(parts)


def _affiliations(email_on=2, corresponding_note=False, numbered=True):
    lines = []
    for i, aff in enumerate(AFFS if numbered else AFFS[:1]):
        line = f"{i + 1}- {aff}" if numbered else aff
        if corresponding_note and i == email_on:
            line += " (Corresponding Author)"
        if i == email_on or (not numbered and email_on is not None):
            line += " , <span dir='ltr'><skip_numfa>mparan90@gmail.com</skip_numfa></span>"
        lines.append(line)
    return " <br> ".join(lines)


def _table_page(byline, affiliations, abstract=ABSTRACT, refs=REFS, generator=GENERATOR, names=NAMES):
    """The older layout: table rows."""
    metas = "".join(f'<meta name="citation_author" content="{n}">'
                    f'<meta name="citation_author_institution" content="{AFFS[i]}">' for i, n in enumerate(names))
    ref_rows = (f'<tr><td align="center" colspan="2" class="row2t1">References</td></tr><tr><td colspan="2" '
                f'class="row1t1 articles_ref">{refs}</td></tr>') if refs else ""
    return (f'<html><head>{generator}<meta name="citation_title" content="Academic procrastination">{metas}'
            f'<meta name="citation_doi" content="10.32598/qums.15.7.2428.1"><meta property="og:url" content="{URL}">'
            f'<meta name="description" content="Background and Objectives: Academic procrastination can have an '
            f'adverse"></head><body><table id="table_article">'
            f'<tr><td class="abstractmed"><strong><a href="./article-1-3235-en.pdf"><span class="abstract_title">'
            f'Academic procrastination</span></a></strong></td></tr>'
            f'<tr><td colspan="2" class="abstract">{byline}</td></tr>'
            f'<tr><td colspan="2" dir="ltr" class="abstractsmall"><em>{affiliations}</em></td></tr>'
            f'<tr><td height="10" colspan="2"></td></tr>'
            f'<tr><td dir="ltr" class="row2t1 persian" colspan="2"><strong>Abstract:</strong> &nbsp; '
            f'<span dir=ltr> (1014 Views)</span> </td></tr>'
            f'<tr><td class="abstractmed" style="text-align:justify" colspan="2">{abstract}</td></tr>'
            f'<tr><td colspan="2" class="abstractmed"><strong>Keywords: </strong> <a href="search.php?sid=1&amp;'
            f'slc_lang=en&srchterm=students">students</a></td></tr>{ref_rows}</table></body></html>')


def _div_page(byline, affiliations, abstract=ABSTRACT, refs=REFS, generator=GENERATOR, names=NAMES):
    """The newer layout: div.yw_text_small blocks."""
    metas = "".join(f'<meta name="citation_author" content="{n}">'
                    f'<meta name="citation_author_institution" content="{AFFS[i]}">' for i, n in enumerate(names))
    ref_block = (f'<hr><div class="yw_text"><div class="yw_text_small"><strong>References</strong></div>'
                 f'<div class="yw_text_small articles_ref">{refs}</div></div>') if refs else ""
    return (f'<html><head>{generator}<meta name="citation_title" content="Academic procrastination">{metas}'
            f'<meta name="citation_doi" content="10.61186/ijcm.33.1.121"></head><body>'
            f'<div class="wid70p maxwSmall"><div class="yw_text abstractmed"><strong><a href="./article-1-1923-en.pdf">'
            f'<span class="abstract_title">Academic procrastination</span></a></strong></div>'
            f'<div class="yw_text_small abstract" dir="ltr">{byline}</div>'
            f'<div class="yw_text_small abstractsmall" dir="ltr"><em>{affiliations}</em></div>'
            f'<div class="yw_text_small persian" dir="ltr"><strong>Abstract:</strong> &nbsp; '
            f'<span dir=ltr> (556 Views)</span></div>'
            f'<div class="yw_text_small" dir="ltr" style="text-align:justify"><p>{abstract}</p></div>'
            f'<div class="yw_text_small"><strong>Keywords: </strong> <a href="search.php?sid=1&amp;slc_lang=en&'
            f'srchterm=x">x</a></div>{ref_block}</div></body></html>')


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _corr(html):
    return [a["name"] for a in _parse(html)["authors"] if a["is_corresponding"]]


def _own(html):
    return Yektaweb(BeautifulSoup(html, parser="lxml", features="lxml")).parse()


def test_claims_both_layouts_by_generator_tag():
    for page in (_table_page(_byline(), _affiliations()), _div_page(_byline(), _affiliations())):
        parser = Yektaweb(BeautifulSoup(page, parser="lxml", features="lxml"))
        assert parser.is_publisher_specific_parser() and parser.authors_found()


def test_look_alike_page_of_another_template_is_not_claimed():
    # the same byline, abstract and reference markup under another platform's generator tag (an Open Journal Systems
    # page, the template the meta-tag readers share), and a page with no generator tag at all
    for generator in ('<meta name="generator" content="Open Journal Systems 3.3.0.10"/>', ""):
        page = _div_page(_byline(), _affiliations(), generator=generator)
        parser = Yektaweb(BeautifulSoup(page, parser="lxml", features="lxml"))
        assert not parser.is_publisher_specific_parser() and not parser.authors_found()


def test_authors_and_affiliations_are_the_citation_tags():
    out = _parse(_table_page(_byline(), _affiliations()))
    assert [a["name"] for a in out["authors"]] == NAMES
    assert [[x["name"] for x in a["affiliations"]] for a in out["authors"]] == [[aff] for aff in AFFS]


def test_star_explained_by_the_email_on_that_authors_affiliation_is_corresponding():
    # star on the third author, whose affiliation line 3 ends with the only e-mail address
    assert _corr(_div_page(_byline(star=2), _affiliations(email_on=2))) == ["Paran, Maryam"]
    assert _corr(_table_page(_byline(star=1), _affiliations(email_on=1))) == ["Amiri, Azadeh"]


def test_single_unnumbered_affiliation_line_with_the_email_explains_the_star():
    page = _div_page(_byline(star=1, numbered=False), _affiliations(numbered=False))
    assert _corr(page) == ["Amiri, Azadeh"]


def test_corresponding_author_note_on_the_affiliation_line():
    page = _div_page(_byline(star=None), _affiliations(email_on=0, corresponding_note=True))
    assert _corr(page) == ["Azizi, Farnoush"]


def _explained(html):
    """The marks this parser adds itself (the generic parser's own byline-star guess is kept as it is)."""
    authors = [{"name": n, "affiliations": [], "is_corresponding": None} for n in NAMES]
    Yektaweb(BeautifulSoup(html, parser="lxml", features="lxml"))._mark_explained_corresponding(authors)
    return [a["name"] for a in authors if a["is_corresponding"]]


def test_star_explained_marks_by_this_parser_itself():
    assert _explained(_div_page(_byline(star=2), _affiliations(email_on=2))) == ["Paran, Maryam"]


def test_star_without_an_explaining_email_is_not_marked_by_this_parser():
    # a bare star (no e-mail, no note) adds no mark here (playbook: a mark the page never explains is not one)
    assert _explained(_div_page(_byline(star=1), _affiliations(email_on=None))) == []


def test_email_on_another_authors_line_does_not_explain_the_star():
    assert _explained(_div_page(_byline(star=1), _affiliations(email_on=2))) == []


def test_abstract_from_the_abstract_row_in_both_layouts():
    for page in (_table_page(_byline(), _affiliations()), _div_page(_byline(), _affiliations())):
        abstract = _parse(page)["abstract"]
        assert abstract.startswith("Background and Objectives: Academic procrastination can have")
        assert abstract.endswith("students with higher self-efficacy.")
        assert "Keywords" not in abstract and "Views" not in abstract


def test_abstract_stops_before_key_words_funding_and_how_to_cite():
    tail = ("<br>\n<strong>Key words:</strong> Aerobics, Attention<br>\n<strong>Funding:</strong> This study was funded "
            "by Yazd University.<br>\n<strong>Conflict of interest:</strong> None declared.<br>\n<strong>How to cite this "
            "article:</strong> Sadeghian M. The Effect of Aerobic Trainings. J Rafsanjan Univ Med Sci 2022; 21 (9).")
    abstract = _parse(_div_page(_byline(), _affiliations(), abstract=ABSTRACT + tail))["abstract"]
    assert abstract.endswith("students with higher self-efficacy.")
    assert "Funding" not in abstract and "Key words" not in abstract


def test_references_numbered_one_to_n_are_whole():
    out = _own(_table_page(_byline(), _affiliations()))
    refs = out["references"]
    assert [r["position"] for r in refs] == [1, 2, 3]
    assert refs[0]["raw"].startswith("Xu P, Xiong ZH. State anxiety") and refs[0]["doi"] == "10.1007/s11031-016-9554-x"
    assert refs[0]["raw"].count("DOI:10.1007/s11031-016-9554-x") == 1  # the platform's linked copy is left out
    assert refs[1]["doi"] is None
    assert refs[2]["doi"] == "10.1027/1016-9040/a000138" and "DOI:10.1027/1016-9040/a000138" in refs[2]["raw"]
    assert out["references_complete"] is True


def test_references_with_a_gap_are_not_whole():
    gapped = REFS.replace(">2. Nasri", ">4. Nasri")
    out = _own(_div_page(_byline(), _affiliations(), refs=gapped))
    assert len(out["references"]) == 3 and out["references_complete"] is False


def test_page_without_references_returns_no_reference_keys():
    out = _own(_div_page(_byline(), _affiliations(), refs=""))
    assert not out.get("references") and not out.get("references_complete")
