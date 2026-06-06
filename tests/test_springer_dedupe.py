"""In-process tests for Springer author NBSP normalization and dedupe.

Pins the iter-2 patch: `_normalize_and_dedupe` runs at the end of
`Springer.parse()` and (a) strips `\\xa0` from all author names and
affiliations, (b) collapses duplicate authors by lowercased name,
merging their affiliations and OR-ing the corresponding flag.

All fixtures are minimal hand-crafted HTML — no Taxicab, no network.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from parseland_lib.publisher.parsers.springer import Springer


# Page that emits the same author twice via the modern listing layout —
# happens in templates that show authors in both the header listing and
# in an "Author information" expander block.
DUPLICATE_AUTHORS_SAME_LAYOUT = """
<html>
  <head>
    <link rel="canonical" href="https://link.springer.com/article/10.1007/example" />
  </head>
  <body>
    <ul>
      <li class="c-article-authors-listing__item">
        <span class="search-name">Suk-Ha Lee</span>
        <ol class="c-article-author-affiliation__list">
          <li><p>Seoul National University</p></li>
        </ol>
      </li>
      <li class="c-article-authors-listing__item">
        <span class="search-name">Hakyung Kwon</span>
        <ol class="c-article-author-affiliation__list">
          <li><p>Seoul National University</p></li>
        </ol>
      </li>
      <li class="c-article-authors-listing__item">
        <span class="search-name">Suk-Ha Lee</span>
        <ol class="c-article-author-affiliation__list">
          <li><p>Seoul National University</p></li>
        </ol>
      </li>
    </ul>
  </body>
</html>
"""


# Page with NBSP-padded author names from a ld+json fallback path.
# The dedupe key must lowercase and NBSP-normalize so two visually
# identical names ('Anders Wahlin' vs 'Anders Wahlin\xa0') collapse.
NBSP_PADDED_NAMES = """
<html>
  <head>
    <link rel="canonical" href="https://link.springer.com/article/10.1007/example" />
    <script type="application/ld+json">
    {
      "mainEntity": {
        "author": [
          {"@type": "Person", "name": " Anders Wahlin ", "email": "wahlin@example.org"},
          {"@type": "Person", "name": "Fryderyk Lorenz"}
        ]
      }
    }
    </script>
  </head>
  <body>
    <!-- No primary-path markup; parser falls through to parse_ld_json -->
  </body>
</html>
"""


# Page where author appears first with NO affiliation, then again with
# the real affiliation + CA flag. Dedupe must take the affiliation from
# the second occurrence (because first was empty) and OR the CA flag.
# This rescues the case where parse_ld_json runs first (giving names only)
# and a later DOM path enriches with details.
DUPLICATE_AUTHOR_MERGE_AFF_AND_CA = """
<html>
  <head>
    <link rel="canonical" href="https://link.springer.com/article/10.1007/example" />
  </head>
  <body>
    <ul>
      <li class="c-article-authors-listing__item">
        <span class="search-name">Jane Doe</span>
      </li>
      <li class="c-article-authors-listing__item">
        <span class="search-name">Jane Doe</span>
        <ol class="c-article-author-affiliation__list">
          <li><p>Department B, Some University</p></li>
        </ol>
      </li>
    </ul>
    <p>Correspondence to Jane Doe .</p>
  </body>
</html>
"""


# A page with three distinct authors and a 'Correspondence to' line.
# Dedupe must not collapse distinct people — control test.
NO_DUPLICATES_NO_COLLAPSE = """
<html>
  <head>
    <link rel="canonical" href="https://link.springer.com/article/10.1007/example" />
  </head>
  <body>
    <ul>
      <li class="c-article-authors-listing__item">
        <span class="search-name">Alice First</span>
        <ol class="c-article-author-affiliation__list"><li><p>Inst</p></li></ol>
      </li>
      <li class="c-article-authors-listing__item">
        <span class="search-name">Bob Second</span>
        <ol class="c-article-author-affiliation__list"><li><p>Inst</p></li></ol>
      </li>
      <li class="c-article-authors-listing__item">
        <span class="search-name">Carol Third</span>
        <ol class="c-article-author-affiliation__list"><li><p>Inst</p></li></ol>
      </li>
    </ul>
  </body>
