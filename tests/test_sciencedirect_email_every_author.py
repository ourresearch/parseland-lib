"""
ScienceDirect: an e-mail on every author is not a corresponding mark; a correspondence note in another author group is
(oxjob #2288).

ScienceDirect draws an envelope for every author whose e-mail the page state carries (`encoded-e-address`). On pages
whose author group has no correspondence note, the parser took every such e-mail as a mark, so ~89K works with an
envelope on every author (old Elsevier volumes, IFAC proceedings) showed every author as corresponding, and pages that
put each author in a group of their own flagged the e-mailed co-author beside the starred one. #1791's gold (label-v1):
an e-mail shown for every author is not a mark; one tied to some authors is. Fragments mirror stored page state.
"""
import json

from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.sciencedirect import ScienceDirect

URL = "https://www.sciencedirect.com/science/article/pii/S1474667016426418"


def author(given, surname, *extra):
    return {"#name": "author", "$": {"id": f"aep-{surname}"},
            "$$": [{"#name": "given-name", "_": given}, {"#name": "surname", "_": surname}, *extra]}


def email():
    return {"#name": "encoded-e-address", "__encoded": "JTdCJTIyJTIzbmFtZSUyMiUzQSUyMmUtYWRkcmVzcyUyMiU3RA=="}


def ref(refid):
    return {"#name": "cross-ref", "$": {"refid": refid}, "$$": [{"#name": "sup", "$": {"loc": "post"}, "_": "⁎"}]}


def aff(aff_id, text):
    return {"#name": "affiliation", "$": {"id": aff_id}, "$$": [{"#name": "textfn", "_": text}]}


def corr(corr_id, text="Corresponding author."):
    return {"#name": "correspondence", "$": {"id": corr_id},
            "$$": [{"#name": "label", "_": "⁎"}, {"#name": "text", "_": text}]}


def html(groups):
    state = {"authors": {"content": [{"#name": "author-group", "$$": g} for g in groups]}}
    return (f'<html><head><link rel="canonical" href="{URL}"><meta name="citation_publisher" content="Elsevier"/>'
            f'<meta name="citation_title" content="Control of a plant"/></head>'
            f'<body><div class="author-group" id="author-group"></div>'
            f'<script>window.__PRELOADED_STATE__ = {json.dumps(state)};</script></body></html>')


def sd_corr(groups):
    out = ScienceDirect(BeautifulSoup(html(groups), "lxml")).parse()
    return [a["name"] for a in out["authors"] if a["is_corresponding"]]


def page_corr(groups):
    return [a["name"] for a in parse_page(html(groups).encode(), "doi", URL)["authors"] if a["is_corresponding"]]


def test_email_on_every_author_marks_no_one():
    group = [author("Elena", "Goncharova", email()), author("Alexander", "Ovseevich", email()),
             aff("af1", "Institute for Problems in Mechanics, Moscow, Russia")]
    assert sd_corr([group]) == []
    assert page_corr([group]) == []


def test_email_on_some_authors_still_marks_them():
    group = [author("Jie", "Qiu", email()), author("Xiaofeng", "Liu"), author("Junli", "Liu"),
             aff("af1", "Tianjin University of Technology, Tianjin, China")]
    assert sd_corr([group]) == ["Jie Qiu"]


def test_note_in_another_group_marks_only_its_author():
    # each author in a group of their own; the note sits in the first author's group, both carry an e-mail
    first = [author("Ye", "Zhou", ref("cr1"), email()), aff("af1", "Lawrence Livermore National Laboratory, USA"),
             corr("cr1")]
    second = [author("Robin J.R.", "Williams", email()), aff("af2", "AWE Aldermaston, UK")]
    assert sd_corr([first, second]) == ["Ye Zhou"]
    assert page_corr([first, second]) == ["Ye Zhou"]


def test_every_author_starred_still_marks_everyone():
    group = [author("Emily", "Mather", ref("cor1"), email()), author("Kim", "Plunkett", ref("cor1"), email()),
             aff("af1", "Department of Experimental Psychology, University of Oxford, United Kingdom"),
             corr("cor1", "Corresponding authors.")]
    assert sd_corr([group]) == ["Emily Mather", "Kim Plunkett"]


def test_single_author_with_email_still_marked():
    group = [author("Huimin", "Zhao", email()), aff("af1", "University of Illinois, Urbana, USA")]
    assert sd_corr([group]) == ["Huimin Zhao"]
