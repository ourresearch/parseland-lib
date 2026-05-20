"""
Smoke tests for the POST /parseland HTTP contract.

Covers the fa98bf1 fix: POST /parseland accepts optional ``namespace`` and
``resolved_url`` fields in the JSON body, and is backward compatible with
callers that send only ``html``. Before fa98bf1 the endpoint unconditionally
500'd when ``namespace`` was None.

These tests use Flask's test_client — no boto3 calls, no Taxicab, no R2.
"""
from __future__ import annotations

import pytest

from app import app as flask_app


MINIMAL_HTML = "<html><body><p>hello world</p></body></html>"

EXPECTED_KEYS = {"authors", "urls", "license", "version", "abstract"}


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as test_client:
        yield test_client


def test_post_parseland_html_only_is_backward_compatible(client):
    """Backward compat: callers that send only 'html' (no namespace,
    no resolved_url) must get 200 and a well-formed response."""
    resp = client.post("/parseland", json={"html": MINIMAL_HTML})

    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert set(body.keys()) == EXPECTED_KEYS
    assert body["authors"] == []
    assert body["abstract"] is None


def test_post_parseland_accepts_namespace_field(client):
    """fa98bf1: POST body may carry an optional 'namespace' field."""
    resp = client.post(
        "/parseland",
        json={"html": MINIMAL_HTML, "namespace": "doi"},
    )

    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert set(body.keys()) == EXPECTED_KEYS


def test_post_parseland_accepts_namespace_and_resolved_url(client):
    """fa98bf1: POST body may carry both 'namespace' and 'resolved_url'."""
    resp = client.post(
        "/parseland",
        json={
            "html": MINIMAL_HTML,
            "namespace": "doi",
            "resolved_url": "https://example.com/article/123",
        },
    )

    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert set(body.keys()) == EXPECTED_KEYS


def test_post_parseland_explicit_null_namespace(client):
    """fa98bf1: explicit namespace=None must not 500. This is the case
    that previously raised UnboundLocalError in parse_page."""
    resp = client.post(
        "/parseland",
        json={"html": MINIMAL_HTML, "namespace": None, "resolved_url": None},
    )

    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert set(body.keys()) == EXPECTED_KEYS


def test_post_parseland_missing_html_returns_400(client):
    """Backward compat: missing 'html' still returns 400."""
    resp = client.post("/parseland", json={"namespace": "doi"})

    assert resp.status_code == 400
    body = resp.get_json()
    assert "msg" in body
