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
_FRONT_PART = r"(?:front cover|cover|table of contents|title page|splash (?:page|screen))"
_ROLES = r"(?:staff|board members|committee members|society officers|editorial board members)"
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
    # IEEE Xplore's whole "abstract" for an advertisement page, the item's kind standing alone like the labels above:
    # "Advertisement.", "Advertisement, IEEE." (#2239 round 6: 3 of 33,557 sampled pages; gold none on both labelled
    # ones). An advertisement given with its text stays.
    r"advertisement(?: ieee)?",
    # IEEE Xplore's stock sentences for front matter: "Presents the table of contents/splash page of the proceedings
    # record.", "Presents the front cover/table of contents for this issue of the periodical.", "The author index
    # contains an entry for each author and coauthor included in the proceedings record.", "Provides instructions and
    # guidelines to prospective authors who wish to submit manuscripts." They say what kind of item it is, not what it
    # says; the stored parse has none on these pages, so none is never worse (#2239 round 8: the loop's call, after
    # check1's tripwire; the gate's gold kept one, the labels most). Exact wordings only: a sentence that goes on is
    # kept. 30 more wordings (editorials, welcome messages) are in KNOWN.
    rf"presents the {_FRONT_PART}(?: (?:or )?{_FRONT_PART})* (?:for|of|from) (?:this issue of the (?:periodical|"
    r"publication|magazine|journal)|the proceedings record|the conference proceedings record|the proceedings of this "
    r"conference)",
    r"the author index contains an entry for each author and coauthor included in the proceedings record",
    r"presents an index of the authors whose articles are published in the conference proceedings record",
    r"provides instructions and guidelines to prospective authors who wish to submit manuscripts",
    r"presents the copyright information for the conference(?: may include reprint permission information)?",
    rf"provides a listing of (?:current )?{_ROLES}(?:(?: and)? {_ROLES})*",
    r"presents a listing of conference committees",
    r"lists the conference organizers sponsors patrons and or committee members",
    r"presents the welcome message from this conference",
    r"provides notice of upcoming conference events of interest to practitioners and researchers",
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
    # A data citation line, as PANGAEA writes its description tag: 'Preßler, Erhard (1992): Tree-ring width of Quercus
    # species ..., PANGAEA, https://doi.org/10.1594/PANGAEA.148663' (3 of 3 such pages read by #2239: gold no abstract)
    re.compile(r"[^():]{2,600} \((?:1[5-9]|20)\d{2}[a-z]?\): .{1,1000}https?://(?:dx\.)?doi\.org/10\.\d{4,9}/\S+$"),
    # Taylor & Francis citation line for older articles without an abstract: '(1983). Title. International Journal of
    # Mental Health: Vol. 12, Mental Health Care in Developing Countries, pp. 1-15.' (#2239)
    re.compile(r"\((?:1[5-9]|20)\d{2}\)\. .{1,600}: vol\. ?\d+.{0,300}, pp?\. ?[0-9ivxlcdm]+(?: ?[–-] ?[0-9ivxlcdm]+)?\.?$"),
    # A book review's heading line: 'Generations on the Land: A Conservation Legacy. By Joe Nick Patoski. 2011. Sand
    # County Foundation/Texas A&M University Press, College Station, TX, USA. 136 p. US$25. hardcover. ISBN 978-...'
    re.compile(r".{1,400}\. by .{1,300}\. (?:1[5-9]|20)\d{2}\. .{1,400}\bisbn[ :-]*[0-9][0-9x-]{9,16}\.?$"),
    # A "no abstract" notice followed by the issue's citation: 'No hay resúmenes disponibles. Investigaciones UCA, Año. 1,
    # Vol. 1, 2019-2020: 48-52.' (OJS, #2239)
    re.compile(r"(?:no hay res[uú]men(?:es)? disponibles?|sin resumen(?: disponible)?|no (?:abstract|summary) (?:is )?"
               r"available|abstract not available|resumo não disponível|résumé non disponible)\.?(?:\s.{0,200})?$", re.S),
    # CABI Compendium datasheet stand-in, one per taxon: 'This datasheet on Mesorchis covers Identity, Distribution.'
    re.compile(r"this datasheet on .{1,200} covers [a-z/ ,&()-]{3,400}\.?$"),
    # Meeting-abstract pages with no abstract show a presenter or author line instead (HPB 'Presenter: Nora Singh
    # BA | Hartford Hospital', Endocrine Practice 'Author Block: ...'; ~850 works on 26 Oct, oxjob #1794). Short
    # only: a field that goes on past the byline into the abstract is kept.
    re.compile(r"(?:presenter|presenting author(?: contact details)?|author block|primary author|authors?)\s*:.{0,400}$", re.S),
    # CABI book front matter: the publisher's disclaimers (oxjob #1800 EXPLORE § 13, 26 Oct)
    re.compile(r"the views expressed in this (?:publication|book|volume|report|chapter) are those of the author"),
    re.compile(r"the information is supplied without obligation and on the understanding that"),
    # Frontiers article header saved as the abstract: 'EDITORIAL article Front. Neurol., 30 August 2023Sec. Epilepsy
    # Volume 14 - 2023 | https://doi.org/10.3389/fneur.2023.1270702' (16.6K works on 26 Oct, legacy backfill; #1857)
    re.compile(r"[a-z][a-z -]{2,40} article front\. [^,]{2,60}, \d{1,2} [a-z]+ \d{4}.{0,200}?https?://doi\.org/10\.3389/\S+$"),
    # Authorea's stand-in for a document with no abstract: 'A document by Carlos Zetina Rosales. Click on the document
    # to view its contents.' (#2239 phase 2)
    re.compile(r"a document by .{1,200}\. click on the document to view its contents\.?$"),
    # Thieme's history and copyright block, read where a page has no abstract: 'Publication History Article published
    # online: 23 September 2025 © 2025. Thieme. All rights reserved. ...' (#2239 phase 2)
    re.compile(r"publication history\b.{0,300}(?:©|\(c\)|all rights reserved)"),
    # Springer's description tag for a chapter or reference-work entry that has no abstract: "'Probenquittierung'
    # published in 'Lexikon der Medizinischen Laboratoriumsdiagnostik'" (#2239 phase 2, round 3: 17 of 33,557
    # sampled pages)
    re.compile(r"'.{1,500}' published in '.{1,500}'\.?$"),
    # Jukuri (Natural Resources Institute Finland): a research note's "abstract" is the citation of the article it
    # reports on, "Seloste artikkelista: Jalkanen, R. ... 2007. ... Silva Fennica 41(4): 755–762." (round 3)
    re.compile(r"seloste artikkelista: .{1,400}$", re.S),
    # (#2239 round 8, from check1's confirmed-worse pages) A source note where the abstract would be: "In: Abstracts of
    # the annual meeting of the Southern African Society for Plant Pathology, Rob Ferreira, p. 27." (Pure portals)
    re.compile(r"in: .{3,300}$", re.S),
    # ... or the meeting's name with the abstract's number: "22 - 62nd Meeting of the Phycological Society of America"
    re.compile(r"(?:\d{1,4} ?[-–] ?)?\d{1,3}(?:st|nd|rd|th) (?:annual |international )?(?:meeting|congress|conference|"
               r"symposium|workshop)\b.{0,150}$"),
    # A notice that the abstract is elsewhere or must be asked for: "L'abstract è presente nell'allegato / the abstract
    # is in the attachment" (IRIS), "Jika membutuhkan abstrak atau isi jurnal silahkan menghubungi author melalui email
    # ..." ("if you need the abstract or the article, contact the author", OJS)
    re.compile(r".{0,120}\b(?:the )?abstract is (?:in|available in|included in|attached in|given in) the "
               r"(?:attach|enclosed|full text|pdf)", re.S),
    re.compile(r".{0,120}\bpresente nell'allegato\b", re.S),
    re.compile(r".{0,80}\b(?:abstra(?:k|ct)|resumen|resumo)\b.{0,80}\b(?:menghubungi|hubungi|contact the authors?|"
               r"contactar (?:al|con el) autor)\b.{0,200}$", re.S),
    # A software notice where the abstract would be: "Для открытия архива необходима программа WinRAR версии 5.0 и
    # выше." ("to open the archive you need WinRAR 5.0 or later", a DSpace repository)
    re.compile(r"(?=.{0,200}(?:необходим|требуется|потрібн|required|needed|you need|must be installed))"
               r".{0,100}\b(?:winrar|7-zip|adobe (?:acrobat )?reader)\b.{0,100}$", re.S),
    # An epigraph alone (a quotation and its author): „Das Geheimnis des Glücks ist die Freiheit, ...“ Perikles
    re.compile(r"[„“\"«][^„“\"«”»]{10,300}[“”\"»]\s*[-–—]?\s*[^\W\d_][\w.' -]{1,60}$"),
    # A corrigendum's body: "The incorrect statement was “...” It was corrected to: ..." (PMC)
    re.compile(r".{0,200}\bthe (?:incorrect|original|erroneous) (?:statement|sentence|text|wording) (?:was|read|reads)\b"
               r".{0,1000}\b(?:corrected to|should (?:have )?read)\b", re.S),
    # A correction notice that cites the corrected article: "Sun J-M, Chao Y, Kim S-B, et al. First-line ... In this
    # Article, ... The file has been corrected as of Feb 2, 2026." (The Lancet)
    re.compile(r"[^\W\d_][\w'’-]+ [a-z]{1,3}(?:-[a-z]{1,2})?, .{0,1300}\b(?:has|have) been corrected\b", re.S),
    # A journal's or site's description of itself where the abstract would be (a journal or portal home page stored
    # for an article): "Beytulhikme An International Journal of Philosophy is a peer-reviewed, hybrid open-access
    # academic journal, ...", "E-Journal IAIN Pekalongan adalah Web Portal yang ..." (#2239 round 8). Not "This
    # journal is ..." nor "In this ...", which an editorial may say of the journal it opens.
    re.compile(r"(?=[^.]{0,300}?(?:journal|portal))(?![\s\S]*\b(?:this|the present|our|we) (?:study|paper|article|analysis|research|work|examine|analy[sz]e)"
               r")(?!this |the present |in this |here )[^.]{0,150}? (?:is|adalah) (?:an? |the )?(?:(?:international|"
               r"peer[- ]reviewed|open[- ]access|hybrid|refereed|scholarly|academic|online|double[- ]blind|scientific|"
               r"bi-?annual|quarterly|multidisciplinary|interdisciplinary)[ ,]*(?:and )?)*(?:journal|web portal|"
               r"portal web)\b"),
    # NIMS MDR's phonon datasets: one generated description per record, the compound and space group filled in: "Ab-initio
    # phonon calculation for BaNd2ZnO5 / I4/mcm (140)\nPhonon band structure, phonon DOS, thermal properties at constant
    # volume, and phonon raw data are presented.\nThe initial crystal structure ... is obtained from the Materials
    # Project using pymatgen MPRester. The phonon band structure paths are determined using SeeK-path." Stock text like
    # Materials Project's description in KNOWN (#2239 round 8: check1's tripwire, 3 records).
    re.compile(r"ab-initio phonon calculation for \S{1,60} / \S{1,30} \(\d{1,3}\) phonon band structure, phonon dos, thermal "
               r"properties at constant volume, and phonon raw data are presented\. the initial crystal structure used to "
               r"perform phonon calculation is obtained from the materials project using pymatgen mprester\. the phonon "
               r"band structure paths are determined using seek-path\.?$"),
    # IntechOpen's author card read under its empty "Abstract": "Author Information Show + Alcínia Zita Sampaio *
    # Department of Civil Engineering, ... Address all correspondence to: ..."
    re.compile(r"author information (?:show|hide)\b"),
]

