"""Institutional-repository site blurbs must not become abstracts (oxjob #23518).

WEKO / JAIRO Cloud record pages emit no ``citation_abstract`` and repeat the
repository's own site description in ``og:description`` and ``description`` on
every record. Before the fix that blurb became the abstract for 48,180 University
of Tokyo works, and 42,928 of them were then assigned topics derived from it.
"""

from bs4 import BeautifulSoup

from parseland_lib.publisher.parsers.generic import GenericPublisherParser


UTOKYO_BLURB = (
    "UTokyo Repositoryは本学で生産されたさまざまな学術成果を電子的形態で集中的に蓄積・保存し、"
    "世界に発信することを目的としたインターネット上の発信拠点です。"
    "The UTokyo Repository is the system to store and provide digital resources "
    "created by members of the University of Tokyo, including journal articles, "
    "theses, bulletins and other research outputs, and to make them openly "
    "available to the world through the internet."
)

WEKO_RECORD_HTML = f"""
<html><head>
  <meta name="citation_title" content="地震のマグニチュードと頻度の関係式について" />
  <meta name="citation_publisher" content="東京大学" />
  <meta property="og:description" content="{UTOKYO_BLURB}" />
  <meta name="description" content="{UTOKYO_BLURB}" />
</head><body></body></html>
"""


def test_generic_parser_rejects_repository_site_blurb():
    parsed = GenericPublisherParser(BeautifulSoup(WEKO_RECORD_HTML, "lxml")).parse()
    assert parsed["abstract"] is None, (
        "generic parser must not use og:description/description as an abstract; "
        f"got {parsed['abstract']!r}"
    )


def test_generic_parser_still_uses_article_level_meta():
    """citation_abstract and dc.description stay trusted on the generic path."""
    real = (
        "本研究では、地震のマグニチュードと発生頻度の関係を再検討し、"
        "グーテンベルク・リヒター則の適用限界について定量的な評価を行った。"
        "観測データに基づく解析の結果、従来の推定値には系統的な偏りが認められ、"
        "特に浅発地震において顕著であることが明らかとなった。"
        "本手法は他地域への適用も可能であり、地震活動の長期評価に資すると考えられる。"
        "さらに、余震活動の減衰過程についても改良大森公式を用いた解析を行い、"
        "本震規模との相関を検討した。得られた知見は地震ハザード評価の精度向上に"
        "寄与するものであり、今後の防災計画立案において有用な基礎資料となる。"
    )
    html = f"""
    <html><head>
      <meta name="citation_abstract" content="{real}" />
      <meta property="og:description" content="{UTOKYO_BLURB}" />
    </head><body></body></html>
    """
    parsed = GenericPublisherParser(BeautifulSoup(html, "lxml")).parse()
    assert parsed["abstract"] == real


def test_publisher_parsers_keep_seo_tag_fallback():
    """Default behaviour is unchanged for the ~20 publisher parsers that opt in."""
    long_desc = "This is a genuine article abstract supplied via og:description. " * 5
    html = f'<html><head><meta property="og:description" content="{long_desc}" /></head></html>'
    parser = GenericPublisherParser(BeautifulSoup(html, "lxml"))
    # default (what the ~20 publisher parsers call) still accepts SEO tags
    assert parser.parse_abstract_meta_tags() == long_desc.strip()
    # opted-out path (what generic.py now calls) does not
    assert parser.parse_abstract_meta_tags(include_seo_tags=False) is None
