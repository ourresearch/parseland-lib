from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.thieme import Thieme


THIEME_HEAD = """
<meta name="citation_publisher" content="Thieme Medical Publishers">
<link rel="canonical" href="https://www.thieme-connect.de/products/ejournals/abstract/10.1055/example">
"""


def _soup(body, head=THIEME_HEAD):
    return BeautifulSoup(f"<html><head>{head}</head><body>{body}</body></html>", "lxml")


def test_thieme_citation_author_fallback_shares_unlabelled_affiliation():
    head = """
    <meta name="citation_publisher" content="Thieme">
    <meta name="citation_author" content="P. Toth Daru">
    <meta name="citation_author" content="E. Huszka">
    <link rel="canonical" href="https://www.thieme-connect.de/products/ejournals/abstract/10.1055/example">
    """
    body = """
    <div class="authors">P. Toth Daru, E. Huszka</div>
    <ul class="authorsAffiliationsList">
      <li>Department of Pediatric Surgery, Example University, Budapest</li>
    </ul>
    """

    parsed = Thieme(_soup(body, head=head)).parse()

    assert [author.name for author in parsed["authors"]] == ["P. Toth Daru", "E. Huszka"]
    assert parsed["authors"][0].affiliations == [
        "Department of Pediatric Surgery, Example University, Budapest"
    ]
    assert parsed["authors"][1].affiliations == parsed["authors"][0].affiliations


def test_thieme_labelled_affiliation_ids_do_not_mutate_soup():
    body = """
    <div class="authors">
      HC Tsay <a href="#AF1"><sup><b>1</b></sup></a>
      YF Chang <a href="#AF2"><sup><b>2</b></sup></a>
    </div>
    <ul class="authorsAffiliationsList">
      <li><sup><b>1</b></sup>Department of Neurology, First Hospital</li>
      <li><sup><b>2</b></sup>Department of Surgery, Second Hospital</li>
    </ul>
    """
    parser = Thieme(_soup(body))

    first = parser.parse()
    second = parser.parse()

    assert first["authors"][0].affiliations == ["Department of Neurology, First Hospital"]
    assert first["authors"][1].affiliations == ["Department of Surgery, Second Hospital"]
    assert second["authors"][0].affiliations == first["authors"][0].affiliations
    assert second["authors"][1].affiliations == first["authors"][1].affiliations


def test_thieme_collects_multiple_anchor_affiliation_refs():
    body = """
    <span class="authors">
      HC Tsay <a href="#AF1"><sup><b>1</b></sup></a><sup>,</sup><a href="#AF2"><sup><b>2</b></sup></a><sup>,</sup><a href="#AF3"><sup><b>3</b></sup></a>,
      Q Yuan <a href="#AF2"><sup><b>2</b></sup></a><sup>,</sup><a href="#AF3"><sup><b>3</b></sup></a>
      <div class="authorsAffiliationsList">
        <ul>
          <li><a name="AF1"></a><sup><b>1</b></sup>MicroRNA Group</li>
          <li><a name="AF2"></a><sup><b>2</b></sup>Gastroenterology Department</li>
          <li><a name="AF3"></a><sup><b>3</b></sup>TWINCORE</li>
        </ul>
      </div>
    </span>
    """

    parsed = Thieme(_soup(body)).parse()

    assert parsed["authors"][0].affiliations == [
        "MicroRNA Group",
        "Gastroenterology Department",
        "TWINCORE",
    ]
    assert parsed["authors"][1].affiliations == [
        "Gastroenterology Department",
        "TWINCORE",
    ]


def test_thieme_numeric_superscript_refs_use_visible_affiliation_list():
    body = """
    <span class="authors">
      M. Lorenzen<sup>1</sup>, C. H. Lund<sup>1</sup>, C. Beythien<sup>2</sup>
    </span>
    <div class="authorsAffiliationsList">
      <ul>
        <li>1 Abteilung Röntgendiagnostik, Universitätsklinikum Hamburg-Eppendorf</li>
        <li>2 Kardiologische Klinik, Universitätsklinikum Hamburg-Eppendorf</li>
      </ul>
    </div>
    """

    parsed = Thieme(_soup(body)).parse()

    assert [author.name for author in parsed["authors"]] == [
        "M. Lorenzen",
        "C. H. Lund",
        "C. Beythien",
    ]
    assert parsed["authors"][0].affiliations == [
        "Abteilung Röntgendiagnostik, Universitätsklinikum Hamburg-Eppendorf"
    ]
    assert parsed["authors"][2].affiliations == [
        "Kardiologische Klinik, Universitätsklinikum Hamburg-Eppendorf"
    ]


def test_thieme_embedded_author_spans_include_affiliations():
    body = """
    <span class="author">
      A. Bruderer
      <div class="affiliation">1 Abteilung für Nutztierchirurgie, Vetsuisse-Fakultät Zürich</div>,
    </span>
    <span class="author">
      S. De Brot
      <div class="affiliation">2 Institut für Veterinärpathologie der Vetsuisse-Fakultät Zürich</div>,
    </span>
    """

    parsed = Thieme(_soup(body)).parse()

    assert [author.name for author in parsed["authors"]] == ["A. Bruderer", "S. De Brot"]
    assert parsed["authors"][0].affiliations == [
        "Abteilung für Nutztierchirurgie, Vetsuisse-Fakultät Zürich"
    ]
    assert parsed["authors"][1].affiliations == [
        "Institut für Veterinärpathologie der Vetsuisse-Fakultät Zürich"
    ]


