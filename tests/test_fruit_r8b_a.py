"""Three existing misses of 100K+ works each, found on the practice draws' random pages (oxjob #2239, round 8b).

1. arXiv abstract pages link their licence (div.abs-license -> arxiv.org/licenses/nonexclusive-distrib/1.0/, or
   .../assumed-1991-2003/ for 1991-2003 papers). The licence table's arXiv keys ("arxiv.orgperpetual",
   "arxiv.orgnonexclusive") match only the licence's name in words, never its link, so the link read as no licence.
2. ACS: older ("non-JATS") pages mark the corresponding author only by a '*' in the dc.Creator tag ("K. N.  Houk*"),
   explained by the page's '*' footnote; some list the author under an "Author Information" -> "Corresponding Author"
   heading with no mark in the byline.
3. DergiPark: record pages (OAI-PMH ids) are read by the repository parser, which kept no mark; the 2025 template
   marks the corresponding author by the name link's title "Sorumlu Yazar" and a '*'.
Markup cut down from stored pages of the dev and check1 draws (18 Nov 2026).
"""
from bs4 import BeautifulSoup

from parseland_lib.legacy_parse_utils.pdf import find_normalized_license
from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.acs import ACS


# --- 1. arXiv licence links -------------------------------------------------------------------------------------

def _arxiv(licence_div):
    return (
        '<html><head><title>[1201.6343] A title</title>'
        '<meta name="citation_title" content="A title" /><meta name="citation_author" content="Arinkin, Dima" />'
        '<meta name="citation_pdf_url" content="http://arxiv.org/pdf/1201.6343" />'
        '<link rel="canonical" href="https://arxiv.org/abs/1201.6343v4" />'
        '<meta property="og:url" content="https://arxiv.org/abs/1201.6343v4" />'
        '</head><body><div id="abs"><h1 class="title">A title</h1>'
        '<blockquote class="abstract">We study a thing. ' + "It is studied at length here. " * 8 + '</blockquote>'
        '</div><div class="extra-services"><div class="full-text"><ul><li><a href="/pdf/1201.6343v4" '
        'class="abs-button download-pdf">View PDF</a></li></ul></div>' + licence_div + '</div>'
        '<footer><a href="https://info.arxiv.org/help/license/index.html">Copyright</a></footer></body></html>')


NONEXCLUSIVE = ('<div class="abs-license"><a href="http://arxiv.org/licenses/nonexclusive-distrib/1.0/" '
                'title="Rights to this article">view license</a></div>')
ASSUMED = ('<div class="abs-license"><a href="http://arxiv.org/licenses/assumed-1991-2003/" '
           'title="Rights to this article">view license</a></div>')
CC_BY_NC_SA = ('<div class="abs-license"><a href="http://creativecommons.org/licenses/by-nc-sa/4.0/" '
               'title="Rights to this article" class="has_license"><img alt="license icon" role="presentation" '
               'src="https://arxiv.org/icons/licenses/by-nc-sa-4.0.png"/><span>view license</span></a></div>')


def test_arxiv_nonexclusive_licence_link_is_publisher_specific():
    assert find_normalized_license("http://arxiv.org/licenses/nonexclusive-distrib/1.0/") == "publisher-specific-oa"
    assert find_normalized_license("https://arxiv.org/licenses/nonexclusive-distrib/1.0/") == "publisher-specific-oa"


def test_arxiv_assumed_1991_2003_licence_link_is_publisher_specific():
    assert find_normalized_license("http://arxiv.org/licenses/assumed-1991-2003/") == "publisher-specific-oa"


def test_arxiv_licence_name_in_words_still_reads():
    assert find_normalized_license("arXiv.org perpetual, non-exclusive license") == "publisher-specific-oa"


def test_arxiv_page_licence_link_reads_on_the_page():
    out = parse_page(_arxiv(NONEXCLUSIVE).encode(), "doi", None)
    assert out["license"] == "publisher-specific-oa"
    out = parse_page(_arxiv(ASSUMED).encode(), "doi", "https://arxiv.org/abs/astro-ph/9907445")
    assert out["license"] == "publisher-specific-oa"


