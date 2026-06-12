import json

from scripts.goldie_backfill_propose import _doi_hash, propose_for_row


def test_propose_corresponding_reparses_cached_ssrn_contact_author(tmp_path):
    doi = "10.2139/ssrn.4398349"
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / f"{_doi_hash(doi)}.html").write_text(
        """
        <html>
          <head>
            <link rel="canonical" href="https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4398349">
          </head>
          <body>
            <div class="authors">
              <h2>Marco Ceccarelli</h2>
              <p>Maastricht University - Department of Finance</p>
              <h2>Steven Ongena</h2>
              <p>University of Zurich - Department of Banking and Finance</p>
            </div>
            <div class="author">
              <h3>Steven R. G. Ongena (Contact Author)</h3>
              <p>University of Zurich - Department of Banking and Finance</p>
            </div>
          </body>
        </html>
        """,
        encoding="utf-8",
    )
    row = {
        "doi": doi,
        "link": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4398349",
        "field_status": {"corresponding": "gold_empty_parser_present"},
    }

    proposals = propose_for_row(row, {}, "ssrn", {"corresponding"}, cache_dir)

    assert json.loads(json.dumps(proposals))
    assert len(proposals) == 1
    assert proposals[0]["field"] == "corresponding"
    assert proposals[0]["parseland_candidate"] == {
        "authors": [
            {
                "name": "Steven Ongena",
                "affiliations": [
                    {"name": "University of Zurich - Department of Banking and Finance"}
                ],
                "is_corresponding": True,
            }
        ]
    }
    assert proposals[0]["confidence"] == "candidate"


def test_propose_corresponding_records_reparse_blocker_when_cache_missing(tmp_path):
    row = {
        "doi": "10.2139/ssrn.missing",
        "link": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=missing",
        "field_status": {"corresponding": "gold_empty_parser_present"},
    }

    proposals = propose_for_row(row, {}, "ssrn", {"corresponding"}, tmp_path / "cache")

    assert proposals == [
        {
            "field": "corresponding",
            "gold_value": None,
            "parseland_candidate": {
                "authors": [],
                "blocker": "missing_cached_html",
            },
            "confidence": "blocked",
            "evidence_excerpt": None,
            "status": "blocked_candidate_reparse",
            "rejection_reason": "missing_cached_html",
        }
    ]
