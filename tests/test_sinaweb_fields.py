"""Sinaweb journal pages beyond ekb.eg (oxjob #2289): mostly Iranian and Iraqi university journals.

Markup is cut down from the batch's 80 stored Sinaweb pages. Sinaweb serves an article at /article_<id>.html (or
/article_<id>_en.html) and prints the same id in citation_id; the meta-tag parser already reads the byline, so the
Sinaweb parser adds only what it misses: the corresponding author the byline marks (an envelope `mailto` titled
"Email to Corresponding Author", Persian "ارسال ایمیل به نویسنده اصلی", or with no envelope a Font Awesome asterisk
that singles an author out; the same marks egyptian_knowledge_bank.py reads on ekb.eg) and the reference panel.
ekb.eg pages stay with egyptian_knowledge_bank.py.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.egyptian_knowledge_bank import EgyptianKnowledgeBank
from parseland_lib.publisher.parsers.sinaweb import Sinaweb

URL = "https://jgeo.example.ac.ir/article_121962.html"


def _page(authors, body, abstract_url=URL, citation_id="121962"):
    metas = "".join(f'<meta name="citation_author" content="{n}"/>'
                    f'<meta name="citation_author_institution" content="{aff}"/>' for n, aff in authors)
    cid = f'<meta name="citation_id" content="{citation_id}"/>' if citation_id else ""
    return (f'<!DOCTYPE html><html><head><meta name="citation_title" content="A title"/>{cid}{metas}'
            f'<meta name="citation_doi" content="10.22071/gsj.2020.1"/>'
            f'<meta name="citation_abstract_html_url" content="{abstract_url}"/>'
            f'<link rel="shortcut icon" href="./data/jgeo/coversheet/favicon.ico"/></head><body>{body}</body></html>')


ENVELOPE = ('<sup><a class="inline-block" href="mailto:a@example.com" data-toggle="tooltip" data-placement="bottom" '
            'title="Email to Corresponding Author"><i class="fa fa-envelope-o" ></i></a></sup>')
ENVELOPE_FA = ENVELOPE.replace("Email to Corresponding Author", "ارسال ایمیل به نویسنده اصلی")
ASTERISK = '<sup><i class="fa fa-asterisk" ></i></sup>'


def _byline(names, marks):
    items = "".join(f'<li class="padding-3"><a href="./?_action=article&amp;au={i}&amp;_au={n.replace(" ", "+")}">{n}</a>'
                    f'{m}<sup><a class="inline-block" href="#aff{i}">{i}</a></sup></li>'
                    for i, (n, m) in enumerate(zip(names, marks), 1))
    return f'<ul class="list-inline list-inline-seprator margin-bottom-6 rtl">{items}</ul>'


AUTHORS = [("غفله مرمضی, هاجر", "دانشگاه صنعتی شاهرود، شاهرود، ایران"),
           ("موسیوند, فردین", "دانشگاه صنعتی شاهرود، شاهرود، ایران"),
           ("زراسوندی, علیرضا", "دانشگاه شهید چمران اهواز، اهواز، ایران")]
BYLINE = ["هاجر  غفله مرمضی", "فردین  موسیوند", "علیرضا  زراسوندی"]


def _out(html):
    return parse_page(html.encode(), "doi", URL)


def _corr(html):
    return [a["name"] for a in _out(html)["authors"] if a["is_corresponding"]]


def _parser(html):
    return Sinaweb(BeautifulSoup(html, "lxml"))


def test_claims_sinaweb_article_pages():
    assert _parser(_page(AUTHORS, "")).is_publisher_specific_parser()
    english = _page(AUTHORS, "", abstract_url="https://jkm.ihu.ac.ir/article_205178_en.html", citation_id="205178")
    assert _parser(english).is_publisher_specific_parser()


def test_leaves_ekb_pages_to_their_parser():
    html = _page(AUTHORS, _byline(BYLINE, [ENVELOPE, "", ""]),
                 abstract_url="https://jesaun.journals.ekb.eg/article_114598.html", citation_id="114598")
    assert not _parser(html).is_publisher_specific_parser()
    assert EgyptianKnowledgeBank(BeautifulSoup(html, "lxml")).is_publisher_specific_parser()


def test_does_not_claim_look_alikes():
    # Yektaweb, the other Iranian journal platform: /article-1-1243-en.html and no citation_id
    yekta = _page(AUTHORS, _byline(BYLINE, [ENVELOPE, "", ""]),
                  abstract_url="http://ismj.bpums.ac.ir/article-1-1243-en.html", citation_id=None)
    assert not _parser(yekta).is_publisher_specific_parser()
    # an article_<n>.html address whose number is not the page's citation_id
    other = _page(AUTHORS, "", abstract_url="https://example.org/article_5.html", citation_id="77")
    assert not _parser(other).is_publisher_specific_parser()
    assert not _parser("<p>no head at all</p>").is_publisher_specific_parser()


def test_envelope_marks_its_author():
    assert _corr(_page(AUTHORS, _byline(BYLINE, [ENVELOPE_FA, "", ""]))) == ["غفله مرمضی, هاجر"]
    assert _corr(_page(AUTHORS, _byline(BYLINE, ["", ENVELOPE, ""]))) == ["موسیوند, فردین"]


def test_lone_asterisk_marks_its_author():
    assert _corr(_page(AUTHORS, _byline(BYLINE, ["", "", ASTERISK]))) == ["زراسوندی, علیرضا"]


def test_asterisk_on_every_author_marks_no_one():
    assert _corr(_page(AUTHORS, _byline(BYLINE, [ASTERISK] * 3))) == []


def test_unmarked_page_keeps_the_meta_tag_reading():
    html = _page(AUTHORS, _byline(BYLINE, ["", "", ""]))
    out = _out(html)
    assert [a["name"] for a in out["authors"]] == [n for n, _ in AUTHORS]
    assert [a["affiliations"] for a in out["authors"]] == [[{"name": aff}] for _, aff in AUTHORS]
    assert not any(a["is_corresponding"] for a in out["authors"])


def _panel(inner, toggle='<a href="#collapsesRef">References</a>', box_id="collapsesRef"):
    return (f'<div class="panel-heading card-header"><h4 class="panel-title">{toggle}</h4></div>'
            f'<div class="panel-collapse collapse" id="{box_id}"><div class="panel-body justify">{inner}</div></div>')


def test_single_ordered_list_is_a_whole_list():
    refs = _panel('<ol><li class="ltr justify">Afrasyabi, S. (2013). Factors affecting wheat insurance. '
                  '<em>Agricultural Science</em>, 23(4).</li>'
                  '<li class="ltr justify">Bielza, M. (2008). Agricultural insurance schemes. '
                  'https://doi.org/10.1016/j.foodpol.2008.01.002</li></ol>')
    out = _parser(_page(AUTHORS, _byline(BYLINE, ["", "", ""]) + refs)).parse()
    assert [r["position"] for r in out["references"]] == [1, 2]
    assert out["references"][0]["raw"] == "Afrasyabi, S. (2013). Factors affecting wheat insurance. Agricultural Science, 23(4)."
    assert out["references"][1]["doi"] == "10.1016/j.foodpol.2008.01.002"
    assert out["references_complete"] is True


def test_unnumbered_lines_are_not_a_whole_list():
    toggle = ('<a class="accordion-toggle" data-toggle="collapse" href="#collapseOne1">'
              '<span class="glyphicon glyphicon-plus"><h5 style="display: inline;">مراجع</h5></span></a>')
    lines = ['<div class="padding-3 margin-top-3 rtl justify">کتابنگاری</div>',
             '<div class="padding-3 margin-top-3 rtl justify">استوری، جان. (1385). مطالعات فرهنگی. تهران: آگه.</div>',
             '<div class="padding-3 margin-top-3 ltr justify"><strong>References</strong></div>',
             '<div class="padding-3 margin-top-3 ltr justify">Storey, J. (2006). Cultural studies. Tehran: Agah.</div>']
    out = _parser(_page(AUTHORS, _panel("".join(lines), toggle, "collapseOne1"))).parse()
    assert [r["raw"] for r in out["references"]] == ["استوری، جان. (1385). مطالعات فرهنگی. تهران: آگه.",
                                                      "Storey, J. (2006). Cultural studies. Tehran: Agah."]
    assert out["references_complete"] is False


def test_numbered_lines_in_one_block_are_a_whole_list():
    block = ('<div class="padding-3 margin-top-3 ltr justify">1. Cushing B. L. Recent advances. Chem. Rev. 2004; '
             '104(9): 3893-3946<br/>2. Lekshmi NC. Antibacterial activity. Microbiol. Biotech. Res. 2012; 2(1): 115-119.'
             '<br/>3. Rao C. N. R. Metal nanoparticles. Chem. Soc. Rev. 2000; 29: 27-35.</div>')
    out = _parser(_page(AUTHORS, _panel(block))).parse()
    assert [r["raw"][:10] for r in out["references"]] == ["Cushing B.", "Lekshmi NC", "Rao C. N. "]
    assert out["references_complete"] is True


def test_no_reference_panel_no_references():
    out = _parser(_page(AUTHORS, _byline(BYLINE, [ENVELOPE, "", ""]))).parse()
    assert "references" not in out
