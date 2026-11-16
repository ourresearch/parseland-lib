"""
The work's own licence statement, wherever the page puts it; never one that is about something else
(oxjob #2239, phase 2, round 2).

39 confirmed dev pages: 29 where the re-parse dropped a licence the page states for the work, 10 where it wrote one the
page does not state. What decides is who the statement is about, read from where and how it is made:

- a RightsLink permissions link carries the licence of the article named in its contentID (Taylor & Francis prints it
  nowhere else on older pages; on a Wiley issue page the link belongs to one listed article);
- a footer the page names as the article's ("article-footer"), inside its <article>, is that article's own;
- a site footer that says "This is an open access article distributed under ..." speaks of the page's article;
  "This work is licensed under ..." in a footer is the site's own badge, and "All published work ..." or
  "<Journal> is licensed under ..." are left for a decision (the labels go both ways);
- a list of licence options, a code comment, a map's attribution and an image credit are not statements about the work.

Fragments mirror stored pages; no network.
"""
import pytest

from parseland_lib.legacy_parse_utils.pdf import find_normalized_license
from parseland_lib.legacy_parse_utils.version_and_license import license_search_text, page_potential_license_text
from parseland_lib.parse import parse_page

TRUSTED_URL = "https://journals.example.org/article/1"
CC_BY_LINK = '<a href="https://creativecommons.org/licenses/by/4.0/">Creative Commons Attribution 4.0 License</a>'


def searched_license(page, url=TRUSTED_URL):
    return find_normalized_license(license_search_text(page, url))


def page_of(body, head=""):
    return f"<html><head><title>t</title>{head}</head><body>{body}</body></html>"


# --- RightsLink permissions links: the licence of the article in contentID

TF_HEAD = '<meta name="dc.Identifier" scheme="doi" content="10.1080/13530194.2021.1916154"/>'


def rightslink(doi, oa, encoded=True):
    """Taylor & Francis writes the link's parameters URL-encoded twice; Wiley writes them once."""
    if encoded:
        oa_part = f"%26oa%3D{oa}" if oa else ""
        return ('<a class="reprints" href="/servlet/linkout?type=rightslinkReprints&amp;url=startPage%3D418%26'
                f'contentID%3D{doi.replace("/", "%252F")}%26numPages%3D15%26pa%3D{oa_part}%26issn%3D1353-0194">'
                'Order Reprints</a>')
    oa_part = f"oa={oa}%26" if oa else ""
    return (f'<a href="/servlet/linkout?type=rightslink&amp;url={oa_part}publisherName=Wiley%26publication=ACER%26'
            f'contentID={doi.replace("/", "%252F")}">Request permissions</a>')


@pytest.mark.parametrize("oa, expected", [("CC-BY-NC-ND", "cc-by-nc-nd"), ("CC-BY-NC", "cc-by-nc"), ("CC-BY", "cc-by")])
def test_rightslink_of_the_pages_own_article_states_its_licence(oa, expected):
    page = page_of(f"<main><h1>Methods in the madness?</h1>{rightslink('10.1080/13530194.2021.1916154', oa)}</main>",
                   TF_HEAD)
    assert searched_license(page) == expected
    assert parse_page(page, "doi", "https://www.tandfonline.com/doi/full/10.1080/13530194.2021.1916154")[
        "license"] == expected


def test_rightslink_title_naming_a_licence_is_not_the_licence():
    # the link also carries the article's title: only its oa= value is a statement
    link = rightslink("10.1080/13530194.2021.1916154", "CC-BY").replace(
        "%26numPages", "%26title%3DThe%2Bpublic%2Bdomain%2Band%2BCreative%2BCommons%2BAttribution-NonCommercial%26numPages")
    assert searched_license(page_of(link, TF_HEAD)) == "cc-by"
    other = link.replace("1916154", "1916155")
    assert searched_license(page_of(other, TF_HEAD)) is None


def test_rightslink_doi_match_ignores_case():
    page = page_of(rightslink("10.4161/MABS.26871", "CC-BY-NC"),
                   '<meta name="dc.Identifier" scheme="doi" content="10.4161/mabs.26871"/>')
    assert searched_license(page) == "cc-by-nc"


def test_rightslink_without_an_oa_parameter_states_nothing():
    page = page_of(rightslink("10.1080/13530194.2021.1916154", None), TF_HEAD)
    assert searched_license(page) is None
    assert page_potential_license_text(page) is page


