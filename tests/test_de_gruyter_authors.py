"""De Gruyter / De Gruyter Brill author regressions (oxjob #1808).

The degruyterbrill.com template (2023 on) wraps each contributor in ``span.contributor-dgb`` inside
``li.contributors-<ROLE>``; affiliations and the corresponding author's e-mail sit in attributes of a
``<contributor-popdown>`` element, not in visible text. The parser only knew the older ``span.contributor``
markup, fell back to the citation meta tags and lost every affiliation and corresponding mark.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from parseland_lib.publisher.parsers.de_gruyter import DeGruyter

HEAD = """
<head>
  <meta property="og:url" content="https://www.degruyterbrill.com/document/doi/10.1515/ncrs-2025-0504/html" />
  <meta name="citation_author" content="Min Lu" />
  <meta name="citation_author" content="Tiantian Li" />
</head>
"""


def _dgb_li(role, people):
    spans = []
    for name, email, affs in people:
        spans.append(f"""
        <span class="contributor-dgb">
          <span class="displayName">{name}</span>
          <contributor-popdown name="{name}" position="1" email="{email}" affiliations="{affs}">
          </contributor-popdown>
          {f'<a href="mailto:{email}"><img alt="EMAIL logo" src="/mail.svg"/></a>' if email else ''}
        </span><span class="comma">, </span>""")
    return f'<li class="contributors-{role}">{"".join(spans)}</li>'


def test_degruyterbrill_template_reads_affiliations_and_corresponding_mark():
    body = _dgb_li("AUTHOR", [
        ("Min Lu", "", "School of Pharmacy, Guizhou University of Traditional Chinese Medicine, Guiyang, 550025, China"),
        ("Tiantian Li", "525708251@qq.com", "School of Pharmacy, Guizhou University; Second Institute, Guiyang"),
    ])
    soup = BeautifulSoup(f'<html>{HEAD}<body><ul class="contributors-dgb">{body}</ul></body></html>', "lxml")
    parser = DeGruyter(soup)

    assert parser.authors_found()
    assert parser.parse_authors() == [
        {"name": "Min Lu", "is_corresponding": False,
         "affiliations": ["School of Pharmacy, Guizhou University of Traditional Chinese Medicine, Guiyang, 550025, China"]},
        {"name": "Tiantian Li", "is_corresponding": True,
         "affiliations": ["School of Pharmacy, Guizhou University", "Second Institute, Guiyang"]},
    ]


def test_degruyterbrill_template_editors_are_not_authors():
    body = _dgb_li("EDITOR", [("Ann Editor", "", "Some University")])
    soup = BeautifulSoup(f'<html><head></head><body><ul class="contributors-dgb">{body}</ul></body></html>', "lxml")

    assert DeGruyter(soup).parse_authors() == []


def test_old_degruyter_template_unchanged():
    html = """
    <html><body><span class="contributor">
      <span class="displayName linkAnimation">S. Kaur</span>
      <contributor-popdown name="S. Kaur" position="1" email=""
        affiliations="Apollo Center for Advanced Pediatrics, Indraprastha Apollo Hospital, New Delhi, India">
      </contributor-popdown>
    </span></body></html>
    """
    authors = DeGruyter(BeautifulSoup(html, "lxml")).parse_authors()

    assert authors == [{"name": "S. Kaur", "is_corresponding": False,
                        "affiliations": ["Apollo Center for Advanced Pediatrics, Indraprastha Apollo Hospital, New Delhi, India"]}]
