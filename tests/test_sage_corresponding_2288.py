"""
SAGE: an e-mail on every author is not a corresponding mark; the correspondence note is (oxjob #2288).

SAGE's 2022 ("core") template prints each author's block in ``section.core-authors`` and the JATS ``<corresp>``
notes in ``section.core-authors-notes``. Many journals put every author's e-mail in their affiliation (Human Relations,
Qualitative Research), or give every author a note of their own (AMA journals: "(e-mail: ...)"), and the template
repeats one author's note e-mail in every co-author's block (``div.core-email``). The parser took any e-mail in a block
as a mark, so these pages flagged every author. #1791's gold (label-v1): an e-mail shown for every author is not a
mark; a note naming one author marks that author, even when the template repeats it in every author's block; a page
that explicitly marks every author keeps every flag. Fragments are cut down from stored pages; e-mails are
Cloudflare-protected as on the live site.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.sage import Sage

URL = "https://journals.sagepub.com/doi/10.1177/00187267221108729"


def cf(address, key=0x3F):
    """Cloudflare's e-mail protection: a key byte, then the address XORed with it, in hex."""
    return f"{key:02x}" + "".join(f"{ord(c) ^ key:02x}" for c in address)


def mail(address, prop=True):
    p = ' property="email"' if prop else ""
    return (f'<a href="/cdn-cgi/l/email-protection#{cf(address, 0x51)}"{p}>'
            f'<span class="__cf_email__" data-cfemail="{cf(address)}">[email&#160;protected]</span></a>')


def person(i, given, family, aff, aff_email=None, core_email=None):
    aff_html = aff + (", " + mail(aff_email) if aff_email else "")
    core = f'<div class="core-email">{mail(core_email)}</div>' if core_email else ""
    return (f'<div id="con{i}" property="author" typeof="Person"><div class="heading">'
            f'<span property="givenName">{given}</span> <span property="familyName">{family}</span></div>'
            f'<div class="content"><div class="affiliations"><div property="affiliation" typeof="Organization">'
            f'<span property="name">{aff_html}</span></div></div>{core}'
            f'<div class="core-author-link"><a href="/authored-by/{family}/{given}">View all articles by this author'
            f'</a></div></div></div>')


def note(text, address=None, nid=None):
    i = f' id="{nid}"' if nid else ""
    return f'<div{i} role="doc-footnote">{text}{mail(address, prop=False) if address else ""}</div>'


def html(persons, notes=()):
    notes_html = f'<section class="core-authors-notes"><h4>Notes</h4>{"".join(notes)}</section>' if notes else ""
    return (f'<html><head><meta property="og:url" content="{URL}"><link rel="canonical" href="{URL}">'
            f'<meta name="dc.Title" content="Earnings management in banks"></head><body>'
            f'<div class="core-container"><section class="core-authors"><h4>Affiliations</h4>{"".join(persons)}'
            f'</section>{notes_html}</div></body></html>')


def sage_corr(persons, notes=()):
    out = Sage(BeautifulSoup(html(persons, notes), "lxml")).parse()
    return [a["name"] for a in out["authors"] if a["is_corresponding"]]


def page_corr(persons, notes=()):
    return [a["name"] for a in parse_page(html(persons, notes).encode(), "doi", URL)["authors"]
            if a["is_corresponding"]]


def test_note_names_one_of_three_authors_who_all_show_an_email():
    # 10.1177/00187267221108729 (Human Relations 2022): every affiliation carries the author's e-mail, the note and
    # the separate e-mail block are Voulgaris's alone
    persons = [person(1, "Mohamed", "Janahi", "University of Bahrain, Bahrain", "mjanahi@uob.edu.bh"),
               person(2, "Yuval", "Millo", "University of Warwick, UK", "Yuval.Millo@wbs.ac.uk"),
               person(3, "Georgios", "Voulgaris", "University of Manchester, UK",
                      "Georgios.Voulgaris@manchester.ac.uk", core_email="Georgios.Voulgaris@manchester.ac.uk")]
    notes = [note("Georgios Voulgaris, Alliance Manchester Business School, University of Manchester, Manchester, "
                  "M15 6PB, UK. Email: ", "Georgios.Voulgaris@manchester.ac.uk", "corresp1-00187267221108729")]
    assert sage_corr(persons, notes) == ["Georgios Voulgaris"]
    assert page_corr(persons, notes) == ["Georgios Voulgaris"]


def test_email_in_every_affiliation_marks_no_one():
    # 10.1177/1468794110380548 (Qualitative Research 2010): each author's own e-mail, no note
    persons = [person(1, "Mitch", "Librett", "Bridgewater State College, USA", "mlibrett@bridgew.edu"),
               person(2, "Dina", "Perrone", "California State University, Long Beach, USA", "dperrone@csulb.edu")]
    assert sage_corr(persons) == []
    assert page_corr(persons) == []


def test_own_email_note_for_every_author_marks_no_one():
    # 10.1509/jm.16.0179 (Journal of Marketing): one "(email: ...)" note per author, each in that author's block
    persons = [person(1, "Ashlee", "Humphreys", "Northwestern University", core_email="a-humphreys@northwestern.edu"),
               person(2, "Gregory S.", "Carpenter", "Northwestern University",
                      core_email="g-carpenter@kellogg.northwestern.edu")]
    notes = [note("(email: ", "a-humphreys@northwestern.edu", "corresp1-jm-16-0179"),
             note("(email: ", "g-carpenter@kellogg.northwestern.edu", "corresp2-jm-16-0179")]
    assert sage_corr(persons, notes) == []
    assert page_corr(persons, notes) == []


