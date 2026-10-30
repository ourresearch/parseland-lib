"""In-process tests for the iter-3 book-editor filter.

Pins `_drop_book_editors_from_authors` — the post-dedupe filter that drops
names found in the `<div id="editor-information-section">` block from the
parsed author list. Book-chapter pages on SpringerLink put their editors
here; the legacy parser paths sometimes scoop them into the chapter author
list and inflate parsed_total well past gold_total.

All fixtures are minimal hand-crafted HTML — no Taxicab, no network.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from parseland_lib.publisher.parsers.springer import Springer


BOOK_CHAPTER_WITH_EDITOR = """
<html>
  <head>
    <link rel="canonical" href="https://link.springer.com/chapter/10.1007/example" />
  </head>
  <body>
    <ul>
      <li class="c-article-authors-listing__item">
        <span class="search-name">Nathan J. Morris</span>
        <ol class="c-article-author-affiliation__list"><li><p>Case Western</p></li></ol>
      </li>
      <li class="c-article-authors-listing__item">
        <span class="search-name">Catherine M. Stein</span>
        <ol class="c-article-author-affiliation__list"><li><p>Case Western</p></li></ol>
      </li>
      <!-- A third entry the parser also picks up because the page lists
           the book's editor in the same author-listing markup -->
      <li class="c-article-authors-listing__item">
        <span class="search-name">Robert C. Elston</span>
        <ol class="c-article-author-affiliation__list"><li><p>Case Western</p></li></ol>
      </li>
    </ul>
    <div id="editor-information-section">
      <h2 id="editor-information">Editor information</h2>
      <div id="editor-information-content">
        Editors and Affiliations
        Case Western Reserve University, Cleveland, OH, USA
        Robert C. Elston
      </div>
    </div>
  </body>
</html>
"""


BOOK_CHAPTER_WITH_TITLED_EDITORS = """
<html>
  <head>
    <link rel="canonical" href="https://link.springer.com/chapter/10.1007/example" />
  </head>
  <body>
    <ul>
      <li class="c-article-authors-listing__item">
        <span class="search-name">Jan Caha</span>
        <ol class="c-article-author-affiliation__list"><li><p>X Univ</p></li></ol>
      </li>
      <li class="c-article-authors-listing__item">
        <span class="search-name">Jaroslav Burian</span>
        <ol class="c-article-author-affiliation__list"><li><p>X Univ</p></li></ol>
      </li>
      <li class="c-article-authors-listing__item">
        <span class="search-name">Prof. Igor Ivan</span>
        <ol class="c-article-author-affiliation__list"><li><p>Y Univ</p></li></ol>
      </li>
      <li class="c-article-authors-listing__item">
        <span class="search-name">Prof. Jiří Horák</span>
        <ol class="c-article-author-affiliation__list"><li><p>Y Univ</p></li></ol>
      </li>
    </ul>
    <div id="editor-information-section">
      <div id="editor-information-content">
        Editors and Affiliations
        Inst Geoinformatics, VŠB-Technical University of Ostrava, Czech Republic
        Prof. Igor Ivan
        Inst Geoinformatics, VŠB-Technical University of Ostrava, Czech Republic
        Prof. Jiří Horák
      </div>
    </div>
  </body>
</html>
"""


JOURNAL_ARTICLE_NO_EDITOR_SECTION = """
<html>
  <head>
    <link rel="canonical" href="https://link.springer.com/article/10.1007/example" />
  </head>
  <body>
    <ul>
      <li class="c-article-authors-listing__item">
        <span class="search-name">Joana Bittencourt-Silvestre</span>
        <ol class="c-article-author-affiliation__list"><li><p>UFRJ</p></li></ol>
      </li>
      <li class="c-article-authors-listing__item">
        <span class="search-name">Leandro Lemgruber</span>
        <ol class="c-article-author-affiliation__list"><li><p>UFRJ</p></li></ol>
      </li>
      <li class="c-article-authors-listing__item">
        <span class="search-name">Wanderley de Souza</span>
        <ol class="c-article-author-affiliation__list"><li><p>UFRJ</p></li></ol>
      </li>
    </ul>
  </body>