# Platform page furniture anywhere in a short text: Silverchair's author card and toolbar ("Search for other works by
# this author on: Oxford Academic Google Scholar", "Cite Icon Cite", "Share Icon Share", "Views Icon Views"). On 26 Oct
# 2026 ~781K works showed such a page dump as their abstract (OUP 454K, UC Press 80K, AIP 40K, Portland 36K, Duke 33K,
# GSA 20K; all from the legacy abstracts_backfill; #1857 / #1800). Short only, like the templates: a judge read 200 of
# 200 dumps under 1,500 characters as boilerplate, but 80 of 200 longer ones hold the work's own abstract among the
# furniture (7 of 79 already at 1,500-2,000 characters).
_FURNITURE_RE = re.compile(
    r"search for other works by this author on|\b(?:cite|share|views) icon (?:cite|share|views)\b"
    # Wiley's notice under an article's "Supporting Information" section, read where a page has no abstract with the
    # captions and statements before it ("Figure S1. ...", a data-availability statement) (#2239 phase 2, round 3)
    r"|the publisher is not responsible for the content or functionality of any supporting information supplied by")


# A chapter's list of section headings printed where its abstract would be (Wiley book chapters: "This chapter
# contains sections titled: Introduction ... References"): a table of contents, whatever its length (#2239 phase 2).
_CONTENTS_LIST_RE = re.compile(r"this (?:chapter|article|section|entry) contains sections titled\b")

