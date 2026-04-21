"""Pilot P3: OpenAI Structured-Outputs reviewer for extracted CSVs.

Reads one or more extracted CSVs (passive and/or agentic) plus the cached
snapshot(s) for ground truth, and asks GPT (with `response_format: json_schema`)
to grade each field as `valid | invalid | unclear` with a brief reason.

Writes `eval/data/random-50-review.csv` with one row per (DOI, pass, field).
Captures OpenAI usage → cost tracked via `pricing.compute_openai_cost`.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any

from parseland_eval.paths import EVAL_DIR
from parseland_eval.pricing import compute_openai_cost

try:
    from dotenv import load_dotenv
    load_dotenv(EVAL_DIR / ".env", override=True)
except ImportError:
    pass

log = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4o-2024-08-06"
SNAPSHOT_DIR = EVAL_DIR / "data" / "snapshots"
OUTPUT_CSV = EVAL_DIR / "data" / "random-50-review.csv"

# Pass-name → extracted-CSV path
DEFAULT_PASSES = {
    "passive": EVAL_DIR / "data" / "random-50-extracted.csv",
    "agentic": EVAL_DIR / "data" / "random-50-agentic.csv",
}

FIELDS_TO_REVIEW = ["Authors", "Abstract", "PDF URL",
                    "Has Bot Check", "Resolves To PDF",
                    "broken_doi", "no english"]

VERDICT_ENUM = ["valid", "invalid", "unclear"]

REVIEW_SCHEMA = {
    "name": "field_review",
    "schema": {
        "type": "object",
        "properties": {
            "authors_verdict": {"type": "string", "enum": VERDICT_ENUM},
            "authors_reason": {"type": "string"},
            "abstract_verdict": {"type": "string", "enum": VERDICT_ENUM},
            "abstract_reason": {"type": "string"},
            "pdf_url_verdict": {"type": "string", "enum": VERDICT_ENUM},
            "pdf_url_reason": {"type": "string"},
            "has_bot_check_verdict": {"type": "string", "enum": VERDICT_ENUM},
            "has_bot_check_reason": {"type": "string"},
            "resolves_to_pdf_verdict": {"type": "string", "enum": VERDICT_ENUM},
            "resolves_to_pdf_reason": {"type": "string"},
            "broken_doi_verdict": {"type": "string", "enum": VERDICT_ENUM},
            "broken_doi_reason": {"type": "string"},
            "no_english_verdict": {"type": "string", "enum": VERDICT_ENUM},
            "no_english_reason": {"type": "string"},
        },
        "required": [
            "authors_verdict", "authors_reason",
            "abstract_verdict", "abstract_reason",
            "pdf_url_verdict", "pdf_url_reason",
            "has_bot_check_verdict", "has_bot_check_reason",
            "resolves_to_pdf_verdict", "resolves_to_pdf_reason",
            "broken_doi_verdict", "broken_doi_reason",
            "no_english_verdict", "no_english_reason",
        ],
        "additionalProperties": False,
    },
    "strict": True,
}

SYSTEM_PROMPT = """You are a QA reviewer for scholarly-metadata extraction. \
Given a publisher landing page's content and an extracted metadata row, grade \
each field as one of: valid, invalid, unclear.

- valid   : the extracted value is consistent with what the page shows.
- invalid : the extracted value contradicts the page OR is clearly wrong.
- unclear : you cannot tell from the provided content (e.g., page was too \
short, content was behind a bot-check, partial render).

For empty extraction values, use:
- valid   if the page genuinely has no such data (e.g., no abstract listed).
- invalid if the page clearly shows data that was missed.
- unclear if content is ambiguous.

