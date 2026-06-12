"""In-process tests for Springer corresponding-author detection.

Pins the iter-1 fixes for `_get_correspondence_name` regex truncation on
author initials and the additive `_mark_corresponding_from_emails` enrichment
from <meta name="citation_author_email"> and ld+json author.email.

All fixtures are minimal hand-crafted HTML — no Taxicab, no network.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from parseland_lib.publisher.parsers.springer import Springer


# Minimal page with the modern Springer authors-listing layout plus a
# "Correspondence to" sentence with an initial in the CA name.
CORRESP_WITH_INITIAL = """
<html>
  <head>
    <link rel="canonical" href="https://link.springer.com/article/10.1007/s00122-008-0865-5" />
  </head>
  <body>
    <ul>
      <li class="c-article-authors-listing__item">
        <span class="search-name">Chen Niu</span>
        <ol class="c-article-author-affiliation__list">
          <li><p>Texas Tech University</p></li>
        </ol>
      </li>
      <li class="c-article-authors-listing__item">
        <span class="search-name">Bay Nguyen</span>
        <ol class="c-article-author-affiliation__list">
          <li><p>Texas Tech University</p></li>
        </ol>
      </li>
      <li class="c-article-authors-listing__item">
        <span class="search-name">Robert J. Wright</span>
        <ol class="c-article-author-affiliation__list">
          <li><p>Texas Tech University</p></li>
        </ol>
      </li>
    </ul>
    <p>Correspondence to Robert J. Wright .</p>
  </body>
</html>
"""


# Page with NO "Correspondence to" text but with citation_author_email metas
# pointing at a specific author.
CORRESP_FROM_CITATION_EMAIL_META = """
<html>
  <head>
    <link rel="canonical" href="https://link.springer.com/article/10.1007/example" />
    <meta name="citation_author" content="Sheng Bao-Huai" />
    <meta name="citation_author" content="Ye Peixin" />
    <meta name="citation_author_email" content="ye@example.org" />
    <meta name="citation_author" content="Yanwen Wu" />
  </head>
  <body>
    <ul>
      <li class="c-article-authors-listing__item">
        <span class="search-name">Sheng Bao-Huai</span>
        <ol class="c-article-author-affiliation__list"><li><p>X University</p></li></ol>
      </li>
      <li class="c-article-authors-listing__item">
        <span class="search-name">Ye Peixin</span>
        <ol class="c-article-author-affiliation__list"><li><p>X University</p></li></ol>
      </li>
      <li class="c-article-authors-listing__item">
        <span class="search-name">Yanwen Wu</span>
        <ol class="c-article-author-affiliation__list"><li><p>X University</p></li></ol>
      </li>
    </ul>
  </body>
</html>
"""


# Same-surname coauthor case: the email meta points at Anders Wahlin only.
# Surname-only matching used to also flag Björn E. Wahlin.
CORRESP_EMAIL_META_SHARED_SURNAME = """
<html>
  <head>
    <link rel="canonical" href="https://link.springer.com/article/10.1007/example" />
    <meta name="citation_author" content="Wahlin, Anders" />
    <meta name="citation_author_email" content="anders@example.org" />
    <meta name="citation_author" content="Wahlin, Björn E." />
  </head>
  <body>
    <ul>
      <li class="c-article-authors-listing__item">
        <span class="search-name">Anders Wahlin</span>
        <ol class="c-article-author-affiliation__list"><li><p>Inst</p></li></ol>
      </li>
      <li class="c-article-authors-listing__item">
        <span class="search-name">Björn E. Wahlin</span>
        <ol class="c-article-author-affiliation__list"><li><p>Inst</p></li></ol>
      </li>
    </ul>
  </body>
</html>
"""


# Page with ld+json author email — must surface CA flag even when an earlier
# parser path already populated authors (was previously only honored when
# parse_ld_json was the primary path).
CORRESP_FROM_LDJSON_EMAIL = """
<html>
  <head>
    <link rel="canonical" href="https://link.springer.com/chapter/10.1007/example" />
    <script type="application/ld+json">
    {
      "mainEntity": {
        "author": [
          {"@type": "Person", "name": "Alice First"},
          {"@type": "Person", "name": "Bob Email", "email": "bob@example.org"}
        ]
      }
    }
    </script>
  </head>
  <body>
    <ul>
      <li class="c-article-authors-listing__item">
        <span class="search-name">Alice First</span>
        <ol class="c-article-author-affiliation__list"><li><p>Inst</p></li></ol>
      </li>
      <li class="c-article-authors-listing__item">
        <span class="search-name">Bob Email</span>
        <ol class="c-article-author-affiliation__list"><li><p>Inst</p></li></ol>
      </li>
    </ul>
  </body>
</html>
"""


# Page where the "Correspondence to" text ends with a sentence period but the
# CA name has NO initial. Earlier-pattern fix must not regress this case.
CORRESP_NO_INITIAL = """
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
        <span class="search-name">Anders Wahlin</span>
        <ol class="c-article-author-affiliation__list"><li><p>Inst</p></li></ol>
      </li>
    </ul>
    <p>Correspondence to Anders Wahlin .</p>
  </body>
</html>
"""


# Page with NEITHER signal — no Correspondence text, no email metas, no
# ld+json email. Parser must not invent a CA.
CORRESP_NO_SIGNAL = """
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
    </ul>
  </body>
