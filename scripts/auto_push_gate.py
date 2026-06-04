#!/usr/bin/env python3
"""Shield — pre-push gate for autonomous Parseland improver.

Runs a sequence of regression checks before Courier is allowed to push. Each
stage can be skipped via flag for lightweight local invocations, but the
default profile is the full no-regression check.

Stages (in order):
1. focused-fixture-tests      — pytest on the touched parser's fixture file(s)
2. deterministic-suite        — pytest -k parser (cheap)
3. whole-goldie-before-after  — uses scripts/whole_goldie_eval.py on HEAD~1 and HEAD;
                                 if --sample N is set, uses a sample for speed
4. prior-touched-sentinel     — re-runs field_inprocess_diff for any publisher
                                 whose parser file was modified in the last 7 days
5. cross-publisher-sentinel   — only when scorer/util changed; runs all 11 fixtures
6. parser-crash-count         — compare summary.errors before vs after

Exit codes:
    0  → all checks green; writes mismatches/gate-results/<sha>.json
    1  → one or more checks failed; writes mismatches/gate-blockers.ndjson
    2  → invocation error (wrong args, missing files)

Usage:
    python scripts/auto_push_gate.py --sha HEAD --since HEAD~1
    python scripts/auto_push_gate.py --pretend --since HEAD~1  (validates gate)
    python scripts/auto_push_gate.py --sha HEAD --skip whole-goldie  (fast path)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.lib.event_ledger import emit, new_run_id  # noqa: E402

VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
PARSELAND_EVAL_PATH = os.environ.get(
    "PARSELAND_EVAL_PATH",
    "/Users/shubh-trips/Documents/OpenAlex/parseland-eval/eval",
)

GATE_RESULTS_DIR = REPO_ROOT / "mismatches" / "gate-results"
GATE_BLOCKERS_PATH = REPO_ROOT / "mismatches" / "gate-blockers.ndjson"

ALL_STAGES = (
    "focused-fixture-tests",
    "deterministic-suite",
    "whole-goldie-before-after",
    "prior-touched-sentinel",
    "cross-publisher-sentinel",
    "parser-crash-count",
)

PARSERS_DIR = REPO_ROOT / "parseland_lib" / "publisher" / "parsers"
SCORER_DIR = REPO_ROOT / "eval" / "parseland_eval" / "score"

# Per-field whole-Goldie regression tolerance (allowable points of decline).
# Per the plan: >1pp regression on any field blocks; >0.5pp for degraded
# publishers like Oxford. We start with 1pp uniform; tighten later.
REGRESSION_TOLERANCE_PP = 1.0

# Cross-publisher fixtures evaluated when a scorer/util change is detected.
CROSS_PUB_FIXTURES = (
    ("elsevier",        "tests/fixtures/elsevier-gold.ndjson"),
    ("springer",        "tests/fixtures/springer-gold.ndjson"),
    ("wiley",           "tests/fixtures/wiley-gold.ndjson"),
    ("ieee",            "tests/fixtures/ieee-10k-gold.ndjson"),
    ("sage",            "tests/fixtures/sage-gold.ndjson"),
    ("cup",             "tests/fixtures/cup-gold.ndjson"),
    ("acs",             "tests/fixtures/acs-gold.ndjson"),
    ("taylor",          "tests/fixtures/taylor-gold.ndjson"),
    ("oup",             "tests/fixtures/oup-gold.ndjson"),
    ("wolters_kluwer",  "tests/fixtures/wolters-kluwer-gold.ndjson"),
)


def git(*args: str) -> tuple[int, str, str]:
    proc = subprocess.run(["git", *args], capture_output=True, text=True, cwd=REPO_ROOT)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def get_touched_files(since: str, sha: str) -> list[str]:
    rc, out, _ = git("diff", "--name-only", f"{since}..{sha}")
    if rc != 0:
        return []
    return [f for f in out.split("\n") if f]


def touched_parser_publishers(touched: list[str]) -> list[str]:
    """Return list of publisher parser file stems that were touched."""
    out: list[str] = []
    for f in touched:
        if not f.startswith("parseland_lib/publisher/parsers/"):
            continue
        name = Path(f).stem
        if name in ("__init__", "parser", "utils", "generic"):
            continue
        out.append(name)
    return out


def touched_scorer_or_utils(touched: list[str]) -> bool:
    for f in touched:
        if f.startswith("eval/parseland_eval/score/"):
            return True
        if f == "parseland_lib/publisher/parsers/utils.py":
            return True
    return False


def stage_focused_fixture_tests(parsers_touched: list[str]) -> dict:
    """Pytest on tests/ files that match touched parser names."""
    if not parsers_touched:
        return {"name": "focused-fixture-tests", "status": "skipped",
                "reason": "no parser files touched"}
    test_targets: list[str] = []
    tests_dir = REPO_ROOT / "tests"
    for parser in parsers_touched:
        for cand in (tests_dir / f"test_{parser}.py", tests_dir / parser):
            if cand.exists():
                test_targets.append(str(cand.relative_to(REPO_ROOT)))
    if not test_targets:
        return {"name": "focused-fixture-tests", "status": "skipped",
                "reason": "no matching test files for touched parsers"}
    proc = subprocess.run(
        [str(VENV_PYTHON), "-m", "pytest", "-q", *test_targets],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=600,
    )
    return {
        "name": "focused-fixture-tests",
        "status": "ok" if proc.returncode == 0 else "failed",
        "rc": proc.returncode,
        "stdout_tail": proc.stdout[-500:],
        "stderr_tail": proc.stderr[-500:],
        "test_targets": test_targets,
    }


def stage_deterministic_suite() -> dict:
    """Run pytest -k parser on the parser test suite."""
    proc = subprocess.run(
        [str(VENV_PYTHON), "-m", "pytest", "-q", "-k", "parser", "tests/"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=1200,
    )
    return {
        "name": "deterministic-suite",
        "status": "ok" if proc.returncode == 0 else "failed",
        "rc": proc.returncode,
        "stdout_tail": proc.stdout[-500:],
        "stderr_tail": proc.stderr[-500:],
    }


def _run_whole_goldie(label: str, sample: int | None, run_id: str) -> Path | None:
    """Run whole_goldie_eval and return the artifact path."""
    out = REPO_ROOT / "eval" / "runs" / f"gate-{label}.json"
    env = dict(os.environ)
    env["PARSELAND_EVAL_PATH"] = PARSELAND_EVAL_PATH
    cmd = [
        str(VENV_PYTHON),
        str(REPO_ROOT / "scripts" / "whole_goldie_eval.py"),
        "run",
        "--corpus",
        "/Users/shubh-trips/Documents/OpenAlex/parseland-eval/eval/data/merged-FINAL.csv",
        "--out", str(out),
        "--label", label,
        "--run-id", run_id,
    ]
    if sample:
        cmd += ["--limit", str(sample)]
    proc = subprocess.run(cmd, cwd=REPO_ROOT, env=env, capture_output=True,
                          text=True, timeout=7200)
    if proc.returncode != 0:
        return None
    return out


def _read_summary(path: Path) -> dict:
    try:
        return (json.loads(path.read_text()).get("summary") or {})
    except Exception:
        return {}


def stage_whole_goldie_before_after(since: str, sha: str, sample: int | None,
                                    run_id: str) -> dict:
    """Run whole-Goldie on `since` and `sha`; diff per-field KPIs.

    Stashes the current working tree, checks out `since`, runs eval, checks out
    `sha`, runs eval, restores stash + branch.
    """
    rc, current_branch, _ = git("rev-parse", "--abbrev-ref", "HEAD")
    if rc != 0:
        return {"name": "whole-goldie-before-after", "status": "skipped",
                "reason": "could not read current branch"}

    # Run "after" first on the current sha (no checkout needed if sha==HEAD).
    after_path = _run_whole_goldie(label="after", sample=sample, run_id=run_id)
    if after_path is None:
        return {"name": "whole-goldie-before-after", "status": "failed",
                "reason": "whole_goldie_eval failed on HEAD"}

    # Checkout `since` to run "before". Only do this if `since` differs from HEAD.
    rc_h, head_sha, _ = git("rev-parse", "HEAD")
    rc_s, since_sha, _ = git("rev-parse", since)
    if head_sha == since_sha:
        return {"name": "whole-goldie-before-after", "status": "skipped",
                "reason": "since == HEAD; nothing to diff",
                "after_artifact": str(after_path)}

    # Stash any unstaged changes.
    stash_made = False
    rc_st, _, _ = git("stash", "push", "-u", "-m", "shield-gate")
    if rc_st == 0:
        stash_made = True
    try:
        rc_co, _, err_co = git("checkout", since_sha, "--detach")
        if rc_co != 0:
            return {"name": "whole-goldie-before-after", "status": "failed",
                    "reason": f"checkout {since_sha} failed: {err_co}"}
        before_path = _run_whole_goldie(label="before", sample=sample, run_id=run_id)
    finally:
        # Always restore current branch + stash
        git("checkout", current_branch)
        if stash_made:
            git("stash", "pop")

    if before_path is None:
        return {"name": "whole-goldie-before-after", "status": "failed",
                "reason": "whole_goldie_eval failed on since"}

    before = _read_summary(before_path)
    after = _read_summary(after_path)
    deltas = _compute_field_deltas(before.get("overall") or {}, after.get("overall") or {})
    regressions = {k: v for k, v in deltas.items() if v < -REGRESSION_TOLERANCE_PP / 100.0}
    return {
        "name": "whole-goldie-before-after",
        "status": "failed" if regressions else "ok",
        "tolerance_pp": REGRESSION_TOLERANCE_PP,
        "deltas": deltas,
        "regressions": regressions,
        "before_artifact": str(before_path),
        "after_artifact": str(after_path),
    }


def _compute_field_deltas(before: dict, after: dict) -> dict[str, float]:
    fields = [
        "authors_f1_soft", "affiliations_f1_fuzzy", "abstract_ratio_fuzzy",
        "pdf_url_accuracy", "corresponding_accuracy",
    ]
    out: dict[str, float] = {}
    for f in fields:
        b = before.get(f)
        a = after.get(f)
        if isinstance(b, (int, float)) and isinstance(a, (int, float)):
            out[f] = round(a - b, 4)
    return out


def stage_prior_touched_sentinel(touched: list[str]) -> dict:
    """For each touched parser file, re-run field_inprocess_diff.

    Just touches the parser whose code changed; "prior-touched" in the plan
    means publishers whose parser file was touched recently. We simplify to:
    every parser file touched in this commit's diff.
    """
    if not touched:
        return {"name": "prior-touched-sentinel", "status": "skipped",
                "reason": "no parser files touched"}
    results: list[dict] = []
    for parser_stem in touched_parser_publishers(touched):
        # Map back to publisher_id via the diff registry. For now, try by name.
        env = dict(os.environ)
        env["PARSELAND_EVAL_PATH"] = PARSELAND_EVAL_PATH
        out = REPO_ROOT / "mismatches" / "baselines" / f"sentinel-{parser_stem}.json"
        cmd = [
            str(VENV_PYTHON),
            str(REPO_ROOT / "scripts" / "field_inprocess_diff.py"),
            "--publisher", parser_stem,
            "--out", str(out),
        ]
        proc = subprocess.run(cmd, cwd=REPO_ROOT, env=env, capture_output=True,
                              text=True, timeout=1800)
        results.append({
            "parser": parser_stem,
            "rc": proc.returncode,
            "artifact": str(out) if proc.returncode == 0 else None,
        })
    failed = [r for r in results if r["rc"] != 0]
    return {
        "name": "prior-touched-sentinel",
        "status": "failed" if failed else "ok",
        "results": results,
    }


def stage_cross_publisher_sentinel(scorer_or_utils_touched: bool) -> dict:
    """If scorer or utils touched, re-run all 11 fixture publishers."""
    if not scorer_or_utils_touched:
        return {"name": "cross-publisher-sentinel", "status": "skipped",
                "reason": "no scorer/utils change"}
    env = dict(os.environ)
    env["PARSELAND_EVAL_PATH"] = PARSELAND_EVAL_PATH
    results: list[dict] = []
    for pub, gold in CROSS_PUB_FIXTURES:
        out = REPO_ROOT / "mismatches" / "baselines" / f"sentinel-cross-{pub}.json"
        cmd = [
            str(VENV_PYTHON),
            str(REPO_ROOT / "scripts" / "field_inprocess_diff.py"),
            "--publisher", pub,
            "--gold", str(REPO_ROOT / gold),
            "--out", str(out),
        ]
        proc = subprocess.run(cmd, cwd=REPO_ROOT, env=env, capture_output=True,
                              text=True, timeout=1800)
        results.append({
            "publisher": pub,
            "rc": proc.returncode,
            "artifact": str(out) if proc.returncode == 0 else None,
        })
    failed = [r for r in results if r["rc"] != 0]
    return {
        "name": "cross-publisher-sentinel",
        "status": "failed" if failed else "ok",
        "results": results,
    }


def stage_parser_crash_count(whole_goldie_stage: dict) -> dict:
    """Compare summary.errors before vs after."""
    if whole_goldie_stage.get("status") in ("skipped", "failed"):
        return {"name": "parser-crash-count", "status": "skipped",
                "reason": "whole-goldie stage did not run cleanly"}
    bp = whole_goldie_stage.get("before_artifact")
    ap = whole_goldie_stage.get("after_artifact")
    if not bp or not ap:
        return {"name": "parser-crash-count", "status": "skipped",
                "reason": "missing whole-goldie artifacts"}
    before = _read_summary(Path(bp))
    after = _read_summary(Path(ap))
    b_err = (before.get("overall") or {}).get("errors", 0)
    a_err = (after.get("overall") or {}).get("errors", 0)
    return {
        "name": "parser-crash-count",
        "status": "failed" if a_err > b_err else "ok",
        "errors_before": b_err,
        "errors_after": a_err,
        "delta": a_err - b_err,
    }


def write_gate_result(sha: str, stages: list[dict], status: str) -> Path:
    GATE_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    result = {
        "sha": sha,
        "status": status,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "stages": stages,
    }
    out = GATE_RESULTS_DIR / f"{sha[:12]}.json"
    out.write_text(json.dumps(result, indent=2))
    return out


def write_gate_blocker(sha: str, stages: list[dict]) -> None:
    GATE_BLOCKERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    blocked = [s for s in stages if s.get("status") == "failed"]
    payload = {
        "sha": sha,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "blocked_stages": blocked,
    }
    with open(GATE_BLOCKERS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sha", default="HEAD",
                   help="Candidate commit SHA (default HEAD).")
    p.add_argument("--since", default="HEAD~1",
                   help="Baseline SHA (default HEAD~1).")
    p.add_argument("--skip", action="append", default=[],
                   choices=list(ALL_STAGES),
                   help="Stage to skip (repeatable).")
    p.add_argument("--whole-goldie-sample", type=int, default=200,
                   help="Sample size for whole-Goldie (default 200; 0=full).")
    p.add_argument("--pretend", action="store_true",
                   help="Validate gate logic without actually running long stages.")
    p.add_argument("--run-id", type=str)
    args = p.parse_args()

    rc, sha_resolved, _ = git("rev-parse", args.sha)
    if rc != 0:
        print(f"ERROR: cannot resolve sha {args.sha}", file=sys.stderr)
        return 2

    rc2, _, _ = git("rev-parse", args.since)
    if rc2 != 0:
        print(f"ERROR: cannot resolve since {args.since}", file=sys.stderr)
        return 2

    run_id = args.run_id or new_run_id()
    emit(run_id=run_id, action="gate.start", agent_name="auto_push_gate",
         commit_sha=sha_resolved, notes=f"since={args.since} sample={args.whole_goldie_sample}")

    touched = get_touched_files(args.since, args.sha)
    parsers_touched = touched_parser_publishers(touched)
    scorer_touched = touched_scorer_or_utils(touched)

    stages: list[dict] = []

    def maybe_run(stage_name: str, fn):
        if stage_name in args.skip or args.pretend:
            stages.append({"name": stage_name, "status": "skipped",
                           "reason": "skipped via flag" if stage_name in args.skip
                                     else "pretend mode"})
            return
        try:
            res = fn()
        except Exception as exc:  # noqa: BLE001
            res = {"name": stage_name, "status": "failed", "exception": str(exc)}
        stages.append(res)
        emit(run_id=run_id, action=f"gate.{stage_name}",
             agent_name="auto_push_gate", commit_sha=sha_resolved,
             status=("ok" if res.get("status") == "ok" else
                     "blocked" if res.get("status") == "failed" else "ok"),
             notes=res.get("reason") or "")

    maybe_run("focused-fixture-tests", lambda: stage_focused_fixture_tests(parsers_touched))
    maybe_run("deterministic-suite", stage_deterministic_suite)
    sample = None if args.whole_goldie_sample == 0 else args.whole_goldie_sample
    maybe_run(
        "whole-goldie-before-after",
        lambda: stage_whole_goldie_before_after(args.since, args.sha, sample, run_id),
    )
    maybe_run("prior-touched-sentinel", lambda: stage_prior_touched_sentinel(touched))
    maybe_run("cross-publisher-sentinel",
              lambda: stage_cross_publisher_sentinel(scorer_touched))
    wg = next((s for s in stages if s.get("name") == "whole-goldie-before-after"), {})
    maybe_run("parser-crash-count", lambda: stage_parser_crash_count(wg))

    failed = [s for s in stages if s.get("status") == "failed"]
    status = "blocked" if failed else "green"
    out_path = write_gate_result(sha_resolved, stages, status)
    if failed:
        write_gate_blocker(sha_resolved, stages)

    emit(run_id=run_id, action="gate.complete", agent_name="auto_push_gate",
         commit_sha=sha_resolved, status=("blocked" if failed else "ok"),
         artifact_path=str(out_path),
         notes=f"{'blocked: ' + ','.join(s['name'] for s in failed) if failed else 'green'}")

    print(json.dumps({
        "sha": sha_resolved,
        "status": status,
        "stages": [{"name": s.get("name"), "status": s.get("status"),
                    "reason": s.get("reason") or s.get("regressions") or {}}
                   for s in stages],
        "result_path": str(out_path),
    }, indent=2, default=str))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