def test_rightslink_of_a_listed_article_is_not_the_issues_licence():
    # Wiley issue page (doi 10.1111/acer.v45.2): one of twenty listed articles is open access
    listed = "".join(f"<div class='issue-item'>{rightslink(f'10.1111/acer.{n}', oa, encoded=False)}</div>"
                     for n, oa in [(14098, None), (14537, "CC-BY-NC-ND"), (14540, None)])
    page = page_of(f"<main>{listed}</main>", '<meta name="citation_doi" content="10.1111/acer.v45.2"/>')
    assert searched_license(page) is None
    assert parse_page(page, "doi", "https://onlinelibrary.wiley.com/toc/15300277/45/2")["license"] is None


def test_rightslink_on_a_page_that_names_no_doi_is_not_trusted():
    page = page_of(rightslink("10.1111/acer.14537", "CC-BY-NC-ND", encoded=False))
    assert searched_license(page) is None


def test_wiley_article_page_keeps_its_own_rightslink_licence():
    page = page_of(rightslink("10.1111/acer.14537", "CC-BY-NC-ND", encoded=False),
                   '<meta name="citation_doi" content="10.1111/acer.14537"/>')
    assert searched_license(page) == "cc-by-nc-nd"


# --- <article> ... <footer class="article-footer">: the article's own footer

ARTICLE_FOOTER = ('<footer class="article-footer"><div class="article__attribution"><div class="article__attribution-text">'
                  'This work is licensed under a <a class="article__attribution-link" '
                  'href="https://creativecommons.org/licenses/by-nc/4.0/">Creative Commons Attribution-NonCommercial '
                  '4.0 International License</a></div></div></footer>')


def test_article_footer_inside_its_article_keeps_its_licence():
    page = page_of(f'<main><article class="article-body"><h1>Title</h1><p>Text.</p>{ARTICLE_FOOTER}</article></main>'
                   '<footer><p>Journal office</p></footer>')
    assert searched_license(page) == "cc-by-nc"
    assert parse_page(page, "doi", TRUSTED_URL)["license"] == "cc-by-nc"


def test_site_footer_outside_main_is_still_cleared_when_main_has_its_own_footer():
    page = page_of(f'<main><article><h1>Title</h1><footer><p>Received 2 May.</p></footer></article></main>'
                   f'<footer><p>This work is licensed under a {CC_BY_LINK}.</p></footer>')
    assert searched_license(page) is None


def test_footer_named_for_the_article_but_outside_any_article_is_site_chrome():
    page = page_of(f'<div class="wrap"><h1>Title</h1><p>Text.</p></div>{ARTICLE_FOOTER}')
    assert searched_license(page) is None


@pytest.mark.parametrize("body", [
    # doi.org: the site's footer sits inside <main>, on its "not found" page even inside <main><article>
    '<main><div class="container"><h1>DOI Not Found</h1></div><footer><div class="col copyright"><p>Copyright © 2023 '
    f'DOI Foundation. The content of this site is licensed under a {CC_BY_LINK}.</p></div></footer></main>',
    '<main><div class="page-content"><article><h1>DOI Not Found</h1><div><footer><div class="col copyright"><p>'
    f'The content of this site is licensed under a {CC_BY_LINK}.</p></div></footer></div></article></div></main>',
    # an OJS theme: the site footer follows the closed <article>, still inside <main>
    '<main class="pkp_structure_main"><article><h1>Title</h1><p>Text.</p></article><footer class="footer" id="footer">'
    f'<p>This work is licensed under {CC_BY_LINK}</p></footer></main>',
    # an <article> that wraps the whole page is not inside <main>
    f'<article><main><h1>Title</h1></main><footer><p>This work is licensed under {CC_BY_LINK}</p></footer></article>',
])
def test_site_footer_inside_main_or_article_is_still_site_chrome(body):
    assert searched_license(page_of(body)) is None


# --- article-worded statements in site chrome

@pytest.mark.parametrize("statement, expected", [
    # jnthss.com (OJS footer)
    ('This is an open-access article distributed under the terms and conditions of the Creative Commons Attribution '
     '(CC BY) 4.0 International License (<a href="https://creativecommons.org/licenses/by/4.0/">'
     'https://creativecommons.org/licenses/by/4.0/</a>).', "cc-by"),
    # ijvm.ut.ac.ir
    ('Copyright The Author(s); This is an open access article distributed under the terms of the <a href="https://'
     'creativecommons.org/licenses/by-nc/4.0/deed.en">Creative Commons Attribution License (CC-By-NC)</a> , which '
     'permits use, distribution, and reproduction in any medium.', "cc-by-nc"),
    ('This article is licensed under a Creative Commons Attribution-ShareAlike 4.0 International License.', "cc-by-sa"),
    # journal.thebritishacademy.ac.uk
    ('This is an open access article licensed under a Creative Commons Attribution-NonCommercial-NoDerivs 4.0 '
     'International License.', "cc-by-nc-nd"),
])
@pytest.mark.parametrize("wrapper", [
    "<footer><p>Journal office, 1 Example Road</p><p>{}</p></footer>",
    '<div class="pkp_structure_footer_wrapper" role="contentinfo"><div class="pkp_footer_content"><p>{}</p></div></div>',
])
def test_footer_statement_about_the_articles_is_kept(statement, expected, wrapper):
    page = page_of("<main><h1>Title</h1><p>Abstract text.</p></main>" + wrapper.format(statement))
    assert searched_license(page) == expected
    assert parse_page(page, "doi", TRUSTED_URL)["license"] == expected