def test_thieme_embedded_author_spans_mark_corresponding_from_email_meta():
    head = """
    <meta name="citation_publisher" content="Thieme">
    <meta name="citation_author" content="Andreas E. May">
    <meta name="citation_author" content="Klaus T. Preissner">
    <meta name="citation_author_email" content="klaus.t.preissner@biochemie.example">
    """
    body = """
    <span class="author">
      <div class="name">Andreas E. May</div>
      <div class="affiliation">1 Deutsches Herzzentrum München</div>
    </span>
    <span class="author">
      <div class="name">Klaus T. Preissner</div>
      <div class="affiliation">2 Institut für Biochemie Giessen</div>
    </span>
    """

    parsed = Thieme(_soup(body, head=head)).parse()

    assert [author.is_corresponding for author in parsed["authors"]] == [False, True]


def test_thieme_dedupes_repeated_visible_author_with_same_affiliation():
    body = """
    <div class="authors">
      T Gomes <a href="#AF1"><sup><b>1</b></sup></a>,
      KW Karandagoda <a href="#AF2"><sup><b>2</b></sup></a>,
      KW Karandagoda <a href="#AF2"><sup><b>2</b></sup></a>,
      R Obeid <a href="#AF3"><sup><b>3</b></sup></a>
    </div>
    <ul class="authorsAffiliationsList">
      <li><sup><b>1</b></sup>First Clinic</li>
      <li><sup><b>2</b></sup>Castle Street Hospital</li>
      <li><sup><b>3</b></sup>Central Laboratory</li>
    </ul>
    """

    parsed = Thieme(_soup(body)).parse()

    assert [author.name for author in parsed["authors"]] == [
        "T Gomes",
        "KW Karandagoda",
        "R Obeid",
    ]
    assert parsed["authors"][1].affiliations == ["Castle Street Hospital"]


def test_thieme_star_footnote_byline_uses_citation_author_split():
    head = """
    <meta name="citation_publisher" content="Thieme">
    <meta name="citation_author" content="Toshimasa Katagiri">
    <meta name="citation_author" content="Fumihiro Obara">
    <meta name="citation_author" content="Sanae Toda">
    <meta name="citation_author" content="Keizo Furuhashi">
    """
    body = """
    <div class="authors">Toshimasa Katagiri<sup>*</sup>, Fumihiro Obara, Sanae Toda, Keizo Furuhashi</div>
    <ul class="authorsAffiliationsList">
      <li>Pharmaceuticals and Biotechnology Laboratory</li>
    </ul>
    """

    parsed = Thieme(_soup(body, head=head)).parse()

    assert [author.name for author in parsed["authors"]] == [
        "Toshimasa Katagiri",
        "Fumihiro Obara",
        "Sanae Toda",
        "Keizo Furuhashi",
    ]
    assert parsed["authors"][0].affiliations == ["Pharmaceuticals and Biotechnology Laboratory"]


def test_thieme_abstract_uses_visible_abstract_and_drops_boilerplate():
    body = """
    <div id="abstract">
      PDF Download Buy Article Permissions and Reprints
      Zusammenfassung Dieses Kapitel beschreibt die wichtigsten klinischen Merkmale.
      Abstract This English abstract should not replace the German abstract.
      Key words sample words
    </div>
    """

    abstract = Thieme(_soup(body)).parse_abstract()

    assert abstract == "Dieses Kapitel beschreibt die wichtigsten klinischen Merkmale."


def test_thieme_citation_abstract_cleans_html_fragment():
    head = """
    <meta name="citation_publisher" content="Thieme">
    <meta name="citation_author" content="A. Researcher">
    <meta name="citation_abstract" content="&lt;p&gt;Abstract This is a long Thieme abstract with inline markup and enough text to pass the parser threshold.&lt;/p&gt;">
    """

    parsed = Thieme(_soup("", head=head)).parse()

    assert parsed["authors"][0].name == "A. Researcher"
    assert parsed["abstract"] == (
        "This is a long Thieme abstract with inline markup and enough text "
        "to pass the parser threshold."
    )


def test_parse_page_dispatches_thieme_from_citation_publisher():
    head = """
    <meta name="description" content="Article landing page">
    <meta name="citation_publisher" content="Georg Thieme Verlag">
    <meta name="citation_author" content="A. Researcher">
    <meta name="citation_abstract" content="This citation abstract is long enough for the Thieme parser to keep from metadata.">
    """

    parsed = parse_page(str(_soup("", head=head)), "doi", "https://doi.org/10.1055/example")

    assert parsed["authors"][0]["name"] == "A. Researcher"
    assert parsed["abstract"].startswith("This citation abstract")


def test_parse_page_dispatches_thieme_visible_abstract_without_authors():
    head = """
    <meta name="description" content="Thieme E-Books & E-Journals">
    <link rel="canonical" href="https://www.thieme-connect.de/products/ejournals/abstract/10.1055/example">
    """
    body = """
    <div id="abstract">
      Buy Article (opens in new window) Permissions and Reprints (opens in new window)
      Die Aortenisthmusstenose ist eine isolierte Enge der Aorta
      in unmittelbarer Nachbarschaft zum Ductus arteriosus und hat eine relevante
      Inzidenz bei Neugeborenen.
    </div>
    """

    parsed = parse_page(str(_soup(body, head=head)), "doi", "https://doi.org/10.1055/example")

    assert parsed["authors"] == []
    assert parsed["abstract"].startswith("Die Aortenisthmusstenose")
