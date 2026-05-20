"""Snapshot parseland's current output for each Elsevier gold DOI.

Produces a Python literal block that can be pasted into
``parseland_lib/publisher/parsers/elsevier_bv.py`` as the ``test_cases``
class attribute. Each entry has the shape:

    {
        "doi": "10.1016/...",
        "result": {
            "authors": [
                {"name": "...", "affiliations": ["..."], "is_corresponding": ...},
                ...
            ],
            "abstract": "<h2>Abstract</h2><p>...</p>",   # parseland's HTML-wrapped output
        },
    }

The test runner (``tests/test_parsers.py``) does strict author comparison
(name + affiliation + is_corresponding) and a loose abstract check
(present and >100 chars). Rows where parseland returns no authors get
``"authors": []`` — still a valid expected snapshot. Rows where R2 has a
captcha or redirect stub are flagged in the comment.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, "/Users/shubh-trips/Documents/OpenAlex/parseland-eval/eval")
sys.path.insert(0, "/Users/shubh-trips/Documents/OpenAlex/parseland-lib")

import boto3  # noqa: E402
import requests  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from parseland_eval.api import TAXICAB_BASE  # noqa: E402
from parseland_lib.s3 import get_landing_page_from_r2  # noqa: E402

NDJSON_PATH = Path(
    "/Users/shubh-trips/Documents/OpenAlex/parseland-lib/tests/fixtures/elsevier-gold.ndjson"
)
OUT_PATH = Path(
    "/Users/shubh-trips/Documents/OpenAlex/parseland-lib/tests/fixtures/elsevier-test-cases-snapshot.py.fragment"
)
LOCAL_PARSELAND = os.environ.get("LOCAL_PARSELAND_URL", "http://localhost:8080")


def _make_r2_client():
    load_dotenv("/Users/shubh-trips/Documents/OpenAlex/parseland-lib/.env", override=True)
    return boto3.client(
        "s3",
        endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def resolve_latest_harvest(doi: str) -> tuple[str | None, str | None]:
    """Return (latest_uuid, resolved_url) for the DOI's most recent harvest."""
    try:
        r = requests.get(f"{TAXICAB_BASE}/taxicab/doi/{doi}", timeout=30)
        if r.status_code != 200:
            return None, None
        body = r.json()
        records = body.get("html") or []
        if not records:
            return None, None
        latest = max(records, key=lambda h: h.get("created_date") or "")
        return latest.get("id"), latest.get("resolved_url")
    except Exception:  # noqa: BLE001
        return None, None


def post_parseland(html: str, resolved_url: str | None) -> dict | None:
    try:
        r = requests.post(
            f"{LOCAL_PARSELAND}/parseland",
            json={"html": html, "namespace": "doi", "resolved_url": resolved_url},
            timeout=30,
        )
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:  # noqa: BLE001
        return None


def _format_authors_for_test_case(parsed_authors: list[dict]) -> list[dict]:
    """Match the existing elsevier_bv.test_cases shape exactly.

    is_corresponding stored as bool (not None). affiliations as list of strings.
    """
    out = []
    for a in parsed_authors or []:
        name = (a.get("name") or "").strip()
        affs = []
        for aff in a.get("affiliations") or []:
            if isinstance(aff, dict):
                affs.append((aff.get("name") or "").strip())
            elif isinstance(aff, str):
                affs.append(aff.strip())
        out.append({
            "name": name,
            "affiliations": affs,
            "is_corresponding": bool(a.get("is_corresponding")),
        })
    return out


