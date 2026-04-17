"""Invoke parseland-lib against cached HTML for each gold row."""
from __future__ import annotations

import logging
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from parseland_eval.fetch import read_cached
from parseland_eval.gold import GoldRow
from parseland_eval.paths import PARSELAND_LIB

log = logging.getLogger(__name__)


def _ensure_parseland_lib_on_path() -> None:
    lib_str = str(PARSELAND_LIB)
    if lib_str not in sys.path:
        sys.path.insert(0, lib_str)


@dataclass(frozen=True)
class ParserRun:
    doi: str
    parsed: dict[str, Any] | None
    error: str | None
    duration_ms: float
    html_cached: bool
    publisher_domain: str


def _publisher_domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        return host.removeprefix("www.")
    except Exception:
        return ""


def run_one(row: GoldRow) -> ParserRun:
    _ensure_parseland_lib_on_path()
    from parseland_lib.parse import parse_page  # type: ignore[import-not-found]

    html = read_cached(row.doi)
    if html is None:
        return ParserRun(
            doi=row.doi,
            parsed=None,
            error="html-not-cached",
            duration_ms=0.0,
            html_cached=False,
            publisher_domain=_publisher_domain(row.link),
        )

    start = time.perf_counter()
    try:
        parsed = parse_page(html, namespace="doi", resolved_url=row.link)
        err = None
    except Exception as exc:  # noqa: BLE001 — record any parser crash
        parsed = None
        err = f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=3)}"
    duration_ms = (time.perf_counter() - start) * 1000.0

    return ParserRun(
        doi=row.doi,
        parsed=parsed,
        error=err,
        duration_ms=duration_ms,
        html_cached=True,
        publisher_domain=_publisher_domain(row.link),
    )


def run_all(rows: list[GoldRow]) -> list[ParserRun]:
    return [run_one(r) for r in rows]
