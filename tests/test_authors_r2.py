"""Accuracy loop phase 2, class authors-r2 (oxjob #2239): the record-page creator fill returns people who wrote the
item (not the site, not two people in one entry), and a publisher page's citation_author tags settle its byline's
order and its group author. Markup cut from the class's dev pages."""
from bs4 import BeautifulSoup

from parseland_lib.parse import _add_byline_groups, _in_tag_order, _unmangled, dublin_core_authors, parse_page

TITLE = '<meta name="DC.title" content="Modeling Ammonothermal Growth of GaN Single Crystals"/>'


def creators(head, body=""):
    """The fill's names for a record page with this <head> and <body> content."""
    html = f'<html><head><meta charset="utf-8"/>{head}</head><body>{body}</body></html>'
    return [a["name"] for a in parse_page(html.encode(), "pmh", None)["authors"]]


def named(*names):
    return [{"name": n, "affiliations": [], "is_corresponding": None} for n in names]


# --- creator tags that describe the site, not the item ---

def test_creator_without_a_title_tag_is_the_site():
    # the German National Library's URN resolver: its developer, on every page
    assert creators('<title>URN:NBN Resolver für Deutschland und Schweiz</title>'
                    '<meta name="author" content="Kadir Karaca Koçer"/><meta name="DC.creator" content="Kadir Karaca Koçer"/>'
                    '<meta name="DC.publisher" content="German National Library"/>') == []


def test_creator_that_equals_the_author_tag_stays_when_the_page_has_its_title():
    # look-alike: OpenEdition and PANGAEA repeat the item's author in the generic author tag
    assert creators('<meta name="author" content="Fernandes, Bruno"/><meta name="DC.creator" content="Fernandes, Bruno"/>'
                    '<meta name="DC.title" content="Itô Mika: The Imaginal Moulting"/>') == ["Fernandes, Bruno"]


def test_creator_that_repeats_a_title_tag_is_the_site():
    # a Chinese Academy of Sciences repository's log-in wall
    assert creators('<meta name="DCTERMS.title" content="中国科学院半导体研究所机构知识库"/>'
                    '<meta name="DCTERMS.creator" content="中国科学院半导体研究所机构知识库"/>'
                    '<meta name="DCTERMS.contributor" content="Zhu Zhongming,Lu Linong,Yao Xiaona,etc"/>') == []


def test_item_creators_stay_beside_the_site_tags_and_the_reprint_address_goes():
    # the same repository's item page: DC.creator holds the people, then Web of Science's reprint address
    assert creators('<meta name="DCTERMS.title" content="中国科学院力学研究所机构知识库"/>'
                    '<meta name="DCTERMS.creator" content="中国科学院力学研究所机构知识库"/>' + TITLE +
                    '<meta name="DC.creator" content="Pendurti S"/><meta name="DC.creator" content="陈启生"/>'
                    '<meta name="DC.creator" content="Prasad V"/><meta name="DC.creator" content="Pendurti, S (reprint '
                    'author), Florida Int Univ, Dept Engn Mech, EAS 2710,10555 W Flagler St, Miami, FL 33199 USA."/>'
                    ) == ["Pendurti S", "陈启生", "Prasad V"]


def test_libguides_creator_is_the_librarian_not_an_author():
    assert creators('<meta name="DC.Title" content="LibGuides: The André Savine Collection: About"/>'
                    '<meta name="DC.Creator" content="Kirill Tolpygo"/>'
                    '<meta name="DC.Publishers" content="University of North Carolina at Chapel Hill"/>') == []


def test_government_bodies_in_french_and_spanish_are_not_people():
    assert creators('<meta name="dcterms.title" content="Constricted hydrodynamic flow"/><meta name="dcterms.creator" '
                    'content="Gouvernement du Canada. Conseil national de recherches Canada"/>') == []
    # stored as UTF-8 read as Latin-1: "ConsejerÃ\xada" is "Consejería"
    assert creators('<meta name="DC.Title" content="CDAEA Elektra"/>'
                    '<meta name="DC.Creator" content="CDAEA AAIICC ConsejerÃ\xada de Cultura"/>') == []


