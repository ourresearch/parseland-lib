from bs4 import BeautifulSoup

from parseland_lib.elements import AuthorAffiliations
from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.oxford import Oxford


def _parser(html: str) -> Oxford:
    return Oxford(BeautifulSoup(html, "lxml"))


def test_oxford_product_domain_dispatches_from_canonical() -> None:
    html = """
    <html><head>
      <link rel="canonical" href="https://www.oxfordscholarlyeditions.com/display/10.1093/foo/bar" />
    </head><body></body></html>
    """
    assert _parser(html).is_publisher_specific_parser() is True


def test_oxford_trove_and_research_domains_dispatch_from_canonical() -> None:
    for host in (
        "www.oxfordbusinesstrove.com",
        "www.oxfordlawtrove.com",
        "oxfordre.com",
    ):
        html = f"""
        <html><head>
          <link rel="canonical" href="https://{host}/display/10.1093/foo/bar" />
        </head><body></body></html>
        """
        assert _parser(html).is_publisher_specific_parser() is True


def test_schema_org_author_meta_fallback_when_byline_dom_absent() -> None:
    html = """
    <html><head>
      <link rel="canonical" href="https://www.oxfordscholarlyeditions.com/display/10.1093/foo/bar" />
      <meta property="http://schema.org/author" content="John Dryden" />
      <meta property="http://schema.org/author" content="John Milton" />
    </head><body></body></html>
    """
    result = _parser(html).parse()
    assert result["authors"] == [
        AuthorAffiliations(
            name="John Dryden",
            affiliations=[],
            is_corresponding=None,
        ),
        AuthorAffiliations(
            name="John Milton",
            affiliations=[],
            is_corresponding=None,
        ),
    ]


def test_article_byline_dom_still_wins_over_meta_fallback() -> None:
    html = """
    <html><head>
      <link rel="canonical" href="https://academic.oup.com/journal/article/1" />
      <meta property="http://schema.org/author" content="Metadata Author" />
    </head><body>
      <div class="at-ArticleAuthors">
        <div class="info-card-author">
          <div class="info-card-name">Visible Author</div>
        </div>
      </div>
    </body></html>
    """
    result = _parser(html).parse()
    assert [author.name for author in result["authors"]] == ["Visible Author"]


def test_article_card_free_text_affiliation_and_clean_name() -> None:
    html = """
    <html><head>
      <link rel="canonical" href="https://academic.oup.com/carcin/article/35/2/365/2462982" />
    </head><body>
      <div class="at-ArticleAuthors">
        <div class="info-card-author">
          <div class="info-card-name">Sarah C. Forester</div>
          Search for other works by this author on: Oxford Academic PubMed Google Scholar
        </div>
        <div class="info-card-author">
          <div class="info-card-name">Joshua D. Lambert *</div>
          *To whom correspondence should be addressed.
          Department of Food Science, The Pennsylvania State University,
          332 Food Science Building, University Park, PA 16802, USA.
          Tel: +1 814-865-5223 ; Fax: +1 814-863-6132 ;
          Email: jdl134@psu.edu
          Search for other works by this author on: Oxford Academic PubMed Google Scholar
        </div>
      </div>
    </body></html>
    """
    result = _parser(html).parse()
    assert result["authors"][1] == AuthorAffiliations(
        name="Joshua D. Lambert",
        affiliations=[
            "Department of Food Science, The Pennsylvania State University, "
            "332 Food Science Building, University Park, PA 16802, USA"
        ],
        is_corresponding=False,
    )
    assert result["authors"][0].affiliations == []


def test_structured_single_affiliation_is_shared_across_article_cards() -> None:
    html = """
    <html><head>
      <link rel="canonical" href="https://academic.oup.com/jac/article/11/3/281/784072" />
    </head><body>
      <div class="at-ArticleAuthors">
        <div class="info-card-author">
          <div class="info-card-name">D.J. Platt</div>
          Correspondence: Dr D. J. Platt, Dept. of Bacteriology,
          Glasgow Royal Infirmary, Glasgow, G4 0SF, Scotland.
        </div>
        <div class="info-card-author">
          <div class="info-card-name">A.J. Guthrie</div>
        </div>
        <div class="info-card-author">
          <div class="info-card-name">C.F. Langan</div>
          <div class="info-card-affilitation">
            <div class="aff">*General Pratice, Royal Infirmary</div>
          </div>
        </div>
      </div>
    </body></html>
    """
    result = _parser(html).parse()
    assert [author.affiliations for author in result["authors"]] == [
        ["General Pratice, Royal Infirmary"],
        ["General Pratice, Royal Infirmary"],
        ["General Pratice, Royal Infirmary"],
    ]