def main() -> int:
    s3 = _make_r2_client()
    rows = [json.loads(line) for line in NDJSON_PATH.read_text().splitlines() if line.strip()]
    print(f"# Snapshotting parseland output for {len(rows)} Elsevier gold DOIs", file=sys.stderr)

    snapshots = []
    for row in rows:
        doi = row["doi"]
        bot_check = row["annotation"].get("has_bot_check")
        resolves_to_pdf = row["annotation"].get("resolves_to_pdf")

        uuid, resolved_url = resolve_latest_harvest(doi)
        if not uuid:
            print(f"  SKIP  {doi}  (no harvest UUID)", file=sys.stderr)
            snapshots.append({"doi": doi, "skip_reason": "no harvest UUID", "_uuid": None})
            continue

        try:
            html = get_landing_page_from_r2(uuid, s3)
        except Exception as e:  # noqa: BLE001
            print(f"  SKIP  {doi}  (R2 error: {type(e).__name__})", file=sys.stderr)
            snapshots.append({"doi": doi, "skip_reason": f"R2: {type(e).__name__}", "_uuid": uuid})
            continue

        if not html or len(html) < 1000:
            html_len = len(html) if html else 0
            print(f"  SKIP  {doi}  (HTML too small: {html_len} bytes — likely captcha/redirect)", file=sys.stderr)
            snapshots.append({"doi": doi, "skip_reason": f"html_too_small_{html_len}b", "_uuid": uuid})
            continue

        if isinstance(html, bytes):
            html = html.decode("utf-8", errors="replace")

        parsed = post_parseland(html, resolved_url or row["annotation"].get("link"))
        if not parsed:
            print(f"  SKIP  {doi}  (parseland error)", file=sys.stderr)
            snapshots.append({"doi": doi, "skip_reason": "parseland_error", "_uuid": uuid})
            continue

        authors = _format_authors_for_test_case(parsed.get("authors") or [])
        abstract = parsed.get("abstract")

        snapshots.append({
            "doi": doi,
            "_uuid": uuid,
            "_bot_check": bot_check,
            "_resolves_to_pdf": resolves_to_pdf,
            "result": {
                "authors": authors,
                "abstract": abstract,
            },
        })
        print(
            f"  OK    {doi}  authors={len(authors)}  abstract_len={len(abstract) if abstract else 0}",
            file=sys.stderr,
        )

    # ---------- emit python literal ----------
    py_lines = ["    test_cases = ["]
    for snap in snapshots:
        doi = snap["doi"]
        comments = []
        if snap.get("_bot_check"):
            comments.append("bot-check in gold")
        if snap.get("_resolves_to_pdf"):
            comments.append("resolves-to-pdf")
        if snap.get("_uuid"):
            comments.append(f"harvest UUID: {snap['_uuid']}")
        comment = f"  # {' | '.join(comments)}" if comments else ""

        if "skip_reason" in snap:
            py_lines.append(f"        # SKIPPED {doi} — {snap['skip_reason']}{comment}")
            continue

        result = snap["result"]
        py_lines.append(f"        {{{comment}")
        py_lines.append(f"            \"doi\": {json.dumps(doi)},")
        py_lines.append(f"            \"result\": {{")
        py_lines.append(f"                \"authors\": [")
        for a in result["authors"]:
            py_lines.append(f"                    {{")
            py_lines.append(f"                        \"name\": {json.dumps(a['name'], ensure_ascii=False)},")
            if a["affiliations"]:
                py_lines.append(f"                        \"affiliations\": [")
                for aff in a["affiliations"]:
                    py_lines.append(f"                            {json.dumps(aff, ensure_ascii=False)},")
                py_lines.append(f"                        ],")
            else:
                py_lines.append(f"                        \"affiliations\": [],")
            py_lines.append(f"                        \"is_corresponding\": {a['is_corresponding']},")
            py_lines.append(f"                    }},")
        py_lines.append(f"                ],")
        if result["abstract"]:
            py_lines.append(f"                \"abstract\": {json.dumps(result['abstract'], ensure_ascii=False)},")
        else:
            py_lines.append(f"                \"abstract\": None,")
        py_lines.append(f"            }},")
        py_lines.append(f"        }},")
    py_lines.append("    ]")

    OUT_PATH.write_text("\n".join(py_lines), encoding="utf-8")
    print(f"\n  fragment written to: {OUT_PATH}", file=sys.stderr)
    print(f"  snapshots captured: {sum(1 for s in snapshots if 'result' in s)} of {len(snapshots)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
