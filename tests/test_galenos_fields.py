"""Galenos Publishing House journal pages (oxjob #2268).

About 50 Turkish medical journals (hasekidergisi.com, jcrpe.org, turkjps.org, eajem.com ...) run Galenos's Nuxt
journal system: assets on Galenos's CloudFront host, a "Galenos Publishing House" footer, the byline as one
<a role="link"> per author (affiliation numbers in <sup>, a mail icon after the corresponding author), the numbered
affiliations in the "Author Information" panel, the abstract in <div id="abstract">, the back matter as
<div class="py-2"> blocks ("Financial Disclosure:", "Acknowledgments"), and the reference list in
<div id="references">. The page state (__NUXT_DATA__) flags the corresponding author too. Generic parsing read the
citation_author tags only: no affiliations, no corresponding author. Markup below is cut down from stored pages;
names are placeholders.
"""
import json

from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.galenos import Galenos

URL = "https://www.example-medj.org/articles/a-title/doi/medj.galenos.2024.1"
CDN = "https://d2v96fxpocvxx.cloudfront.net/a2440bda-5c5c-4e7b-8a75-abf1691c9260"
MAIL = '<span class="ms-1"><span class="iconify i-material-symbols-light:mail-outline-rounded text-xl"></span></span>'
MAIL_SVG = '<span class="ms-1"><svg class="icon text-xl" viewBox="0 0 24 24"><path d="M4 6"/></svg></span>'
FOOTER = '<div class="bg-primary-800 text-white">2024 ©️ Galenos Publishing House</div>'


def _payload(authors):
    """A __NUXT_DATA__ array (devalue) holding the article's authors."""
    arr = [{"data": 1}, {"article": 2}, {"authors": 3}, []]
    for name, corr in authors:
        i = len(arr)
        arr.append({"full_name": i + 1, "isCorrespondingAuthor": i + 2})
        arr += [name, corr]
        arr[3].append(i)
    return f'<script type="application/json" id="__NUXT_DATA__" data-ssr="true">{json.dumps(arr)}</script>'


def _author(name, sups="", corr=False, mail=MAIL):
    sup = f"<sup></sup><sup>{sups}</sup>" if sups else ""
    cls = "text-cyan-300 text-sm ms-2 text-nowrap" if corr else "text-sm ms-2 text-nowrap"
    return (f'<div class="block md:flex items-center md:flex-nowrap md:mb-0 mb-4"><a tabindex="0" role="link" '
            f'class="relative focus:outline-none"><div class="flex items-center flex-nowrap">'
            f'<span class="iconify i-fa6-brands:orcid"></span><span class="{cls}">{name} {sup}</span>'
            f'{mail if corr and mail else ""}</div></a></div>')


def _affs(affs):
    items = "".join(f'<div><div class="mb-1"><span class="font-semibold me-1">{i}.</span> {a}</div></div>'
                    for i, a in enumerate(affs, 1))
    return (f'<div class="block md:flex items-center text-xs gap-4"><button class="opacity-75 flex items-center">'
            f' Author Information</button><button class="opacity-75 flex items-center"> Copyright &amp; Licence '
            f'Information</button><button class="opacity-75 flex items-center"> Galenos &amp; Med J Disclaimer'
            f'</button></div><div class="text-sm overflow-hidden max-h-0 px-6"><div class="py-3 opacity-85">{items}'
            f'</div></div><div class="text-sm overflow-hidden max-h-0 px-6"><div class="py-3 opacity-85">No '
            f'information available.</div></div>')


ABSTRACT = ('<div class="mb-10 section" id="abstract"><h1>ABSTRACT</h1><span></span>'
            '<p class="font-semibold mt-4">Aim:</p><span></span><p class="">This study evaluated the duration of '
            'viral shedding in children admitted to a training hospital over three months.</p>'
            '<p class="font-semibold mt-4">Results</p><p class=""> We evaluated 258 patients with a median age of '
            '132.6 months, and lymphopenia predicted prolonged positivity.</p>'
            '<div class="flex items-baseline gap-2 mt-4 keywords"><div class="font-semibold">Keywords:</div>'
            '<div class=""><span>Children, COVID-19, PCR</span></div></div></div>')

BACK = ('<div class="py-2"><h3 class="mb-1">Ethics</h3><div class="mb-4"><div><strong>Ethics Committee Approval:'
        '</strong> Approved by the ethics committee (no: 23-2021).</div></div></div>'
        '<div class="py-2"><h3 class="mb-1">Acknowledgments</h3><div class="mb-4"><div>The authors thank the '
        'nurses of the paediatric ward.</div><div><strong>Footnotes</strong></div></div></div>'
        '<div class="py-2"><div class=""><div><strong>Conflict of Interest:</strong> No conflict of interest was '
        'declared by the authors.</div></div></div>'
        '<div class="py-2"><div class=""><div><strong>Financial Disclosure:</strong> The authors declared that this '
        'study received no financial support.</div></div></div>')