# Site descriptions the frozen list misses because the site has reworded or translated its blurb since: matched on
# the key's opening, so the next rewording is caught too (#2239 phase 2: Spain's historical-newspaper library in
# English, Galiciana's two added sentences; both are in the list in their 24 Oct wording).
# shortcut: a handful of openings kept by hand (eight by round 4, three of them Galiciana's). Past about ten, build
# the frequency rule named at the top of this module instead.
_SITE_BLURB_STARTS = (
    "the virtual library of historical newspapers bvph managed by the subdirectorate general for library coordination",
    "a biblioteca dixital de galicia forma parte de galiciana",
    # Dresden State Art Collections' object pages and Andalusia's performing-arts archive (#2239 phase 2 round 2)
    "die online collection der staatlichen kunstsammlungen dresden ist das",
    # Spain's bibliographic-heritage library, the newspaper library's sibling, in Spanish and in English
    "la biblioteca virtual del patrimonio bibliográfico gestionada por la subdirección general de coordinación",
    "the virtual library of bibliographic heritage bvpb managed by the subdirectorate general for library",
    "elektra es el archivo digital de las artes esc",
    # Galiciana's blurb as its English pages give it (round 3)
    "the digital library of galicia forms part of galiciana",
    # ... and in Spanish: every record page holds the three wordings, one DC.description tag each (round 4)
    "la biblioteca digital de galicia forma parte de galiciana",
    # (#2239 round 8: check1's tripwire, 3 pages) the Valencian Digital Library's blurb on its record pages
    "the valencian digital library bivaldi is a free access repository whose purpose is",
    "la biblioteca valenciana digital bivaldi",  # ... in Spanish and Valencian, one DC.description tag each
    # medwave.cl's note on its congress lectures, printed under "Resumen": "Este texto completo es la transcripción
    # editada y revisada de la conferencia dictada en ..." (the lecture has no abstract)
    "este texto completo es la transcripción editada y revisada de",
)


