#!/usr/bin/env python3
"""Scribe — render KPI-vs-publisher-count curve.

Reads evidence/kpi-by-publisher-count.csv (one row per batch step) and emits:
- evidence/curve-latest.png   (matplotlib)
- evidence/curve-latest.svg   (matplotlib)
- evidence/curve-latest.json  (raw series for the HTML console to consume)

KPI CSV schema (columns):
    batch_id, publishers_processed, cumulative_rows,
    overall_authors_f1_soft, overall_affiliations_f1_fuzzy,
    overall_abstract_ratio_fuzzy, overall_pdf_url_accuracy,
    overall_corresponding_accuracy,
    marginal_lift_per_100, blocked_count, shipped_count, timestamp_utc

Usage:
    python scripts/build_curve.py \\
        --kpi-csv /Users/shubh-trips/Documents/OpenAlex/oxjobs/working/parseland-work-reporting/evidence/kpi-by-publisher-count.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

EVIDENCE_DIR_DEFAULT = Path(
    "/Users/shubh-trips/Documents/OpenAlex/oxjobs/working/parseland-work-reporting/evidence"
)

FIELDS = [
    ("overall_authors_f1_soft", "Authors F1 (soft)"),
    ("overall_affiliations_f1_fuzzy", "Affiliations F1 (fuzzy)"),
    ("overall_abstract_ratio_fuzzy", "Abstract ratio (fuzzy)"),
    ("overall_pdf_url_accuracy", "PDF URL accuracy"),
    ("overall_corresponding_accuracy", "Corresponding accuracy"),
]


def load_kpi(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                row = {
                    "batch_id": int(r.get("batch_id") or 0),
                    "publishers_processed": int(r.get("publishers_processed") or 0),
                    "cumulative_rows": int(r.get("cumulative_rows") or 0),
                    "marginal_lift_per_100": float(r.get("marginal_lift_per_100") or 0.0),
                    "blocked_count": int(r.get("blocked_count") or 0),
                    "shipped_count": int(r.get("shipped_count") or 0),
                    "timestamp_utc": r.get("timestamp_utc") or "",
                }
                for k, _ in FIELDS:
                    row[k] = float(r.get(k) or 0.0)
                rows.append(row)
            except (ValueError, TypeError):
                # Skip malformed rows
                continue
    return rows


def emit_json(rows: list[dict], out_path: Path) -> None:
    payload = {
        "fields": [{"key": k, "label": l} for k, l in FIELDS],
        "series": rows,
    }
    out_path.write_text(json.dumps(payload, indent=2))


def emit_plot(rows: list[dict], png_path: Path, svg_path: Path) -> bool:
    """Emit PNG and SVG curve plots. Returns True if successful."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        # matplotlib not installed; the json artifact alone is still usable.
        return False
    if not rows:
        # Render an empty placeholder
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.text(0.5, 0.5, "no batches yet", ha="center", va="center")
        ax.set_axis_off()
        fig.savefig(png_path)
        fig.savefig(svg_path)
        plt.close(fig)
        return True
    xs = [r["publishers_processed"] for r in rows]
    fig, ax = plt.subplots(figsize=(10, 6))
    for k, label in FIELDS:
        ys = [r[k] for r in rows]
        ax.plot(xs, ys, marker="o", label=label)
    ax.set_xlabel("Publishers processed")
    ax.set_ylabel("KPI (0–1)")
    ax.set_title("Whole-Goldie KPI vs Publishers processed")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="lower right", fontsize=8)
    # Annotate marginal lift per 100 if available
    if len(rows) >= 2:
        last = rows[-1]
        ax.annotate(
            f"Marginal lift / 100 publishers: {last['marginal_lift_per_100']:+.3f}pp",
            xy=(0.02, 0.97), xycoords="axes fraction",
            ha="left", va="top", fontsize=9,
            bbox=dict(boxstyle="round,pad=0.3", fc="lightyellow", alpha=0.8),
        )
    fig.tight_layout()
    fig.savefig(png_path, dpi=120)
    fig.savefig(svg_path)
    plt.close(fig)
    return True


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--kpi-csv", type=Path,
        default=EVIDENCE_DIR_DEFAULT / "kpi-by-publisher-count.csv",
    )
    p.add_argument(
        "--out-dir", type=Path, default=None,
        help="Output directory (default: parent of --kpi-csv).",
    )
    args = p.parse_args()

    out_dir = args.out_dir or args.kpi_csv.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = load_kpi(args.kpi_csv)
    json_path = out_dir / "curve-latest.json"
    png_path = out_dir / "curve-latest.png"
    svg_path = out_dir / "curve-latest.svg"

    emit_json(rows, json_path)
    plot_ok = emit_plot(rows, png_path, svg_path)

    print(json.dumps({
        "kpi_csv": str(args.kpi_csv),
        "json_path": str(json_path),
        "png_path": str(png_path) if plot_ok else None,
        "svg_path": str(svg_path) if plot_ok else None,
        "row_count": len(rows),
        "matplotlib_ok": plot_ok,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
