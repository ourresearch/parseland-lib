"""Frozen gold corpus bundles for the Parseland gate: fetch them (tests, CI) or pack them (oxjob #1791 only).

Two bundles per corpus version, in the private bucket named in gate/corpus.lock.json:
  dev      pages, manifest and gold that improvement sessions work against and the unit tests pin
  holdout  the sealed half: AES-256 encrypted; only CI (and #1791 when refreshing it) holds the key
Each bundle unpacks to <dir>/{manifest.ndjson, gold.ndjson, pages/<page_id>.html.gz}.

  python gate/corpus.py fetch dev                  # -> ~/.cache/parseland-gate/<version>/dev (or $PARSELAND_GATE_CACHE)
  python gate/corpus.py fetch holdout              # needs $PARSELAND_HOLDOUT_KEY; CI only
  python gate/corpus.py path dev                   # print where the bundle lives
  python gate/corpus.py pack --src <dir> --split dev|holdout --version v1   # #1791 only: build + upload, update the lock

Improvement sessions never fetch or decrypt the holdout: the gate's only output on it is counts per cell.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LOCK = os.path.join(HERE, "corpus.lock.json")
KEY_ENV = "PARSELAND_HOLDOUT_KEY"


def lock():
    return json.load(open(LOCK))


def version():
    return lock()["version"] if os.path.exists(LOCK) else "unlocked"


def cache_root():
    return os.environ.get("PARSELAND_GATE_CACHE") or os.path.expanduser("~/.cache/parseland-gate")


def bundle_dir(split):
    if not os.path.exists(LOCK):
        return os.path.join(cache_root(), "unlocked", split)
    return os.path.join(cache_root(), lock()["version"], split)


def _s3():
    import boto3
    prof = os.environ.get("PARSELAND_GATE_AWS_PROFILE")
    return (boto3.Session(profile_name=prof) if prof else boto3.Session()).client("s3", region_name="us-east-1")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _openssl(args, src, dst):
    if not os.environ.get(KEY_ENV):
        raise SystemExit(f"{KEY_ENV} is not set: the holdout is sealed (CI only)")
    subprocess.run(["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-iter", "200000", *args,
                    "-pass", f"env:{KEY_ENV}", "-in", src, "-out", dst], check=True)


def fetch(split):
    if not os.path.exists(LOCK):  # local dry runs before a corpus is published
        d = bundle_dir(split)
        if os.path.exists(os.path.join(d, "manifest.ndjson")):
            return d
        raise SystemExit("gate/corpus.lock.json is missing: no corpus published yet")
    lk = lock()
    meta = lk[split]
    dest = bundle_dir(split)
    stamp = os.path.join(dest, ".sha256")
    if os.path.exists(stamp) and open(stamp).read().strip() == meta["sha256"]:
        return dest
    with tempfile.TemporaryDirectory() as tmp:
        blob = os.path.join(tmp, "bundle")
        _s3().download_file(lk["bucket"], meta["key"], blob)
        got = sha256(blob)
        if got != meta["sha256"]:
            raise SystemExit(f"{split} bundle checksum mismatch: {got} != {meta['sha256']}")
        tar = blob
        if meta.get("encrypted"):
            tar = os.path.join(tmp, "bundle.tar.gz")
            _openssl(["-d"], blob, tar)
        if os.path.exists(dest):
            shutil.rmtree(dest)
        os.makedirs(dest)
        with tarfile.open(tar) as t:
            t.extractall(dest, filter="data")
    open(stamp, "w").write(meta["sha256"])
    return dest


def pack(src, split, version, bucket):
    """Build a bundle from a directory holding manifest.ndjson, gold.ndjson and pages/ (#1791 only)."""
    lk = json.load(open(LOCK)) if os.path.exists(LOCK) else {}
    if lk.get("version") not in (None, version):
        lk = {}
    with tempfile.TemporaryDirectory() as tmp:
        tar = os.path.join(tmp, f"{split}.tar.gz")
        with tarfile.open(tar, "w:gz") as t:
            for name in ("manifest.ndjson", "gold.ndjson", "pages", "regression", "labels"):
                if os.path.exists(os.path.join(src, name)) or name in ("manifest.ndjson", "gold.ndjson", "pages"):
                    t.add(os.path.join(src, name), arcname=name)
        out, key = tar, f"corpus/{version}/{split}.tar.gz"
        if split == "holdout":
            out, key = tar + ".enc", key + ".enc"
            _openssl(["-salt"], tar, out)
        digest = sha256(out)
        _s3().upload_file(out, bucket, key)
        n = sum(1 for _ in open(os.path.join(src, "manifest.ndjson")))
        lk.update(version=version, bucket=bucket)
        lk[split] = {"key": key, "sha256": digest, "pages": n, "encrypted": split == "holdout",
                     "bytes": os.path.getsize(out)}
    json.dump(lk, open(LOCK, "w"), indent=1)
    open(LOCK, "a").write("\n")
    print(f"packed {split}: {n} pages -> s3://{bucket}/{key} ({digest[:12]})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch"); f.add_argument("split", choices=["dev", "holdout"])
    p = sub.add_parser("path"); p.add_argument("split", choices=["dev", "holdout"])
    k = sub.add_parser("pack"); k.add_argument("--src", required=True); k.add_argument("--split", required=True)
    k.add_argument("--version", required=True); k.add_argument("--bucket", default="openalex-parseland-gate")
    a = ap.parse_args()
    if a.cmd == "fetch":
        print(fetch(a.split))
    elif a.cmd == "path":
        print(bundle_dir(a.split))
    else:
        pack(a.src, a.split, a.version, a.bucket)
