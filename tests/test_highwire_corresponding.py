"""Corresponding authors on HighWire pages (oxjob #2252).

Markup is cut down from stored pages (15 Nov 2026, #2252 EXPLORE § 1): Springer Publishing and ERS (e-mail tag on one
author), J Neurosci and BMJ (``li.corresp`` note), Genome Research and Cold Spring Harbor Perspectives (e-mail-only
note; byline link to ``li.fn-corresp``). No publisher parser claims the society sites, so the meta-tag parser wins and
marks no one. Gold v1.3 labels the e-mail-tagged author corresponding on HighWire's bioRxiv, medRxiv and ERS pages.
"""
from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.highwire import is_highwire_page, pick_highwire_corresponding

URL = "https://connect.springerpub.com/content/sgrvv/40/3/281"
HIGHWIRE = '<script src="/sites/all/modules/highwire/highwire/js/highwire.js"></script>'


def _page(authors, body="", head=HIGHWIRE):
    """authors: (name, e-mail or None); HighWire writes citation_author_email right after its citation_author."""
    metas = "".join(f'<meta name="citation_author" content="{n}"/>'
                    + (f'<meta name="citation_author_email" content="{e}"/>' if e else "") for n, e in authors)
    return (f"<html><head>{head}{metas}<meta name=\"citation_title\" content=\"A title\"/>"
            f"<meta name=\"citation_doi\" content=\"10.1891/vv-2023-0139\"/></head><body>{body}</body></html>")


def _corr(html, url=URL):
    return [a["name"] for a in parse_page(html.encode(), "doi", url)["authors"] if a["is_corresponding"]]


def test_email_tag_on_one_author():
    html = _page([("Kathryn Showalter", None), ("Lynn Langton", "langton@example.edu"), ("Jane Roe", None)])
    assert _corr(html) == ["Lynn Langton"]


def test_email_tag_on_every_author_marks_no_one():
    html = _page([("Kathryn Kaminski", "kk@example.com"), ("Marat Molyboga", "mm@example.com")])
    assert _corr(html) == []


def test_email_tag_on_the_one_author():
    # with the address printed in the author's pop-up (ccjm.org); the tag alone on a sole author is not a mark
    # (#2239, tests/test_corresponding_r2.py)
    popup = ('<li class="author-corresp-email-link last"><span>For correspondence: '
             '<a href="mailto:dfraser@example.ca">dfraser@example.ca</a></span></li>')
    html = _page([("Debbie Fraser", "dfraser@example.ca")], popup)
    assert _corr(html) == ["Debbie Fraser"]


def test_no_mark_marks_no_one():
    assert _corr(_page([("H Itoh", None), ("K Ohsato", None)], '<ol class="corresp-list"></ol>')) == []


def test_correspondence_should_be_addressed_to():
    authors = [("Novraj S. Dhanjal", None), ("Lahiru Handunnetthi", None), ("Richard J. S. Wise", None)]
    body = ('<ul><li class="corresp" id="corresp-1">Correspondence should be addressed to Dr. Novraj S. Dhanjal, '
            '<span class="addr-line">Division of Neuroscience, Imperial College London.</span> <span class="em-link">'
            '<span class="em-addr">novraj.dhanjal{at}imperial.ac.uk</span></span></li></ul>')
    assert _corr(_page(authors, body), "https://www.jneurosci.org/content/28/36/9056") == ["Novraj S. Dhanjal"]


def test_correspondence_to_full_name_byline_initials():
    authors = [("M-J Berthiaume", None), ("J-P Raynauld", None), ("J Martel-Pelletier", None)]
    body = ('<ol class="corresp-list"><li class="corresp" id="corresp-1">Correspondence to:<br/> Dr Jean-Pierre Raynauld'
            '<br/> Osteoarthritis Research Unit, Montreal, Quebec; <span class="em-link" title="jp@example.ca"></span>'
            '</li></ol>')
    assert _corr(_page(authors, body)) == ["J-P Raynauld"]


def test_email_only_note_matches_surname_in_address():
    authors = [("Paul B. Talbert", None), ("Steven Henikoff", None)]
    body = ('<li class="corresp" id="corresp-1">Corresponding authors: ptalbert{at}fredhutch.org , '
            'steveh{at}fhcrc.org</li>')
    assert _corr(_page(authors, body)) == ["Paul B. Talbert"]


def test_byline_link_to_correspondence_footnote():
    authors = [("Xavier Didelot", None), ("Rory Bowden", None), ("Daniel Falush", None)]
    body = ('<ol class="contributor-list" id="contrib-group-1">'
            '<li id="contrib-1"><span class="name">Xavier Didelot</span><a class="xref-corresp" href="#fn-2">5</a>, </li>'
            '<li id="contrib-2"><span class="name">Rory Bowden</span>, </li>'
            '<li id="contrib-3"><span class="name">Daniel Falush</span></li></ol>'
            '<ul><li class="fn-corresp" id="fn-2">5 Corresponding author. E-mail X.Didelot{at}warwick.ac.uk</li></ul>')
    assert _corr(_page(authors, body)) == ["Xavier Didelot"]


def test_byline_link_wins_over_email_tags():
    authors = [("Anders Isaksson", "a@example.se"), ("Ann Other", None), ("Chandrasekhar Kanduri", None)]
    body = ('<ol class="contributor-list"><li><span class="name">Anders Isaksson</span>'
            '<a class="xref-corresp" href="#fn-1">3</a></li><li><span class="name">Ann Other</span></li>'
            '<li><span class="name">Chandrasekhar Kanduri</span><a class="xref-corresp" href="#fn-1">3</a></li></ol>')
    assert _corr(_page(authors, body)) == ["Anders Isaksson", "Chandrasekhar Kanduri"]


def test_not_a_highwire_page_is_left_alone():
    html = _page([("Kathryn Showalter", None), ("Lynn Langton", "langton@example.edu")], head="")
    assert not is_highwire_page(html)
    assert _corr(html) == []


def test_pick_skips_a_mark_on_every_author():
    marks = {"byline": [], "heads": [], "emails": [], "emailed": ["A Smith", "B Jones"]}
    assert pick_highwire_corresponding(["A Smith", "B Jones"], marks) == []
