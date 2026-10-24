"""Placeholders, site blurbs and SEO templates never leave Parseland as an abstract (oxjob #1800).

On 24 Oct 2026 about 1.7M works showed one of these as their abstract ("No abstract available.", the IUCN
Red List's site description on 251K DOIs, ChemInform's notice on 280K, Taylor & Francis citation lines on
175K, De Gruyter "Article ... was published on ..." lines on 161K). parse_page() drops them for every parser.
Offline: inline strings and inline HTML only.
"""
import pytest

from bs4 import BeautifulSoup

from parseland_lib.not_abstract import _KEY_RE, clean_abstract, is_not_abstract, key
from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.generic import GenericPublisherParser

# Over 200 characters, like LONG_REAL below: the generic parser already ignores shorter citation_abstract
# text, so a short placeholder would pass the parse_page tests without the filter.
CHEMINFORM = (
    "ChemInform is a weekly Abstracting Service, delivering concise information at a glance that was extracted "
    "from about 100 leading journals. To access a ChemInform Abstract of an article which was published elsewhere, "
    "please select a “Full Text” option. The original article is trackable via the “References” option."
)
LONG_REAL = (
    "We report a case of severe cobalt poisoning from a damaged metal-on-ceramic hip prosthesis in a 56-year-old man. "
    "He was treated with a total hip revision and chelation therapy; blood cobalt fell from 6,521 to 25 micrograms per "
    "litre over twelve months and his cardiomyopathy and hearing loss partly recovered."
)

NOT_ABSTRACTS = [
    # explicit "no abstract" wordings (ACM, ECS, Wiley, Elsevier, SSRN, J-STAGE, LWW, NEJM ...)
    "No abstract available.",
    "no abstract available",
    "<p>No abstract available.</p>",
    "No Abstract Available for this article.",
    "No abstract is available for this article.",
    "No abstract available. doi:10.2204/iodp.sd.7.04.2009",
    "Abstract not available.",
    "Abstract is not available at this time",
    "Abstract not provided to SSRN.",
    "This article has no abstract.",
    "This article does not have an abstract",
    "This article was submitted without an abstract, please refer to the full-text PDF file.",
    "No extract is available for articles shorter than 400 words.",
    "Keine Zusammenfassung",
    "[In Japanese]",
    "本記事に「抄録」はありません。",
    "not provided.",
    "N/A",
    "NA",
    "None.",
    "Abstract:",
    "摘要：",
    "Background",
    ".",
    "-",
    "■",
    # notices and site text from the list built from production (parseland_lib/data/not_abstracts.tsv)
    "A graphical abstract is available for this content",
    CHEMINFORM,
    "For abstract see ChemInform Abstract in Full Text.",
    "Established in 1964, the IUCN Red List of Threatened Species has evolved to become the world’s most "
    "comprehensive information source on the global conservation status of animal, fungi and plant species.",
    "This is a scanned image of the original Editorial Board page(s) for this issue.",
    "Data sharing is not applicable to this article as no new data were created or analyzed in this study.",
    "An abstract is not available for this content so a preview has been provided. Please use the Get access "
    "link above for information on how to access this content.",
    # per-page SEO templates
    '"Editor\'s Preface." Royal United Services Institution. Journal, 37(180), pp. 89–90',
    '"How to Identify Priority Questions for Bioethics Research." The American Journal of Bioethics, 22(1), pp. 17–18',
    '"To Arthur Osborne Alleyne" published on  by null.',
    "Article Severe Dietary Protein Sensitivity and Hyperinsulinemic Hypoglycemia in a Patient with Heterozygous "
    "Mutation in HADH Gene was published on September 1, 2009 in the journal Hormone Research in Paediatrics "
    "(volume 72, issue 3).",
    "Authors and Affiliations Department of Neurology, Academic Medical Centre, Amsterdam, 1100, DE, The Netherlands "
    "Pim van Gool Authors Pim van Gool View author publications You can also search for this author in PubMed Google Scholar",
    # CABI Compendium datasheet stand-ins (one per taxon; 564 of 581 CABI front-matter texts in the 24 Oct pilot)
    "This datasheet on Mesorchis covers Identity.",
    "This datasheet on Brassolis sophorae covers Identity, Distribution, Hosts/Species Affected, Natural Enemies, "
    "Further Information.",
]

