"""Abstracts on Open Journal Systems (OJS) article pages (oxjob #2267).

Markup is cut down from stored OJS pages (15 Nov 2026, #2267 EXPLORE § 1). When an OJS page's meta tags hold no
abstract, the page still prints one in the theme's own block: OJS 3 `section.item.abstract`, OJS 2
`div#articleAbstract`, or a custom theme's "Abstract" heading in the article column (omniscient.sg). The generic heading
reader skipped them, because OJS 3 wraps the article column in `pkp_structure_content has_sidebar`.
"""
from parseland_lib.parse import parse_page

URL = "https://journals.example.org/index.php/j/article/view/134515"
GENERATOR = '<meta name="generator" content="Open Journal Systems 3.3.0.16"/>'
TEXT = ("Engineering curriculum often fails to connect content and decisions to impacts on diverse communities. We "
        "provide resources in the form of a workshop that teaches faculty how to bring social justice into problems.")
ZH = ("农村公路桥梁病害影响通行安全与使用寿命。本文分析农村公路桥梁主要病害，涵盖上部、下部及附属结构，探讨设计、施工、运营与环境层面"
      "核心成因。提出日常养护措施，为提升农村公路桥梁养护水平提供理论支持。")


def _page(main, generator=GENERATOR, head=""):
    return (f'<html><head>{generator}<meta name="citation_author" content="Alexis N. Prybutok"/>'
            f'<meta name="citation_title" content="A title"/>{head}</head>'
            f'<body class="pkp_page_article"><div class="pkp_structure_page"><header class="pkp_structure_head">'
            f'<nav class="pkp_navigation_primary_wrapper"><ul><li><a href="/search">Abstract</a></li></ul></nav></header>'
            f'<div class="pkp_structure_content has_sidebar"><div class="pkp_structure_main" role="main">'
            f'<article class="obj_article_details"><div class="main_entry">{main}</div></article></div>'
            f'<div class="pkp_structure_sidebar" role="complementary"><div class="pkp_block block_x"><h2>Abstract</h2>'
            f'<p>{TEXT.replace("Engineering", "Sidebar")}</p></div></div></div></div></body></html>')


def _abstract(html):
    return parse_page(html.encode(), "doi", URL)["abstract"]


def test_ojs3_item_abstract_section():
    main = f'<section class="item abstract"><h2 class="label">Abstract</h2><p>{TEXT}</p></section>'
    assert _abstract(_page(main)) == TEXT


def test_ojs2_article_abstract_div():
    main = f'<div id="articleAbstract"><h4>Abstract</h4><br /><div>{TEXT}</div><br /></div>'
    assert _abstract(_page(main, generator='<meta name="generator" content="Open Journal Systems 2.4.8.0"/>')) == TEXT


def test_custom_theme_heading_in_article_column():
    # omniscient.sg: h4.art_h4 under an unclosed site header; a Chinese abstract
    main = (f'<div class="Article_the"><h4 class="art_h4">Abstract</h4><p><p>{ZH}</p></p>'
            f'<h4 class="art_h4">Keywords</h4><span>农村公路桥梁</span></div>')
    assert _abstract(_page(main)) == ZH


def test_meta_tag_abstract_still_wins():
    head = f'<meta name="DC.Description" xml:lang="en" content="{TEXT.replace("Engineering", "Meta")}"/>'
    main = f'<section class="item abstract"><h2 class="label">Resumen</h2><p>{TEXT}</p></section>'
    assert _abstract(_page(main, head=head)).startswith("Meta curriculum")


def test_english_version_first():
    main = (f'<section class="item abstract"><h2 class="label">Resumen</h2><p>{TEXT.replace("Engineering", "Spanish")}'
            f'</p><h2 class="label">Abstract</h2><p>{TEXT}</p></section>')
    assert _abstract(_page(main)) == TEXT


def test_placeholders_and_lists_are_not_abstracts():
    assert _abstract(_page('<div id="articleAbstract"><h4>Abstract</h4><br /><div>.</div></div>')) is None
    assert _abstract(_page('<section class="item abstract"><h2 class="label">Abstract</h2><div>Not available</div>'
                           '</section>')) is None
    titles = "".join(f"<li>TITLE NUMBER {i} OF A CONGRESS ABSTRACT BOOK IN COLOMBIA</li>" for i in range(6))
    assert _abstract(_page(f'<div class="item abstract"><h3 class="label">Resumen</h3><ul>{titles}</ul></div>')) is None


def test_custom_theme_rights_box_is_not_an_abstract():
    # a tab panel titled "Abstract" that shows only the rights box (no sentence end)
    main = ('<div class="ap-tab-panel"><h2 class="ap-panel-title">Abstract</h2><div class="ap-rights">Rights and '
            'Permissions Open Access © 2025 Science Press All rights reserved · Permission required for reuse of '
            'this material</div></div>')
    assert _abstract(_page(main)) is None


def test_open_monograph_press_synopsis_is_left_alone():
    main = f'<div class="item abstract"><h2 class="label"> Synopsis </h2><div class="value"><p>{TEXT}</p></div></div>'
    assert _abstract(_page(main, generator='<meta name="generator" content="Open Monograph Press 3.4.0.9"/>')) is None


def test_not_an_ojs_page_is_not_claimed():
    main = f'<section class="item abstract"><h2 class="label">Abstract</h2><p>{TEXT}</p></section>'
    html = _page(main, generator="").replace("pkp_", "site_")
    assert _abstract(html) is None
