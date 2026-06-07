from bs4 import BeautifulSoup

from parseland_lib.publisher.parsers.mdpi import MDPI


def test_mdpi_single_author_defaults_to_corresponding():
    html = """
    <html>
      <head>
        <meta property="og:url" content="https://www.mdpi.com/2673-6497/2/2/15" />
      </head>
      <body>
        <div class="art-authors">
          <span class="inlineblock"><a>Mulugeta Wayu</a><sup></sup></span>
        </div>
      </body>
    </html>
    """

    out = MDPI(BeautifulSoup(html, "lxml")).parse()

    assert out["authors"][0].name == "Mulugeta Wayu"
    assert out["authors"][0].is_corresponding is True