# A book-review item's "abstract" that lists the reviewed books: 'Karla Poewe, (ed.), Charismatic Christianity as a
# Global Culture. Columbia, ..., 1994, 300 pp. $34.95, ISBN 0 87249 996 0.' one line per book (#2239 round 8, T&F)
_ISBN_RE = re.compile(r"\bISBN(?:-1[03])?[\s:]*[0-9][0-9Xx -]{8,20}", re.I)


def _is_book_list(text: str) -> bool:
    """True when two or more lines of `text` cite a book by its ISBN and such lines are most of the text."""
    if text.upper().count("ISBN") < 2:
        return False
    lines = [line.strip() for line in _plain_lines(text) if line.strip()]
    cited = [line for line in lines if _ISBN_RE.search(line)]
    return len(cited) >= 2 and sum(map(len, cited)) >= 0.6 * sum(map(len, lines))


def _plain_lines(text: str):
    return re.split(r"\s*(?:\n|<br\s*/?>|</p>\s*<p[^>]*>)\s*", text)


# A list of people's names where the abstract would be (Thieme's eRef: a book's og:description is its contributors:
# "Susanne Andreae, Peter Avelini, Melanie Berg, ...") (#2239 round 8)
_PERSON_NAME_RE = re.compile(r"(?:[A-ZÀ-Ý][^\W\d_'’.-]*[.'’-]?\s?){1,2}(?:(?:von|van|de|der|den|da|di|du|le|la|zu) )?"
                             r"[A-ZÀ-Ý][^\W\d_'’-]+(?:[-'’][A-ZÀ-Ý]?[^\W\d_]+)?")


_PROSE_WORDS_RE = re.compile(r"\b(?:the|of|in|is|are|was|were|with|for|to)\b")


def _is_name_list(text: str) -> bool:
    """True when `text` is only people's names separated by commas (eight or more)."""
    if text.count(",") < 7 or len(text) > 3000 or _PROSE_WORDS_RE.search(text):
        return False
    items = [item.strip() for item in re.split(r",|;|\bund\b|\band\b", text.strip().rstrip("."))]
    return len(items) >= 8 and all(_PERSON_NAME_RE.fullmatch(item) for item in items)


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
    if k in _known() or k.startswith(_SITE_BLURB_STARTS):
        return True
    # Digital Commons (bepress) record pages that have no abstract describe the item with its opening paragraph and
    # say so: "(First paragraph) Plucking chickens the kosher way ..." An opening the page marks as such is body
    # text, not the abstract (oxjob #2162's rule; seen by #2239 on repository pages).
    if plain.startswith("(first paragraph)") or _CONTENTS_LIST_RE.match(plain):
        return True
    if len(k) <= 200 and _KEY_RE.fullmatch(k):
        return True
    if _is_book_list(text) or _is_name_list(text):
        return True
    return len(plain) <= 1500 and (bool(_FURNITURE_RE.search(plain)) or any(r.match(plain) for r in _TEMPLATE_RES))


