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


def test_ssrn_drops_independent_no_affiliation_placeholder():
    html = """
    <html>
      <head>
        <link rel="canonical" href="https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4891740">
      </head>
      <body>
        <div class="authors">
          <h2>Razieh Sadat Neyband</h2>
          <p>Independent - affiliation not provided to SSRN</p>
          <h2>Mohammad Almasi</h2>
          <p>affiliation not provided to SSRN</p>
        </div>
      </body>
    </html>
    """

    parser = SSRN(BeautifulSoup(html, "lxml"))
    parsed = parser.parse()

    assert [author.name for author in parsed["authors"]] == [
        "Razieh Sadat Neyband",
        "Mohammad Almasi",
    ]
    assert [author.affiliations for author in parsed["authors"]] == [[], []]


def test_ssrn_uses_detail_blocks_for_long_affiliations():
    html = """
    <html>
      <head>
        <link rel="canonical" href="https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1156271">
      </head>
      <body>
        <div class="authors">
          <h2>Albert Sole-Olle</h2>
          <p>University of Barcelona; CESifo (Center for Economic Studies and Ifo Institute)</p>
          <h2>Pilar Sorribas-Navarro</h2>
          <p>University of Barcelona - Faculty of Economic Science and Business Studies</p>
        </div>
        <div class="author">
          <h3>Albert Sole-Olle (Contact Author)</h3>
          <div class="block-quote">
            <h4>University of Barcelona (email)</h4>
            <p><span>Gran Via de les Corts Catalanes, 585<br>Barcelona, 08007<br>Spain</span></p>
          </div>
        </div>
        <div class="author">
          <div class="block-quote">
            <h4>CESifo (Center for Economic Studies and Ifo Institute)</h4>
            <p><span>Poschinger Str. 5<br>Munich, DE-81679<br>Germany</span></p>
          </div>
        </div>
        <div class="author">
          <h3>Pilar Sorribas-Navarro</h3>
          <div class="block-quote">
            <h4>University of Barcelona - Faculty of Economic Science and Business Studies (email)</h4>
            <p><span>Barcelona<br>Spain</span></p>
          </div>
        </div>
      </body>
    </html>
    """

    parser = SSRN(BeautifulSoup(html, "lxml"))
    parsed = parser.parse()

    assert parsed["authors"][0].affiliations == [
        "University of Barcelona, Gran Via de les Corts Catalanes, 585, Barcelona, 08007, Spain",
        "CESifo (Center for Economic Studies and Ifo Institute), Poschinger Str. 5, Munich, DE-81679, Germany",
    ]
    assert parsed["authors"][1].affiliations == [
        "University of Barcelona - Faculty of Economic Science and Business Studies, Barcelona, Spain"
    ]


def test_ssrn_detail_blocks_do_not_duplicate_same_name_affiliations():
    html = """
    <html>
      <head>
        <link rel="canonical" href="https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4905313">
      </head>
      <body>
        <div class="authors">
          <h2>Liang Yu</h2>
          <p>Chongqing University</p>
          <h2>Liang Yu</h2>
          <p>Chongqing University</p>
        </div>
        <div class="author">
          <h3>Liang Yu</h3>
          <div class="block-quote">
            <h4>Chongqing University</h4>
          </div>
        </div>
        <div class="author">
          <h3>Liang Yu</h3>
          <div class="block-quote">
            <h4>Chongqing University</h4>
          </div>
        </div>
      </body>
    </html>
    """

    parser = SSRN(BeautifulSoup(html, "lxml"))
    parsed = parser.parse()

    assert [author.affiliations for author in parsed["authors"]] == [
        ["Chongqing University"],
        ["Chongqing University"],
    ]


def test_ssrn_detail_blocks_do_not_share_same_last_initial_names():
    html = """
    <html>
      <head>
        <link rel="canonical" href="https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4389166">
      </head>
      <body>
        <div class="authors">
          <h2>Yulin Li</h2>
          <p>Capital Medical University - Beijing Anzhen Hospital</p>
          <h2>Yang Li</h2>
          <p>Capital Medical University - Beijing Anzhen Hospital</p>
          <h2>Yingkai Li</h2>
          <p>Capital Medical University - Beijing Anzhen Hospital</p>
        </div>
        <div class="author">
          <h3>Yulin Li</h3>
          <div class="block-quote">
            <h4>Capital Medical University - Beijing Anzhen Hospital</h4>
          </div>
        </div>
        <div class="author">
          <h3>Yang Li</h3>
          <div class="block-quote">
            <h4>Capital Medical University - Beijing Anzhen Hospital</h4>
          </div>
        </div>
        <div class="author">
          <h3>Yingkai Li</h3>
          <div class="block-quote">
            <h4>Capital Medical University - Beijing Anzhen Hospital</h4>
          </div>
        </div>
      </body>
    </html>
    """

    parser = SSRN(BeautifulSoup(html, "lxml"))
    parsed = parser.parse()

    assert [author.affiliations for author in parsed["authors"]] == [
        ["Capital Medical University - Beijing Anzhen Hospital"],
        ["Capital Medical University - Beijing Anzhen Hospital"],
        ["Capital Medical University - Beijing Anzhen Hospital"],
    ]