@pytest.mark.parametrize("statement", [
    # the Creative Commons chooser's badge text, pasted into site footers: the site is "this work"
    f'This work is licensed under a {CC_BY_LINK}.',
    f'Esta obra está bajo una {CC_BY_LINK}.',
    # journal-level and site-level statements: not decided here (gold labels them both ways)
    f'Journal of Examples is licensed under a {CC_BY_LINK}.',
    f'All Published work is licensed under a {CC_BY_LINK} Copyright © 2023 All rights reserved',
    f'Todos los artículos están licenciados bajo {CC_BY_LINK}.',
    f'The content of this site is licensed under a {CC_BY_LINK}.',
    f'Except where otherwise noted, all material on this site is licensed under a {CC_BY_LINK}.',
    # only some of the journal's articles (revistas.itm.edu.co, on a 2013 article's page)
    'The articles published in this journal after June 2018 are licensed under a Creative Commons '
    'Attribution-NonCommercial-ShareAlike 4.0 licence.',
    'All articles published before 2016 are licensed under a Creative Commons Attribution-NonCommercial 3.0 License.',
    # a condition, not a statement
    'If this article is published under a Creative Commons Attribution (CC BY) licence, you may reuse it freely.',
    # the phrase and the licence are different sentences
    f'Share this article. Contact us. Site content: {CC_BY_LINK}.',
    f'This is an open access article. The website is licensed under a {CC_BY_LINK}.',
])
def test_other_footer_statements_are_still_site_chrome(statement):
    page = page_of(f"<main><h1>Title</h1><p>Purchase this article.</p></main><footer><p>{statement}</p></footer>")
    assert searched_license(page) is None
    assert parse_page(page, "doi", TRUSTED_URL)["license"] is None


def test_kept_footer_statement_does_not_bring_the_rest_of_the_footer():
    statement = ('<p>This is an open access article distributed under the terms of the Creative Commons '
                 'Attribution-NonCommercial-NoDerivatives License.</p>')
    footer = f'<footer>{statement}<p>Website design: Example Studio, under the Elsevier user license</p></footer>'
    text = page_potential_license_text(page_of("<main><p>Text.</p></main>" + footer))
    assert "open access article" in text and "Example Studio" not in text and "Elsevier" not in text
    assert find_normalized_license(text) == "cc-by-nc-nd"
    # until round 5 a second Creative Commons licence in another block of the footer was dropped with the rest of
    # it; chrome that names two different licences now licenses nothing (charter § 6, 16 Nov 2026)
    footer = f'<footer>{statement}<p>Website design: Example Studio, {CC_BY_LINK}</p></footer>'
    text = page_potential_license_text(page_of("<main><p>Text.</p></main>" + footer))
    assert "open access article" not in text and find_normalized_license(text) is None


# --- not statements about the work

AGECON_ENUM = ('<script>var colDefs = [{"field_type": "string", "name": "rec_license", "visible": true, "enum": '
               '[{"name": "copyright", "label": "Copyrighted"}, {"name": "CC BY", "label": "CC BY (Creative Commons: '
               'Attribution)"}, {"name": "CC BY-NC-ND", "label": "CC BY-NC-ND (Creative Commons: Attribution-'
               'NonCommercial-No Derivatives)"}, {"name": "CC0", "label": "CC0 (No rights reserved)"}, {"name": '
               '"MIT License", "label": "MIT License"}]}]; var license = "LICENSE_VALUE";</script>')


def test_list_of_licence_options_is_not_a_statement():
    page = page_of(f'<main><h1>Record</h1><div id="record-files">{AGECON_ENUM.replace("LICENSE_VALUE", "")}</div></main>')
    assert searched_license(page) is None
    assert parse_page(page, "doi", None)["license"] is None
    assert parse_page(page, "pmh", None)["license"] is None


def test_licence_assigned_beside_the_options_list_still_counts():
    page = page_of(f'<main>{AGECON_ENUM.replace("LICENSE_VALUE", "CC BY-NC")}</main>')
    assert searched_license(page) == "cc-by-nc"