# --- Markup and page text glued onto an abstract (oxjob #2239, phase 2) ---------------------------------------------
# Meta tags often hold the abstract as HTML or JATS ("<p><strong>Abstract.</strong> ...</p>", "<h3>Background</h3>",
# "CO<sub>2</sub>", "&nbsp;"), and a reader that takes a page block takes the page's own text with it. On a random
# 33,557 stored pages: 261 abstracts with raw tags, 142 ending in Springer's machine-keywords disclaimer, 28 in IGI
# Global's access notice, 16 starting with ACS's figure toolbar. An abstract is plain text.

# A tag as markup writes it: a bare name, a closing tag, or a name with quoted attributes. "<Frankfurt, Main>",
# "<https://github.com/...>", "<Delta z = 0.3>" and "a<b and c>d" are not that shape.
_TAG_NAME = r"[a-zA-Z][\w:.-]*"
_MARKUP_RE = re.compile(rf"""<(/?)({_TAG_NAME})(\s+[\w:.-]+\s*=\s*["'][^<>]*|\s*/?)>""")
_CLOSER_RE = re.compile(rf"<(?:/({_TAG_NAME})\s*|({_TAG_NAME})\s*/)>")  # </i>, and HAL's <i/>
# An entity with its ';': the "&copy=2&region=eu" of a URL is not one.
_ENTITY_RE = re.compile(r"&(?:#\d{1,7}|#[xX][0-9a-fA-F]{1,6}|[a-zA-Z][a-zA-Z0-9]{1,31});")
_VOID_TAGS = frozenset("br hr img wbr".split())  # never closed
_BREAK = "\x00"  # where a block tag stood, until the lines are built
# Elements that start a new line (HTML, and JATS's sec / title / list-item); other markup closes up, as
# CO<sub>2</sub> must.
_BLOCK_TAGS = frozenset(
    "abstract address article aside blockquote br dd div dl dt figcaption figure footer h1 h2 h3 h4 h5 h6 header hr "
    "li list list-item ol p pre sec section table td th title tr ul".split())
# The label a tag or a glued prefix set apart from the text: "<p>Abstract</p>", "<strong>Abstract.</strong>". Only
# with its own punctuation or line: "Abstract interpretation is ..." is a sentence.
_LABEL_RE = re.compile(r"^abstract\s*(?:[:.]\s*|\n)", re.I)

# Page text glued to the abstract's start or end, exact wordings only. Each site's own reader leaves its notice
# out too; these cover the generic readers, which take the same block or tag.
# shortcut: one phrase per site, added as a sample shows it. Fine for a handful; past that, drop link-only and
# figure blocks in the generic block reader instead.
_GLUED_START_RE = re.compile(
    r"^\s*(?:High Resolution Image\s+Download MS PowerPoint Slide\s+"  # ACS: the graphical abstract's toolbar
    r"|CiteSeerX - Document Details \([^()]{1,300}\):\s*"  # CiteSeerX's description tag
    # (#2239 round 8, from check1's confirmed-worse pages and tripwire groups)
    # MS Word's style sheet pasted with the abstract: "Normal 0 false false false BS-LATN-BA X-NONE X-NONE /* Style
    # Definitions */ table.MsoNormalTable {mso-style-name:"Table Normal"; ...}" (OJS, DergiPark)
    r"|Normal\s+0\s+(?:[\d.]+\s*(?:pt)?\s+)?false\s+false\s+false\s+(?:(?:[A-Z]{2,3}(?:-[A-Z]{2,4}){0,2}|X-NONE"
    r"|MicrosoftInternetExplorer\d)\s+)*(?:/\*\s*Style Definitions\s*\*/\s*)?(?:[\w.#:-]+(?:\s*,\s*[\w.#:-]+)*\s*"
    r"\{[^{}]{0,3000}\}\s*)*"
    # (Not Cochrane's "This is a protocol for a Cochrane Review (...). The objectives are as follows:": the page shows
    # it as the protocol's abstract and label-v2 keeps it, #2239 round 8c.)
    # JMIR Preprints' warning before the abstract
    r"|#Preprint #PeerReviewMe: Warning: This is a\s+unreviewed preprint\.[\s\S]{0,1000}?\(if you are the "
    r"author\)\.\s*"
    # an editor's correction note run onto the abstract: "Correction: On 16th February 2017, the author K. Peiris was
    # removed from this paper. ... This error is regretted. - Editor" (DOAJ)
    r"|(?:Correction|Corrigendum|Erratum)\s*:\s[^\n]{0,600}?\bThis error is regretted\.(?:\s*[-–—]\s*(?:The )?"
    r"Editors?(?![a-z]))?\s*"
    # a retraction notice in its own paragraph before the abstract (Emerald: "Retraction Notice: The publisher wishes
    # to retract the chapter ... agree with the retraction.")
    r"|Retraction (?:Notice|Note|Statement)\s*:\s[^\n]{20,3000}\n\s*(?=\S[^\n]{200}))")