def test_one_word_alone_is_the_platform():
    assert creators(TITLE + '<meta name="DC.creator" content="Artstor"/>') == []


def test_one_word_names_that_stay():
    # look-alikes: a one-word name among other authors, and a name in a script written without spaces
    assert creators(TITLE + '<meta name="DC.creator" content="Cheshta"/><meta name="DC.creator" content="Dutt, Suneel"/>'
                    ) == ["Cheshta", "Dutt, Suneel"]
    assert creators(TITLE + '<meta name="DC.creator" content="王劭夫"/>') == ["王劭夫"]


# --- one entry per person ---

def test_empty_creator_rows_are_not_names():
    head = TITLE + "".join(f'<meta name="eprints.creators_name" content="{n}"/>'
                           for n in ("Mukai, T", "Tomasella, M", "Parlikad, AKN", ", "))
    assert creators(head) == ["Mukai, T", "Tomasella, M", "Parlikad, AKN"]


def test_semicolons_split_a_creator_tag():
    assert creators(TITLE + '<meta name="DC.creator" content="Huang, JH; Yang, CY; Ho, ZY"/>') == [
        "Huang, JH", "Yang, CY", "Ho, ZY"]


def test_semicolon_inside_parentheses_is_part_of_one_name():
    # look-alike: the French National Library's authority form
    assert creators(TITLE + '<meta name="DC.creator" content="Roux, Antoine (19..-.... ; pédagogue). Réalisateur"/>') == [
        "Roux, Antoine (19..-.... ; pédagogue). Réalisateur"]


def test_the_same_people_in_two_scripts_are_listed_once():
    assert creators(TITLE + '<meta name="DC.creator" content="王一中;陳培哲"/>'
                    '<meta name="DC.creator" content="WANG, I-JONG;CHEN, PEI-JER"/>'
                    '<meta name="citation_authors" content="WANG, I-JONG;CHEN, PEI-JER"/>') == [
        "WANG, I-JONG", "CHEN, PEI-JER"]
    assert creators(TITLE + '<meta name="DC.creator" content="Fouskas, Vasilios"/>'
                    '<meta name="DC.creator" content="Φούσκας,  Βασίλειος"/>'
                    '<meta name="citation_authors" content="Φούσκας,  Βασίλειος"/>') == ["Φούσκας,  Βασίλειος"]


def test_creator_tags_win_when_citation_authors_is_not_part_of_them():
    # look-alike: the same person written two ways, one per tag family
    assert creators(TITLE + '<meta name="DC.creator" content="Saimir Beqiraj"/>'
                    '<meta name="citation_authors" content="Beqiraj, Saimir"/>') == ["Saimir Beqiraj"]


def test_ampersand_between_two_family_given_names_splits():
    assert creators('<meta name="citation_title" content="Orofacial rehabilitation"/><meta name="citation_authors" '
                    'content="Guttal, K. S.; Rao, C. B.; Nadiger, R. K. &amp; Guttal, S. S."/>') == [
        "Guttal, K. S.", "Rao, C. B.", "Nadiger, R. K.", "Guttal, S. S."]
    assert creators('<meta name="citation_title" content="X"/>'
                    '<meta name="citation_authors" content="Lahariya, C. &amp; Baveja, U.K."/>') == [
        "Lahariya, C.", "Baveja, U.K."]


def test_ampersand_inside_one_name_stays():
    assert creators(TITLE + '<meta name="DC.creator" content="Johnson &amp; Johnson Pharmaceutical Research"/>') == [
        "Johnson & Johnson Pharmaceutical Research"]


def test_citeseerx_lists_its_authors_with_commas():
    head = ('<title>CiteSeerX — Insulin Receptor-Associated Proteins:</title><meta name="citation_title" content="Insulin"/>'
            '<meta name="citation_authors" content="Stratagene Mxp, Stratagene Mx"/>')
    assert creators(head) == ["Stratagene Mxp", "Stratagene Mx"]