def _ref(n, text, doi=None):
    links = (f'<a href="https://dx.doi.org/{doi}" target="_blank"> CrossRef </a><a href="https://pubmed.ncbi.nlm.nih.'
             f'gov/17304022" target="_blank"> PubMed </a>') if doi else ""
    return (f'<div><div class="flex items-baseline ref-list border-b pb-3"><div class="flex items-start gap-3">'
            f'<span id="refnum" class="refnum font-semibold text-gray-700">{n}</span><div class="flex-1">'
            f'<div class="break-words text-gray-800" style="overflow-wrap:anywhere;">{text}</div>'
            f'<div class="flex flex-wrap gap-4 mt-1 text-xs text-gray-500">{links}</div></div></div></div></div>')


REFS = [("Zou L, Ruan F. SARS-CoV-2 viral load in upper respiratory specimens. N Engl J Med 2020;382:1177-9.",
         "10.1056/NEJMc2001737"),
        ("World Health Organization. Clinical management of severe acute respiratory infection. 2020.", None),
        ("Riley S, Ainslie KEC. Resurgence of SARS-CoV-2. Science 2021;372:990-5.", "10.1126/science.abf0874")]


def _refs(refs=REFS, numbers=None):
    numbers = numbers or range(1, len(refs) + 1)
    items = "".join(_ref(n, t, d) for n, (t, d) in zip(numbers, refs))
    return (f'<div id="references" class="section mt-6"><h1 class="mb-3">References</h1>'
            f'<div class="flex flex-col gap-4">{items}</div></div>')


def _page(byline, affs, article="", payload="", footer=FOOTER, cdn=CDN):
    head = ('<head><meta name="citation_title" content="A title"/>'
            '<meta name="citation_doi" content="10.4274/medj.galenos.2024.1"/>'
            + "".join(f'<meta name="citation_author" content="{n}"/>' for n in ("Berker Okay", "Fidel Ceren Yavuzyilmaz"))
            + (f'<meta property="og:image" content="{cdn}/logo.png"/>' if cdn else "")
            + '<link rel="modulepreload" href="/_nuxt/kATWg3xI.js"/></head>')
    header = f'<div class="block md:flex items-center md:flex-wrap gap-5 mt-6 px-1 text-gray-100">{byline}</div>{affs}'
    body = (f'<body><div id="__nuxt"><div>{header}<div class="flex-1 text-gray-600 article border">{article}</div>'
            f'</div>{footer}</div>{payload}</body>')
    return f"<html>{head}{body}</html>"


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _raw(html):
    return Galenos(BeautifulSoup(html, "lxml")).parse()


TWO_AFFS = ["University of Health Sciences Turkey, Haseki Training and Research Hospital, Clinic of Pediatrics, "
            "Istanbul, Turkey", "Marmara University Faculty of Medicine, Department of Infectious Diseases, "
            "Istanbul, Turkey"]


def test_byline_numbers_link_each_author_to_its_affiliations():
    byline = (_author("Berker Okay", "1", corr=True) + _author("Fidel Ceren Yavuzyilmaz", "2")
              + _author("Gulsen Akkoc", "1,2"))
    out = _parse(_page(byline, _affs(TWO_AFFS), ABSTRACT))
    assert [a["name"] for a in out["authors"]] == ["Berker Okay", "Fidel Ceren Yavuzyilmaz", "Gulsen Akkoc"]
    assert [[x["name"] for x in a["affiliations"]] for a in out["authors"]] == [
        TWO_AFFS[:1], TWO_AFFS[1:], TWO_AFFS]


def test_mail_icon_marks_the_corresponding_author():
    byline = _author("Berker Okay", "1") + _author("Fidel Ceren Yavuzyilmaz", "2", corr=True)
    out = _parse(_page(byline, _affs(TWO_AFFS)))
    assert [a["is_corresponding"] for a in out["authors"]] == [False, True]


def test_single_affiliation_without_numbers_goes_to_every_author():
    byline = _author("Kemal Hansu") + _author("Alev Ozer") + _author("Ilter Bakkaloglu", corr=True)
    out = _parse(_page(byline, _affs(["Kahramanmaras University Faculty of Medicine, Department of Obstetrics"])))
    assert [len(a["affiliations"]) for a in out["authors"]] == [1, 1, 1]
    assert [a["is_corresponding"] for a in out["authors"]] == [False, False, True]


