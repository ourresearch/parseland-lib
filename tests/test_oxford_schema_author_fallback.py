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
