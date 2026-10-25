"""Run one checkout's parse_page over a frozen corpus, exactly as production calls it.

Production (app.py) reads the stored body bytes and calls parse_page(bytes, namespace, resolved_url) with the
resolved URL recorded for that fetch; this does the same, with no network. The checkout is imported from --lib,
so the same script can run the commit in production and the candidate side by side.

Usage: python gate/run_parser.py --lib <checkout root> --corpus <bundle dir> --out parsed.ndjson [--workers 4]
Output, one line per page: {"page_id", "out": <parse_page response> | null, "error": str | null, "ms": float}
"""
from __future__ import annotations

import argparse
import gzip
import json
import multiprocessing as mp
import os
import sys
import time
import traceback
import warnings

_parse = None
WORKERS = max(1, min(4, os.cpu_count() or 2))  # GitHub's standard runners have 4 vCPUs


def _init(lib):
    global _parse
    sys.path.insert(0, os.path.abspath(lib))
    warnings.filterwarnings("ignore")
    import logging
    logging.disable(logging.CRITICAL)
    import parseland_lib
    from parseland_lib.parse import parse_page  # noqa: E402  (imported from the checkout under test)
    if not os.path.abspath(parseland_lib.__path__[0]).startswith(os.path.abspath(lib)):
        raise RuntimeError(f"parseland_lib came from {parseland_lib.__path__[0]}, not {lib}")
    _parse = parse_page


def _one(args):
    pages_dir, r = args
    t0 = time.perf_counter()
    try:
        body = gzip.open(os.path.join(pages_dir, f"{r['page_id']}.html.gz")).read()
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):  # parsers print debug lines
            out = _parse(body, r["ns"], r.get("resolved_url"))
        err = None
    except Exception as e:  # noqa: BLE001 - a crash is a result
        out, err = None, f"{type(e).__name__}: {e} | {traceback.format_exc(limit=2)[-300:]}"
    return {"page_id": r["page_id"], "out": out, "error": err, "ms": round((time.perf_counter() - t0) * 1000, 1)}


def shard_rows(rows, shard, size=lambda r: 1):
    """Slice i of n of the manifest for shard (i, n): CI parses a corpus as n slices at once. Pages go biggest first
    to the lightest slice, so slices finish together (parse time tracks page size: on dev v1.3 the slowest of 3
    slices had 1,219 s of parsing by stride, 885 s by size). Same rows and sizes give the same slices in every job."""
    if not shard:
        return rows
    i, n = shard
    if not 0 <= i < n:
        raise ValueError(f"shard {i}/{n} out of range")
    load, out = [0] * n, []
    for r in sorted(rows, key=lambda r: (-size(r), r["page_id"])):
        k = load.index(min(load))
        load[k] += size(r)
        if k == i:
            out.append(r)
    return out


def run(lib, corpus, out_path, workers=WORKERS, shard=None):
    pages = os.path.join(corpus, "pages")
    rows = shard_rows([json.loads(l) for l in open(os.path.join(corpus, "manifest.ndjson"))], shard,
                      lambda r: os.path.getsize(os.path.join(pages, f"{r['page_id']}.html.gz")))
    t0 = time.time()
    with mp.get_context("spawn").Pool(workers, initializer=_init, initargs=(lib,), maxtasksperchild=200) as pool, \
            open(out_path, "w") as f:
        for i, res in enumerate(pool.imap_unordered(_one, [(pages, r) for r in rows], chunksize=8), 1):
            f.write(json.dumps(res, ensure_ascii=False) + "\n")
            if i % 500 == 0:
                print(f"  parsed {i}/{len(rows)} ({time.time() - t0:.0f}s)", file=sys.stderr, flush=True)
    print(f"parsed {len(rows)} pages with {lib} in {time.time() - t0:.0f}s", file=sys.stderr)
    return len(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--lib", required=True)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=WORKERS)
    a = ap.parse_args()
    run(a.lib, a.corpus, a.out, a.workers)