Give a ≤1-sentence reason per field."""


@dataclass
class ReviewRow:
    no: int
    doi: str
    pass_name: str
    field: str
    extracted_value: str
    verdict: str
    reason: str


@dataclass
class PassMeta:
    cost_usd: float = 0.0
    reviewed: int = 0
    errors: int = 0


def _load_client():
    try:
        from openai import OpenAI  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "openai SDK not installed. Run: .venv/bin/pip install openai"
        ) from e
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set (expected in eval/.env)")
    return OpenAI(api_key=api_key)


def _load_snapshot(doi: str) -> dict[str, str]:
    """Return {resolved_url, head_html, body_text} from the cached snapshot.
    Empty if snapshot missing."""
    key = hashlib.sha1(doi.encode("utf-8")).hexdigest()
    path = SNAPSHOT_DIR / f"{key}.json"
    if not path.exists():
        return {"resolved_url": "", "head_html": "", "body_text": ""}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "resolved_url": data.get("resolved_url") or "",
        "head_html": (data.get("head_html") or "")[:4000],
        "body_text": (data.get("body_text") or "")[:12000],
    }


def _user_message(row: dict[str, str], snapshot: dict[str, str]) -> str:
    return (
        f"DOI: {row.get('DOI','')}\n"
        f"Resolved URL: {snapshot.get('resolved_url') or row.get('Link','')}\n"
        f"\nPage <head> excerpt ({len(snapshot['head_html'])} chars):\n"
        f"{snapshot['head_html']}\n"
        f"\nPage body excerpt ({len(snapshot['body_text'])} chars):\n"
        f"{snapshot['body_text']}\n"
        f"\n--- Extracted row to review ---\n"
        f"Authors: {row.get('Authors','')}\n"
        f"Abstract: {row.get('Abstract','')[:2000]}\n"
        f"PDF URL: {row.get('PDF URL','')}\n"
        f"Has Bot Check: {row.get('Has Bot Check','')}\n"
        f"Resolves To PDF: {row.get('Resolves To PDF','')}\n"
        f"broken_doi: {row.get('broken_doi','')}\n"
        f"no english: {row.get('no english','')}\n"
    )


def review_one(client, model: str, row: dict[str, str]) -> tuple[dict[str, Any], dict[str, int]]:
    snapshot = _load_snapshot(row.get("DOI", ""))
    resp = client.chat.completions.create(
        model=model,
        response_format={"type": "json_schema", "json_schema": REVIEW_SCHEMA},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _user_message(row, snapshot)},
        ],
    )
    content = resp.choices[0].message.content
    parsed = json.loads(content)
    usage = {
        "input_tokens": resp.usage.prompt_tokens,
        "output_tokens": resp.usage.completion_tokens,
    }
    return parsed, usage


def to_review_rows(
    doi_no: int, doi: str, pass_name: str, extracted: dict[str, str], parsed: dict
) -> list[ReviewRow]:
    # Map schema field names back to CSV column names.
    mapping = [
        ("Authors", "authors"),
        ("Abstract", "abstract"),
        ("PDF URL", "pdf_url"),
        ("Has Bot Check", "has_bot_check"),
        ("Resolves To PDF", "resolves_to_pdf"),
        ("broken_doi", "broken_doi"),
        ("no english", "no_english"),
    ]
    rows: list[ReviewRow] = []
    for csv_name, schema_key in mapping:
        rows.append(ReviewRow(
            no=doi_no,
            doi=doi,
            pass_name=pass_name,
            field=csv_name,
            extracted_value=(extracted.get(csv_name) or "")[:200],
            verdict=parsed.get(f"{schema_key}_verdict", "unclear"),
            reason=parsed.get(f"{schema_key}_reason", ""),
        ))
    return rows


def _load_pass_rows(pass_path: Path) -> list[dict[str, str]]:
    if not pass_path.exists():
        log.warning("pass CSV missing: %s (skipping)", pass_path)
        return []
    with pass_path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--output", default=str(OUTPUT_CSV))
    ap.add_argument("--limit", type=int, default=None,
                    help="Cap rows reviewed per pass (for smoke tests).")
    ap.add_argument("--passive-csv", default=str(DEFAULT_PASSES["passive"]))
    ap.add_argument("--agentic-csv", default=str(DEFAULT_PASSES["agentic"]))
    args = ap.parse_args()

    client = _load_client()
    passes = {
        "passive": _load_pass_rows(Path(args.passive_csv)),
        "agentic": _load_pass_rows(Path(args.agentic_csv)),
    }
    if args.limit:
        passes = {k: v[: args.limit] for k, v in passes.items()}

    review_rows: list[ReviewRow] = []
    meta: dict[str, PassMeta] = {"passive": PassMeta(), "agentic": PassMeta()}
    total_cost = 0.0
    start = time.monotonic()

    for pass_name, rows in passes.items():
        if not rows:
            continue
        log.info("reviewing %d rows for pass=%s", len(rows), pass_name)
        for row in rows:
            try:
                parsed, usage = review_one(client, args.model, row)
                cost = compute_openai_cost(args.model, **usage)
                total_cost += cost
                meta[pass_name].cost_usd += cost
                meta[pass_name].reviewed += 1
                doi_no = int(row.get("No") or 0)
                doi = row.get("DOI", "")
                review_rows.extend(to_review_rows(doi_no, doi, pass_name, row, parsed))
                log.info("[ok] %s %s/%s %s  $%.4f",
                         pass_name, doi_no, len(rows), doi, cost)
            except Exception as e:  # noqa: BLE001
                meta[pass_name].errors += 1
                log.error("[err] %s %s: %s", pass_name, row.get("DOI"), e)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "no", "doi", "pass_name", "field",
            "extracted_value", "verdict", "reason",
        ])
        writer.writeheader()
        for r in review_rows:
            writer.writerow(r.__dict__)

    # Sidecar meta
    meta_path = Path(args.output).with_suffix(".meta.json")
    meta_path.write_text(json.dumps({
        "model": args.model,
        "total_cost_usd": round(total_cost, 4),
        "wall_seconds": round(time.monotonic() - start, 1),
        "per_pass": {k: asdict(v) for k, v in meta.items()},
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"wrote {len(review_rows)} review rows to {args.output}")
    print(f"  total cost: ${total_cost:.4f}")
    for k, m in meta.items():
        print(f"  pass={k}: reviewed={m.reviewed}, errors={m.errors}, cost=${m.cost_usd:.4f}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sys.exit(main())
