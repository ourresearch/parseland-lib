from __future__ import annotations

import json

from scripts.real_query_corresponding import (
    classify_spotcheck,
    detect_ca_marker,
    extract_dois,
    join_candidate,
    public_artifact_violations,
    sanitize_ticket_rows,
    zcli_active_profile,
    zendesk_auth_headers,
    zcli_core_get_json,
)


def test_extract_dois_normalizes_urls_punctuation_and_dedupes() -> None:
    text = (
        "See https://doi.org/10.1016/J.FUEL.2020.118433, "
        "doi:10.1109/ACCESS.2024.1234567 and again 10.1016/j.fuel.2020.118433."
    )

    assert extract_dois(text) == [
        "10.1016/j.fuel.2020.118433",
        "10.1109/access.2024.1234567",
    ]


def test_sanitize_ticket_rows_hashes_ticket_and_omits_private_text() -> None:
    rows = sanitize_ticket_rows(
        ticket={
            "id": 12345,
            "subject": "Missing corresponding author for DOI 10.1002/test.123",
            "description": "Requester jane@example.com says the CA is missing.",
        },
        comments=[{"body": "Internal comment repeats 10.1002/test.123"}],
        search_term="missing corresponding author",
        subdomain="openalex",
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["doi"] == "10.1002/test.123"
    assert row["ticket_hash"]
    assert "12345" not in json.dumps(row)
    assert "jane@example.com" not in json.dumps(row)
    assert "requester" not in json.dumps(row).lower()
    assert "comment" not in json.dumps(row).lower()


def test_join_current_marks_goldie_ca_parser_empty_as_parser_owned() -> None:
    candidate = {
        "doi": "10.1016/j.example.2024.1",
        "ticket_hash": "abc123",
        "matched_search_term": "corresponding author",
        "sanitized_issue_class": "missing_corresponding_author",
    }
    whole_rows = {
        "10.1016/j.example.2024.1": {
            "doi": "10.1016/j.example.2024.1",
            "link": "https://www.sciencedirect.com/science/article/pii/example",
            "publisher": "elsevier",
            "field_status": {"corresponding": "gold_present_parser_empty"},
            "score": {"corresponding": {"accuracy": 0.0}},
        }
    }
    queue = {
        ("elsevier", "corresponding"): {
            "task_id": "v2_elsevier_corresponding_test",
            "status": "blocked",
        }
    }

    joined = join_candidate(candidate, whole_rows=whole_rows, queue=queue, reg_cache={})

    assert joined["in_goldie"] is True
    assert joined["publisher"] == "elsevier"
    assert joined["classification"] == "still_parser_owned"
    assert joined["queue_task_id"] == "v2_elsevier_corresponding_test"


def test_detect_ca_marker_and_parser_missing_classifies_parser_owned() -> None:
    marker = detect_ca_marker(
        """
        <html><body>
          <p>Correspondence should be addressed to Ada Lovelace.</p>
        </body></html>
        """
    )

    assert marker["marker_type"] == "text_correspondence_marker"
    assert classify_spotcheck(
        block_reason=None,
        marker_type=marker["marker_type"],
        parser_ca_names=[],
        joined_classification="still_parser_owned",
        gold_has_ca=True,
    ) == "still_parser_owned"


def test_public_artifact_violations_flags_private_markers(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(
        '{"ticket_id": 123, "email": "person@example.com", '
        '"Authorization": "Basic abcdefghijklmnop"}',
        encoding="utf-8",
    )

    violations = public_artifact_violations(path)

    assert "raw_ticket_id_key" in violations
    assert "email_address" in violations
    assert "authorization_header" in violations
    assert "basic_auth_header" in violations


def test_zcli_active_profile_reads_subdomain_without_secret(tmp_path) -> None:
    config = tmp_path / ".zcli"
    request_js = tmp_path / "request.js"
    config.write_text('{"activeProfile":{"subdomain":"openalex"}}', encoding="utf-8")
    request_js.write_text("// fake zcli-core request module", encoding="utf-8")

    subdomain, mode = zcli_active_profile(config_path=config, request_js_path=request_js)

    assert subdomain == "openalex"
    assert mode == "zcli_core_keychain"


def test_zendesk_auth_headers_prefers_env_over_zcli(monkeypatch) -> None:
    monkeypatch.setenv("ZENDESK_SUBDOMAIN", "envsub")
    monkeypatch.setenv("ZENDESK_EMAIL", "bot@example.com")
    monkeypatch.setenv("ZENDESK_API_TOKEN", "env-token")
    monkeypatch.setattr("scripts.real_query_corresponding.zcli_active_profile", lambda: ("openalex", "zcli_core_keychain"))

    subdomain, headers, mode = zendesk_auth_headers()

    assert subdomain == "envsub"
    assert mode == "api_token"
    assert headers["Authorization"].startswith("Basic ")


def test_zendesk_auth_headers_falls_back_to_zcli(monkeypatch) -> None:
    monkeypatch.delenv("ZENDESK_SUBDOMAIN", raising=False)
    monkeypatch.delenv("ZENDESK_EMAIL", raising=False)
    monkeypatch.delenv("ZENDESK_API_TOKEN", raising=False)
    monkeypatch.delenv("ZENDESK_OAUTH_TOKEN", raising=False)
    monkeypatch.setattr("scripts.real_query_corresponding.zcli_active_profile", lambda: ("openalex", "zcli_core_keychain"))

    subdomain, headers, mode = zendesk_auth_headers()

    assert subdomain == "openalex"
    assert mode == "zcli_core_keychain"
    assert "Authorization" not in headers


def test_zcli_core_get_json_uses_bridge_without_exposing_auth(monkeypatch) -> None:
    calls = []

    class Completed:
        returncode = 0
        stdout = '{"status":200,"data":{"results":[{"id":1}]}}'
        stderr = ""

    def fake_run(cmd, *, input, text, capture_output, timeout, check):
        calls.append(json.loads(input))
        return Completed()

    monkeypatch.setattr("scripts.real_query_corresponding.subprocess.run", fake_run)

    data = zcli_core_get_json(
        "https://openalex.zendesk.com/api/v2/search.json?query=type%3Aticket",
        subdomain="openalex",
    )

    assert data == {"results": [{"id": 1}]}
    assert calls[0]["path"] == "/api/v2/search.json?query=type%3Aticket"
    assert "Authorization" not in json.dumps(calls[0])