def test_arxiv_page_creative_commons_link_unchanged():
    out = parse_page(_arxiv(CC_BY_NC_SA).encode(), "doi", None)
    assert out["license"] == "cc-by-nc-sa"


def test_arxiv_page_without_a_licence_link_has_none():
    # the footer's "Copyright" help page is the site's, not the work's licence
    out = parse_page(_arxiv("").encode(), "doi", None)
    assert out["license"] is None


def test_other_arxiv_licence_paths_are_not_read():
    assert find_normalized_license("https://arxiv.org/licenses/") is None
    assert find_normalized_license("https://info.arxiv.org/help/license/index.html") is None


# --- 2. ACS -------------------------------------------------------------------------------------------------------

def _acs(creators, footnote="", info="", byline_names=None):
    byline_names = byline_names or [c.split("*")[0].split(",")[0].replace(" and", "").strip() for c in creators]
    metas = "".join(f'<meta name="dc.Creator" content="{c}" />' for c in creators)
    lis = "".join(
        f'<li><span><span class="hlFld-ContribAuthor" property="author"><a href="/action/doSearch?text1={n}">'
        f'{" ".join(n.split())}</a></span></span></li>' for n in byline_names)
    return (
        '<html><head><meta property="og:url" content="https://pubs.acs.org/doi/abs/10.1021/ja0376487" />'
        + metas + '</head><body><div class="article_header"><ul class="loa non-jats-loa">' + lis + '</ul></div>'
        '<div class="article_content-left">' + footnote + info + '</div></body></html>')


ASTERISK_NOTE = ('<div class="extra-info-sec fnGroup"><div class="fnGroupItem" id="ja0376487AF1"><span><h4>'
                 '<span class="NLM_fn-symbol">*</span></h4></span><span><p class="last"> In papers with more than '
                 'one author, the asterisk indicates the name of the author to whom inquiries about the paper should '
                 'be addressed.</p></span></div></div>')
CORRESPONDENCE_NOTE = ('<div class="extra-info-sec fnGroup"><div class="fnGroupItem" id="jf0011AF1"><span><h4>'
                       '<span class="NLM_fn-symbol">§</span></h4></span><span><p class="last">Tokyo.</p></span></div>'
                       '<div class="fnGroupItem" id="jf0011AF2"><span><h4><span class="NLM_fn-symbol">*</span></h4>'
                       '</span><span><p class="last"> Author to whom correspondence should be addressed (telephone '
                       '+81 3-5477-2444).</p></span></div></div>')
EQUAL_NOTE = ('<div class="extra-info-sec fnGroup"><div class="fnGroupItem" id="x1"><span><h4>'
              '<span class="NLM_fn-symbol">*</span></h4></span><span><p class="last"> These authors contributed '
              'equally.</p></span></div></div>')


def _marks(html):
    return {a.name: a.is_corresponding for a in ACS(BeautifulSoup(html, "lxml")).parse()["authors"]}


def test_acs_dc_creator_star_with_asterisk_note_marks_that_author():
    html = _acs(["Zhi-Xiang  Yu and", "K. N.  Houk*"], ASTERISK_NOTE, byline_names=["Zhi-Xiang Yu", "K. N. Houk"])
    assert _marks(html) == {"Zhi-Xiang Yu": False, "K. N. Houk": True}


def test_acs_dc_creator_star_among_other_symbols():
    html = _acs(["Seiichi  Kasaoka,†", "Mariko  Uehara,§", "Shiro  Goto*,§"], CORRESPONDENCE_NOTE,
                byline_names=["Seiichi Kasaoka", "Mariko Uehara", "Shiro Goto"])
    assert _marks(html) == {"Seiichi Kasaoka": False, "Mariko Uehara": False, "Shiro Goto": True}
    html = _acs(["Donald J.  Darensbourg,*", "Ryan Mackiewicz, and", "Jody L.  Rodgers"], ASTERISK_NOTE,
                byline_names=["Donald J. Darensbourg", "Mackiewicz", "Jody L. Rodgers"])
    assert _marks(html)["Donald J. Darensbourg"] is True
    assert not _marks(html)["Mackiewicz"]