</html>
"""


CORRESP_MULTI_TARGET = """
<html>
  <head>
    <link rel="canonical" href="https://link.springer.com/article/10.1007/example" />
  </head>
  <body>
    <ul>
      <li class="c-article-authors-listing__item">
        <span class="search-name">Song-Liang Qiu</span>
        <ol class="c-article-author-affiliation__list"><li><p>Inst</p></li></ol>
      </li>
      <li class="c-article-authors-listing__item">
        <span class="search-name">Tamanna Akter</span>
        <ol class="c-article-author-affiliation__list"><li><p>Inst</p></li></ol>
      </li>
      <li class="c-article-authors-listing__item">
        <span class="search-name">Yu-Ming Chu</span>
        <ol class="c-article-author-affiliation__list"><li><p>Inst</p></li></ol>
      </li>
    </ul>
    <p>Correspondence to Song-Liang Qiu or Yu-Ming Chu.</p>
  </body>
</html>
"""


CORRESP_TEXT_OVERRIDES_LDJSON_EMAILS = """
<html>
  <head>
    <link rel="canonical" href="https://link.springer.com/chapter/10.1007/example" />
    <script type="application/ld+json">
    {
      "mainEntity": {
        "author": [
          {"@type": "Person", "name": "Kiran Devi", "email": "kiran@example.org"},
          {"@type": "Person", "name": "Kaushal Sharma", "email": "kaushal@example.org"},
          {"@type": "Person", "name": "Neeraj Saini", "email": "neeraj@example.org"}
        ]
      }
    }
    </script>
  </head>
  <body>
    <p>Correspondence to Kiran Devi.</p>
  </body>
</html>
"""


def _ca_names(result):
    return [
        a["name"] for a in result["authors"]
        if isinstance(a, dict) and a.get("is_corresponding")
    ] + [
        a.name for a in result["authors"]
        if not isinstance(a, dict) and getattr(a, "is_corresponding", False)
    ]


def test_correspondence_to_regex_handles_author_initials():
    """Regression: 'Correspondence to Robert J. Wright .' must match the
    full name, not truncate at the middle initial's period."""
    soup = BeautifulSoup(CORRESP_WITH_INITIAL, "lxml")
    result = Springer(soup).parse()
    ca_names = _ca_names(result)
    assert any("Robert J. Wright" in n for n in ca_names), (
        f"expected 'Robert J. Wright' in CAs but got {ca_names!r}"
    )
    # Other authors not flagged
    assert not any("Niu" in n for n in ca_names)
    assert not any("Nguyen" in n for n in ca_names)


def test_correspondence_to_regex_no_initial_still_works():
    """Regression: must not regress the existing no-initial path that the
    old `(.+?)(?:\\.|$)` regex handled correctly."""
    soup = BeautifulSoup(CORRESP_NO_INITIAL, "lxml")
    result = Springer(soup).parse()
    ca_names = _ca_names(result)
    assert any("Anders Wahlin" in n for n in ca_names)
    assert not any("Alice" in n for n in ca_names)


def test_citation_author_email_meta_flags_ca():
    """Iter-1 addition: <meta name='citation_author_email'> should flag the
    paired citation_author as CA even when no 'Correspondence to' text
    exists on the page (97% of failing FN rows had this signal available)."""
    soup = BeautifulSoup(CORRESP_FROM_CITATION_EMAIL_META, "lxml")
    result = Springer(soup).parse()
    ca_names = _ca_names(result)
    assert any("Ye Peixin" in n for n in ca_names), (
        f"expected 'Ye Peixin' from citation_author_email meta but got {ca_names!r}"
    )


def test_citation_author_email_meta_does_not_overmark_shared_surname():
    """Email-meta CA matching must not mark every same-surname coauthor."""
    soup = BeautifulSoup(CORRESP_EMAIL_META_SHARED_SURNAME, "lxml")
    result = Springer(soup).parse()
    ca_names = _ca_names(result)
    assert ca_names == ["Anders Wahlin"]


def test_ldjson_email_flags_ca_even_when_not_primary_path():
    """Iter-1 addition: ld+json author.email signal should fire even when an
    earlier path (here, parse_authors_method_3) produced the author list.
    Before iter-1 the ld+json email was only honored as a primary path."""
    soup = BeautifulSoup(CORRESP_FROM_LDJSON_EMAIL, "lxml")
    result = Springer(soup).parse()
    ca_names = _ca_names(result)
    assert any("Bob Email" in n for n in ca_names), (
        f"expected 'Bob Email' from ld+json email but got {ca_names!r}"
    )
    # Alice (no email) is not CA
    assert not any("Alice First" in n for n in ca_names)


def test_no_ca_signal_means_no_ca_flagged():
    """Defensive: when no CA signal is present, the parser must not
    invent one. Pre-existing _mark_corresponding_author returns the
    author list unchanged when no Correspondence text exists; the
    iter-1 email enrichment must preserve that behavior."""
    soup = BeautifulSoup(CORRESP_NO_SIGNAL, "lxml")
    result = Springer(soup).parse()
    ca_names = _ca_names(result)
    assert ca_names == [], f"expected no CA but got {ca_names!r}"


def test_correspondence_to_marks_multiple_visible_targets():
    """Visible multi-name correspondence text should flag every named
    target, not stop after the first author match."""
    soup = BeautifulSoup(CORRESP_MULTI_TARGET, "lxml")
    result = Springer(soup).parse()
    ca_names = _ca_names(result)
    assert ca_names == ["Song-Liang Qiu", "Yu-Ming Chu"]


def test_correspondence_to_overrides_ldjson_email_overflags():
    """When LD+JSON emails mark every author as CA, explicit visible
    correspondence text should constrain the final CA set."""
    soup = BeautifulSoup(CORRESP_TEXT_OVERRIDES_LDJSON_EMAILS, "lxml")
    result = Springer(soup).parse()
    ca_names = _ca_names(result)
    assert ca_names == ["Kiran Devi"]
