# Parseland test gate

Every push to `main` now runs this gate before the ECS deploy, and the deploy happens only if it passes
(`.github/workflows/aws.yml`, job "Test gate"). Built in oxjob #1791 (landing-pages charter,
`oxjobs/plans/landing-pages.md`). Two parts:

1. **Unit tests, offline.** `pytest tests` with the network off. Besides the hand-written tests, every page of the
   frozen **dev corpus** (~1,900 stored landing pages with gold labels) is a test: each page x field is pinned to
   `gate/known_failures.json`.
2. **The sealed holdout.** ~1,900 other stored pages whose gold no improvement session ever sees. CI parses them with
   this commit and with the commit now running in ECS, scores both against the gold, and refuses the deploy when a
   field gets worse on a publisher beyond noise (rules below). It prints counts per publisher x field only.

## Working on Parseland with the gate

```bash
pip install -r requirements.txt -r gate/requirements.txt
PARSELAND_GATE_AWS_PROFILE=desk python gate/corpus.py fetch dev   # once per corpus version (private S3 bucket)
python -m pytest tests -q --disable-socket                         # what CI runs (plus gate/test_gate.py)
```

- A test failing with **REGRESSION on [...]** means a page x field that was right is now wrong: fix the code.
- A test failing with **now right on [...]** means you improved it: record that with `python gate/ledger.py update`
  and commit `gate/known_failures.json` with your change. Its diff is the record of what got better.
- To see the holdout verdict without deploying, push your branch as `gate-proof/<name>`: the gate runs, nothing
  deploys, and the job summary shows the counts. Then ship to `main` and log it in charter § 7.
- After a ship, check `openalex.monitoring.landing_page_alerts` for `page=true` rows on the hosts you touched; revert
  if one appears (charter rule).

## What "worse beyond noise" means

A page x field is right or wrong by `gate/fields.py` (gold vs `parse_page` on the stored bytes and stored URL, as
production calls it). Parseland is deterministic, so a flip is a real change; the noise is gold errors and one-off
pages. The gate refuses when:

| Rule | Refuse when |
|---|---|
| per cell | in any publisher x field, losses >= 2 and losses > wins, against the commit in production |
| pooled | for any field over all publishers, losses - wins >= 3 |
| cumulative | any publisher x field has >= 2 fewer right pages than the published baseline (`gate/baseline.json`) |
| crashes | any page now crashes `parse_page` |
| ledger | the commit's `known_failures.json` lists a dev page x field as wrong that production's ledger didn't (writing a regression into the ledger doesn't make it pass) |

One lone loss passes and shows in the summary. The gate doesn't require a gain, so non-parser changes deploy.
Fields: authors (names, order), affiliations (strings per author, strict), corresponding author, abstract (>= 0.90
similarity), PDF link (canonical URL), licence (Parseland's slugs). A value the gold doesn't have counts as wrong.

## Rules for sessions

- **Never fetch or decrypt the holdout, and never look for its pages.** Only CI holds the key. The gate's counts
  are the only thing you learn from it, and each look is a deploy logged in charter § 7.
- **Never edit gold.** If you believe a dev gold value is wrong, append one line to `gate/disputes.ndjson`
  (`{"page_id", "field", "gold", "proposed", "evidence"}`) and tell the charter session; #1791 adjudicates and
  releases a new gold version. June's swarm stalled on unchecked "gold is wrong" claims.
- **Emergency override** (Casey or Jason only, never a swarm session): a `Gate-Override: <reason>` line in the
  commit message skips the holdout rules but never the unit tests or new crashes. Log it in charter § 7.

## Files

| File | What |
|---|---|
| `corpus.py` | fetch / pack the bundles; `corpus.lock.json` pins version, bucket, checksums |
| `run_parser.py` | run one checkout's `parse_page` over a bundle (used for both production and candidate) |
| `score.py`, `fields.py` | page x field scoring and the matching rules |
| `compare.py` | the gate's decision and its counts-only summary |
| `ledger.py`, `known_failures.json` | the dev ledger |
| `baseline.json` | holdout counts per cell for the published baseline commit |
| `test_gate.py` | tests of the rules themselves |

The corpus, labelling method (Opus 5.5 at xhigh, two independent passes on two renderings, adjudication of
disagreements and of values not found in the page), sampling plan and the checks on the gold are in oxjob #1791's
README and EXPLORE.
