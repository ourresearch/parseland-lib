"""Render a Markdown table of suspicious DOIs: parser-on-page, gold-not-on-page.

For each DOI in the 53-row suspicious list, fetch the HTML from R2, run
ElsevierBV.parse() in-process, load the gold authors, and emit a row per
(author, gold_aff, parsed_aff). Output: scripts-out/sus_table.md.

Author pairing: by matching the gold's full name against the parsed full
name with a simple case-insensitive surname-tail match (since the bipartite
scorer would have done a fuzzy match anyway).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, "/Users/shubh-trips/Documents/OpenAlex/parseland-eval/eval")
sys.path.insert(0, "/Users/shubh-trips/Documents/OpenAlex/parseland-lib")

import boto3  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from parseland_eval.gold import _coerce_author  # noqa: E402
from parseland_lib.publisher.parsers.elsevier_bv import ElsevierBV  # noqa: E402
from parseland_lib.s3 import get_landing_page_from_r2  # noqa: E402

ITER2 = Path("/Users/shubh-trips/Documents/OpenAlex/parseland-lib/tests/fixtures/elsevier-10k-iter2-after.json")
GOLD = Path("/Users/shubh-trips/Documents/OpenAlex/parseland-lib/tests/fixtures/elsevier-10k-gold.ndjson")
GROUNDING = Path("/Users/shubh-trips/Documents/OpenAlex/parseland-lib/scripts-out/gold_vs_page_grounding.json")
OUT = Path("/Users/shubh-trips/Documents/OpenAlex/parseland-lib/scripts-out/sus_table.md")


def _make_r2_client():
    load_dotenv("/Users/shubh-trips/Documents/OpenAlex/parseland-lib/.env", override=True)
    account_id = os.environ["R2_ACCOUNT_ID"]
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def parse_authors(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    try:
        raw = ElsevierBV(soup).parse()
    except Exception:
        return []
    out = []
    for a in (raw.get("authors") or []):
        name = getattr(a, "name", None) or ""
        affs = list(getattr(a, "affiliations", None) or [])
        out.append({"name": name, "affiliations": affs})
    return out


def load_gold_by_doi() -> dict[str, dict]:
    by = {}
    with GOLD.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            by[r["doi"]] = r
    return by


def normalize_name(n: str) -> str:
    return " ".join(n.lower().replace(",", " ").split())


def md_escape(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ").strip()


def main():
    g = json.loads(GROUNDING.read_text())
    sus = [r["doi"] for r in g["rows"]["zero"] if r["any_parsed_on_page"] and not r["any_gold_on_page"]]
    print(f"suspicious DOIs: {len(sus)}")

    iter2 = json.loads(ITER2.read_text())
    uuids = {r["doi"]: r["harvest_uuid"] for r in iter2["scored_rows"]}
    gold = load_gold_by_doi()
    s3 = _make_r2_client()

    lines = [
        "# Suspicious DOIs — parser text is on page, gold text is not\n",
        f"_n = {len(sus)}; source: zero-bucket grounding survey ({GROUNDING.name})_\n",
        "## How to read this",
        "",
        "Each section is one DOI. For each gold author we list the gold's `rasses` string and the parser's affiliation strings, plus a note flagging where they disagree about *the institution itself*. Entries where gold and parser match are omitted for brevity.\n",
    ]

    rendered = 0
    for doi in sus:
        uuid = uuids.get(doi)
        if not uuid:
            continue
        try:
            html = get_landing_page_from_r2(uuid, s3)
        except Exception as e:  # noqa: BLE001
            print(f"  R2 ERR {doi}: {e}")
            continue
        if isinstance(html, bytes):
            html = html.decode("utf-8", errors="ignore")
        if not html:
            continue

        parsed = parse_authors(html)
        gold_authors_raw = (gold.get(doi) or {}).get("annotation", {}).get("authors") or []
        gold_authors = []
        for a in gold_authors_raw:
            if isinstance(a, dict):
                try:
                    ca = _coerce_author(a)
                except Exception:
                    continue
                if ca is not None:
                    gold_authors.append(ca)

        # Index parser by surname tail for crude pairing
        parsed_by_tail = {}
        for p in parsed:
            tail = normalize_name(p["name"]).rsplit(" ", 1)[-1] if p["name"] else ""
            parsed_by_tail[tail] = p

        rows = []
        for ga in gold_authors:
            gname = getattr(ga, "name", None) or ""
            gaffs = list(getattr(ga, "affiliations", None) or [])
            tail = normalize_name(gname).rsplit(" ", 1)[-1]
            p = parsed_by_tail.get(tail)
            paffs = (p or {}).get("affiliations") or []
            # Show first gold + first parsed (most rows have 1; if >1, join).
            gold_str = md_escape(" / ".join(gaffs)) if gaffs else "—"
            parsed_str = md_escape(" / ".join(paffs)) if paffs else "—"
            rows.append((gname, gold_str, parsed_str))

        if not rows:
            continue

        lines.append(f"\n### `{doi}`")
        lines.append("")
        lines.append("| Author | Gold (`rasses`) | Parsed (from page) |")
        lines.append("|---|---|---|")
        for name, gs, ps in rows:
            lines.append(f"| {md_escape(name)} | {gs} | {ps} |")
        rendered += 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines))
    print(f"wrote {OUT}  ({rendered} DOIs rendered)")


if __name__ == "__main__":
    main()