def test_acs_dc_creator_star_without_a_correspondence_note_marks_no_one():
    html = _acs(["Zhi-Xiang  Yu and", "K. N.  Houk*"], "", byline_names=["Zhi-Xiang Yu", "K. N. Houk"])
    assert not any(_marks(html).values())
    html = _acs(["Zhi-Xiang  Yu*", "K. N.  Houk*"], EQUAL_NOTE, byline_names=["Zhi-Xiang Yu", "K. N. Houk"])
    assert not any(_marks(html).values())


def test_acs_corresponding_author_heading_marks_the_author():
    info = ('<div class="article_authorInformation"><ul><li><span class="author-information-subsection-header">'
            'Corresponding Author</span><ul><li><div class="authorItemInformation"><span class="hlFld-ContribAuthor '
            'strong">Cynthia J. Burrows</span>,&nbsp; <span><span class="NLM_role">Editor</span></span></div></li>'
            '</ul></li><li><span class="author-information-subsection-header">Notes</span><ul><li>Views expressed '
            'are those of the author.</li></ul></li></ul></div>')
    html = _acs(["Cynthia J.  Burrows"], "", info, byline_names=["Cynthia J. Burrows"])
    assert _marks(html) == {"Cynthia J. Burrows": True}


def test_acs_authors_heading_is_not_a_corresponding_mark():
    info = ('<div class="article_authorInformation"><ul><li><span class="author-information-subsection-header">'
            'Authors</span><ul><li><div class="authorItemInformation"><span class="hlFld-ContribAuthor">Jody L. '
            'Rodgers</span></div></li></ul></li></ul></div>')
    html = _acs(["Donald J.  Darensbourg", "Jody L.  Rodgers"], "", info,
                byline_names=["Donald J. Darensbourg", "Jody L. Rodgers"])
    assert not any(_marks(html).values())


# --- 3. DergiPark -----------------------------------------------------------------------------------------------

def _uds(entries, names):
    metas = "".join(f'<meta name="citation_author" content="{n}" /><meta name="citation_author_institution" '
                    f'content="Bir Üniversite" />' for n in names)
    return (
        '<html lang="tr"><head><meta name="generator" content="uds" />'
        '<meta property="og:url" content="https://dergipark.org.tr/tr/pub/tbj/article/1384335" />' + metas +
        '<meta name="citation_title" content="Bir başlık" /></head><body>'
        '<script src="https://dergipark.org.tr/assets/app.js"></script>'
        '<table class="record_properties table"><tr><th>Yazarlar</th><td>' + "<hr>".join(entries) +
        '</td></tr></table></body></html>')


def _titled(i, name, star=False):
    icon = '<span class="fa fa-star-of-life primary-author-icon m-0"></span>' if star else ""
    return (f'<p id="author270479{i}"><a aria-label="Sorumlu Yazar: {name}" data-toggle="tooltip" '
            f'href="/tr/pub/@x{i}" style="font-weight: 600" title="Sorumlu Yazar">{name} {icon}</a> '
            '<span class="row no-space-row"><label aria-label="Kurum : Bir Üniversite" class="m-0 p-0">'
            '<label aria-hidden="true" class="m-0 p-0">Bir Üniversite</label></label></span> '
            '<span class="row no-space-row"><label class="m-0 p-0">Türkiye</label></span></p>')


def _small(i, name, label=None):
    small = f"<small>({label})</small>" if label else ""
    return (f'<p id="author162294{i}"><a href="/tr/pub/@y{i}" style="font-weight: 600">{name} '
            f'<span class="fa fa-check-circle"></span></a> {small} <br/> Bir Üniversite <br/> Türkiye </p>')


def _corr(out):
    return [a["name"] for a in out["authors"] if a["is_corresponding"]]


def test_dergipark_record_page_keeps_the_star_mark():
    html = _uds([_titled(1, "Ayşe Kaş"), _titled(2, "Enayatullah Azimi", star=True)], ["Ayşe Kaş", "Enayatullah Azimi"])
    for ns, url in (("pmh", None), ("doi", "https://dergipark.org.tr/tr/pub/tbj/article/1384335")):
        assert _corr(parse_page(html.encode(), ns, url)) == ["Enayatullah Azimi"]