def test_code_comment_is_not_a_statement():
    # rosap.ntl.bts.gov, stacks.cdc.gov: the site's script, on every record
    page = page_of('<main><h1>Report</h1></main><script>\n  $(".page-view h1").text("Records");\r\n'
                   '  // Appends the Public Domain image\r\n  $(".col-12").addClass("mobile-hide");\n</script>')
    assert searched_license(page) is None


def test_licence_in_script_data_still_counts():
    page = page_of('<main><h1>T</h1></main><script>\n// page state\nvar authorizationData = {"licenseDetails": '
                   '{"is_open": true, "license_terms": {"description": "Creative Commons Attribution-NonCommercial-'
                   'NoDerivatives 4.0 International License (CC BY-NC-ND 4.0)"}}};</script>')
    assert searched_license(page) == "cc-by-nc-nd"


def test_map_attribution_does_not_swallow_the_next_elements_statement():
    page = page_of('<main><div class="leaflet-control-attribution">Map data © <a href="https://www.openstreetmap.org/">'
                   'OpenStreetMap</a> contributors, <a href="https://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA'
                   '</a></div><p>This article is published under the Creative Commons Attribution-NonCommercial 4.0 '
                   'licence.</p></main>')
    assert searched_license(page) == "cc-by-nc"


@pytest.mark.parametrize("site_footer", ["", "<footer><p>University Libraries</p></footer>"])
def test_map_attribution_is_the_maps_licence(site_footer):
    # digital.library.unt.edu record pages; with a footer to clear, the search text is the re-serialised tree, where
    # the script's markup is escaped
    page = page_of("<main><h1>Photograph</h1></main><script>aps.mapData.settings.attribution = 'Map data &copy; "
                   '<a href="https://www.openstreetmap.org/">OpenStreetMap</a> contributors <a href="https://'
                   "creativecommons.org/licenses/by-sa/2.0/\">CC-BY-SA</a>';\nvar next = 1;</script>" + site_footer)
    assert searched_license(page) is None


@pytest.mark.parametrize("credit", [
    # sciencetrends.com: schema.org ImageObject caption
    '<script type="application/ld+json">{"@type":"ImageObject","url":"https:\\/\\/example.org\\/g.png","caption":'
    '"Image by CSTAR via Wikipedia licensed under CC-BY-SA 3.0 https:\\/\\/creativecommons.org\\/licenses\\/by-sa\\/3.0\\/"}'
    '</script>',
    # eve.gd: the post's description
    '<meta name="description" content="Fees. Featured image by Katherine Lynn under a CC-BY-NC-ND license. Quoted in '
    'The Guardian today, the minister said so."/>',
    '<p><i>Featured image by <a href="http://www.flickr.com/photos/kgregory/">Katherine Lynn</a> under a CC-BY-NC-ND '
    'license.</i></p><p>Quoted in The Guardian today.</p>',
    '<p class="wp-caption-text">Photo by A. Reader, licensed under CC BY-SA 4.0</p>',
    # news.mongabay.com: an image's alt text
    '<img src="/original-768x512.jpg" alt="African baobab, Chikwawa district, Malawi. Image by Rob Palmer via '
    'iNaturalist (CC BY-NC-SA 4.0)."/>',
])
def test_image_credit_is_the_images_licence(credit):
    assert searched_license(page_of(f"<main><h1>Post</h1><p>Body text.</p>{credit}</main>")) is None


def test_licence_after_an_image_credit_sentence_still_counts():
    page = page_of("<main><p>Cover image by A. Reader. This article is published under the Creative Commons "
                   "Attribution 4.0 licence.</p></main>")
    assert searched_license(page) == "cc-by"


# --- "no known copyright restrictions" is a public-domain statement (Plazi, BHL)

def test_no_known_copyright_restrictions_is_public_domain():
    assert find_normalized_license("Copyright notice: No known copyright restrictions apply. See terms.") == "public-domain"
    page = page_of('<div class="panel-body"><p>No known copyright restrictions apply. See '
                   '<a href="/terms">Agosti et al.</a></p></div>')
    assert parse_page(page, "pmh", "http://publication.plazi.org/id/FFD2FFF7BA0FBD5C")["license"] == "public-domain"


def test_copyright_restrictions_that_do_apply_are_not_public_domain():
    assert find_normalized_license("Copyright restrictions apply to this item.") is None


# --- unchanged pages stay untouched

def test_page_with_nothing_to_drop_is_returned_untouched():
    page = page_of('<main><p>Body <a href="https://creativecommons.org/licenses/by/4.0/">CC BY</a></p></main>')
    assert page_potential_license_text(page) is page