</html>
"""


def _names(result):
    return [
        a["name"] if isinstance(a, dict) else getattr(a, "name", None)
        for a in result["authors"]
    ]


def test_drops_book_editor_with_no_title():
    """The simplest case — book chapter with two chapter authors plus the
    editor's name appearing as a third "author" via the listing markup.
    Editor section names the same person. Filter drops them."""
    soup = BeautifulSoup(BOOK_CHAPTER_WITH_EDITOR, "lxml")
    result = Springer(soup).parse()
    names = _names(result)
    assert "Nathan J. Morris" in names
    assert "Catherine M. Stein" in names
    assert "Robert C. Elston" not in names, (
        f"Robert C. Elston (book editor) should be dropped — got {names!r}"
    )
    assert len(names) == 2


def test_drops_titled_editors():
    """Multiple editors with academic titles ('Prof.') get dropped."""
    soup = BeautifulSoup(BOOK_CHAPTER_WITH_TITLED_EDITORS, "lxml")
    result = Springer(soup).parse()
    names = _names(result)
    assert "Jan Caha" in names
    assert "Jaroslav Burian" in names
    assert "Prof. Igor Ivan" not in names
    assert "Prof. Jiří Horák" not in names
    assert len(names) == 2


def test_journal_article_unchanged():
    """Defensive: pages with no `editor-information-section` are
    no-ops. Filter must not affect journal articles."""
    soup = BeautifulSoup(JOURNAL_ARTICLE_NO_EDITOR_SECTION, "lxml")
    result = Springer(soup).parse()
    names = _names(result)
    assert names == [
        "Joana Bittencourt-Silvestre",
        "Leandro Lemgruber",
        "Wanderley de Souza",
    ]


def test_drops_editor_when_section_id_is_content_variant():
    """Some pages use `#editor-information-content` directly (no outer
    `-section` wrapper). The filter must check both ids."""
    html = """
    <html>
      <body>
        <ul>
          <li class="c-article-authors-listing__item">
            <span class="search-name">Real Author</span>
            <ol class="c-article-author-affiliation__list"><li><p>X</p></li></ol>
          </li>
          <li class="c-article-authors-listing__item">
            <span class="search-name">Book Editor</span>
            <ol class="c-article-author-affiliation__list"><li><p>Y</p></li></ol>
          </li>
        </ul>
        <div id="editor-information-content">
          Editors and Affiliations
          Y
          Book Editor
        </div>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "lxml")
    result = Springer(soup).parse()
    names = _names(result)
    assert "Real Author" in names
    assert "Book Editor" not in names


def test_preserves_single_author_who_is_also_book_editor():
    """Edge case from iter-3 scale eval: single-author book chapters where
    the chapter author is ALSO the book editor (e.g. Jan W. Gooch's
    encyclopedia contributions where he authored the chapter and edited
    the book). A naive drop would zero out the author list. The filter
    must preserve all parsed authors when every parsed name appears in
    the editor section — that's the signal of same-person-both-roles,
    not "these are extra editors"."""
    html = """
    <html>
      <body>
        <ul>
          <li class="c-article-authors-listing__item">
            <span class="search-name">Jan W. Gooch</span>
            <ol class="c-article-author-affiliation__list"><li><p>Atlanta, USA</p></li></ol>
          </li>
        </ul>
        <div id="editor-information-section">
          Editor information
          Editors and Affiliations
          2020 Howell Mill Road C227, Atlanta, GA, 30318, USA
          Jan W. Gooch
        </div>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "lxml")
    result = Springer(soup).parse()
    names = _names(result)
    assert names == ["Jan W. Gooch"], (
        f"single-author-also-editor case dropped to empty — got {names!r}"
    )


def test_preserves_multi_author_when_all_are_also_editors():
    """Variant of the single-author guard: a co-edited chapter where BOTH
    chapter authors are also the book editors (e.g. the Stevenses'
    encyclopedia entry). All parsed authors appearing in the editor
    section still triggers the all-flagged-preserve rule."""
    html = """
    <html>
      <body>
        <ul>
          <li class="c-article-authors-listing__item">
            <span class="search-name">John Gehret Stevens</span>
            <ol class="c-article-author-affiliation__list"><li><p>UNC Asheville</p></li></ol>
          </li>
          <li class="c-article-authors-listing__item">
            <span class="search-name">Virginia E. Stevens</span>
            <ol class="c-article-author-affiliation__list"><li><p>UNC Asheville</p></li></ol>
          </li>
        </ul>
        <div id="editor-information-section">
          Editor information
          Editors and Affiliations
          UNC Asheville, USA
          John Gehret Stevens
          Virginia E. Stevens
        </div>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "lxml")
    result = Springer(soup).parse()
    names = _names(result)
    assert names == ["John Gehret Stevens", "Virginia E. Stevens"]


