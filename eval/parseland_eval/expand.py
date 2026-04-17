"""Anthropic-driven extraction: generate silver-standard rows for unlabeled DOIs.

Feeds the 50-row seed as few-shot examples, then extracts metadata from each
target DOI's cached HTML via the Messages API. Writes results to
`eval/silver/<label>-<timestamp>.json`.

Bulk DOI sourcing (Crossref SRS per oxjob #122) is NOT wired here — this
module exposes `extract_one`/`extract_many` so a downstream driver can feed
DOIs in.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import sys
from dataclasses import dataclass
from typing import Iterable

from parseland_eval.fetch import read_cached
from parseland_eval.paths import EVAL_DIR, GOLD_SEED_JSON, PROMPTS_DIR, SILVER_DIR

try:
    from dotenv import load_dotenv
    load_dotenv(EVAL_DIR / ".env")
except ImportError:
    pass

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-6"  # 1M context at standard pricing
HTML_EXCERPT_CHARS = 30_000
FEW_SHOT_EXCERPT_CHARS = 12_000
FEW_SHOT_MAX = 10  # take up to 10 seed rows with one per publisher domain for diversity
PROMPT_VERSION = "extraction_v1"


@dataclass(frozen=True)
class SilverRow:
    doi: str
    extraction: dict
    model: str
    prompt_version: str
    error: str | None


def _load_client():
    try:
        from anthropic import Anthropic  # type: ignore
    except ImportError as e:
        raise RuntimeError("anthropic package not installed. Add to pyproject deps.") from e
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set in environment.")
    return Anthropic(api_key=api_key)


def _system_prompt() -> str:
    path = PROMPTS_DIR / f"{PROMPT_VERSION}.md"
    text = path.read_text(encoding="utf-8")
    seed = json.loads(GOLD_SEED_JSON.read_text(encoding="utf-8"))
    return text.replace("{N}", str(len(seed)))


def _pick_diverse_seed() -> list[dict]:
    """Up to FEW_SHOT_MAX seed rows, one per DOI prefix (publisher registrant)
    for diversity. Includes at least one Status=FALSE row so the model also
    learns the bot-check / paywall / broken-DOI pattern.
    """
    seed = json.loads(GOLD_SEED_JSON.read_text(encoding="utf-8"))
    seen_prefix: set[str] = set()
    clean: list[dict] = []
    blocked: list[dict] = []
    for row in seed:
        if not read_cached(row["DOI"]):
            continue
        prefix = (row.get("DOI") or "").split("/")[0]  # e.g. "10.1016"
        if prefix in seen_prefix:
            continue
        seen_prefix.add(prefix)
        (clean if row.get("Status") == "TRUE" else blocked).append(row)
    picks = clean[: FEW_SHOT_MAX - 1] + blocked[:1]
    return picks[:FEW_SHOT_MAX]


def _few_shot_messages() -> list[dict]:
    """Turn a diverse subset of seed rows into alternating user/assistant messages.

    Marks the final assistant message of the few-shot block with
    `cache_control: ephemeral` so the entire seed block is reused across
    subsequent holdout calls for ~90% input cost reduction.
    """
    picks = _pick_diverse_seed()
    msgs: list[dict] = []
    for i, row in enumerate(picks):
        html = (read_cached(row["DOI"]) or "")[:FEW_SHOT_EXCERPT_CHARS]
        if not html:
            continue
        msgs.append({
            "role": "user",
            "content": [{"type": "text",
                         "text": f"Extract from this HTML (DOI {row['DOI']}):\n\n{html}"}],
        })
        assistant_text = json.dumps({
            "authors": row.get("Authors") if isinstance(row.get("Authors"), list) else [],
            "abstract": row.get("Abstract") or None,
            "pdf_url": row.get("PDF URL") or None,
            "confidence": "high" if row.get("Status") == "TRUE" else "low",
            "notes": row.get("Notes") or "",
        }, ensure_ascii=False)
        content_block = {"type": "text", "text": assistant_text}
        # cache_control on the last few-shot assistant turn makes the whole
        # prefix (system + all few-shot) reusable across the 50 holdout calls
        if i == len(picks) - 1:
            content_block["cache_control"] = {"type": "ephemeral"}
        msgs.append({"role": "assistant", "content": [content_block]})
    return msgs


def extract_one(doi: str, *, client, model: str = DEFAULT_MODEL) -> SilverRow:
    html = read_cached(doi) or ""
    if not html:
        return SilverRow(doi=doi, extraction={}, model=model, prompt_version=PROMPT_VERSION,
                         error="no_cached_html")
    messages = _few_shot_messages() + [{
        "role": "user",
        "content": f"Extract from this HTML (DOI {doi}):\n\n{html[:HTML_EXCERPT_CHARS]}",
    }]
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=4096,
            system=_system_prompt(),
            messages=messages,
        )
        text = "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")
        parsed = json.loads(text)
        return SilverRow(doi=doi, extraction=parsed, model=model,
                         prompt_version=PROMPT_VERSION, error=None)
    except json.JSONDecodeError as e:
        return SilverRow(doi=doi, extraction={"raw": text}, model=model,
                         prompt_version=PROMPT_VERSION, error=f"json_decode: {e}")
    except Exception as e:
        return SilverRow(doi=doi, extraction={}, model=model,
                         prompt_version=PROMPT_VERSION, error=f"{type(e).__name__}: {e}")


def extract_many(dois: Iterable[str], *, model: str = DEFAULT_MODEL) -> list[SilverRow]:
    client = _load_client()
    return [extract_one(doi, client=client, model=model) for doi in dois]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dois-file", required=True,
                    help="Text file with one DOI per line to extract.")
    ap.add_argument("--label", required=True, help="Run label, used in output filename.")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()

    dois = [d.strip() for d in open(args.dois_file) if d.strip() and not d.startswith("#")]
    results = extract_many(dois, model=args.model)

    SILVER_DIR.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = SILVER_DIR / f"{args.label}-{args.model}-{ts}.json"
    out.write_text(json.dumps([r.__dict__ for r in results], ensure_ascii=False, indent=2),
                   encoding="utf-8")
    ok = sum(1 for r in results if r.error is None)
    print(f"wrote {ok}/{len(results)} successful extractions to {out}")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main())