def test_comma_lists_elsewhere():
    # one "Family, Given" name stays whole; three or more full names can't be one person
    assert creators('<meta name="citation_title" content="X"/>'
                    '<meta name="citation_authors" content="Nogueira, Pedro Henrique Pedrosa"/>') == [
        "Nogueira, Pedro Henrique Pedrosa"]
    assert creators('<meta name="citation_title" content="X"/>'
                    '<meta name="citation_authors" content="A. Coccoli, A. Bondavalli, L. Simoncini"/>') == [
        "A. Coccoli", "A. Bondavalli", "L. Simoncini"]
    assert creators('<meta name="citation_title" content="X"/>'
                    '<meta name="citation_authors" content="King, Martin Luther, Jr."/>') == ["King, Martin Luther, Jr."]


def test_two_people_with_the_same_initials_stay_two():
    assert creators('<meta name="citation_title" content="X"/>'
                    '<meta name="citation_authors" content="Wang Y;Chen H;Wang Y; ;"/>') == ["Wang Y", "Chen H", "Wang Y"]


def test_names_stored_in_the_wrong_encoding_come_back_as_the_page_has_them():
    # look-alike: Figshare pages are stored that way and labelled as they read; only the people test reads through it
    assert creators('<meta name="DataCite.title" content="X"/><meta property="og:site_name" content="figshare"/>'
                    '<meta name="DataCite.contributor" content="FrangeÅ¾, Å½iva"/>') == ["FrangeÅ¾, Å½iva"]


def test_text_stored_in_the_wrong_encoding_is_put_right():
    assert _unmangled("DomÃ©nigg") == "Doménigg"
    assert _unmangled("H.Â\xa0P. Hye") == "H.\xa0P. Hye"
    assert _unmangled("Doménigg") == "Doménigg"  # already right
    assert _unmangled("SÃ£o Paulo – Ã") == "SÃ£o Paulo – Ã"  # not such bytes from end to end: left alone


# --- the site's own byline ---

PUBMED_AUTHOR = ('<span class="authors-list-item "><a class="full-name" href="/?term=x">{}</a>'
                 '<sup class="affiliation-links"><a class="affiliation-link" title="Columbia University">1</a></sup>'
                 '<span class="comma">,&nbsp;</span></span>')


def test_pubmed_byline_gives_full_names_and_the_group_author():
    byline = ('<div class="inline-authors"><div class="authors"><div class="authors-list">'
              + PUBMED_AUTHOR.format("Anthony C Sciscione") + PUBMED_AUTHOR.format("George A Macones")
              + '<span class="authors-list-item "><a class="full-name" href="/?term=x%5BCorporate+Author%5D">Maternal-Fetal '
                'Medicine Units (MFMU) Network, Bethesda, Maryland</a></span></div></div></div>')
    head = ('<link rel="canonical" href="https://pubmed.ncbi.nlm.nih.gov/41712929/"/><meta name="citation_title" '
            'content="Activity Restriction in Pregnancy"/><meta name="citation_authors" content="Sciscione AC;Macones GA; ;"/>')
    # the page prints its byline twice (full view, then the short view)
    assert creators(head, byline + byline) == [
        "Anthony C Sciscione", "George A Macones", "Maternal-Fetal Medicine Units (MFMU) Network, Bethesda, Maryland"]
    assert creators(head) == ["Sciscione AC", "Macones GA"]  # no byline in the page: the tag, as before


LEXICON_HEAD = ('<meta name="DC.Title" content="Taaffe, Eduard Franz Joseph Gf."/><meta name="DC.Creator" content="Ã\x96'
                'sterreichisches Biographisches Lexikon und biographische Dokumentation"/>')


def test_lexicon_entry_is_signed_by_its_author():
    assert creators(LEXICON_HEAD, '<div id="autor" class="autor">(H.Â\xa0P. Hye)\nÂ\xa0Â\xa0</div>'
                                  '<div class="autor">Zuletzt aktualisiert: 15.12.2020</div>') == ["H.\xa0P. Hye".replace("\xa0", " ")]


def test_unsigned_lexicon_entry_credits_no_one():
    assert creators(LEXICON_HEAD, '<div id="Lieferung" class="lieferung">PUBLIKATION: ÖBL 1815-1950</div>') == []