def test_named_note_for_every_author_marks_no_one():
    # 10.1177/18793665251358857: each author's own address note, naming them
    persons = [person(1, "Svetlana", "Barsukova", "Higher School of Economics, Russia", core_email="sbarsukova@hse.ru"),
               person(2, "Elena", "Denisova-Schmidt", "University of St Gallen, Switzerland",
                      core_email="elena.denisova-schmidt@unisg.ch")]
    notes = [note("Svetlana Barsukova, Higher School of Economics (HSE), Moscow 101000, Russia. Email: ",
                  "sbarsukova@hse.ru", "corresp1-18793665251358857"),
             note("Elena Denisova-Schmidt, University of St Gallen (HSG), St Gallen 9000, Switzerland. Email: ",
                  "elena.denisova-schmidt@unisg.ch", "corresp2-18793665251358857")]
    assert sage_corr(persons, notes) == []


def test_note_repeated_in_every_block_marks_only_its_author():
    # 10.1177/0886368719851371: the template copies Flannery's note e-mail into McMullen's block too
    persons = [person(1, "Thomas P.", "Flannery", "Korn Ferry, Boston, MA, USA", core_email="tom.flannery@kornferry.com"),
               person(2, "Thomas D.", "McMullen", "Korn Ferry, Chicago, IL, USA",
                      core_email="tom.flannery@kornferry.com")]
    notes = [note("Thomas P. Flannery, Korn Ferry, Boston, MA 02110, USA. Email: ", "tom.flannery@kornferry.com",
                  "corresp1-0886368719851371")]
    assert sage_corr(persons, notes) == ["Thomas P. Flannery"]
    assert page_corr(persons, notes) == ["Thomas P. Flannery"]


def test_corresponding_author_note_marks_the_author_with_that_email():
    # 10.1177/194008291300600607 (Tropical Conservation Science): every author shows an e-mail, the starred note
    # gives only the corresponding author's
    persons = [person(1, "Luciana C.", "Castilho", "UESC, Brazil", "lu_ccastilho@yahoo.com.br",
                      core_email="lu_ccastilho@yahoo.com.br"),
               person(2, "Romari A.", "Martinez", "UESC, Brazil", "cebus@yahoo.com", core_email="cebus@yahoo.com"),
               person(3, "Alexandre", "Schiavetti", "UESC, Brazil", "aleschi@uesc.br", core_email="aleschi@uesc.br")]
    notes = [note("* Corresponding author. E-mail: ", "lu_ccastilho@yahoo.com.br")]
    assert sage_corr(persons, notes) == ["Luciana C. Castilho"]


def test_note_listing_every_address_marks_no_one():
    # 10.1177/0265813515599509: one note lists both authors' e-mails; the template copies the first into each block
    persons = [person(1, "Yukio", "Sadahiro", "University of Tokyo, Japan", core_email="sada@csis.u-tokyo.ac.jp"),
               person(2, "Takashi", "Oguchi", "University of Tokyo, Japan", core_email="sada@csis.u-tokyo.ac.jp")]
    notes = [note("Kashiwa-shi, Chiba 277-8568, Japan; e-mail: ", "sada@csis.u-tokyo.ac.jp",
                  "corresp1-0265813515599509")]
    assert sage_corr(persons, notes) == []


def test_note_without_email_names_no_one():
    # a "current affiliation" note is not a correspondence note
    persons = [person(1, "Cristian", "Márquez Romo", "ITESO, Mexico", "cmarquez@iteso.mx"),
               person(2, "Monica", "Montaño Reyes", "Universidad de Guadalajara, Mexico",
                      "monica.montano@academicos.udg.mx")]
    notes = [note("Current affiliation: Cristian Márquez Romo is now affiliated with ITESO, Guadalajara, Mexico.")]
    assert sage_corr(persons, notes) == []


def test_email_on_some_authors_still_marks_them():
    persons = [person(1, "Janet Baack", "Kukreja", "MD Anderson Cancer Center, USA", "jekukreja@mdanderson.org"),
               person(2, "Ashish M.", "Kamat", "MD Anderson Cancer Center, USA")]
    assert sage_corr(persons) == ["Janet Baack Kukreja"]


def test_page_marking_every_author_keeps_every_flag():
    persons = [person(1, "Weiyong", "Lu", "Luliang University, China", core_email="489698551@qq.com"),
               person(2, "Changchun", "He", "East China University of Technology, China",
                      core_email="hechangchun87@126.com")]
    notes = [note("Corresponding author: Weiyong Lu, Luliang University, Lvliang 033001, China. Email: ",
                  "489698551@qq.com", "corresp1-01445987211009389"),
             note("Corresponding author: Changchun He, East China University of Technology, Nanchang, China. "
                  "Email: ", "hechangchun87@126.com", "corresp2-01445987211009389")]
    assert sage_corr(persons, notes) == ["Weiyong Lu", "Changchun He"]


def test_single_author_with_email_still_marked():
    persons = [person(1, "Huimin", "Zhao", "University of Illinois, USA", core_email="zhao5@illinois.edu")]
    notes = [note("Huimin Zhao, University of Illinois, Urbana, IL, USA. Email: ", "zhao5@illinois.edu",
                  "corresp1-x")]
    assert sage_corr(persons, notes) == ["Huimin Zhao"]