_GLUED_END_RE = re.compile(
    # Springer: machine-chosen keywords and their disclaimer, printed inside the abstract's section
    r"(?:(?:\bKeywords\b[^.]{0,600})?These keywords were added by machine and not by the authors\.\s*This process "
    r"is experimental and the keywords may be updated as the learning algorithm improves\.?"
    # IGI Global: the paywall's notice inside the abstract's element
    r"|Request access from your librarian to read this (?:chapter|article|book|title)['’]s full text\.?"
    # SPIE Digital Library: the eBook access notice after a chapter's abstract
    r"|Online access to SPIE eBooks is limited to subscribing institutions\.?"
    # the publisher's copyright line after the abstract (#2239 phase 2, round 3). APS, as LaTeX: "\textcopyright{}
    # 1996 The American Physical Society."; Wiley's accepted articles, also on repository copies
    r"|\\textcopyright\s*(?:\{\})?\s*(?:1[89]|20)\d{2} [^.\\]{3,80}\.?"
    r"|This article is protected by copyright\. All rights reserved\.?"
    # Thieme: the history, copyright or licence lines and the publisher's address, read from the abstract's block
    r"|(?:\bPublication History\b[^©]{0,200})?©\s?\d{4}\.[^©]{0,700}?\bGeorg Thieme Verlag(?: KG)?\b[^©]{0,100}"
    # (#2239 round 8, check1's tripwire groups) The FASEB Journal's note under a meeting abstract; Monthly Review's
    # archive notice
    r"|This abstract is from the [^.]{3,120} Meeting\. There is no full text article associated with this abstract "
    r"published in The FASEB Journal\.?"
    r"|This article can also be found at the Monthly Review website, where most recent articles are published in "
    r"full\.\s*Click here to purchase a PDF version of this article at the Monthly Review website\.?)\s*$")
# _GLUED_END_RE can start anywhere, so it scans the whole text: it runs only on a text that ends like one of its
# notices.
_GLUED_END_TAILS = ("improves.", "improves", "full text.", "full text", "institutions.", "institutions",
                    "All rights reserved.", "All rights reserved", "Stuttgart, Germany", "Stuttgart, Germany.",
                    "The FASEB Journal.", "The FASEB Journal", "Monthly Review website.", "Monthly Review website")


# A whole title page where the abstract should be (Dove Medical Press records on DOAJ): the byline, the numbered
# affiliations and "Correspondence: ... Email ...", then "Abstract:" and the text, then "Keywords: ...". The label is
# what marks the text's start; where the page's e-mail protection swallowed it, "[email protected] :" does.
_TITLE_PAGE_RE = re.compile(
    r"^.{20,4000}?Correspondence:\s.{0,1500}?(?:Abstract\s*:|\[email\s+protected\]\s*:)\s*(?=\S)", re.S)
_KEYWORDS_TAIL_RE = re.compile(  # in the languages such pages were pasted in (round 4: Turkish)
    r"\s*\b(?:Keywords|Anahtar [Kk]elimeler|Palabras clave|Palavras-chave|Mots[- ]clés)\s*:[^\n]{0,600}$")


# The same title page with no "Abstract:" label (round 3): the text opens with the byline and its affiliation numbers
# ("Ming Guan,1,2 Yangmengfan Chen,1 ..."), and a structured abstract's first label stands glued to the address or
# e-mail before it ("... People's Republic of ChinaBackground: ...", "...@gmail.comPurpose: ...").
_BYLINE_START_RE = re.compile(r"[^\d:.]{3,60}(?:,\d|\d,)")  # "Ming Guan,1,2", and "Omary Mashiku Minzi1, Deus Buma2"
# ... and the abstract's own label after the affiliations, unglued: "..., Henan 463000, China Abstract: The miR17-92
# family ..." (Dove Medical Press records on DOAJ; #2239 round 8)
_BYLINE_ABSTRACT_LABEL_RE = re.compile(r"(?<=\S)\s+Abstract\s*:\s+(?=\S)")
_GLUED_PART_LABEL_RE = re.compile(
    r"(?<=[a-z])(?=(?:Background|Purpose|Objectives?|Introduction|Aims?|Context|Importance|Rationale)\s*:\s)")
