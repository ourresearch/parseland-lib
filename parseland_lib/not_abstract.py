"""Text that must never leave Parseland as an abstract (oxjob #1800).

Landing pages put many things where an abstract would be: "No abstract available.", a site's own
description ("Established in 1964, the IUCN Red List ..."), ChemInform's service notice, generated SEO
lines ('"Title." Journal, 12(3), pp. 4-5'), author blocks, retraction and withdrawal notices. On 24 Oct
2026 about 1.7M works showed one of these as their abstract. Two places use this module:
parse_abstract_meta_tags() skips such a candidate so a later real one can win, and parse_page() drops
whatever is left, so one check covers every publisher and repository parser.

Two layers:
- KNOWN: data/not_abstracts.tsv, every text that sat in 100+ different DOIs' landing-page abstracts
  (1,000+ repository records') on 24 Oct 2026, read by hand; kept out are real abstracts that Pensoft
  and PLOS repeat on a paper's figure and supplement DOIs, and OECD's Taxing Wages chapter text.
  Rebuild: oxjobs working/parseland-swarm-abstracts/work/build_not_abstracts.py.
  # shortcut: a frozen snapshot, so a new site's blurb isn't caught until the list is rebuilt. The
  # upgrade is a frequency rule where walden picks a work's abstract ("the abstract of N+ works with
  # different titles is nobody's"), which would also cover Crossref and the legacy backfill.
- PATTERNS: explicit "no abstract" wordings and per-page templates (unique per DOI, so no list can
  hold them).
Matching is on a key of letters and digits only, so case, punctuation, markup and spacing don't matter.
"""
from __future__ import annotations

import html
import os
import re
from functools import cache

_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "not_abstracts.tsv")

# Tags that sit inside a word (CO<sub>2</sub>) close up; every other tag becomes a space, as in walden's
# clean_text, so a key built here equals one built from the text works store. [^<>] (walden: [^>]) keeps
# the strip linear on text full of unclosed '<' (maths like "x<y"); real tags strip the same either way.
_INLINE_TAGS = frozenset(
    "a abbr b bdi bdo cite code data dfn em font i kbd mark q s samp small span strong sub sup "
    "time tt u var wbr".split()
)
# No space after '<': "<< ABSTRACT Starting with French Painting Today ... >>" is text, and reading "< ABSTRACT ... >"
# as one tag emptied a 1,529-character abstract (5 texts on 26 Oct; oxjob #1800 EXPLORE § 15).
_TAG_RE = re.compile(r"</?([a-zA-Z][\w:.-]*)[^<>]*>")
_WORD_RE = re.compile(r"[^\W_]+")


def _plain(text: str) -> str:
    """Entities decoded, tags removed, whitespace collapsed, lower case."""
    s = html.unescape(html.unescape(text)).lower()
    s = _TAG_RE.sub(lambda m: "" if m.group(1).rsplit(":", 1)[-1] in _INLINE_TAGS else " ", s)
    return " ".join(s.split())


def _key_of(plain: str) -> str:
    return " ".join(_WORD_RE.findall(plain))


def key(text: str) -> str:
    """Letters and digits of the plain text, single-spaced."""
    return _key_of(_plain(text))


# Whole-text matches on the key. Short by construction: none can match a real abstract.
_NO = r"(?:no|not an?|without(?: an?)?|there is no)"
_ABS = r"(?:english )?(?:abstract|summary|extract|résumé|resumen|resumo|riassunto|zusammenfassung|abstrakt|аннотация)"
_ITEM = r"(?:article|paper|chapter|content|item|record|publication|document|contribution|entry|issue|presentation)"
_KEY_PATTERNS = [
    # "No abstract available.", "No abstract is available for this article.", "Without abstract"
    rf"{_NO} {_ABS}(?: is| was| has been)?(?: currently)?(?: available| provided| supplied| present| given| published| included| for perspectives)?(?: for this {_ITEM})?(?: in english)?(?: doi .+)?",
    # "Abstract not available.", "Abstract is not available at this time", "Abstract not provided to SSRN."
    rf"{_ABS}(?: is| was)? (?:not|un) ?(?:available|provided|supplied|applicable|received|given|published)(?: at this time| to ssrn| for this {_ITEM})?(?: disclosure)?",
    # "This article has no abstract", "This article does not have an abstract", "... was submitted without an abstract ..."
    rf"this {_ITEM} (?:has no|does not have an?|was submitted without an?|is without an?) {_ABS}(?: please refer to the full text pdf file| to view the article select the view print version pdf link above)?",
    rf"(?:abstracts|{_ABS}) (?:are|is) not published in this journal",
    r"no extract is available for articles shorter than \d+ words",
    r"keine zusammenfassung(?: verfügbar| vorhanden)?",
    r"résumé non (?:reçu|disponible)",
    r"in japanese",
    r"本記事に 抄録 はありません",
    # a label, a placeholder word or a page furniture line standing alone
    r"abstracts?|summary|graphical abstract|lay summary|background|introduction|conclusions?|"
    r"(?:letter )?to the editor|dear editor|sir|erratum|accepted|received|description definition|"
    r"n ?a|none|nil|null|tb[ad]|not (?:provided|applicable)|no translation|full text available|"
    r"(?:graphical abstract)?display full size|j stage|abstract figure legend|"
    r"摘要|要旨|抄録|はじめに|中图分类号|zusammenfassung|resumen|resumo|résumé|аннотация|\d{1,3}",
    # a meeting abstract's disclosure checkbox standing alone (GIE / DDW, 978 works on 26 Oct; oxjob #1794)
    r"(?:disclosure compliance )?i understand",
]
_KEY_RE = re.compile("|".join(f"(?:{p})" for p in _KEY_PATTERNS))

