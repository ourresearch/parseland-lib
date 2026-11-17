"""
Cambridge Core: a star on every author is not a corresponding mark unless the notes it leads to say so (oxjob #2288).

Cambridge Core puts "*" after every author whose JATS record points to a correspondence note and lists those notes, one
per author in byline order, in a "*" row under the authors. Many journals use that note for something else: the
Applied Probability journals print each author's postal address there, others each author's e-mail. The parser took
every star as a mark, so those pages showed every author as corresponding. #1791's gold (label-v1): an e-mail shown for
every author is not a mark, one tied to some authors is, and a note that says "corresponding author" marks whom it
belongs to. Fragments mirror stored pages (doi in each test).
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.cup import CUP

URL = "https://www.cambridge.org/core/journals/journal-of-applied-probability/article/x/ABC123"


def author(name, affiliation, starred=True):
    star = "*" if starred else ""
    return (f'<div class="row author" data-test-author="{name}"><dt class="col-12 col-sm-2 title">{name}{star}</dt>'
            f'<dd class="col content d-inline d-sm-flex"><span class="content__title">Affiliation:</span>'
            f'<div class="d-sm-flex flex-column flex-sm-1 d-inline"><span><span>{affiliation}</span></span></div>'
            f'</dd></div>')


def notes(*texts):
    inner = "".join(f'<div class="d-inline"><span><div class="corresp">{t}</div></span></div>' for t in texts)
    return (f'<div class="row"><dt class="col-sm-2 col-12 title">*</dt><dd class="col content"><div class="row">'
            f'<div class="d-sm-flex d-inline flex-sm-1 flex-sm-wrap">{inner}</div></div></dd></div>')


def page(authors, note_texts=()):
    body = "".join(author(*a) for a in authors) + (notes(*note_texts) if note_texts else "")
    return (f'<html><head><meta property="og:url" content="{URL}"/><link rel="canonical" href="{URL}"/>'
            f'<meta name="citation_title" content="A paper"/></head><body>'
            f'<dl class="authors-details collapse" id="authors-details">{body}</dl></body></html>')


def cup_corr(authors, note_texts=()):
    out = CUP(BeautifulSoup(page(authors, note_texts), "lxml")).parse()
    return [a.name for a in out["authors"] if a.is_corresponding]


def page_corr(authors, note_texts=()):
    out = parse_page(page(authors, note_texts).encode(), "doi", URL)
    return [a["name"] for a in out["authors"] if a["is_corresponding"]]


def test_postal_addresses_mark_no_one():
    # 10.1017/s0021900200043515 (J. Appl. Probab. 1992)
    authors = [("Sid Browne", "Columbia University"), ("Karl Sigman", "Columbia University")]
    texts = ["<span class='label'>∗</span> Postal addresses: Graduate School of Business, 402 Uris Hall, and",
             "<span class='label'>∗∗</span> Department of Industrial Engineering and Operations Research, Columbia "
             "University, Mudd Building, New York, NY 10027, USA."]
    assert cup_corr(authors, texts) == []
    assert page_corr(authors, texts) == []


def test_one_email_note_listing_every_author_marks_no_one():
    # 10.1017/s1752971915000068 (International Theory): the same note repeated under each author
    authors = [("Sebastian Schindler", "Peace Research Institute Frankfurt, Germany"),
               ("Tobias Wille", "Goethe University Frankfurt, Germany")]
    note = ('E-mail: <a href="mailto:schindler@hsfk.de">schindler@hsfk.de</a>; '
            '<a href="mailto:wille@soz.uni-frankfurt.de">wille@soz.uni-frankfurt.de</a>')
    assert cup_corr(authors, [note, note]) == []
    assert page_corr(authors, [note, note]) == []


def test_springer_journal_on_cambridge_core_email_per_author_marks_no_one():
    # 10.1007/s10683-019-09635-w (Experimental Economics on Cambridge Core): one e-mail under every author
    authors = [("Marco Castillo", "Texas A&amp;M University, College Station, USA"),
               ("Greg Leo", "Vanderbilt University, Nashville, USA"),
               ("Ragan Petrie", "Texas A&amp;M University, College Station, USA")]
    texts = ['<a href="mailto:marco.castillo@tamu.edu">marco.castillo@tamu.edu</a>',
             '<a href="mailto:gregleo@gmail.com">gregleo@gmail.com</a>',
             '<a href="mailto:rpetrie@tamu.edu">rpetrie@tamu.edu</a>']
    assert cup_corr(authors, texts) == []
    assert page_corr(authors, texts) == []


def test_corresponding_author_note_marks_only_its_author():
    # 10.1017/s0003055424001308 (APSR 2025)
    authors = [("CHRISTOPHER J. CLARK", "University of North Carolina at Chapel Hill, United States"),
               ("STEVEN ROGERS", "Saint Louis University, United States")]
    texts = ["Corresponding author: Christopher J. Clark, Associate Professor, Department of Political Science, "
             'University of North Carolina at Chapel Hill, United States, <a href="mailto:chriclar@unc.edu">'
             "chriclar@unc.edu</a>",
             "Steven Rogers, Associate Professor, Department of Political Science, Saint Louis University, United "
             'States, <a href="mailto:smrogers@slu.edu">smrogers@slu.edu</a>']
    assert cup_corr(authors, texts) == ["CHRISTOPHER J. CLARK"]
    assert page_corr(authors, texts) == ["CHRISTOPHER J. CLARK"]


def test_starred_corresponding_note_marks_only_its_author():
    # 10.1017/jea.2021.30 (J. East Asian Studies)
    authors = [("Peter Gries", "The University of Manchester, United Kingdom"), ("Yasuki Masui", "Niigata Daigaku")]
    texts = ['<span class="label">*</span> Corresponding author. E-mail: '
             '<a href="mailto:peter.gries@manchester.ac.uk">peter.gries@manchester.ac.uk</a>',
             '(<a href="mailto:masui@jura.niigata-u.ac.jp">masui@jura.niigata-u.ac.jp</a>)']
    assert cup_corr(authors, texts) == ["Peter Gries"]


def test_email_under_some_authors_still_marks_them():
    # 10.1017/jpr.2016.47: postal address for both, an e-mail only for the first
    authors = [("Bojan Basrak", "University of Zagreb"), ("Drago Špoljarić", "University of Zagreb")]
    texts = ["<span class='label'>*</span> Postal address: Department of Mathematics, University of Zagreb, "
             "Bijenićka 30, Zagreb, Croatia. Email address: <a href='mailto:bbasrak@math.hr'>bbasrak@math.hr</a>",
             "<span class='label'>**</span> Postal address: Faculty of Mining, Geology and Petroleum Engineering, "
             "University of Zagreb, Pierottijeva 6, Zagreb, Croatia."]
    assert cup_corr(authors, texts) == ["Bojan Basrak"]
    assert page_corr(authors, texts) == ["Bojan Basrak"]


def test_note_naming_every_author_for_correspondence_keeps_everyone():
    # 10.1017/s0022377821000611 (J. Plasma Phys.): the page marks everyone
    authors = [("Reza Nemati", "University of Guilan, Iran"), ("Saeed Jafari", "University of Guilan, Iran")]
    note = ("† Email addresses for correspondence: rnemati@phd.guilan.ac.ir, sjafari@guilan.ac.ir")
    assert cup_corr(authors, [note, note]) == ["Reza Nemati", "Saeed Jafari"]


def test_single_author_with_email_still_marked():
    authors = [("David Ellis", "Leeds Trinity University, UK")]
    assert cup_corr(authors, ["Email: d.ellis@leedstrinity.ac.uk"]) == ["David Ellis"]


def test_star_on_some_authors_still_marks_them():
    authors = [("B. Akan", "Ankara University"), ("B. Ozel", "Ankara University"),
               ("G. Asut", "Ankara University", False)]
    assert cup_corr(authors, ["* Corresponding author.", "* Corresponding author."]) == ["B. Akan", "B. Ozel"]