def test_structured_affiliation_block_keeps_non_university_affiliation() -> None:
    html = """
    <html><head>
      <link rel="canonical" href="https://academic.oup.com/ajcn/article/74/3/409/4737411" />
    </head><body>
      <section class="abstract"><p>Full Oxford abstract text is preserved.</p></section>
      <div class="at-ArticleAuthors">
        <div class="info-card-author">
          <div class="info-card-name">Undurti N Das</div>
          <div class="info-author-correspondence">E-mail: author@example.org</div>
          <div class="info-card-affilitation">
            <div class="aff">1 EFA Sciences LLC, 1420 Providence Highway, Suite 266,
            Norwood, MA 02062</div>
          </div>
        </div>
      </div>
    </body></html>
    """
    result = _parser(html).parse()
    assert result["abstract"] == "Full Oxford abstract text is preserved."
    assert result["authors"] == [
        AuthorAffiliations(
            name="Undurti N Das",
            affiliations=[
                "EFA Sciences LLC, 1420 Providence Highway, Suite 266, "
                "Norwood, MA 02062"
            ],
            is_corresponding=True,
        )
    ]


def test_product_popover_author_bios_supply_affiliations() -> None:
    html = """
    <html><head>
      <link rel="canonical" href="https://www.oxfordlawtrove.com/view/10.1093/he/foo" />
      <meta name="citation_author" content="John Stanton" />
      <meta name="citation_author" content="Craig Prescott" />
    </head><body>
      <ul class="creatorInfo">
        <li data-role="author">
          <span class="popoverButton">John Stanton</span>
          <span class="popoverContainer">
            <span class="popoverAuthorBio">
              Senior Lecturer in Law, The City Law School, City, University of London
            </span>
          </span>
        </li>
        <li data-role="author">
          <span class="popoverButton">Craig Prescott</span>
          <span class="popoverContainer">
            <span class="popoverAuthorBio">Lecturer in Law, Bangor University</span>
          </span>
        </li>
      </ul>
    </body></html>
    """
    result = _parser(html).parse()
    assert result["authors"] == [
        AuthorAffiliations(
            name="John Stanton",
            affiliations=[
                "Senior Lecturer in Law, The City Law School, City, University of London"
            ],
            is_corresponding=None,
        ),
        AuthorAffiliations(
            name="Craig Prescott",
            affiliations=["Lecturer in Law, Bangor University"],
            is_corresponding=None,
        ),
    ]


def test_citation_title_author_affiliation_fallback() -> None:
    html = """
    <html><head>
      <link rel="canonical" href="https://oxford.universitypressscholarship.com/view/10.1093/oso/foo" />
      <meta name="citation_title" content="The Environmental Justice Imperative:
        Patrick N. Breysse, PhD, National Center for Environmental Health/Agency for
        Toxic Substances and Disease Registry, Centers for Disease Control and Prevention
        Robert Bullard, PhD, Distinguished Professor, Dean, Barbara Jordan-Mickey
        Leland School of Public Affairs, Texas Southern University
        Elizabeth Sawin, PhD, Co-Founder and Co-Director, Climate Interactive" />
    </head><body></body></html>
    """
    result = _parser(html).parse()
    assert result["authors"] == [
        AuthorAffiliations(
            name="Patrick N. Breysse",
            affiliations=[
                "National Center for Environmental Health/Agency for Toxic Substances "
                "and Disease Registry, Centers for Disease Control and Prevention"
            ],
            is_corresponding=None,
        ),
        AuthorAffiliations(
            name="Robert Bullard",
            affiliations=[
                "Barbara Jordan-Mickey Leland School of Public Affairs, "
                "Texas Southern University"
            ],
            is_corresponding=None,
        ),
        AuthorAffiliations(
            name="Elizabeth Sawin",
            affiliations=["Climate Interactive"],
            is_corresponding=None,
        ),
    ]


def test_parse_page_uses_oxford_schema_author_fallback() -> None:
    html = """
    <html><head>
      <link rel="canonical" href="https://www.oxforddnb.com/display/10.1093/odnb/entry" />
      <meta property="http://schema.org/author" content="P. G. Walker" />
    </head><body>
      <p>No article byline DOM on this product page.</p>
    </body></html>
    """
    result = parse_page(html, namespace="doi", resolved_url="https://doi.org/10.1093/odnb/example")
    assert [author["name"] for author in result["authors"]] == ["P. G. Walker"]
