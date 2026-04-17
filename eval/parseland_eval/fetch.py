"""Cache raw HTML per DOI so evaluation is parser-deterministic across runs."""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import requests

from parseland_eval.paths import HTML_CACHE

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 parseland-eval/0.1"
)
TIMEOUT_SECONDS = 20.0
BOT_MARKERS = ("captcha", "challenge", "cloudflare", "just a moment", "access denied")


@dataclass(frozen=True)
class FetchResult:
    doi: str
    cache_path: Path
    status_code: int | None
    final_url: str | None
    bot_check_suspected: bool
    error: str | None


def _cache_path(doi: str) -> Path:
    HTML_CACHE.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(doi.lower().encode("utf-8")).hexdigest()
    return HTML_CACHE / f"{digest}.html"


def read_cached(doi: str) -> str | None:
    path = _cache_path(doi)
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def _is_bot_check(html: str, final_url: str) -> bool:
    lowered = html[:8000].lower()
    if any(marker in lowered for marker in BOT_MARKERS):
        return True
    if "captcha" in final_url.lower() or "challenge" in final_url.lower():
        return True
    return False


def fetch_one(doi: str, *, force: bool = False) -> FetchResult:
    path = _cache_path(doi)
    if path.exists() and not force:
        html = path.read_text(encoding="utf-8", errors="replace")
        return FetchResult(
            doi=doi,
            cache_path=path,
            status_code=None,
            final_url=None,
            bot_check_suspected=_is_bot_check(html, ""),
            error=None,
        )

    url = doi if doi.startswith("http") else f"https://doi.org/{doi}"
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
            timeout=TIMEOUT_SECONDS,
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        log.warning("fetch failed for %s: %s", doi, exc)
        return FetchResult(
            doi=doi,
            cache_path=path,
            status_code=None,
            final_url=None,
            bot_check_suspected=False,
            error=str(exc),
        )

    path.write_text(resp.text, encoding="utf-8")
    return FetchResult(
        doi=doi,
        cache_path=path,
        status_code=resp.status_code,
        final_url=str(resp.url),
        bot_check_suspected=_is_bot_check(resp.text, str(resp.url)),
        error=None,
    )


def fetch_many(dois: Iterable[str], *, force: bool = False) -> list[FetchResult]:
    return [fetch_one(d, force=force) for d in dois]