def test_keeps_author_whose_name_is_not_in_editor_section():
    """Defensive: a third author who is NOT in the editor section stays."""
    html = """
    <html>
      <body>
        <ul>
          <li class="c-article-authors-listing__item">
            <span class="search-name">Author One</span>
            <ol class="c-article-author-affiliation__list"><li><p>X</p></li></ol>
          </li>
          <li class="c-article-authors-listing__item">
            <span class="search-name">Author Two</span>
            <ol class="c-article-author-affiliation__list"><li><p>X</p></li></ol>
          </li>
          <li class="c-article-authors-listing__item">
            <span class="search-name">Author Three</span>
            <ol class="c-article-author-affiliation__list"><li><p>X</p></li></ol>
          </li>
        </ul>
        <div id="editor-information-section">
          Editors and Affiliations
          Y
          Editor Person
        </div>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "lxml")
    result = Springer(soup).parse()
    names = _names(result)
    assert names == ["Author One", "Author Two", "Author Three"]


def test_short_author_list_fills_missing_coauthor_and_preserves_affiliation():
    """Some Springer chapter pages expose the complete chapter-author list
    only in `ul.c-article-author-list`, while an earlier parser path returns
    a partial list. When the page has one parsed affiliation, the repair can
    safely attach it to the added coauthor too."""
    html = """
    <html>
      <head>
        <link rel="canonical" href="https://link.springer.com/chapter/10.1007/example" />
      </head>
      <body>
        <ul class="c-article-author-list c-article-author-list--short">
          <li class="c-article-author-list__item">
            <a data-test="author-name">Muhammad Qasim</a>
          </li>
          <li class="c-article-author-list__item">
            <a data-test="author-name">Zarook Shareefdeen</a>
          </li>
        </ul>
        <ol class="c-article-author-affiliation__list">
          <li id="Aff1">
            <p class="c-article-author-affiliation__address">Department A</p>
            <p class="c-article-author-affiliation__authors-list">Muhammad Qasim</p>
          </li>
        </ol>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "lxml")
    result = Springer(soup).parse()
    names = _names(result)
    assert names == ["Muhammad Qasim", "Zarook Shareefdeen"]
    assert result["authors"][0]["affiliations"] == ["Department A"]
    assert result["authors"][1]["affiliations"] == ["Department A"]


def test_short_author_list_drops_extra_editor_name():
    """When the short author list is a strict subset of the parsed list,
    prefer the short list. This pins rows where the legacy parser adds a
    book editor beside the actual chapter author."""
    html = """
    <html>
      <head>
        <link rel="canonical" href="https://link.springer.com/chapter/10.1007/example" />
      </head>
      <body>
        <ul class="c-article-author-list c-article-author-list--short">
          <li class="c-article-author-list__item">
            <a data-test="author-name">Colin M. Lewis</a>
          </li>
        </ul>
        <ol class="c-article-author-affiliation__list">
          <li id="Aff1">
            <p class="c-article-author-affiliation__address">Chapter Affiliation</p>
            <p class="c-article-author-affiliation__authors-list">
              Christopher Abel, Colin M. Lewis
            </p>
          </li>
        </ol>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "lxml")
    result = Springer(soup).parse()
    names = _names(result)
    assert names == ["Colin M. Lewis"]
    assert result["authors"][0]["affiliations"] == ["Chapter Affiliation"]


def test_short_author_list_replaces_all_editor_section_names():
    """If all parsed names came from the editor section but the page has a
    distinct short chapter-author list, replace the editor list with the
    short list."""
    html = """
    <html>
      <head>
        <link rel="canonical" href="https://link.springer.com/chapter/10.1007/example" />
      </head>
      <body>
        <ul class="c-article-author-list c-article-author-list--short">
          <li><a data-test="author-name">L. A. S. Johnson</a></li>
          <li><a data-test="author-name">K. L. Wilson</a></li>
        </ul>
        <ol class="c-article-author-affiliation__list">
          <li id="Aff1">
            <p class="c-article-author-affiliation__address">Editor Affiliation</p>
            <p class="c-article-author-affiliation__authors-list">
              Klaus Kubitzki, Volker Bittrich, Jens G. Rohwer
            </p>
          </li>
        </ol>
        <div id="editor-information-section">
          Editors and Affiliations
          Klaus Kubitzki
          Volker Bittrich
          Jens G. Rohwer
        </div>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "lxml")
    result = Springer(soup).parse()
    names = _names(result)
    assert names == ["L. A. S. Johnson", "K. L. Wilson"]


