"""Accuracy loop phase 2, round 8, class authors-r8 (oxjob #2239): the record-page author fill (Dublin Core creators,
citation_authors lists, schema.org author items) writes one person per entry, only the item's own people, and no
labels or blanks. Markup cut from the check1 pages the judge confirmed worse."""
from parseland_lib.parse import parse_page

TITLE = '<meta name="DC.title" content="Anatomic study of the vascular perfusion of the sternum"/>'


def record(head, body="", ns="pmh"):
    html = f'<html><head><meta charset="utf-8"/>{head}</head><body>{body}</body></html>'
    return parse_page(html.encode(), ns, None)["authors"] or []


def creators(head, body=""):
    return [a["name"] for a in record(head, body)]


# --- one tag that lists several people ---

def test_vancouver_list_in_one_creator_tag_splits():
    assert creators(TITLE + '<meta name="DC.Creator" content="Erne B, Klemm W, Frese S, Van Voorhis WC, de Jesus RA"/>'
                    ) == ["Erne B", "Klemm W", "Frese S", "Van Voorhis WC", "de Jesus RA"]


def test_two_vancouver_names_in_citation_authors_split():
    assert creators('<meta name="citation_title" content="Cyclophosphamide"/>'
                    '<meta name="citation_authors" content="Nicol BM, Prasad SB"/>') == ["Nicol BM", "Prasad SB"]


def test_family_given_creators_are_not_vancouver_lists():
    # look-alikes: one "Family, Given" name per tag (Chinese repositories), a name with a suffix, a body with a country
    assert creators(TITLE + '<meta name="DC.creator" content="Tian, K"/><meta name="DC.creator" content="Zhao, XB"/>'
                    ) == ["Tian, K", "Zhao, XB"]
    assert creators(TITLE + '<meta name="DC.creator" content="Smith JA, Jr"/>') == ["Smith JA, Jr"]
    assert creators(TITLE + '<meta name="DC.creator" content="Stratagene Mxp, Stratagene Mx"/>') == [
        "Stratagene Mxp, Stratagene Mx"]


def test_ampersand_before_the_last_given_family_name_of_a_list_splits():
    assert creators('<meta name="citation_title" content="Acarofauna"/><meta name="citation_authors" content="Oscarina '
                    'da Silva Ezequiel; Gilberto Salles Gaz&#234;ta; Marinete Amorim &amp; Nicolau Mau&#233;s '
                    'Serra-Freire"/>') == ["Oscarina da Silva Ezequiel", "Gilberto Salles Gazêta", "Marinete Amorim",
                                           "Nicolau Maués Serra-Freire"]


def test_ampersand_outside_a_list_or_inside_a_body_stays():
    # look-alikes: one creator alone ("Food Science & Human Nutrition" could be a department), a company in a list
    assert creators(TITLE + '<meta name="DC.creator" content="Marinete Amorim &amp; Nicolau Serra"/>') == [
        "Marinete Amorim & Nicolau Serra"]
    assert creators(TITLE + '<meta name="DC.creator" content="Wang Y; Johnson &amp; Johnson"/>') == [
        "Wang Y", "Johnson & Johnson"]
    assert creators(TITLE + '<meta name="DC.creator" content="Wang Y; Marks &amp; Spencer Group"/>') == [
        "Wang Y", "Marks & Spencer Group"]


def test_citeseerx_list_with_an_unclosed_parenthesis_still_splits():
    head = ('<title>CiteSeerX — Development of 11 microsatellite loci</title>'
            '<meta name="citation_title" content="Development of 11 microsatellite loci"/>'
            '<meta name="citation_authors" content="Xiphias Gladius (teleostei Scombridae, Carol A. Reeb, '
            'Loretta Arcangeli, Barbara A. Block"/>')
    assert creators(head) == ["Xiphias Gladius (teleostei Scombridae", "Carol A. Reeb", "Loretta Arcangeli",
                              "Barbara A. Block"]


# --- entries that are not people ---

def test_reprint_address_with_an_ampersand_is_dropped_whole():
    assert creators(TITLE + '<meta name="DC.creator" content="Liu, P"/><meta name="DC.creator" content="Liu, P (reprint '
                    'author), Lanzhou Univ, State Key Lab Appl Organ Chem, Coll Chem &amp; Chem Engn, Lanzhou 730000, '
                    'Peoples R China."/>') == ["Liu, P"]


def test_et_al_is_not_an_author():
    assert creators(TITLE + '<meta name="DC.creator" content="Sist, Plinio"/><meta name="DC.creator" content="et al., "/>'
                    ) == ["Sist, Plinio"]