NRC_PERSON = ('<span class="citation_author"><span itemprop="author" itemtype="https://schema.org/Person" '
              'itemscope="itemscope"><span itemprop="name">{}</span></span></span>')


def test_schema_org_person_items_are_the_authors():
    head = ('<meta name="dcterms.title" content="Constricted hydrodynamic flow"/><meta name="dcterms.creator" '
            'content="Government of Canada. National Research Council Canada"/>')
    body = f'<table><tr><th>Author</th><td>{NRC_PERSON.format("Shih, L. Y.")}; {NRC_PERSON.format("Zheng, Y.")}</td></tr></table>'
    assert creators(head, body) == ["Shih, L. Y.", "Zheng, Y."]


def test_author_items_of_several_works_are_not_one_byline():
    work = '<div itemscope itemtype="https://schema.org/ScholarlyArticle">{}</div>'
    body = work.format(NRC_PERSON.format("Shih, L. Y.")) + work.format(NRC_PERSON.format("Zheng, Y."))
    assert creators("", body) == []


def test_untyped_author_items_are_not_read():
    # a blog template's <meta itemprop="author" content="admin">, GitHub's <span itemprop="author"> user name
    assert creators("", '<meta itemprop="author" content="admin"/><span itemprop="author"><a rel="author">biesro</a></span>') == []


# --- publisher pages: the citation_author tags are the byline ---

def test_authors_grouped_by_affiliation_take_the_tag_order():
    parsed = named("Lin Chen", "Peng Zhang", "Guangyu Shi", "Su Yang", "Shiguang Qin")
    tags = ["Chen, Lin", "Shi, Guangyu", "Qin, Shiguang", "Yang, Su", "Zhang, Peng"]
    assert [a["name"] for a in _in_tag_order(parsed, tags)] == [
        "Lin Chen", "Guangyu Shi", "Shiguang Qin", "Su Yang", "Peng Zhang"]


def test_tag_order_reaches_names_printed_with_degrees():
    parsed = named("Thomas J. Altree FRACP", "Danny J. Eckert PhD", "Ronald R. Grunstein FRACP, PhD")
    tags = ["Altree, Thomas J.", "Grunstein, Ronald R.", "Eckert, Danny J."]
    assert [a["name"] for a in _in_tag_order(parsed, tags)] == [
        "Thomas J. Altree FRACP", "Ronald R. Grunstein FRACP, PhD", "Danny J. Eckert PhD"]


def test_tag_order_matches_the_exact_name_before_a_looser_one():
    # 'Wei Li' and 'Wei Min Li' share first and last name: each goes to its own tag
    parsed = named("Wei Min Li", "Wei Li", "Ana Roy")
    assert [a["name"] for a in _in_tag_order(parsed, ["Roy, Ana", "Li, Wei", "Li, Wei Min"])] == [
        "Ana Roy", "Wei Li", "Wei Min Li"]


def test_order_is_kept_when_the_tags_name_other_people():
    parsed = named("Lin Chen", "Peng Zhang", "Guangyu Shi")
    assert _in_tag_order(parsed, ["Chen, Lin", "Shi, Guangyu"]) is parsed  # a tag short
    assert _in_tag_order(parsed, ["Chen, Lin", "Shi, Guangyu", "Qin, Shiguang"]) is parsed  # another person
    assert _in_tag_order(parsed, ["Chen, Lin", "Shi, Guangyu", "Chen, Lin"]) is parsed  # one person twice


def test_affiliation_grouped_springer_byline_comes_out_in_tag_order():
    html = """<html><head><link rel="canonical" href="https://link.springer.com/article/10.1007/s00376-010-9210-4"/>
    <meta name="citation_author" content="Chen, Lin"/><meta name="citation_author" content="Shi, Guangyu"/>
    <meta name="citation_author" content="Zhang, Peng"/></head><body>
    <ol class="c-article-author-affiliation__list"><li id="Aff1"><p class="c-article-author-affiliation__address">National
    Satellite Meteorological Center, Beijing, China</p><p class="c-article-author-affiliation__authors-list">Lin Chen
    &amp; Peng Zhang</p></li><li id="Aff2"><p class="c-article-author-affiliation__address">Institute of Atmospheric
    Physics, Beijing, China</p><p class="c-article-author-affiliation__authors-list">Guangyu Shi</p></li></ol>
    </body></html>"""
    out = parse_page(html.encode(), "doi", "https://link.springer.com/article/10.1007/s00376-010-9210-4")
    assert [a["name"] for a in out["authors"]] == ["Lin Chen", "Guangyu Shi", "Peng Zhang"]
    assert out["authors"][2]["affiliations"][0]["name"].startswith("National")  # each author keeps their own