_GLUED_KEYWORDS_TAIL_RE = re.compile(r"(?<=[a-z.)\]])Keywords\s*:[^\n]{0,600}$")
# A pasted page (round 4, AVESIS: a congress's name, dates and address, the title, the byline and the affiliation,
# then the abstract): the abstract's own label stands glued to the last word before it, alone at its line's end
# ("... İç Hastalıkları Ana Bilim DalıÖzet\n"), and the keyword line closes the text after a blank line.
_GLUED_ABSTRACT_LABELS = ("Abstract", "Summary", "Özet", "Resumen", "Resumo", "Résumé", "Zusammenfassung")
_GLUED_ABSTRACT_LABEL_RE = re.compile(r"(?<=[^\W\d_])(?:" + "|".join(_GLUED_ABSTRACT_LABELS) + r")[ \t\r]*\n")


# The keyword line printed after the abstract in the same field or paragraph, with whatever the page put after it (a
# DOI, the history dates): "... are presented. Keywords: analytical microsystem-on-chip, ..." (DOAJ), "...\nKata Kunci:
# Sistem Pendukung Keputusan, ..." (OJS). The rubric leaves keywords out. The heading readers stop at a paragraph that
# opens with the label; this covers the label inside the text, whichever reader found it (#2239 round 6: 205 of
# 18,463 sampled abstracts; on the 50 labelled ones 5 become right and none wrong). The label must open a sentence or
# a line ("searched with the keywords: asthma, ..." is a sentence) and stand in the text's last 600 characters, after
# its first 100: a "Keyword:" row in a thesis's front block, before the abstract, is not a tail.
# shortcut: the last label only. "Keywords: ...\nKata kunci: ..." keeps the first line; cutting at the first label
# would also cut a short second-language abstract printed between two keyword lines.
_KEYWORD_TAIL_MAX = 600
_KEYWORD_TAIL_RE = re.compile(
    r"(?:(?<=[.!?。)\]”\"’'])[ \t\xa0]*|\s*\n\s*|[ \t\xa0]{2,})"
    r"(?:key[ -]?words?|index terms|palavras?[- ]chaves?|palabras?[- ]claves?|mots?[- ]cl[ée]s?|schl[üu]sselw[öo]rter"
    r"|parole chiave|ключевые слова|ключові слова|anahtar (?:kelimeler|sözcükler)|kata kunci|słowa kluczowe)"
    r"[ \t\xa0]*[:：]", re.I)


# A section the page prints after the abstract in the same field or block, which the rubric leaves out: highlights,
# a plain-language summary, key messages, a mathematics subject classification (#2239 round 8: DOAJ "HIGHLIGHTS ...",
# Karger "Plain Language Summary. ...", SIAM "MSC codes 39A10 39A12 Keywords ..."). The label must open a sentence or
# a line and stand after the abstract's first 100 characters, with its own punctuation or line, so "plain language
# summaries" inside a sentence stays.
_TRAILING_SECTION_RE = re.compile(
    r"(?:(?<=[.!?。)\]”\"’'])[ \t\xa0]*|\s*\n\s*)"
    r"(?:HIGHLIGHTS\b|Highlights[ \t]*(?::|\n)|(?:Plain[- ]Language|Plain English|Lay) Summary[ \t]*(?:[.:]|\n)"
    r"|Key (?:messages|points)[ \t]*(?::|\n)"
    r"|(?:MSC(?: \d{4})? codes?|AMS subject classifications?|Mathematics Subject Classifications?(?: \(\d{4}\))?)"
    r"[ \t]*:?[ \t]*\d{2}[A-Z0-9-]\d)")
_TRAILING_SECTION_WORDS = ("HIGHLIGHTS", "Highlights", " Summary", "Key messages", "Key points", "MSC", "AMS subject",
                           "Mathematics Subject")
# The FASEB Journal's citation line run onto the abstract's last sentence: "... remain unexplained.-Chatel, B.,
# Bendahan, D., ... Messonnier, L. A. Role of MCT1 and CAII in skeletal muscle pH homeostasis ..." (repository copies)
_CITATION_TAIL_RE = re.compile(
    r"(?<=[.!?])\s?[-—–]\s?(?:[^\W\d_][\w'’ -]{1,40}, (?:[^\W\d_]{1,2}\.[ -]?){1,3}, ){2,}[^\n]{0,600}$")


