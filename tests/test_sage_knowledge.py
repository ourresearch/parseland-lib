from __future__ import annotations

from parseland_lib.parse import parse_page


def _wrap(body: str) -> str:
    return f"""
    <html>
      <head>
        <link rel="canonical"
              href="https://sk.sagepub.com/reference/example/n1.xml" />
      </head>
      <body>{body}</body>
    </html>
    """


def _names(parsed: dict) -> list[str]:
    return [author["name"] for author in parsed["authors"]]


def test_parse_page_dispatches_sage_knowledge_byline_authors() -> None:
    html = _wrap(
        """
        <div class="chapter-info">
          <h3>Romania</h3>
          <ul class="meta-list">
            <li><strong class="title">By:</strong>
              Emily Oros &amp; John Mark Froiland
            </li>
            <li><strong class="title">Edited by:</strong> James Ainsworth</li>
          </ul>
        </div>
        """
    )

    parsed = parse_page(
        html,
        namespace="doi",
        resolved_url="https://doi.org/10.4135/9781452276151.n344",
    )

    assert _names(parsed) == ["Emily Oros", "John Mark Froiland"]
    assert parsed["authors"][0]["affiliations"] == []
    assert parsed["authors"][0]["is_corresponding"] is None


def test_parse_page_dispatches_sage_knowledge_editor_when_no_byline() -> None:
    html = _wrap(
        """
        <div class="chapter-info">
          <h1>Ritual (communications)</h1>
          <ul class="meta-list">
            <li>
              <strong class="title">Edited by:</strong>
              <div class="tooltip-link-holder book-metadata-author">
                <a class="bioIDLink">Larry E. Sullivan</a>
              </div>
            </li>
          </ul>
        </div>
        """
    )

    parsed = parse_page(
        html,
        namespace="doi",
        resolved_url="https://doi.org/10.4135/9781412972024.n2214",
    )

    assert _names(parsed) == ["Larry E. Sullivan"]
