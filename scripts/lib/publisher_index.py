"""DOI prefix + URL domain → publisher_id classifier.

Used by the autonomous Parseland improver to group rows in merged-FINAL.csv
by publisher for ranking and batch processing. Deterministic so that priority
queues are stable across runs.

Strategy:
1. Try high-confidence curated DOI-prefix map (the major publishers we have
   parsers for).
2. Fall back to URL domain.
3. Fall back to CrossRef registrant lookup (cached on disk) for tail prefixes.
4. Return "unknown" if everything fails — never guess.

Public API:
    prefix_to_publisher(doi) -> str | None
    domain_to_publisher(url) -> str | None
    registrant_to_publisher(doi, *, allow_network=True) -> str | None
    classify_row(row, *, allow_network=True) -> str
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse

# Curated DOI-prefix → publisher_id map. Keys are '10.XXXX' DOI registrant
# prefixes; values are publisher_id slugs matching the parser filenames in
# parseland_lib/publisher/parsers/*.py where applicable.
#
# This map is intentionally small and high-confidence. Tail prefixes resolve
# via CrossRef (registrant_to_publisher) so we don't ship speculative
# mappings.
DOI_PREFIX_PUBLISHER: dict[str, str] = {
    # Top-10 highest-volume scholarly publishers
    "10.1002": "wiley",
    "10.1016": "elsevier",
    "10.1109": "ieee",
    "10.1007": "springer",
    "10.1021": "acs",
    "10.1080": "taylor",
    "10.1177": "sage",
    "10.1097": "lippincott",
    "10.1093": "oxford",
    "10.1017": "cup",
    # Major specialty publishers we have parsers for
    "10.3389": "frontiers",
    "10.3390": "mdpi",
    "10.1371": "plos",
    "10.1136": "bmj",
    "10.1056": "nejm",
    "10.1145": "acm",
    "10.1126": "aaas",
    "10.1063": "aip_publishing",
    "10.1103": "aps",
    "10.1175": "ams",
    "10.1108": "emerald",
    "10.1148": "rsna",
    "10.1155": "hindawi",
    "10.1163": "brill",
    "10.1117": "spie",
    "10.1186": "springer",   # BMC titles → Springer Nature
    "10.1057": "springer",   # Palgrave → Springer Nature
    "10.1023": "springer",   # Kluwer legacy
    "10.1111": "wiley",
    "10.1037": "apa",
    "10.1515": "de_gruyter",
    "10.5194": "copernicus",
    "10.21037": "ame",
    "10.3917": "cairn",
    "10.1364": "optica",
    "10.1242": "company_biologists",
    "10.1042": "portland_press",
    "10.1101": "cshlp",
    "10.1158": "aacr",
    "10.1182": "ash",
    "10.1200": "asco",
    "10.1115": "asme",
    "10.2174": "bentham",
    "10.1029": "wiley",      # AGU → Wiley
    "10.1121": "asa",
}


# publisher_id → parser-file stem in parseland_lib/publisher/parsers/.
# Only listed when the publisher_id differs from the parser file name.
# rank_publishers.py uses this to determine parser tractability accurately.
PUBLISHER_TO_PARSER_FILE: dict[str, str] = {
    "elsevier": "elsevier_bv",
    "aaas": "aaas",
    "aip_publishing": "aip_publishing",
    "rxiv": "rxiv",
    "cshlp": "cup",          # no dedicated cshlp parser; rough fallback
    "ascopubs": "asco",      # alias from older mapping
    "company_biologists": "generic",
    "portland_press": "generic",
    "aacr": "generic",
}


def publisher_parser_file(publisher_id: str) -> str:
    """Return the expected parser filename stem for a publisher_id."""
    return PUBLISHER_TO_PARSER_FILE.get(publisher_id, publisher_id)


# URL domain → publisher_id. Lower-cased netloc.
DOMAIN_PUBLISHER: dict[str, str | None] = {
    "sciencedirect.com": "elsevier",
    "linkinghub.elsevier.com": "elsevier",
    "elsevier.com": "elsevier",
    "onlinelibrary.wiley.com": "wiley",
    "wiley.com": "wiley",
    "agupubs.onlinelibrary.wiley.com": "wiley",
    "link.springer.com": "springer",
    "springer.com": "springer",
    "springeropen.com": "springer",
    "nature.com": "springer",
    "biomedcentral.com": "springer",
    "ieeexplore.ieee.org": "ieee",
    "ieee.org": "ieee",
    "pubs.acs.org": "acs",
    "acs.org": "acs",
    "tandfonline.com": "taylor",
    "taylorfrancis.com": "taylor",
    "journals.sagepub.com": "sage",
    "sagepub.com": "sage",
    "journals.lww.com": "lippincott",
    "lww.com": "lippincott",
    "academic.oup.com": "oxford",
    "oup.com": "oxford",
    "cambridge.org": "cup",
    "frontiersin.org": "frontiers",
    "mdpi.com": "mdpi",
    "journals.plos.org": "plos",
    "plos.org": "plos",
    "bmj.com": "bmj",
    "nejm.org": "nejm",
    "dl.acm.org": "acm",
    "acm.org": "acm",
    "science.org": "aaas",
    "ascopubs.org": "ascopubs",
    "ahajournals.org": "lippincott",
    "thieme-connect.com": "thieme",
    "karger.com": "karger",
    "rsc.org": "rsc",
    "pubs.rsc.org": "rsc",
    "iopscience.iop.org": "iop",
    "iop.org": "iop",
    "pubs.aip.org": "aip_publishing",
    "aip.org": "aip_publishing",
    "journals.aps.org": "aps",
    "aps.org": "aps",
    "degruyter.com": "de_gruyter",
    "brill.com": "brill",
    "liebertpub.com": "mary_ann_liebert",
    "spie.org": "spie",
    "spiedigitallibrary.org": "spie",
    "emerald.com": "emerald",
    "emeraldinsight.com": "emerald",
    "hindawi.com": "hindawi",
    "scielo.br": "scielo",
    "scielo.cl": "scielo",
    "scielo.org": "scielo",
    "edpsciences.org": "edp_sciences",
    "copernicus.org": "copernicus",
    "f1000research.com": "f1000",
    "f1000.com": "f1000",
    "ssrn.com": "ssrn",
    "papers.ssrn.com": "ssrn",
    "researchsquare.com": "research_square",
    "biorxiv.org": "rxiv",
    "arxiv.org": "rxiv",
    "medrxiv.org": "rxiv",
    "chemrxiv.org": "rxiv",
    "preprints.org": "rxiv",
    "psyarxiv.com": "rxiv",
    "doi.org": None,        # bare DOI link — fall through to prefix
    "dx.doi.org": None,
}


# CrossRef registrant name → publisher_id normalization rules.
# Lower-cased substring match; first hit wins.
REGISTRANT_NORMALIZE: list[tuple[str, str]] = [
    ("wiley", "wiley"),
    ("elsevier", "elsevier"),
    ("springer", "springer"),
    ("nature", "springer"),
    ("biomed central", "springer"),
    ("ieee", "ieee"),
    ("american chemical society", "acs"),
    ("taylor", "taylor"),
    ("informa", "taylor"),
    ("sage", "sage"),
    ("wolters kluwer", "lippincott"),
    ("lippincott", "lippincott"),
    ("oxford", "oxford"),
    ("cambridge", "cup"),
    ("frontiers", "frontiers"),
    ("mdpi", "mdpi"),
    ("public library of science", "plos"),
    ("plos", "plos"),
    ("bmj", "bmj"),
    ("massachusetts medical society", "nejm"),
    ("association for computing machinery", "acm"),
    ("acm", "acm"),
    ("american association for the advancement of science", "aaas"),
    ("aip publishing", "aip_publishing"),
    ("american physical society", "aps"),
    ("american meteorological society", "ams"),
    ("emerald", "emerald"),
    ("radiological society", "rsna"),
    ("hindawi", "hindawi"),
    ("brill", "brill"),
    ("spie", "spie"),
    ("american psychological association", "apa"),
    ("de gruyter", "de_gruyter"),
    ("copernicus", "copernicus"),
    ("ame publishing", "ame"),
    ("cairn", "cairn"),
    ("optica publishing", "optica"),
    ("company of biologists", "company_biologists"),
    ("portland press", "portland_press"),
    ("cold spring harbor", "cshlp"),
    ("american association for cancer research", "aacr"),
    ("american society of hematology", "ash"),
    ("american society of clinical oncology", "ascopubs"),
    ("american society of mechanical engineers", "asme"),
    ("bentham", "bentham"),
    ("american geophysical union", "wiley"),
    ("acoustical society of america", "asa"),
    ("royal society of chemistry", "rsc"),
    ("iop publishing", "iop"),
    ("thieme", "thieme"),
    ("karger", "karger"),
    ("mary ann liebert", "mary_ann_liebert"),
    ("scielo", "scielo"),
    ("edp sciences", "edp_sciences"),
    ("f1000", "f1000"),
    ("ssrn", "ssrn"),
    ("research square", "research_square"),
    ("biorxiv", "rxiv"),
    ("arxiv", "rxiv"),
    ("medrxiv", "rxiv"),
    ("chemrxiv", "rxiv"),
    ("psyarxiv", "rxiv"),
    ("preprints", "rxiv"),
]


_REGISTRANT_CACHE_PATH = Path(__file__).resolve().parents[2] / "mismatches" / "_registrant-cache.json"


def _load_registrant_cache() -> dict[str, str | None]:
    if not _REGISTRANT_CACHE_PATH.exists():
        return {}
    try:
        return json.loads(_REGISTRANT_CACHE_PATH.read_text())
    except Exception:
        return {}


def _save_registrant_cache(cache: dict[str, str | None]) -> None:
    _REGISTRANT_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _REGISTRANT_CACHE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cache, indent=2, sort_keys=True))
    tmp.replace(_REGISTRANT_CACHE_PATH)


def normalize_doi(doi: str) -> str:
    """Strip whitespace and common DOI URL prefixes; lower-case."""
    if not doi:
        return ""
    s = doi.strip()
    for p in (
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "http://dx.doi.org/",
        "doi:",
    ):
        if s.lower().startswith(p):
            s = s[len(p):]
            break
    return s.strip().lower()


def doi_prefix(doi: str) -> str:
    """Return the '10.NNNN' DOI registrant prefix, or '' if not a DOI."""
    n = normalize_doi(doi)
    if "/" not in n or not n.startswith("10."):
        return ""
    return n.split("/", 1)[0]


def prefix_to_publisher(doi: str) -> str | None:
    """Look up a publisher_id by DOI prefix. Returns None if unknown."""
    p = doi_prefix(doi)
    if not p:
        return None
    return DOI_PREFIX_PUBLISHER.get(p)


def domain_to_publisher(url: str) -> str | None:
    """Look up a publisher_id by URL netloc. Returns None if unknown or bare DOI."""
    if not url:
        return None
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return None
    if not host:
        return None
    if host in DOMAIN_PUBLISHER:
        return DOMAIN_PUBLISHER[host]
    if host.startswith("www."):
        host = host[4:]
        if host in DOMAIN_PUBLISHER:
            return DOMAIN_PUBLISHER[host]
    for d, pub in DOMAIN_PUBLISHER.items():
        if pub is not None and host.endswith("." + d):
            return pub
    return None


def normalize_registrant_name(name: str) -> str | None:
    """Map a CrossRef registrant name to a publisher_id slug."""
    if not name:
        return None
    n = name.lower()
    for substr, pub in REGISTRANT_NORMALIZE:
        if substr in n:
            return pub
    return None


def registrant_to_publisher(doi: str, *, allow_network: bool = True, _cache: dict | None = None) -> str | None:
    """Look up a publisher via CrossRef registrant API (cached).

    Returns None if the lookup fails or the registrant doesn't normalize.
    Pass allow_network=False to disable network calls (only use cache).
    """
    p = doi_prefix(doi)
    if not p:
        return None
    cache = _cache if _cache is not None else _load_registrant_cache()
    if p in cache:
        return cache[p]
    if not allow_network:
        return None
    # Live CrossRef registrant lookup
    try:
        import urllib.request
        url = f"https://api.crossref.org/prefixes/{p}"
        req = urllib.request.Request(url, headers={"User-Agent": "parseland-improver/0.1 (mailto:reach2shubhankar@gmail.com)"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        name = (data.get("message") or {}).get("name") or ""
        pub = normalize_registrant_name(name)
        cache[p] = pub
    except Exception:
        cache[p] = None
        pub = None
    # write through; do this sparingly — rank_publishers.py should batch and
    # save once at end of run rather than on every miss.
    if _cache is None:
        _save_registrant_cache(cache)
    return pub


def classify_row(row: dict, *, allow_network: bool = True, _cache: dict | None = None) -> str:
    """Classify a merged-FINAL.csv row to a publisher_id.

    Looks at DOI prefix → URL domain → CrossRef registrant in turn.
    Returns 'unknown' if everything fails.
    """
    doi = row.get("DOI") or row.get("doi") or ""
    link = row.get("Link") or row.get("link") or ""
    pub = prefix_to_publisher(doi)
    if pub:
        return pub
    pub = domain_to_publisher(link)
    if pub:
        return pub
    pub = registrant_to_publisher(doi, allow_network=allow_network, _cache=_cache)
    if pub:
        return pub
    return "unknown"


__all__ = [
    "DOI_PREFIX_PUBLISHER",
    "DOMAIN_PUBLISHER",
    "REGISTRANT_NORMALIZE",
    "normalize_doi",
    "doi_prefix",
    "prefix_to_publisher",
    "domain_to_publisher",
    "normalize_registrant_name",
    "registrant_to_publisher",
    "classify_row",
]
