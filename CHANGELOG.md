# Changelog

All notable changes to Parseland will be documented in this file.

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