def test_page_state_flag_marks_corresponding_author_without_an_email():
    # the highlighted author has no e-mail, so no mail icon; the page state says isCorrespondingAuthor
    byline = _author("Mishal Shamsi", "1", corr=True, mail=None) + _author("Salman Bashir", "2")
    out = _parse(_page(byline, _affs(TWO_AFFS), payload=_payload([("Mishal Shamsi", True), ("Salman Bashir", False)])))
    assert [a["is_corresponding"] for a in out["authors"]] == [True, False]


def test_highlight_alone_is_not_a_corresponding_mark():
    byline = _author("Mishal Shamsi", "1", corr=True, mail=None) + _author("Salman Bashir", "2")
    out = _parse(_page(byline, _affs(TWO_AFFS)))
    assert not any(a["is_corresponding"] for a in out["authors"])


def test_older_skin_with_svg_icons():
    byline = (_author("Chee Chean Lim", corr=True, mail=MAIL_SVG).replace(
        '<span class="iconify i-fa6-brands:orcid"></span>', '<svg class="icon lg:text-xl"><path d="M2"/></svg>')
              + _author("Yew Toong Liew"))
    out = _parse(_page(byline, _affs(["Department of Otorhinolaryngology, Universiti Malaya, Kuala Lumpur"])))
    assert [a["name"] for a in out["authors"]] == ["Chee Chean Lim", "Yew Toong Liew"]
    assert [a["is_corresponding"] for a in out["authors"]] == [True, False]
    assert all(a["affiliations"] for a in out["authors"])


def test_structured_abstract_keeps_labels_inline_and_drops_keywords():
    out = _parse(_page(_author("Berker Okay", "1"), _affs(TWO_AFFS), ABSTRACT))
    assert out["abstract"].startswith("Aim: This study evaluated the duration")
    assert "Results: We evaluated 258 patients" in out["abstract"]
    assert "Keywords" not in out["abstract"] and "ABSTRACT" not in out["abstract"]


def test_reference_list_with_dois_and_whole_numbering():
    raw = _raw(_page(_author("Berker Okay", "1"), _affs(TWO_AFFS), ABSTRACT + BACK + _refs()))
    assert [r["position"] for r in raw["references"]] == [1, 2, 3]
    assert raw["references"][0]["raw"].startswith("Zou L, Ruan F.")
    assert [r["doi"] for r in raw["references"]] == ["10.1056/NEJMc2001737", None, "10.1126/science.abf0874"]
    assert raw["references_complete"] is True


def test_gap_in_reference_numbers_is_not_whole():
    raw = _raw(_page(_author("Berker Okay", "1"), _affs(TWO_AFFS), _refs(numbers=[1, 2, 4])))
    assert len(raw["references"]) == 3 and raw["references_complete"] is False


def test_back_matter_funding_and_acknowledgments():
    raw = _raw(_page(_author("Berker Okay", "1"), _affs(TWO_AFFS), ABSTRACT + BACK + _refs()))
    assert raw["funding_statement"] == "The authors declared that this study received no financial support."
    assert raw["acknowledgments"] == "The authors thank the nurses of the paediatric ward."


def test_inline_acknowledgments_label():
    back = ('<div class="py-2"><div class=""><div><strong>Acknowledgments:</strong> We thank the participants.</div>'
            '</div></div><div class="py-2"><div class=""><div><strong>Funding:</strong> No funding was received.'
            '</div></div></div>')
    raw = _raw(_page(_author("Berker Okay", "1"), _affs(TWO_AFFS), back))
    assert raw["acknowledgments"] == "We thank the participants."
    assert raw["funding_statement"] == "No funding was received."


def test_page_without_back_matter_returns_none():
    raw = _raw(_page(_author("Berker Okay", "1"), _affs(TWO_AFFS), ABSTRACT))
    assert raw["acknowledgments"] is None and raw["funding_statement"] is None
    assert raw["references"] is None and raw["references_complete"] is False


def test_issue_listing_is_not_read_as_a_byline():
    # a current-issue page lists many articles' bylines and has no "Author Information" panel
    byline = "".join(_author(f"Author Number{i}") for i in range(30))
    page = _page(byline, "")
    assert not Galenos(BeautifulSoup(page, "lxml")).authors_found()


def test_other_nuxt_site_with_similar_markup_is_not_claimed():
    # another Nuxt journal system (IMR Press, MDPI's new pages) without Galenos's CDN or footer
    page = _page(_author("Berker Okay", "1", corr=True), _affs(TWO_AFFS), ABSTRACT, footer="<footer>IMR Press</footer>",
                 cdn=None)
    parser = Galenos(BeautifulSoup(page, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    out = _parse(page)
    assert not any(a["affiliations"] for a in out["authors"])