REAL_ABSTRACTS = [
    # a real CABI book-chapter abstract from the same pilot
    "This chapter describes in detail the structure of the egg shell and sclerotization of Culex, Aedes, Anopheles and "
    "other genera; water relations (resistance to water loss, water uptake and waterproofing); and hatching stimulus "
    "and mechanism.",
    "We report a case of severe cobalt poisoning from a damaged metal-on-ceramic hip prosthesis.",
    "No abstract reasoning task has been solved by current language models; we propose a benchmark of 400 puzzles "
    "and show that the best system solves 31% of them.",
    "Abstract: Background: CD4+ T cells are critical mediators of anti-tumor immunity.",
    '"Fake news" spreads faster than true news on social media; we analyse 126,000 cascades shared by 3 million people.',
    "Article 5 of the European Convention on Human Rights protects liberty; this paper examines detention in 12 states.",
    "Summary: the inelastic scattering of alpha particles from 40Ca and 208Pb has been studied at 79.1 MeV.",
    # kept out of the list on purpose: a real abstract Pensoft repeats on the paper's figure DOIs
    "Rhiniinae (Diptera, Calliphoridae) is a taxon of nearly 400 known species, many of them termitophilous.",
]


@pytest.mark.parametrize("text", NOT_ABSTRACTS)
def test_not_abstract(text):
    assert is_not_abstract(text), text
    assert clean_abstract(text) is None


@pytest.mark.parametrize("text", REAL_ABSTRACTS)
def test_real_abstract_kept(text):
    assert not is_not_abstract(text), text
    assert clean_abstract(text) == text


@pytest.mark.parametrize("value", [None, "", 0, ["No abstract available."]])
def test_non_text_passes_through(value):
    assert clean_abstract(value) == value


def test_key_ignores_markup_case_and_punctuation():
    assert key("<p>No&nbsp;abstract <i>available</i>.</p>") == key("no abstract available")
    assert key("CO<sub>2</sub> uptake") == "co2 uptake"


def _page(abstract):
    return f"""<html><head>
      <meta name="citation_title" content="A study of things" />
      <meta name="citation_author" content="Ada Lovelace" />
      <meta name="citation_author_institution" content="University of London" />
      <meta name="citation_abstract" content="{abstract}" />
    </head><body></body></html>"""


def test_parse_page_drops_boilerplate():
    out = parse_page(_page(CHEMINFORM), "doi", "https://example.org/doi/10.1/x")
    assert out["abstract"] is None
    assert out["authors"] and out["authors"][0]["name"] == "Ada Lovelace"


def test_parse_page_keeps_real_abstract():
    out = parse_page(_page(LONG_REAL), "doi", "https://example.org/doi/10.1/x")
    assert out["abstract"] == LONG_REAL


def test_parse_page_without_filter_would_return_the_boilerplate(monkeypatch):
    """Guards the tests above: the meta-tag skip off and the exit filter off, the page yields the text."""
    monkeypatch.setattr("parseland_lib.publisher.parsers.parser.is_not_abstract", lambda text: False)
    monkeypatch.setattr("parseland_lib.parse.clean_abstract", lambda text: text)
    assert parse_page(_page(CHEMINFORM), "doi", "https://example.org/doi/10.1/x")["abstract"] == CHEMINFORM


def test_meta_tags_skip_a_blurb_for_the_real_abstract_after_it():
    """OJS pages can carry the journal's blurb in the first DC.Description and the abstract in the next."""
    html = f"""<html><head>
      <meta name="DC.Description" xml:lang="es" content="{CHEMINFORM}" />
      <meta name="DC.Description" xml:lang="en" content="{LONG_REAL}" />
    </head></html>"""
    parser = GenericPublisherParser(BeautifulSoup(html, "lxml"))
    assert parser.parse_abstract_meta_tags(include_seo_tags=False) == LONG_REAL


@pytest.mark.parametrize("text", [
    "no abstract available", "no abstract is available for this article", "without abstract",
    "no abstract available doi 10 2204 iodp sd 7 04 2009", "abstract not provided to ssrn",
    "abstract is not available at this time", "this article does not have an abstract",
    "abstracts are not published in this journal", "keine zusammenfassung", "in japanese", "n a", "na", "tbd",
    "graphical abstract", "letter to the editor", "1",
])
def test_wording_patterns(text):
    """The pattern layer on its own (the list catches most real cases first)."""
    assert _KEY_RE.fullmatch(text), text


@pytest.mark.parametrize("text", [
    "no abstract reasoning task has been solved", "abstract algebra for engineers", "summary of findings",
    "introduction to the special issue on coral reefs", "1234",
])
def test_wording_patterns_need_the_whole_text(text):
    assert not _KEY_RE.fullmatch(text), text


def test_meta_tags_short_first_candidate_still_ends_the_search():
    """Only a not-an-abstract candidate hands over: a first tag that is just short keeps the old behaviour
    (dev page be0e211e: the next DC.description is a funding note, not the abstract)."""
    html = f"""<html><head>
      <meta name="DC.Description" content="Proceedings of the IV International Archaeology Days, 2023." />
      <meta name="DC.Description" content="{LONG_REAL}" />
    </head></html>"""
    parser = GenericPublisherParser(BeautifulSoup(html, "lxml"))
    assert parser.parse_abstract_meta_tags(include_seo_tags=False) is None