# Per-page templates, matched (re.match) on the plain text: they need the quotes and punctuation.
_TEMPLATE_RES = [
    # Taylor & Francis SEO line for items without an abstract: '"Title." Journal, 37(180), pp. 89–90'
    re.compile(r'"[^"]{1,400}" [^"]{1,300}, [0-9]+(?: ?\([^)]*\))?, pp?\. ?[0-9ivxlcdm]+(?: ?[–-] ?[0-9ivxlcdm]+)?\.?$'),
    # OUP / IMF SEO line: '"Title" published on <date> by <publisher>.'
    re.compile(r'"[^"]*" published on(?: [^"]{1,40})? by [^"]{1,120}$'),
    # De Gruyter SEO line: 'Article <title> was published on <date> in the journal <journal> (volume 3, issue 2).'
    re.compile(r"(?:article|chapter|book|journal) .{1,500} was published on (?:[a-z]+ \d{1,2}, )?\d{4} in the (?:journal|book|series|edited volume) .{1,300}$"),
    # Springer / Nature author block: 'Authors and Affiliations ... View author publications ...'
    re.compile(r"authors .{0,800}view author publications"),
    # CABI Compendium datasheet stand-in, one per taxon: 'This datasheet on Mesorchis covers Identity, Distribution.'
    re.compile(r"this datasheet on .{1,200} covers [a-z/ ,&()-]{3,400}\.?$"),
    # Meeting-abstract pages with no abstract show a presenter or author line instead (HPB 'Presenter: Nora Singh
    # BA | Hartford Hospital', Endocrine Practice 'Author Block: ...'; ~850 works on 26 Oct, oxjob #1794). Short
    # only: a field that goes on past the byline into the abstract is kept. Never the plain "Author:" label:
    # repository and journal pages start real abstracts with it ("Author: BARBARA SANTICH The French Australian
    # Review 77 ... This article continues ..."; 1,476 DOIs lost theirs to that in the 26 Oct guard re-parse).
    re.compile(r"(?:presenter|presenting author(?: contact details)?|author block|primary author)\s*:.{0,400}$", re.S),
    # CABI book front matter: the publisher's disclaimers (oxjob #1800 EXPLORE § 13, 26 Oct)
    re.compile(r"the views expressed in this (?:publication|book|volume|report|chapter) are those of the author"),
    re.compile(r"the information is supplied without obligation and on the understanding that"),
    # Frontiers article header saved as the abstract: 'EDITORIAL article Front. Neurol., 30 August 2023Sec. Epilepsy
    # Volume 14 - 2023 | https://doi.org/10.3389/fneur.2023.1270702' (16.6K works on 26 Oct, legacy backfill; #1857)
    re.compile(r"[a-z][a-z -]{2,40} article front\. [^,]{2,60}, \d{1,2} [a-z]+ \d{4}.{0,200}?https?://doi\.org/10\.3389/\S+$"),
]

# Platform page furniture anywhere in the text: Silverchair's author card and toolbar ("Search for other works by
# this author on: Oxford Academic Google Scholar", "Cite Icon Cite", "Share Icon Share", "Views Icon Views"). No
# abstract contains these strings; on 26 Oct 2026 ~781K works showed such a page dump as their abstract (OUP 454K,
# UC Press 80K, AIP 40K, Portland 36K, Duke 33K, GSA 20K; all from the legacy abstracts_backfill; #1857 / #1800).
_FURNITURE_RE = re.compile(r"search for other works by this author on|\b(?:cite|share|views) icon (?:cite|share|views)\b")


@cache
def _known() -> frozenset:
    with open(_DATA, encoding="utf-8") as f:  # count, side, text; '#' lines are comments
        return frozenset(key(line.split("\t")[-1]) for line in f if not line.startswith("#"))


def is_not_abstract(text) -> bool:
    """True when text is a placeholder, boilerplate or template, not a work's abstract."""
    if not text or not isinstance(text, str):
        return False
    plain = _plain(text)
    k = _key_of(plain)
    if not k:
        return True  # punctuation or symbols only ('.', '-', '■')
    if k in _known():
        return True
    if len(k) <= 200 and _KEY_RE.fullmatch(k):
        return True
    if _FURNITURE_RE.search(plain):
        return True
    return len(plain) <= 1500 and any(r.match(plain) for r in _TEMPLATE_RES)


def clean_abstract(text):
    """The abstract, or None when it is not one."""
    return None if is_not_abstract(text) else text