def _without_trailing_section(text: str) -> str:
    """`text` up to a highlights, plain-language-summary, key-messages or subject-classification section, or a
    citation line glued on; `text` itself when it has none."""
    m = _TRAILING_SECTION_RE.search(text, 100) if any(w in text for w in _TRAILING_SECTION_WORDS) else None
    if m and m.start() >= 100:
        text = text[:m.start()].rstrip()
    if "., " in text[-700:] and (m := _CITATION_TAIL_RE.search(text, max(len(text) - 700, 100))):
        text = text[:m.start()].rstrip()
    return text


def _without_keyword_tail(text: str) -> str:
    """`text` up to the keyword line that closes it; `text` itself when it has none."""
    start = max(len(text) - _KEYWORD_TAIL_MAX, 100)
    if ":" not in text[start:] and "：" not in text[start:]:
        return text
    last = None
    for last in _KEYWORD_TAIL_RE.finditer(text, start):
        pass
    return text[:last.start()].rstrip() if last else text


def _without_title_page(text: str) -> str:
    """The abstract out of a title page glued around it; `text` itself when it is not that shape."""
    m = _TITLE_PAGE_RE.match(text) if "Correspondence:" in text[:4000] else None
    if m is None and _BYLINE_START_RE.match(text):
        m = _GLUED_PART_LABEL_RE.search(text, 100, 4000) or _BYLINE_ABSTRACT_LABEL_RE.search(text, 100, 4000)
    # (the plain word test first: the pattern opens with a lookbehind, so a search tries every position)
    if m is None and "\n" in text and any(label in text for label in _GLUED_ABSTRACT_LABELS) and (
            glued := _GLUED_ABSTRACT_LABEL_RE.search(text, 20, 4000)) and text[glued.start() - 1].islower():
        m = glued  # glued to a lower-case word only: "... of DNAAbstract" ends an acronym
    if not m or len(text) - m.end() < 200:
        return text
    return _GLUED_KEYWORDS_TAIL_RE.sub("", _KEYWORDS_TAIL_RE.sub("", text[m.end():]))


def _strip_tags(text: str) -> str:
    """Block tags become line breaks, other tags close up. A bare "<name>" counts as a tag when the text also closes
    it, when it is a void element, or when it opens the text (a wrapper whose end was cut off): "the mean <p>",
    "X_<steam>" and "an <EOS> token" are text."""
    closed = {(a or b).lower() for a, b in _CLOSER_RE.findall(text)}
    opening = len(text) - len(text.lstrip())  # where the text itself starts

    def swap(m):
        closing, name, rest = m.group(1), m.group(2).lower(), m.group(3).strip()
        local = name.rsplit(":", 1)[-1]  # jats:p, mml:mi
        if not (closing or rest or local in _VOID_TAGS or name in closed or m.start() == opening):
            return m.group(0)
        return _BREAK if local in _BLOCK_TAGS else ""

    return _MARKUP_RE.sub(swap, text)


def _markup_to_text(text: str) -> str:
    """`text` as a browser shows it: tags read (see _strip_tags), entities decoded, spaces collapsed, one line per
    block (the source's own line breaks are spaces then). A text with neither tags nor entities comes back
    untouched."""
    original = text
    for _ in range(3):  # markup escaped again inside the tag ("&lt;p&gt;", "&amp;lt;SUB&amp;gt;") comes out too
        stripped = _strip_tags(text) if "<" in text else text
        text = _ENTITY_RE.sub(lambda m: html.unescape(m.group(0)), stripped) if "&" in stripped else stripped
        if text == stripped:
            break
    if text == original:
        return original
    lines = (" ".join(line.split()) for line in text.split(_BREAK if _BREAK in text else "\n"))
    return "\n".join(line for line in lines if line)


def clean_abstract(text):
    """The abstract as plain text, without page text glued to it; None when it is not an abstract."""
    if is_not_abstract(text):
        return None
    if not text or not isinstance(text, str):
        return text
    cleaned = _without_title_page(_GLUED_START_RE.sub("", _markup_to_text(text)))
    if cleaned.rstrip().endswith(_GLUED_END_TAILS) or "\\textcopyright" in cleaned[-160:]:
        cleaned = _GLUED_END_RE.sub("", cleaned)
    cleaned = _without_keyword_tail(_without_trailing_section(cleaned))
    if cleaned == text:
        return text
    cleaned = _LABEL_RE.sub("", cleaned.strip()).strip()
    return cleaned if cleaned and not is_not_abstract(cleaned) else None
