from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.acs import ACS


def _acs_soup(body: str) -> BeautifulSoup:
    return BeautifulSoup(
        f"""
        <html>
          <head>
            <meta property="og:url" content="https://pubs.acs.org/doi/10.1021/cen-v073n035.p073" />
            <meta property="og:description" content="Short truncated metadata that should not win." />
          </head>
          <body>
            <ul class="loa">
              <li><div class="loa-info-name">C&amp;EN Staff</div></li>
            </ul>
            {body}
          </body>
        </html>
        """,
        "lxml",
    )


def test_cen_visible_abstract_box_beats_short_meta_description() -> None:
    soup = _acs_soup(
        """
        <h2 class="article_abstract-title">Abstract</h2>
        <div id="abstractBox" class="article_abstract-content hlFld-Abstract">
          The 25th ACS Northeast Regional Meeting (NERM 25) will be held in
          Rochester, N.Y., Oct. 21-25. The meeting, hosted by the ACS Rochester
          Section, will be held at the Rochester Convention Center.
        </div>
        """
    )

    out = ACS(soup).parse()

    assert out["abstract"].startswith("The 25th ACS Northeast Regional Meeting")
    assert "Short truncated metadata" not in out["abstract"]


def test_cen_short_visible_abstract_is_allowed() -> None:
    soup = _acs_soup(
        """
        <div id="abstractBox" class="article_abstract-content hlFld-Abstract">
          Classified Directory of Exhibitors' Products ...
        </div>
        """
    )

    assert ACS(soup).parse()["abstract"] == "Classified Directory of Exhibitors' Products ..."


def test_cen_abstract_cleans_space_before_punctuation() -> None:
    soup = _acs_soup(
        """
        <div id="abstractBox" class="article_abstract-content hlFld-Abstract">
          Employment sections that appeared within the print issues of C&amp;EN ,
          such as recruitment advertising for positions open.
        </div>
        """
    )

    assert "C&EN, such" in ACS(soup).parse()["abstract"]


def test_parse_page_dispatches_acs_cen_visible_abstract() -> None:
    html = str(
        _acs_soup(
            """
            <div id="abstractBox" class="article_abstract-content hlFld-Abstract">
              Full C&EN abstract from the visible ACS abstract box.
            </div>
            """
        )
    )

    out = parse_page(html, namespace="doi", resolved_url="https://doi.org/10.1021/cen-v073n035.p073")

    assert out["abstract"] == "Full C&EN abstract from the visible ACS abstract box."
