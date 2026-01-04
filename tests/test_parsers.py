"""
Test runner for Parseland parser test_cases.

This module discovers all parser classes that have test_cases defined,
fetches the HTML for each test DOI via Taxicab, runs the parser,
and compares the output to the expected result.
"""
import pytest
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import List, Tuple

# Import all parsers (this triggers the dynamic import in __init__.py)
from parseland_lib.publisher import parsers as publisher_parsers
from parseland_lib.repository import parsers as repository_parsers
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.repository.parsers.parser import RepositoryParser

from conftest import fetch_html_for_doi


@dataclass
class ParserTestCase:
    """A single test case for a parser."""
    parser_class: type
    parser_name: str
    doi: str
    expected_result: dict
    namespace: str  # "doi" for publisher, "pmh" for repository


def discover_test_cases() -> List[ParserTestCase]:
    """
    Discover all test cases from all parser classes.
    Returns a list of TestCase objects.
    """
    test_cases = []

    # Discover publisher parser test cases
    for cls in PublisherParser.__subclasses__():
        if hasattr(cls, 'test_cases') and cls.test_cases:
            parser_name = getattr(cls, 'parser_name', cls.__name__)
            for tc in cls.test_cases:
                if 'doi' in tc and 'result' in tc:
                    test_cases.append(ParserTestCase(
                        parser_class=cls,
                        parser_name=parser_name,
                        doi=tc['doi'],
                        expected_result=tc['result'],
                        namespace='doi'
                    ))

    # Discover repository parser test cases
    for cls in RepositoryParser.__subclasses__():
        if hasattr(cls, 'test_cases') and cls.test_cases:
            parser_name = getattr(cls, 'parser_name', cls.__name__)
            for tc in cls.test_cases:
                if 'doi' in tc and 'result' in tc:
                    test_cases.append(ParserTestCase(
                        parser_class=cls,
                        parser_name=parser_name,
                        doi=tc['doi'],
                        expected_result=tc['result'],
                        namespace='pmh'
                    ))

    return test_cases


def normalize_author(author: dict) -> dict:
    """Normalize an author dict for comparison."""
    return {
        'name': author.get('name', '').strip(),
        'affiliations': [a.strip() if isinstance(a, str) else a.get('name', '').strip()
                         for a in author.get('affiliations', [])],
        'is_corresponding': author.get('is_corresponding', False) or False,
    }


def normalize_result(result) -> dict:
    """Normalize a result dict or list for comparison."""
    if result is None:
        return {'authors': [], 'abstract': None}

    # Handle case where result is a list of authors directly
    if isinstance(result, list):
        authors = result
        abstract = None
    else:
        authors = result.get('authors', [])
        abstract = result.get('abstract')

    normalized_authors = []
    for author in authors:
        # Check if it's an object with attributes (AuthorAffiliations)
        if hasattr(author, 'name') and not isinstance(author, dict):
            normalized_authors.append({
                'name': author.name.strip() if author.name else '',
                'affiliations': [a.strip() if isinstance(a, str) else a for a in (author.affiliations or [])],
                'is_corresponding': author.is_corresponding or False,
            })
        else:
            normalized_authors.append(normalize_author(author))

    return {
        'authors': normalized_authors,
        'abstract': abstract,
    }


def compare_authors(expected: list, actual: list) -> Tuple[bool, str]:
    """
    Compare expected and actual author lists.
    Returns (match: bool, diff_message: str)
    """
    if len(expected) != len(actual):
        return False, f"Author count mismatch: expected {len(expected)}, got {len(actual)}"

    for i, (exp, act) in enumerate(zip(expected, actual)):
        # Compare names
        if exp['name'] != act['name']:
            return False, f"Author {i} name mismatch: expected '{exp['name']}', got '{act['name']}'"

        # Compare affiliations
        exp_affs = exp.get('affiliations', [])
        act_affs = act.get('affiliations', [])
        if len(exp_affs) != len(act_affs):
            return False, f"Author {i} affiliation count mismatch: expected {len(exp_affs)}, got {len(act_affs)}"

        for j, (exp_aff, act_aff) in enumerate(zip(exp_affs, act_affs)):
            if exp_aff != act_aff:
                return False, f"Author {i} affiliation {j} mismatch: expected '{exp_aff[:50]}...', got '{act_aff[:50]}...'"

        # Compare is_corresponding
        exp_corr = exp.get('is_corresponding', False) or False
        act_corr = act.get('is_corresponding', False) or False
        if exp_corr != act_corr:
            return False, f"Author {i} is_corresponding mismatch: expected {exp_corr}, got {act_corr}"

    return True, ""


# Discover all test cases at module load time
ALL_TEST_CASES = discover_test_cases()


def generate_test_id(tc: ParserTestCase) -> str:
    """Generate a readable test ID."""
    # Shorten the DOI for readability
    short_doi = tc.doi.split('/')[-1][:20] if '/' in tc.doi else tc.doi[:20]
    return f"{tc.parser_name}:{short_doi}"


@pytest.mark.parametrize(
    "test_case",
    ALL_TEST_CASES,
    ids=[generate_test_id(tc) for tc in ALL_TEST_CASES]
)
def test_parser(test_case: ParserTestCase):
    """
    Test a parser against its expected output.

    For each test case:
    1. Fetch HTML from Taxicab using the DOI
    2. Parse it with the parser class
    3. Compare to expected result
    """
    # Fetch HTML
    html = fetch_html_for_doi(test_case.doi)
    if html is None:
        pytest.skip(f"Could not fetch HTML for DOI: {test_case.doi}")

    # Parse
    soup = BeautifulSoup(html, 'lxml')
    parser = test_case.parser_class(soup)

    try:
        actual_result = parser.parse()
    except Exception as e:
        pytest.fail(f"Parser raised exception: {e}")

    # Normalize both for comparison
    expected = normalize_result(test_case.expected_result)
    actual = normalize_result(actual_result)

    # Compare authors
    match, diff_msg = compare_authors(expected['authors'], actual['authors'])
    if not match:
        pytest.fail(f"Author mismatch for {test_case.doi}: {diff_msg}")

    # Compare abstract (if expected has one)
    if expected['abstract'] is not None:
        if actual['abstract'] is None:
            pytest.fail(f"Expected abstract but got None for {test_case.doi}")
        # Just check that we got an abstract, not exact match (abstracts can have minor formatting differences)
        if len(actual['abstract']) < 100:
            pytest.fail(f"Abstract too short for {test_case.doi}: {len(actual['abstract'])} chars")


if __name__ == "__main__":
    # Print discovered test cases for debugging
    print(f"Discovered {len(ALL_TEST_CASES)} test cases:")
    for tc in ALL_TEST_CASES:
        print(f"  {tc.parser_name}: {tc.doi}")