def test_dergipark_record_page_keeps_the_label_mark():
    html = _uds([_small(1, "Nergis ÖZİSPA", "Sorumlu Yazar"), _small(2, "Gamze ARABELEN")],
                ["Nergis ÖZİSPA", "Gamze ARABELEN"])
    assert _corr(parse_page(html.encode(), "pmh", None)) == ["Nergis ÖZİSPA"]


def test_dergipark_record_page_title_alone_is_not_a_mark():
    # the details table titles every name link that has a DergiPark profile "Sorumlu Yazar"; only the star decides
    html = _uds([_titled(1, "Abbas Said"), _titled(2, "Maamar Benbachır")], ["Abbas Said", "Maamar Benbachır"])
    assert _corr(parse_page(html.encode(), "pmh", None)) == []
    html = _uds([_titled(1, "Gürbüz Çalışkan")], ["Gürbüz Çalışkan"])
    assert _corr(parse_page(html.encode(), "pmh", None)) == []


def test_dergipark_record_page_english_primary_author_is_not_a_mark():
    html = _uds([_small(1, "Saheed RAJI", "Primary Author"), _small(2, "Ola ADE")], ["Saheed RAJI", "Ola ADE"])
    assert _corr(parse_page(html.encode(), "pmh", None)) == []


def _new(names, marked, label="Sorumlu Yazar", lang="tr", sup=True):
    metas = "".join(f'<meta name="citation_author" content="{n}" /><meta name="citation_author_institution" '
                    f'content="Bir Üniversite" />' for n in names)
    hero, cards = "", ""
    for i, n in enumerate(names):
        title = f' title="{label}"' if n == marked else ""
        star = "<sup>*</sup>" if n == marked and sup else ""
        hero += f'<li> <a href="/{lang}/pub/@u{i}"{title}>{n}</a> {star} </li>'
        cards += (f'<div class="min-w-0" id="author313198{i}"><p> <a class="font-medium underline" '
                  f'href="/{lang}/pub/@u{i}"{title}> {n} {star.replace("<sup>", "<sup class=text-accent>")} </a> <br/>'
                  f' <a href="https://orcid.org/0000-0001-5092-230{i}">0000-0001-5092-230{i}</a> <br/> '
                  '<span class="text-text-muted">Türkiye</span> </p></div>')
    return (
        f'<html lang="{lang}"><head><meta property="og:url" content="https://dergipark.org.tr/{lang}/pub/spormetre/'
        'article/1605854" />' + metas + '<meta name="citation_title" content="Bir başlık" /></head><body>'
        '<header id="article-main-header"><ul class="hide-on-sticky list-none">' + hero + '</ul></header>'
        '<div id="sec-article-info"><div class="grid grid-cols-2">' + cards + '</div></div>'
        '<a href="https://dergipark.org.tr/tr/">DergiPark</a></body></html>')


def test_dergipark_new_template_title_and_star_mark_the_author():
    html = _new(["Emrah Şengür", "Ruçhan İri"], "Emrah Şengür")
    for ns in ("doi", "pmh"):
        assert _corr(parse_page(html.encode(), ns, "https://dergipark.org.tr/tr/pub/spormetre/article/1605854")) \
            == ["Emrah Şengür"]
    html = _new(["Umut Hallaç"], "Umut Hallaç")
    assert _corr(parse_page(html.encode(), "doi", None)) == ["Umut Hallaç"]


def test_dergipark_new_template_english_primary_author_is_not_a_mark():
    html = _new(["Vedat Esen"], "Vedat Esen", label="Primary Author", lang="en")
    assert _corr(parse_page(html.encode(), "doi", None)) == []


def test_dergipark_new_template_title_without_star_is_not_a_mark():
    html = _new(["Emrah Şengür", "Ruçhan İri"], "Emrah Şengür", sup=False)
    assert _corr(parse_page(html.encode(), "doi", None)) == []