</html>
"""


METHOD_2_MULTI_AFFILIATION_AUTHOR = """
<html>
  <head>
    <link rel="canonical" href="https://link.springer.com/article/10.1007/example" />
  </head>
  <body>
    <ol class="c-article-author-affiliation__list">
      <li id="Aff1">
        <p class="c-article-author-affiliation__address">Department A, City, Country</p>
        <p class="c-article-author-affiliation__authors-list">Alice Example & Bob Example</p>
      </li>
      <li id="Aff2">
        <p class="c-article-author-affiliation__address">Institute B, City, Country</p>
        <p class="c-article-author-affiliation__authors-list">Alice Example</p>
      </li>
    </ol>
  </body>
</html>
"""


METHOD_2_CREDENTIAL_SUFFIX_AUTHORS = """
<html>
  <head>
    <link rel="canonical" href="https://link.springer.com/article/10.1007/example" />
  </head>
  <body>
    <ol class="c-article-author-affiliation__list">
      <li id="Aff1">
        <p class="c-article-author-affiliation__address">Department A</p>
        <p class="c-article-author-affiliation__authors-list">
          Aurelien Marabelle M.D., Ph.D. & Juliet C. Gray M.A., FRCPCH, Ph.D.
        </p>
      </li>
    </ol>
    <p>Correspondence to Juliet C. Gray M.A., FRCPCH, Ph.D.</p>
  </body>
</html>
"""


def _names(result):
    return [
        a["name"] if isinstance(a, dict) else getattr(a, "name", None)
        for a in result["authors"]
    ]


def _affs_for(result, name):
    for a in result["authors"]:
        n = a["name"] if isinstance(a, dict) else getattr(a, "name", None)
        if n == name:
            return (
                a["affiliations"] if isinstance(a, dict)
                else getattr(a, "affiliations", [])
            )
    return None


def test_duplicate_authors_same_layout_dedupe():
    """A page that lists 'Suk-Ha Lee' twice must produce one Suk-Ha Lee
    in the final output (not two)."""
    soup = BeautifulSoup(DUPLICATE_AUTHORS_SAME_LAYOUT, "lxml")
    result = Springer(soup).parse()
    names = _names(result)
    assert names.count("Suk-Ha Lee") == 1, (
        f"expected 1 'Suk-Ha Lee' after dedupe, got names={names!r}"
    )
    assert "Hakyung Kwon" in names
    # Order preserved — first occurrence wins
    assert names[0] == "Suk-Ha Lee"
    assert names[1] == "Hakyung Kwon"


def test_nbsp_padded_names_stripped():
    """ld+json author names emitted with leading/trailing `\\xa0` must
    end up without NBSP in the final output."""
    soup = BeautifulSoup(NBSP_PADDED_NAMES, "lxml")
    result = Springer(soup).parse()
    names = _names(result)
    assert "\xa0" not in "".join(names or [""]), (
        f"NBSP survived in author names: {names!r}"
    )
    assert "Anders Wahlin" in names
    assert "Fryderyk Lorenz" in names


def test_duplicate_author_aff_rescue_when_first_was_empty():
    """When the first occurrence has NO affiliations and the duplicate
    occurrence has them, dedupe must adopt the duplicate's affiliations.
    Conservative merge: the parser does NOT add duplicate-occurrence affs
    on top of an already-populated first occurrence, because doing so
    inflates the per-author aff set past what gold attributes (one
    primary aff per author per paper) and drags the per-pair F1."""
    soup = BeautifulSoup(DUPLICATE_AUTHOR_MERGE_AFF_AND_CA, "lxml")
    result = Springer(soup).parse()
    names = _names(result)
    assert names.count("Jane Doe") == 1
    affs = _affs_for(result, "Jane Doe") or []
    affs_text = " ".join(affs)
    assert "Department B" in affs_text, (
        f"expected Dept B (rescued from duplicate occurrence) but got {affs!r}"
    )


def test_duplicate_author_preserves_corresponding_flag():
    """When the duplicate occurrence is the one flagged as corresponding,
    the merged entry must carry the CA flag."""
    soup = BeautifulSoup(DUPLICATE_AUTHOR_MERGE_AFF_AND_CA, "lxml")
    result = Springer(soup).parse()
    ca_names = [
        (a["name"] if isinstance(a, dict) else getattr(a, "name", None))
        for a in result["authors"]
        if (a.get("is_corresponding") if isinstance(a, dict)
            else getattr(a, "is_corresponding", False))
    ]
    assert "Jane Doe" in ca_names


CONSERVATIVE_AFF_MERGE_FIRST_WINS = """
<html>
  <head>
    <link rel="canonical" href="https://link.springer.com/article/10.1007/example" />
  </head>
  <body>
    <ul>
      <li class="c-article-authors-listing__item">
        <span class="search-name">Jane Doe</span>
        <ol class="c-article-author-affiliation__list">
          <li><p>Primary Affiliation</p></li>
        </ol>
      </li>
      <li class="c-article-authors-listing__item">
        <span class="search-name">Jane Doe</span>
        <ol class="c-article-author-affiliation__list">
          <li><p>Secondary Affiliation</p></li>
        </ol>
      </li>
    </ul>
  </body>
