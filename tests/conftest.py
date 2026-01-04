"""
Pytest fixtures for Parseland parser tests.
"""
import requests
import pytest
from functools import lru_cache
from typing import Optional

TAXICAB_BASE = "http://harvester-load-balancer-366186003.us-east-1.elb.amazonaws.com/taxicab"


@lru_cache(maxsize=500)
def fetch_html_for_doi(doi: str) -> Optional[str]:
    """
    Fetch HTML content for a DOI via Taxicab.
    Returns the HTML content as a string, or None if not available.
    Uses LRU cache to avoid re-fetching the same DOI.
    """
    # Remove https://doi.org/ prefix if present
    if doi.startswith("https://doi.org/"):
        doi = doi[16:]

    # Step 1: Get html_uuid from Taxicab
    taxicab_url = f"{TAXICAB_BASE}/doi/{doi}"
    try:
        response = requests.get(taxicab_url, timeout=30)
        if response.status_code != 200:
            return None
        data = response.json()

        # Get the download URL for HTML
        html_items = data.get("html", [])
        if not html_items:
            return None

        download_url = html_items[0].get("download_url")
        if not download_url:
            return None

        # Step 2: Fetch the actual HTML
        html_response = requests.get(download_url, timeout=30)
        if html_response.status_code != 200:
            return None

        return html_response.text
    except Exception as e:
        print(f"Error fetching HTML for {doi}: {e}")
        return None


@pytest.fixture
def get_html():
    """Fixture that returns the fetch_html_for_doi function."""
    return fetch_html_for_doi
