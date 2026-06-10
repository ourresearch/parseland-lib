from __future__ import annotations

import json

from scripts.real_query_corresponding import (
    classify_spotcheck,
    detect_ca_marker,
    extract_dois,
    join_candidate,
    public_artifact_violations,
    sanitize_ticket_rows,
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
    path.write_text('{"ticket_id": 123, "email": "person@example.com"}', encoding="utf-8")

    violations = public_artifact_violations(path)

    assert "raw_ticket_id_key" in violations
    assert "email_address" in violations