</html>
"""


def test_conservative_aff_merge_when_first_occurrence_has_affs():
    """Pin the iter-2 conservative-merge rule: when the first occurrence
    already has affiliations, duplicate-occurrence affs are NOT appended.
    Avoids inflating per-author aff sets past gold (which lists one
    primary aff per author), which would otherwise regress per-pair F1."""
    soup = BeautifulSoup(CONSERVATIVE_AFF_MERGE_FIRST_WINS, "lxml")
    result = Springer(soup).parse()
    names = _names(result)
    assert names.count("Jane Doe") == 1
    affs = _affs_for(result, "Jane Doe") or []
    assert affs == ["Primary Affiliation"], (
        f"expected only the first occurrence's affiliation but got {affs!r}"
    )


def test_no_duplicates_no_collapse():
    """Defensive: three distinct authors must not be collapsed by dedupe."""
    soup = BeautifulSoup(NO_DUPLICATES_NO_COLLAPSE, "lxml")
    result = Springer(soup).parse()
    names = _names(result)
    assert names == ["Alice First", "Bob Second", "Carol Third"]


def test_method_2_preserves_multiple_affiliations_for_same_author():
    """The affiliation-list layout maps repeated author names to multiple
    affiliation blocks, not duplicate author records."""
    soup = BeautifulSoup(METHOD_2_MULTI_AFFILIATION_AUTHOR, "lxml")
    result = Springer(soup).parse()
    names = _names(result)
    assert names.count("Alice Example") == 1
    assert names.count("Bob Example") == 1
    assert _affs_for(result, "Alice Example") == [
        "Department A, City, Country",
        "Institute B, City, Country",
    ]


def test_method_2_keeps_comma_separated_author_credentials():
    """Credentials separated by commas are suffixes, not standalone authors."""
    soup = BeautifulSoup(METHOD_2_CREDENTIAL_SUFFIX_AUTHORS, "lxml")
    result = Springer(soup).parse()
    names = _names(result)
    assert names == [
        "Aurelien Marabelle M.D., Ph.D.",
        "Juliet C. Gray M.A., FRCPCH, Ph.D.",
    ]
    ca = [
        a["name"]
        for a in result["authors"]
        if a.get("is_corresponding")
    ]
    assert ca == ["Juliet C. Gray M.A., FRCPCH, Ph.D."]