def test_dublin_core_block_of_the_site_home_page_credits_no_one():
    # Galiciana (DIGIBIB): the site's own DC block, the government body behind the portal as creator, on every record
    head = ('<meta name="DC.title" lang="gl" content="Galiciana: Biblioteca Dixital de Galicia"/>'
            '<meta name="DC.creator" lang="gl" content="Xunta de Galicia. Consellería de Cultura e Turismo"/>'
            '<meta name="DC.publisher" lang="es" content="DIGIBÍS"/>'
            '<meta name="DC.identifier" scheme="DCTERMS.URI" content="https://biblioteca.galiciana.gal/" />')
    assert creators(head) == []


def test_dublin_core_block_of_an_item_keeps_its_creators():
    # look-alike: an item's identifiers (its handle, its DOI) are not the site's home page
    head = (TITLE + '<meta name="DC.creator" content="Fernandes, Bruno"/>'
            '<meta name="DC.identifier" content="https://repo.example.org/handle/123/456"/>'
            '<meta name="DC.identifier" content="https://doi.org/10.1000/xyz"/>')
    assert creators(head) == ["Fernandes, Bruno"]


def test_blank_name_is_not_an_author():
    body = '<div class="authors">\t\t\t</div>'
    assert all(a["name"].strip() for a in record('<meta name="citation_title" content="X"/>', body, ns="doi"))


# --- schema.org author items ---

PERSON = '<span itemprop="author" itemscope itemtype="http://schema.org/Person">{}</span>'


def test_thesis_advisor_item_is_not_an_author():
    body = ('<div itemscope itemtype="http://schema.org/Thesis">'
            + PERSON.format('<a><span itemprop="name">Patberg, L.</span></a><span class="roleDsp"> (Author)</span>')
            + ' ; ' + PERSON.format('<a><span itemprop="name">Wallentowitz, H.</span></a>'
                                    '<span class="roleDsp"> (Thesis advisor)</span>') + '</div>')
    assert creators('', body) == ["Patberg, L."]


def test_author_items_of_related_posts_are_not_the_posts_authors():
    # hypotheses.org (WordPress): the post's byline, then the bylines of "related posts"
    by = '<p class="post-byline"><span class="vcard author"><span class="fn"><a itemprop="author" itemscope ' \
         'itemtype="https://schema.org/Person">{}</a></span></span></p>'
    body = ('<main><article class="post">' + by.format("Marlene Delhaye") + '</article>'
            '<ul class="related-posts group"><li class="related post-hover"><article class="post">'
            + by.format("Isabelle Gras") + '</article></li></ul></main>')
    assert creators('', body) == ["Marlene Delhaye"]


def test_slims_author_item_gives_the_linked_names_without_the_type_label():
    body = ('<div class="s-detail-author" itemprop="author" property="author" itemscope '
            'itemtype="http://schema.org/Person"><a href="?author=%22AFRENI%22&amp;search=Search">AFRENI</a>'
            ' - Nama Orang<br /><a href="?author=%22Budi+Santoso%22&amp;search=Search">Budi Santoso</a>'
            ' - Nama Orang<br /></div>')
    assert creators('<meta name="DC.title" content="Pengaturan alur laut"/><meta name="DC.creator" content="AFRENI; "/>',
                    body) == ["AFRENI", "Budi Santoso"]


# --- German Medical Science (egms.de) ---

GMS = ('<ul class="metaListOfAuthors"><li>\n<a class="link-noicon link-mail" href="/dynamic/en/contact-form.htm">'
       '<img alt="corresponding author" class="bulletpoint" src="/static/images/picto/author-with-mail-corresponding.png"'
       ' title="corresponding author"/> <span> Nick Spindler </span></a>\n\n - Department of Orthopedic Surgery, '
       'University Hospital Leipzig, Leipzig, Germany\n\n\t</li><li>\n<img alt="" class="bulletpoint" '
       'src="/static/images/picto/author-without-mail.png"/> <span> Wolfram LamadÃ© </span>\n\n - Robert '
       'Bosch Krankenhaus, Stuttgart, Deutschland\n\n\t</li></ul>')


def test_gms_byline_gives_full_names_affiliations_and_the_corresponding_mark():
    authors = record(TITLE + '<meta name="DC.Creator" content="Spindler N, LamadÃ© W"/>', GMS)
    assert [a["name"] for a in authors] == ["Nick Spindler", "Wolfram Lamadé"]
    assert [[x["name"] for x in a["affiliations"]] for a in authors] == [
        ["Department of Orthopedic Surgery, University Hospital Leipzig, Leipzig, Germany"],
        ["Robert Bosch Krankenhaus, Stuttgart, Deutschland"]]
    assert [a["is_corresponding"] for a in authors] == [True, False]


def test_gms_byline_with_no_mark_marks_no_one():
    authors = record(TITLE, GMS.replace('alt="corresponding author"', 'alt=""').replace(
        'title="corresponding author"', ''))
    assert [a["is_corresponding"] for a in authors] == [None, None]
