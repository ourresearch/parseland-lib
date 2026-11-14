"""parse_page passes acknowledgments, funding statement and reference list through from the winning parse (#2215).

The output contract (oxjob #2215 README): a parser returns `acknowledgments`, `funding_statement`, `references` and
`references_complete` from parse() beside `authors` and `abstract`; parse_page carries them into the response. A
parser that doesn't read them returns none of them, and the response says None, None, None, False. A malformed value
never touches the six older fields, and a list is never called whole when parse_page had to drop or cut entries.

Offline: hand-made HTML; each test parser claims only pages carrying its own meta marker.
"""
from __future__ import annotations

import pytest

from app import app as flask_app
from parseland_lib.parse import MAX_REFERENCES, MAX_SECTION_CHARS, parse_page
from parseland_lib.publisher.parsers.parser import PublisherParser

NONE_OF_THEM = {"acknowledgments": None, "funding_statement": None, "references": None, "references_complete": False}
SECTIONS_PAGE = '<html><head><meta name="x-test-2215" content="1"></head><body></body></html>'
LIST_PAGE = '<html><head><meta name="x-test-2215-list" content="1"></head><body></body></html>'
GENERIC_PAGE = ('<html><head><meta name="citation_title" content="A title">'
                '<meta name="citation_author" content="Doe, Jane">'
                '<meta name="citation_author_institution" content="Example University"></head><body></body></html>')

NEXT_FIELDS = {}  # what SectionsTestParser.parse() adds for the next parse_page call


class SectionsTestParser(PublisherParser):
    parser_name = "test_2215_sections"

    def is_publisher_specific_parser(self):
        return bool(self.soup.select_one('meta[name="x-test-2215"]'))

    def authors_found(self):
        return self.is_publisher_specific_parser()

    def parse(self):
        return {"authors": [{"name": "Jane Doe", "affiliations": ["Example University"], "is_corresponding": True}],
                "abstract": "A real abstract about the measured thing, long enough to count as one.",
                **NEXT_FIELDS}


class ListOnlyTestParser(PublisherParser):
    """A parser that returns a bare author list, as some older parsers do."""
    parser_name = "test_2215_list_only"

    def is_publisher_specific_parser(self):
        return bool(self.soup.select_one('meta[name="x-test-2215-list"]'))

    def authors_found(self):
        return self.is_publisher_specific_parser()

    def parse(self):
        return [{"name": "Jane Doe", "affiliations": ["Example University"], "is_corresponding": None}]


def run(fields):
    NEXT_FIELDS.clear()
    NEXT_FIELDS.update(fields)
    return parse_page(SECTIONS_PAGE, "doi")


@pytest.mark.parametrize("html", [
    "<html><body><p>hello world</p></body></html>",  # no parser claims it
    GENERIC_PAGE,  # the generic parser reads the citation_author tags and has never heard of the four keys
    LIST_PAGE,  # a bare author list
], ids=["no-parser", "generic", "author-list"])
def test_a_parse_without_the_keys_says_none_of_them(html):
    result = parse_page(html, "doi")
    assert {k: result[k] for k in NONE_OF_THEM} == NONE_OF_THEM


def test_the_four_keys_pass_through_verbatim_and_the_six_fields_are_untouched():
    fields = {
        "acknowledgments": "We thank the field crew.\nThis work used the Example cluster.",
        "funding_statement": "This work was funded by the Example Foundation (grant 12-345).",
        "references": [
            {"position": 1, "raw": "Smith J. A paper. J Ex. 2001;1:1-2.", "doi": "10.1000/abc.1"},
            {"position": 2, "raw": "Doe J. Another paper. 2003.", "doi": None},
        ],
        "references_complete": True,
    }
    without = run({})
    result = run(fields)
    assert {k: result[k] for k in fields} == fields
    for field in ("authors", "urls", "license", "version", "abstract"):
        assert result[field] == without[field]


@pytest.mark.parametrize("flag", [False, None, "true", 1])
def test_a_list_the_parser_does_not_call_whole_stays_not_whole(flag):
    result = run({"references": [{"position": 1, "raw": "Smith J. 2001.", "doi": None}],
                  "references_complete": flag})
    assert result["references"] == [{"position": 1, "raw": "Smith J. 2001.", "doi": None}]
    assert result["references_complete"] is False


@pytest.mark.parametrize("refs", [None, [], "Smith J. 2001.", [{"raw": "  "}]])
def test_whole_without_a_list_is_not_whole(refs):
    result = run({"references": refs, "references_complete": True})
    assert result["references"] is None and result["references_complete"] is False


def test_entries_with_no_text_are_dropped_and_the_list_is_no_longer_whole():
    result = run({"references": [{"position": 1, "raw": " Smith J. 2001. ", "doi": None},
                                 {"position": 2, "raw": "   ", "doi": None},
                                 "not an entry",
                                 {"position": 4, "raw": "Doe J. 2003.", "doi": None}],
                  "references_complete": True})
    assert result["references"] == [{"position": 1, "raw": "Smith J. 2001.", "doi": None},
                                    {"position": 2, "raw": "Doe J. 2003.", "doi": None}]
    assert result["references_complete"] is False


def test_a_list_past_the_cap_is_cut_and_never_whole():
    refs = [{"position": i, "raw": f"Ref {i}.", "doi": None} for i in range(1, MAX_REFERENCES + 2)]
    result = run({"references": refs, "references_complete": True})
    assert len(result["references"]) == MAX_REFERENCES
    assert result["references_complete"] is False


def test_positions_are_page_order_and_dois_are_bare():
    result = run({"references": [
        {"position": 7, "raw": "A.", "doi": "https://doi.org/10.1000/A"},
        {"position": 3, "raw": "B.", "doi": "doi: 10.1000/b"},
        {"position": 9, "raw": "C.", "doi": "http://dx.doi.org/10.1000/c"},
        {"position": 1, "raw": "D.", "doi": "https://hdl.handle.net/123/456"},
    ], "references_complete": True})
    assert [(r["position"], r["doi"]) for r in result["references"]] == [
        (1, "10.1000/A"), (2, "10.1000/b"), (3, "10.1000/c"), (4, None)]
    assert result["references_complete"] is True


@pytest.mark.parametrize("value", ["", "   \n ", None, ["We thank"], "x" * (MAX_SECTION_CHARS + 1)],
                         ids=["empty", "blank", "none", "list", "page-body"])
def test_sections_that_are_empty_or_not_text_or_the_whole_page_are_none(value):
    result = run({"acknowledgments": value, "funding_statement": value})
    assert result["acknowledgments"] is None and result["funding_statement"] is None


def test_section_text_is_trimmed():
    assert run({"acknowledgments": "  We thank Ann.  "})["acknowledgments"] == "We thank Ann."


def test_the_service_response_carries_the_four_keys():
    fields = {"acknowledgments": None, "funding_statement": "Funded by the Example Foundation.",
              "references": [{"position": 1, "raw": "Smith J. 2001.", "doi": None}], "references_complete": True}
    NEXT_FIELDS.clear()
    NEXT_FIELDS.update(fields)
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as client:
        body = client.post("/parseland", json={"html": SECTIONS_PAGE, "namespace": "doi"}).get_json()
    assert {k: body[k] for k in fields} == fields
