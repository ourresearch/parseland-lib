# Changelog

All notable changes to Parseland will be documented in this file.

## [2026-09-10] - Scraped licences must come from the article, not site chrome

### Fixed
- **Site-wide footer licences**: `page_potential_license_text` now strips `<footer>`, `<nav>`,
  `role="contentinfo"` and footer-named containers before the licence regexes run. A
  "content of this site is licensed CC BY" footer had turned paywalled pages into `cc-by`
  (scientific.net: 99.6% of 962K parses; the crossref.org defunct-DOI page).
- **Untrusted licence hosts**: one `UNTRUSTED_LICENSE_HOSTS` list (the duplicate, dead
  `_trust_publisher_license` is gone), matched on a dot boundary, and honoured on the
  repository (pmh) path as well as the publisher path. Added scientific.net, schwabeonline.ch
  (DOI-independent shell page with a CC BY badge), indianjournals.com (pages marked Paid),
  crossref.org (defunct-DOI page and the multiple-resolution chooser) and doaj.org (article
  pages carry DOAJ's own CC BY-SA, not the article's — 10.7M parses, 100% cc-by-sa).
  An untrusted host now yields `None`, not `False`.
- **`cc by` shorthand**: the bare `ccby*` keys were substring-matched against the
  whitespace-stripped page, so base64 blobs licensed pages ("...sheep rearers..." encodes to
  "...ccbyzwfy..."). The shorthand must now be a standalone token in the original text.
- **Licence search saw no scripts**: `cleanup_soup()` extracts `<script>` in place before the
  page string used for the licence search was taken, so JSON payloads were invisible. The
  search now runs on a pre-cleanup snapshot (eLife reviewed-preprint pages carry the
  article licence only in `__NEXT_DATA__` once the site footer is gone).
- Tests: `tests/test_license_untrusted_hosts.py` (offline). Validated on 87 live pages across
  44 publishers where Crossref and the page agree (86/87 before and after) and on 10
  template-host pages (10/10 now `None`, 9/10 were `cc-by`).

## [2026-08-19] - OJS article pages are publishedVersion

### Fixed
- **Repo path version**: pmh-namespace landing pages served by Open Journal Systems
  (detected via the `generator` meta tag OJS core emits on every page) now return
  `version: publishedVersion` instead of the repository default `submittedVersion`.
  An OJS article page is the publisher's own copy — the version of record — not a
  repository deposit. First consumer: journal-endpoint ingestion (oxjob #805,
  Chemical Engineering Transactions pilot). Non-OJS repo pages keep the conservative
  default; regression tests for both in `tests/test_parse_page.py`.

## [2025-01-03] - ScienceDirect and Springer Improvements

### Added
- **ScienceDirect**: Support for `window.__PRELOADED_STATE__` JSON extraction
  - Newer Elsevier pages embed author/affiliation data in JavaScript variables instead of `<script type="application/json">` tags
  - Parser now tries both extraction methods
  - Fixes parsing for many recent Elsevier publications that were returning empty author lists

- **Springer**: Corresponding author detection from "Correspondence to" sections
  - Added `_get_correspondence_name()` to extract author name from "Correspondence to" paragraphs
  - Added `_mark_corresponding_author()` to match extracted name against author list
  - Applied as post-processing step to all Springer parsing methods
  - Fixes many cases where `is_corresponding` was returning `None`

- **Tests**: Added pytest test runner for embedded test_cases
  - `tests/test_parsers.py` - Discovers and runs all test_cases embedded in parser files
  - `tests/conftest.py` - HTML fetching via Taxicab API
  - Added test cases for `__PRELOADED_STATE__` extraction

### Fixed
- `sciencedirect.py`: `get_json_authors_affiliations_abstract()` now returns proper dict `{"authors": [], "abstract": None}` instead of empty dict when no JSON found, preventing downstream KeyError

### Impact
Based on failure analysis of 10k random DOIs:
- **Elsevier BV**: 494 failures identified (276 affiliation, 218 corresponding)
- **Springer Science+Business Media**: 197 failures identified (6 affiliation, 191 corresponding)

Sample verification after deployment:
- Elsevier: 4/4 test DOIs now extract affiliations and corresponding authors
- Springer: 2/2 test DOIs now correctly identify corresponding authors

### Technical Details

#### ScienceDirect `__PRELOADED_STATE__` Pattern
```javascript
// Newer ScienceDirect pages use this pattern:
window.__PRELOADED_STATE__ = {"authors": [...], ...};

// Instead of:
<script type="application/json">{"authors": [...], ...}</script>
```

#### Springer Correspondence Detection
The parser now looks for:
- `<p>Correspondence to [Author Name].</p>`
- `<div>Corresponding author: [Author Name]</div>`

And matches against the parsed author list using fuzzy name matching (at least 2 name parts in common).
