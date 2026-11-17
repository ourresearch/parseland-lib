"""
Taylor & Francis: "Correspondence" and an e-mail under every author marks no one (oxjob #2288).

tandfonline.com prints a "Correspondence <e-mail>" line in the pop-up of each author whose e-mail its record holds, and
the parser took that line as the corresponding mark. On pages that print it for every author, each with their own
address (old volumes, whole journals such as Desalination and Water Treatment), every author came out corresponding.
#1791's gold (label-v1): an e-mail shown for every author is not a mark; one tied to some authors is, and a note about
one author marks that author even when the template repeats it in every author's block. Markup is cut down from stored
production pages.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.taylor import Taylor

URL = "https://www.tandfonline.com/doi/full/10.1080/19443994.2014.972983"


def entry(name, email=None):
    corr = ""
    if email:
        corr = ('<span class="corr-sec"><span class="heading">Correspondence</span><span class="corr-email">'
                '<i aria-hidden="true" class="fa fa-envelope"></i>'
                f'<a href="mailto:{email}">{email}</a></span><br/></span>')
    envelope = '<i aria-hidden="true" class="fa fa-envelope"></i>' if email else ""
    return (f'<div class="entryAuthor"><a class="author" href="/author/x">{name}{envelope}</a>'
            f'<span class="overlay"> Department of Chemistry, University of Batna, Batna, Algeria{corr}</span></div>')


def html(entries):
    return (f'<html><head><link rel="canonical" href="{URL}"/><meta property="og:url" content="{URL}"/>'
            '<meta name="dc.Title" content="Hydrochemical study of a dam"/></head><body>'
            f'<div class="publicationContentAuthors">{"".join(entries)}</div>'
            '<div class="abstractSection abstractInFull"><p>We study the water of a dam in Algeria.</p></div>'
            '</body></html>')


def tf_corr(entries):
    out = Taylor(BeautifulSoup(html(entries), "lxml")).parse()
    return [a.name for a in out["authors"] if a.is_corresponding]


def page_corr(entries):
    return [a["name"] for a in parse_page(html(entries).encode(), "doi", URL)["authors"] if a["is_corresponding"]]


def test_own_email_under_every_author_marks_no_one():
    # 10.1080/19443994.2014.972983: each of the three authors shows "Correspondence" with their own address
    entries = [entry("Ammar Tiri", "tiri_ammar@yahoo.fr"), entry("Noureddine Lahbari", "norlah@gmail.com"),
               entry("Abderrahmane Boudoukha", "abderrahmaneboudoukha@yahoo.fr")]
    assert tf_corr(entries) == []
    assert page_corr(entries) == []


def test_correspondence_under_some_authors_still_marks_them():
    entries = [entry("Joseph Alulu", "josephalulu@gmail.com"), entry("David Jakinda Otieno"),
               entry("Justus Ochieng")]
    assert tf_corr(entries) == ["Joseph Alulu"]
    assert page_corr(entries) == ["Joseph Alulu"]


def test_one_address_repeated_under_every_author_marks_its_owner():
    # 10.1080/24750573.2018.1516397: the same address under all three authors is Nettleton's
    entries = [entry("Richard Dapson", "gsnettleton@gmail.com"), entry("Richard W. Horobin", "gsnettleton@gmail.com"),
               entry("G. S. Nettleton", "gsnettleton@gmail.com")]
    assert tf_corr(entries) == ["G. S. Nettleton"]
    assert page_corr(entries) == ["G. S. Nettleton"]


def test_one_address_repeated_that_names_no_author_marks_no_one():
    # 10.1080/15440478.2019.1697984
    entries = [entry("Dinesh", "macrofpt@gmail.com"), entry("Sanjay Palsule", "macrofpt@gmail.com")]
    assert tf_corr(entries) == []


def test_every_authors_address_in_one_repeated_link_marks_no_one():
    # 10.1080/23257962.2014.944890: one link holding both authors' addresses, under each author
    both = "member@bond007007.freeserve.co.uk dorarayson@greenbee.net"
    entries = [entry("Richard Bond", both), entry("Dora Rayson", both)]
    assert tf_corr(entries) == []


def test_single_author_with_correspondence_keeps_the_flag():
    # the one way this byline marks every author: a one-author page
    entries = [entry("Mois Navon", "navon@example.org")]
    assert tf_corr(entries) == ["Mois Navon"]
    assert page_corr(entries) == ["Mois Navon"]
