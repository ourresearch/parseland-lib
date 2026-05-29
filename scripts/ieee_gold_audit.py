"""IEEE gold-vs-parser side-by-side audit for the human-goldie 10K slice.

Built after iter-1 baseline (388 rows scored) revealed that the IEEE author F1
of 0.209 is dominated by gold-data quality, not parser misses. Six random
F1=0 rows all showed gold listing authors from a completely different paper
than the actual IEEE article (which the parser extracted correctly).

For every "discrepancy" row in tests/fixtures/ieee-iter1-before.json — defined
as either gold-populated/parser-zero, gold-zero/parser-populated, or both
populated with F1_soft below 1.0 — re-fetch the HTML through Taxicab + R2,
re-parse with IEEE(soup), and emit a side-by-side comparison:

  - DOI
  - IEEE resolved_url (so the reviewer can click through and check the truth)
  - gold author names (from human-goldie)
  - parsed author names (from xplGlobal.document.metadata JSON via IEEE.parse)
  - raw JSON metadata authors (the parser's source of truth)
  - heuristic verdict: gold-likely-wrong / parser-likely-wrong / unclear

Outputs:
  /tmp/ieee_gold_audit.json   — machine-readable
  /tmp/ieee_gold_audit.md     — human-readable markdown for Slack canvas
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, "/Users/shubh-trips/Documents/OpenAlex/parseland-lib")
sys.path.insert(0, "/Users/shubh-trips/Documents/OpenAlex/parseland-eval/eval")

import boto3  # noqa: E402
import requests  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from parseland_lib.publisher.parsers.ieee import IEEE  # noqa: E402
from parseland_lib.s3 import get_landing_page_from_r2  # noqa: E402

BASE = Path("/Users/shubh-trips/Documents/OpenAlex/parseland-lib")
ARTIFACT = BASE / "tests/fixtures/ieee-iter1-before.json"
GOLD_NDJSON = BASE / "tests/fixtures/ieee-10k-gold.ndjson"
OUT_JSON = Path("/tmp/ieee_gold_audit.json")
OUT_MD = Path("/tmp/ieee_gold_audit.md")


def _make_r2_client():
    load_dotenv(BASE / ".env", override=True)
    acct = os.environ["R2_ACCOUNT_ID"]
    return boto3.client(
        "s3",
        endpoint_url=f"https://{acct}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def _norm(s: str) -> str:
    """Loose name normalization for the heuristic verdict."""
    return "".join(c.lower() for c in (s or "") if c.isalnum())


def _surname_overlap(gold_names: list[str], parsed_names: list[str]) -> float:
    """Fraction of parsed surnames that share a token with any gold name.

    A coarse heuristic: if parsed names share zero tokens with gold names, the
    two lists describe disjoint people — strong signal the gold is wrong (or
    the parser is wrong about a totally different paper).
    """
    if not gold_names or not parsed_names:
        return 0.0
    g_tokens = set()
    for n in gold_names:
        for tok in (n or "").split():
            tok_n = _norm(tok)
            if len(tok_n) > 2:
                g_tokens.add(tok_n)
    hits = 0
    for n in parsed_names:
        toks = {_norm(t) for t in (n or "").split() if len(_norm(t)) > 2}
        if toks & g_tokens:
            hits += 1
    return hits / len(parsed_names)


def main():
    artifact = json.loads(ARTIFACT.read_text())
    scored = artifact["scored_rows"]

    gold_map = {}
    with GOLD_NDJSON.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            gold_map[obj["doi"]] = obj.get("annotation") or {}

    # Discrepancy rows: anything not at F1_soft=1.0 OR where gold/parser counts
    # disagree. We exclude perfect-1.0 rows because they are uninteresting for
    # an audit.
    discrepancies = []
    for r in scored:
        g = r["score"]["authors"]["gold_total"]
        p = r["score"]["authors"]["parsed_total"]
        f1 = r["score"]["authors"]["f1_soft"]
        if (g == 0 and p == 0):
            continue
        if g > 0 and p > 0 and f1 >= 0.999:
            continue
        discrepancies.append(r)

    print(f"loaded {len(scored)} scored rows. {len(discrepancies)} discrepancies to audit.")
    s3 = _make_r2_client()

    audit_rows = []
    t_start = time.time()
    for i, r in enumerate(discrepancies, 1):
        doi = r["doi"]
        uuid = r["harvest_uuid"]
        gold = gold_map.get(doi) or {}
        gold_authors = [
            a.get("name") for a in (gold.get("authors") or []) if isinstance(a, dict)
        ]

        try:
            tx = requests.get(
                f"http://localhost:8081/taxicab/doi/{doi}", timeout=20
            ).json()
            records = tx.get("html") or []
            # Match the harvest UUID used in the original eval, falling back
            # to whichever record we can find.
            rec = next((rr for rr in records if rr.get("id") == uuid), None)
            if rec is None and records:
                rec = max(records, key=lambda h: h.get("created_date") or "")
            resolved_url = (rec or {}).get("resolved_url") or ""
            html = get_landing_page_from_r2(uuid, s3)
            if isinstance(html, bytes):
                html = html.decode("utf-8", errors="ignore")
        except Exception as e:  # noqa: BLE001
            audit_rows.append(
                {
                    "doi": doi,
                    "resolved_url": "",
                    "gold_authors": gold_authors,
                    "parser_authors": [],
                    "json_authors_raw": [],
                    "verdict": f"fetch_error: {e}",
                    "f1_soft": r["score"]["authors"]["f1_soft"],
                }
            )
            continue

        soup = BeautifulSoup(html, "lxml")
        ieee = IEEE(soup)
        json_data = ieee.get_json_data() or {}
        json_authors_raw = [a.get("name") for a in (json_data.get("authors") or [])]
        try:
            parsed = ieee.parse()
            parser_names = [a.name for a in parsed.get("authors", [])]
        except Exception as e:  # noqa: BLE001
            parser_names = []
            print(f"  parse_err {doi}: {e}")

        # Heuristic verdict
        if not parser_names and not gold_authors:
            verdict = "both_empty"
        elif not parser_names and gold_authors:
            # Real parser miss — these are the 2 found=N rows
            verdict = "parser_miss"
        elif parser_names and not gold_authors:
            verdict = "gold_missing_parser_has"
        else:
            overlap = _surname_overlap(gold_authors, parser_names)
            if overlap == 0.0:
                verdict = "disjoint_names_gold_likely_wrong"
            elif overlap >= 0.5:
                verdict = "names_overlap_format_diff"
            else:
                verdict = "partial_overlap_unclear"

        audit_rows.append(
            {
                "doi": doi,
                "resolved_url": resolved_url,
                "gold_authors": gold_authors,
                "parser_authors": parser_names,
                "json_authors_raw": json_authors_raw,
                "verdict": verdict,
                "f1_soft": r["score"]["authors"]["f1_soft"],
                "authors_found": r.get("authors_found"),
            }
        )

        if i % 25 == 0:
            elapsed = time.time() - t_start
            print(f"  {i}/{len(discrepancies)}  elapsed={elapsed:.0f}s")

    # Tally
    from collections import Counter

    verdict_counts = Counter(r["verdict"] for r in audit_rows)
    print(f"\nverdict tally: {dict(verdict_counts)}")

    OUT_JSON.write_text(
        json.dumps(
            {
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "n_scored": len(scored),
                "n_discrepancies": len(audit_rows),
                "verdict_tally": dict(verdict_counts),
                "rows": audit_rows,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    print(f"\nwrote {OUT_JSON}")

    # Markdown table for Slack canvas
    lines = []
    lines.append(f"# IEEE human-goldie audit — gold vs parseland\n")
    lines.append(
        f"Source: in-process `IEEE.parse()` over {len(scored)} IEEE rows from "
        f"`merged-FINAL.csv` (10K eval + human-goldie).\n"
    )
    lines.append(f"**{len(audit_rows)} discrepancy rows.** Verdict tally:\n")
    for v, c in sorted(verdict_counts.items(), key=lambda x: -x[1]):
        lines.append(f"- `{v}`: {c}")
    lines.append("")
    lines.append(
        "Verdict legend: `disjoint_names_gold_likely_wrong` = gold authors share "
        "zero name tokens with parser-extracted authors → gold likely points to a "
        "different paper. `gold_missing_parser_has` = gold author list empty, "
        "parser found authors. `parser_miss` = parser returned no authors but "
        "gold has some (2 rows total). `names_overlap_format_diff` = at least 50% "
        "of parser surnames overlap gold tokens → likely same paper, formatting "
        "difference. `partial_overlap_unclear` = some overlap, needs review.\n"
    )
    lines.append("| # | DOI | Resolved URL | Gold authors | Parser authors | Verdict |")
    lines.append("|---|-----|--------------|--------------|----------------|---------|")

    def _fmt_authors(names):
        if not names:
            return "_(empty)_"
        return "; ".join(n for n in names if n) or "_(empty)_"

    for i, r in enumerate(audit_rows, 1):
        url = r["resolved_url"] or "_(no url)_"
        # Trim URL display
        if len(url) > 60:
            url_disp = url[:57] + "..."
        else:
            url_disp = url
        lines.append(
            f"| {i} | `{r['doi']}` | {url_disp} | "
            f"{_fmt_authors(r['gold_authors'])} | "
            f"{_fmt_authors(r['parser_authors'])} | "
            f"`{r['verdict']}` |"
        )

    OUT_MD.write_text("\n".join(lines))
    print(f"wrote {OUT_MD}  ({len(audit_rows)} rows)")


if __name__ == "__main__":
    main()