SILVERCHAIR_BYLINE = """<div class="al-authors-list"><div class="al-author-name"><a class="linked-name">M Proietti</a></div>
<div class="al-author-name"><a class="linked-name-byline">G Y H Lip</a><span class="al-author-by">{}</span></div></div>"""


def test_tag_order_is_not_a_rule_for_other_sites():
    # look-alike: a publisher page with no Springer Nature affiliation list keeps its parser's order (Juniper
    # Publishers' tags are scrambled; its own tests hold the byline order)
    html = """<html><head><meta property="og:url" content="https://dtb.bmj.com/content/1/1/1"/>
    <meta name="citation_author" content="Bo Kim"/><meta name="citation_author" content="Ann Lee"/></head><body>
    <ol class="contributor-list"><li><span class="name">Ann Lee</span></li><li><span class="name">Bo Kim</span></li>
    </ol></body></html>"""
    out = parse_page(html.encode(), "doi", "https://dtb.bmj.com/content/1/1/1")
    assert [a["name"] for a in out["authors"]] == ["Ann Lee", "Bo Kim"]


def test_silverchair_group_author_without_a_card_comes_back():
    soup = BeautifulSoup(SILVERCHAIR_BYLINE.format("WARCEF Investigators"), "lxml")
    authors = _add_byline_groups(named("M Proietti", "G Y H Lip"), soup, ["Proietti, M", "Lip, G Y H", "WARCEF Investigators"])
    assert [a["name"] for a in authors] == ["M Proietti", "G Y H Lip", "WARCEF Investigators"]


def test_tag_names_the_byline_does_not_print_are_not_added():
    # a study group's members are in the tags, not in the byline
    soup = BeautifulSoup(SILVERCHAIR_BYLINE.format("for the ALFA Study"), "lxml")
    authors = _add_byline_groups(named("M Proietti", "G Y H Lip"), soup, ["Proietti, M", "Lip, G Y H", "Brugulat-Serrat, Anna"])
    assert [a["name"] for a in authors] == ["M Proietti", "G Y H Lip"]


BMJ_PAGE = """<html><head><meta property="og:url" content="https://dtb.bmj.com/content/s1-1/15/58"/>
<meta name="DC.Publisher" content="British Medical Journal Publishing Group"/>
<meta name="DC.Contributor" content="{0}"/><meta name="citation_title" content="Muscle relaxants - I"/>
<script>window.dataLayer = window.dataLayer || []; window.dataLayer.push({{"content":{{"hwAuthors":"",
"hwContributors":"{0}","hwCorpusCode":"dtb"}}}});</script></head><body></body></html>"""


def test_bmj_page_that_credits_no_one_does_not_get_its_publisher():
    for publisher in ("BMJ Publishing Group Ltd", "British Medical Journal Publishing Group"):
        assert parse_page(BMJ_PAGE.format(publisher).encode(), "doi", "https://dtb.bmj.com/content/s1-1/15/58")["authors"] == []


def test_bmj_contributors_who_are_people_stay():
    out = parse_page(BMJ_PAGE.format("J. Smith, A. Jones").encode(), "doi", "https://dtb.bmj.com/content/s1-1/15/58")
    assert [a["name"] for a in out["authors"]] == ["J. Smith", "A. Jones"]


def test_dublin_core_authors_still_reads_plain_creator_tags():
    html = '<html><head>' + TITLE + '<meta name="DC.creator" content="Lovelace, Ada"/></head><body></body></html>'
    assert dublin_core_authors(BeautifulSoup(html, "lxml")) == named("Lovelace, Ada")