def test_short_author_list_recovers_corporate_author_when_no_primary_path():
    """Corporate chapter authors can appear only in the short author list,
    with no citation_author metadata or affiliation list."""
    html = """
    <html>
      <head>
        <link rel="canonical" href="https://link.springer.com/chapter/10.1007/example" />
      </head>
      <body>
        <ul class="c-article-author-list c-article-author-list--short">
          <li class="c-article-author-list__item">
            <a data-test="author-name">National Industrial Fuel Efficiency Service Ltd.</a>
          </li>
        </ul>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "lxml")
    result = Springer(soup).parse()
    names = _names(result)
    assert names == ["National Industrial Fuel Efficiency Service Ltd."]


# --- oxjob #1943: reference entries that name no author got the book's editors ---------------------------------

REFERENCE_ENTRY_EDITORS_ONLY = """
<html>
  <head>
    <link rel="canonical" href="https://link.springer.com/referenceworkentry/10.1007/978-1-4419-1005-9_100784" />
    <meta name="citation_inbook_title" content="Encyclopedia of Behavioral Medicine" />
    <meta name="citation_title" content="Heavy Episodic Drinking" />
  </head>
  <body>
    <section aria-labelledby="editor-information" data-title="Editor information">
      <div class="c-article-section" id="editor-information-section">
        <h2 id="editor-information">Editor information</h2>
        <div class="c-article-section__content" id="editor-information-content">
          <h3 class="c-article__sub-heading" id="editor-affiliations">Editors and Affiliations</h3>
          <ol class="c-article-author-affiliation__list">
            <li id="Aff1">
              <p class="c-article-author-affiliation__address">Behavioral Medicine Research Center, University of Miami, Miami, FL, USA</p>
              <p class="c-article-author-affiliation__authors-list">Marc D. Gellman</p>
            </li>
            <li id="Aff2">
              <p class="c-article-author-affiliation__address">Cardiovascular Safety, Quintiles, Durham, NC, USA</p>
              <p class="c-article-author-affiliation__authors-list">J. Rick Turner</p>
            </li>
          </ol>
        </div>
      </div>
    </section>
  </body>
</html>
"""


def test_reference_entry_with_only_an_editor_block_has_no_authors():
    """The editor block uses the author block's markup (<li id="Aff1">); the entry names no author, so it has none."""
    result = Springer(BeautifulSoup(REFERENCE_ENTRY_EDITORS_ONLY, "lxml")).parse()
    assert _names(result) == []


def test_reference_entry_author_block_kept_editor_block_ignored():
    html = REFERENCE_ENTRY_EDITORS_ONLY.replace(
        "<body>",
        """<body>
        <section data-title="Authors and Affiliations"><div id="author-information-section">
          <ol class="c-article-author-affiliation__list">
            <li id="Aff3">
              <p class="c-article-author-affiliation__address">School of Public Health, Boston, MA, USA</p>
              <p class="c-article-author-affiliation__authors-list">Jane Q. Writer</p>
            </li>
          </ol>
        </div></section>""",
    )
    result = Springer(BeautifulSoup(html, "lxml")).parse()
    assert _names(result) == ["Jane Q. Writer"]
    assert result["authors"][0]["affiliations"] == ["School of Public Health, Boston, MA, USA"]


OLD_TEMPLATE_EDITORS = """
<html>
  <head><link rel="canonical" href="https://link.springer.com/{kind}/10.1007/978-3-540-29676-8{suffix}" /></head>
  <body>
    <div id="editorsandaffiliations">
      <ul>
        <li itemprop="editor"><span>Florian Lang</span><ul data-role="AuthorsIndexes"><li>1</li></ul></li>
      </ul>
      <ol>
        <li class="affiliation" data-affiliation-highlight="affiliation-1">
          <span itemprop="name">University of Tuebingen</span>
        </li>
      </ol>
    </div>
  </body>
</html>
"""


def test_old_template_chapter_does_not_fall_back_to_editors():
    html = OLD_TEMPLATE_EDITORS.format(kind="referenceworkentry", suffix="_6092")
    assert _names(Springer(BeautifulSoup(html, "lxml")).parse()) == []


def test_old_template_whole_book_keeps_editor_fallback():
    html = OLD_TEMPLATE_EDITORS.format(kind="book", suffix="")
    assert _names(Springer(BeautifulSoup(html, "lxml")).parse()) == ["Florian Lang"]


def test_inverted_meta_names_take_the_byline_form():
    """Meta tags write "Last, First"; the byline shows the same people as "First Last"."""
    html = """
    <html>
      <head>
        <link rel="canonical" href="https://link.springer.com/chapter/10.1007/978-3-642-72386-5_8" />
        <meta name="citation_author" content="Makuuchi, Masatoshi" />
        <meta name="citation_author" content="Bandai, Yasutsugu" />
      </head>
      <body>
        <ul class="c-article-author-list">
          <li><a data-test="author-name">Masatoshi Makuuchi</a></li>
          <li><a data-test="author-name">Yasutsugu Bandai</a></li>
        </ul>
      </body>
    </html>
    """
    result = Springer(BeautifulSoup(html, "lxml")).parse()
    assert _names(result) == ["Masatoshi Makuuchi", "Yasutsugu Bandai"]
