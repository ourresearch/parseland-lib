"""Sample 50 random Crossref DOIs that aren't already in the manual gold standard.

Uses Crossref's `/works?sample=N` endpoint (native random sampling) via the
polite pool. Writes the result to `eval/data/random-50.csv` with the same
column order as `eval/gold-standard.csv` — DOI/Link populated, extraction
columns empty for the downstream browser+Claude pipeline to fill in.

Usage:
    .venv/bin/python scripts/sample_50_random_dois.py
"""

from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

import requests


EVAL_DIR = Path(__file__).resolve().parent.parent
GOLD_CSV = EVAL_DIR / "gold-standard.csv"
OUTPUT_CSV = EVAL_DIR / "data" / "random-50.csv"

CROSSREF_URL = "https://api.crossref.org/works"
POLITE_EMAIL = "reach2shubhankar@gmail.com"
TARGET_COUNT = 50
MAX_ATTEMPTS = 5

COLUMNS = [
    "No", "DOI", "Link", "Authors", "Abstract", "PDF URL",
    "Status", "Notes", "Has Bot Check", "Resolves To PDF",
    "broken_doi", "no english",
]


def load_existing_gold_dois(gold_csv: Path) -> set[str]:
    with gold_csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return {row["DOI"].strip().lower() for row in reader if row.get("DOI")}


def fetch_random_sample(n: int) -> list[str]:
    params = {"sample": n, "mailto": POLITE_EMAIL}
    headers = {"User-Agent": f"parseland-eval/0.1 (mailto:{POLITE_EMAIL})"}
    resp = requests.get(CROSSREF_URL, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    items = resp.json().get("message", {}).get("items", [])
    return [item["DOI"].strip().lower() for item in items if item.get("DOI")]


def sample_unique(target: int, exclude: set[str]) -> list[str]:
    collected: list[str] = []
    seen = set(exclude)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        need = target - len(collected)
        if need <= 0:
            break
        # Sample a bit extra each round to absorb collisions.
        batch = fetch_random_sample(min(100, need * 2))
        for doi in batch:
            if doi in seen:
                continue
            seen.add(doi)
            collected.append(doi)
            if len(collected) >= target:
                break
        print(
            f"[attempt {attempt}] fetched {len(batch)}, unique so far: {len(collected)}/{target}",
            file=sys.stderr,
        )
        if len(collected) < target:
            time.sleep(1.0)  # polite-pool courtesy between calls
    if len(collected) < target:
        raise RuntimeError(
            f"only collected {len(collected)}/{target} unique DOIs after "
            f"{MAX_ATTEMPTS} attempts"
        )
    return collected[:target]


def write_csv(path: Path, dois: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for i, doi in enumerate(dois, start=1):
            writer.writerow({
                "No": i,
                "DOI": doi,
                "Link": f"https://doi.org/{doi}",
                "Authors": "",
                "Abstract": "",
                "PDF URL": "",
                "Status": "",
                "Notes": "",
                "Has Bot Check": "",
                "Resolves To PDF": "",
                "broken_doi": "",
                "no english": "",
            })


def main() -> int:
    if not GOLD_CSV.exists():
        print(f"missing gold standard at {GOLD_CSV}", file=sys.stderr)
        return 1
    existing = load_existing_gold_dois(GOLD_CSV)
    print(f"loaded {len(existing)} DOIs from existing gold standard", file=sys.stderr)
    dois = sample_unique(TARGET_COUNT, existing)
    write_csv(OUTPUT_CSV, dois)
    print(f"wrote {len(dois)} random DOIs to {OUTPUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
