from bs4 import BeautifulSoup

from parseland_lib.publisher.parsers.ssrn import SSRN


def test_ssrn_marks_nonfirst_contact_author_with_middle_initials():
    html = """
    <html>
      <head>
        <link rel="canonical" href="https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4398349">
      </head>
      <body>
        <div class="authors">
          <h2>Marco Ceccarelli</h2>
          <p>Maastricht University - Department of Finance</p>
          <h2>Christoph Herpfer</h2>
          <p>Emory University - Goizueta Business School</p>
          <h2>Steven Ongena</h2>
          <p>University of Zurich - Department of Banking and Finance</p>
        </div>
        <div class="author">
          <h3>Marco Ceccarelli</h3>
          <p>Maastricht University - Department of Finance</p>
        </div>
        <div class="author">
          <h3>Christoph Herpfer</h3>
          <p>Emory University - Goizueta Business School</p>
        </div>
        <div class="author">
          <h3>Steven R. G. Ongena (Contact Author)</h3>
          <p>University of Zurich - Department of Banking and Finance</p>
        </div>
        <div class="abstract-text">
          <p>This is a sufficiently specific SSRN abstract fixture.</p>
        </div>
      </body>
    </html>
    """

    parser = SSRN(BeautifulSoup(html, "lxml"))
    parsed = parser.parse()

    assert [author.name for author in parsed["authors"]] == [
        "Marco Ceccarelli",
        "Christoph Herpfer",
        "Steven Ongena",
    ]
    assert [author.is_corresponding for author in parsed["authors"]] == [
        False,
        False,
        True,
    ]
