from bs4 import BeautifulSoup

from parseland_lib.publisher.parsers.wiley import Wiley


AUTHOR_AFFILIATION_CLASS = """
<html>
  <head>
    <meta property="og:url" content="https://onlinelibrary.wiley.com/doi/10.1002/essoar.example" />
  </head>
  <body>
    <div class="loa-authors">
      <span class="accordion__closed">
        <a>Indhu Varatharajan</a>
        <div class="author-info">
          <div class="author-affiliation">Institute of Planetary Research, German Aerospace Center (DLR), Berlin, Germany</div>
          <div class="author-affiliation">Institute of Geological Sciences, Freie University (FU) Berlin, Germany</div>
        </div>
      </span>
      <span class="accordion__closed">
        <a>Claudia Stangarone</a>
        <div class="author-info">
          <div class="author-affiliation">Institute of Planetary Research, German Aerospace Center (DLR), Berlin, Germany</div>
        </div>
      </span>
    </div>
  </body>
</html>
"""


BR_SEPARATED_AFFILIATION = """
<html>
  <head>
    <meta property="og:url" content="https://onlinelibrary.wiley.com/doi/10.1111/br.example" />
  </head>
  <body>
    <div class="loa-authors">
      <span class="accordion__closed">
        <a>H. YILDIZ</a>
        <p>Food Engineering Department<br/>Faculty of Engineering<br/>Celal Bayar University<br/>45140 Muradiye, Manisa, Turkey</p>
      </span>
    </div>
  </body>
</html>
"""


CORRESPONDENCE_ADDRESS_ONLY = """
<html>
  <head>
    <meta property="og:url" content="https://onlinelibrary.wiley.com/doi/10.1111/address.example" />
  </head>
  <body>
    <div class="loa-authors">
      <span class="accordion__closed">
        <a>Andrew Stables</a>
        <p class="author-type">Corresponding Author</p>
        <p>Correspondence: Andrew Stables, 20 Bulkington, Devizes SN10 1SN, UK.</p>
        <p>Email: hidden@example.org</p>
      </span>
    </div>
  </body>
</html>
"""


def _authors(html: str):
    return Wiley(BeautifulSoup(html, "lxml")).parse()["authors"]


def test_author_affiliation_class_blocks_are_used() -> None:
    authors = _authors(AUTHOR_AFFILIATION_CLASS)

    assert authors[0].affiliations == [
        "Institute of Planetary Research, German Aerospace Center (DLR), Berlin, Germany",
        "Institute of Geological Sciences, Freie University (FU) Berlin, Germany",
    ]
    assert authors[1].affiliations == [
        "Institute of Planetary Research, German Aerospace Center (DLR), Berlin, Germany"
    ]


def test_br_separated_affiliation_keeps_spaces() -> None:
    authors = _authors(BR_SEPARATED_AFFILIATION)

    assert authors[0].affiliations == [
        "Food Engineering Department Faculty of Engineering Celal Bayar University 45140 Muradiye, Manisa, Turkey"
    ]


def test_correspondence_address_is_fallback_affiliation() -> None:
    authors = _authors(CORRESPONDENCE_ADDRESS_ONLY)

    assert authors[0].affiliations == ["20 Bulkington, Devizes SN10 1SN, UK"]
    assert authors[0].is_corresponding is True
