import bisect
import copy
import re
from abc import ABC, abstractmethod

from bs4 import Comment

from parseland_lib.elements import AuthorAffiliations, Author
from parseland_lib.legacy_parse_utils.fulltext import \
    parse_publisher_fulltext_location
from parseland_lib.legacy_parse_utils.strings import cleanup_soup
from parseland_lib.abstract_language import foreign_share, is_english, is_other_language
from parseland_lib.not_abstract import is_not_abstract
from parseland_lib.publisher.parsers.utils import remove_parents, strip_seq, \
    strip_prefix, \
    is_h_tag


# Containers that hold a work's own full text or a post's body (oxjob #2239): JAMA div.article-full-text, Cell Press
# section#bodymatter, WordPress div.entry-content / .post-content.
_BODY_CONTAINER = re.compile(
    r"(?:^|[\s_-])(?:article-full-?text|full-?text|bodymatter|body-matter|entry-content|post-content|article-body|"
    r"articlebody|main-text)(?:$|[\s_-])", re.I)


# A heading or label that names the abstract section, alone (#2239). English plus the languages repository pages
# in the random sample print it in.
_ABSTRACT_HEADING = re.compile(
    r"^\s*(?:abstracts?|résumé|resumen|resumo|riassunto|zusammenfassung|abstrakt|streszczenie|samenvatting|"
    r"sammanfattning|tiivistelmä|аннотация|анотація|özet|摘要|要旨|抄録|초록|요약)\s*[:.]?\s*$", re.I)
# The English heading: on a page that prints "Resumen" and "Abstract", the text under this one is the English version.
_ENGLISH_HEADING = re.compile(r"^\s*abstracts?\s*[:.]?\s*$", re.I)
# "Summary" heads the English version on pages that print "Resumen" / "Résumé" / "Zusammenfassung" for the other one
# (older SciELO pages, French and German journals). It also heads plain-language summaries, so it counts only beside
# an abstract in another language and when its text reads as English (#2239 phase 2, round 3).
_SUMMARY_HEADING = re.compile(r"^\s*summary\s*[:.]?\s*$", re.I)
# The label a structured abstract's part opens with ("Introduction.", "Aim:", "Material and methods."): its parts
# follow, one block each.
_PART_LABEL = re.compile(
    r"\s*(?:introduction|background|aims?|objectives?|purpose|context|rationale|(?:materials? and )?methods?|"
    r"(?:patients|subjects|design|setting) and methods|results?|findings|discussion|conclusions?)\s*[.:]", re.I)
# A cut teaser's end: "...", "…", and MDPI's "[...]" after an editorial's first sentence.
_CUT_ENDS = ("...", "…", "[...]", "[…]")
_LEADING_LABEL = re.compile(r"^abstract[:.]?\s*", re.I)
# Tag names that hold an abstract's language versions (never the page-level description tags).
_ABSTRACT_VERSION_TAGS = ("citation_abstract", "dcterms.abstract", "dc.description.abstract", "dc.description",
                          "eprints.abstract")
# Another section's label where the abstract's text should start: the "Abstract" value was empty and the block
# after it is the reference list or the keyword line (OJS "Resumo" with no text, then "Referências Batty, M. ...").
# Not "References to the classical authors are ...": the label is followed by a colon or a capital.
_OTHER_SECTION_START = re.compile(
    r"(?i:references?|refer[êe]ncias|bibliograf[íi]a|key ?words?|palavras[- ]chave|palabras clave|mots[- ]cl[ée]s)"
    r"\s*(?::|\s(?=[A-Z0-9\[(]))")


_HEADING_TAG = re.compile(r"^h[1-6]$")
_LAY_SUMMARY_HEADING = re.compile(
    r"^\s*(?:(?:simple|lay|plain[- ]language|plain english|author) summary|graphical abstract|highlights)\s*[:.]?\s*$",
    re.I)
_INLINE_RUN = frozenset("a abbr b cite em i mark q small span strong sub sup u".split())


def _tag_language(tag):
    return (tag.get("xml:lang") or tag.get("lang") or "").lower()


def _translation_length(text, first):
    """True when `text` is as long as a translation of `first` would be. Chinese and Japanese abstracts are a third
    of their English version's length."""
    lo, hi = (0.5, 6) if foreign_share(first) >= 0.5 else (0.4, 2.5)
    return lo <= len(text) / len(first) <= hi


# Meta tags that often hold one part of the abstract a page prints whole (see whole_printed_abstract).
_PART_SOURCE_TAGS = re.compile(
    r"^(?:description|og:description|twitter:description|citation_abstract|dc\.description|dcterms\.abstract)$", re.I)


_SECTION_STOP = {"h1", "h2", "h3", "h4", "h5", "h6", "dt", "th", "header", "footer", "nav", "aside", "form", "button"}
# Site chrome, not content: a tab strip's labels, menus, footers. Not "tab-pane" / "article-header": abstracts live
# inside those (Zenodo prints its abstract in an HTML5 <header>). Nor a class that only says the layout HAS a sidebar
# ("has_sidebar", "with-sidebar", "no-sidebar"): that element is the page's content column, with the article in it
# (OJS 3 wraps every article page in <div class="pkp_structure_content has_sidebar">) (#2239 phase 2, round 4).
# shortcut: three words that may stand before "sidebar"; "has-left-sidebar" still reads as chrome. The upgrade is to
# stop the climb in _in_page_chrome at the page's main column (<main>, role="main"): what is named like chrome above
# that is layout. It changes every page whose main column sits in such a wrapper, so it needs its own measurement.
_CHROME = re.compile(r"(?:^|[\s_-])(?:nav|navbar|menu|footer|site-header|page-header|masthead|breadcrumbs?|tabs|"
                     r"tablist|nav-tabs|toolbar|(?<!has[_-])(?<!with[_-])(?<!no[_-])sidebar|modal|dropdown)"
                     r"(?:$|[\s_])", re.I)
# A heading that names the authors' biographies, in the wordings stored pages print it in (Open Journal Systems'
# "Biografia do Autor" / "Author Biographies" / "Biografía del autor/a" ... block follows the abstract's; custom themes
# say "About the Author(s)"). The block under it is never the abstract (#2239 phase 2, round 4).
_AUTHOR_BIO_WORDS = (
    r"(?:author(?:s|['’]s?)?\s+bio(?:graph(?:y|ies)|\(s\)|s)?|about\s+the\s+authors?(?:\(s\))?"
    r"|biogra(?:f[ií]a|phie|fie|m|my)\s+(?:d[oae]s?\s+|del?\s+(?:l[ao]s?\s+|l['’]\s?)?)?"
    r"(?:autor(?:a|es|[óo]w|/a|/es|\(a\)|\(es\))?|auteure?s?|auteur-e)"
    r"|sobre\s+(?:[oa]s?|el|l[ao]s?)\s+autor(?:a|es|as|/a|\(es\))?|autor(?:/innen|en|innen)?-?biografien?"
    r"|biographische\s+angaben|notes?\s+biographiques?|f[öo]rfatt[ae]rbiografi(?:er)?"
    r"|біографі[яї]\s+автор(?:а|ів)|биографи[яи]\s+автор(?:а|ов)|сведения\s+об\s+автор(?:е|ах)|об\s+автор(?:е|ах)"
    r"|szerz[őo]\s+életrajz(?:a|ok)?|információk\s+a\s+szerz[őo]k?r[őo]l|kirjoittajan\s+esittely"
    r"|muallif\s+tarjimai\s+holi|السيرة\s+الشخصية\s+للمؤلف|ประวัติผู้แต่ง|作者简介|biograph(?:y|ies))")
_AUTHOR_BIO_HEADING = re.compile(r"^\s*" + _AUTHOR_BIO_WORDS + r"\s*[:.]?\s*$", re.I)
_AUTHOR_BIO_START = re.compile(r"\s*" + _AUTHOR_BIO_WORDS, re.I)
_AUTHOR_BIO_CLASS = re.compile(r"author[_-]?bios?(?:$|[\s_-])|author[_-]?biograph", re.I)
# An element named for the keyword list (Esploro's <mulo-keywords>, JATS-like "kwd-group", class="keywords"): printed
# inside the abstract's block on some templates, never abstract text.
_KEYWORDS_NAME = re.compile(r"keywords?(?:$|[\s_-])|kwd", re.I)
_ABSTRACT_NAME = re.compile(r"abstract|description|summary|resum", re.I)
# A paragraph that opens with the keyword label ends the abstract's paragraphs ("Palavras-chave: ...", "Keywords : ...").
_KEYWORD_LINE = re.compile(
    r"^\s*(?:key[ -]?words?|index terms|palavras?[- ]chaves?|palabras?[- ]claves?|mots?[- ]cl[ée]s?|schl[üu]sselw[öo]rter"
    r"|parole chiave|ключевые слова|ключові слова|anahtar (?:kelimeler|sözcükler)|kata kunci|słowa kluczowe)\s*[:：]",
    re.I)


def _ident(node):
    """An element's id and classes as one string, for matching its role by name."""
    return " ".join([node.get("id") or ""] + (node.get("class") or []))


def _in_page_chrome(el):
    node = el
    while node is not None and node.name not in ("body", "html", "[document]"):
        if node.name in ("nav", "footer", "aside", "menu", "select"):
            return True
        if node.get("role") in ("navigation", "banner", "tablist", "tab", "menu", "menubar"):
            return True
        if _CHROME.search(_ident(node)):
            return True
        node = node.parent
    return False


# Blocks that show other works than the page's own: related-article panels, recommendations, listings, citing works,
# peer-review reports (#2239: on publisher pages an "Abstract" heading also labels these).
_OTHER_WORKS = re.compile(r"related|recommend|similar|also-?read|more-?(?:from|like)|you-?may|trending|popular|"
                          r"most-?(?:read|cited|viewed)|listing|search-?result|toc|table-?of-?contents|issue-?items?|"
                          r"citing|cited-?by|peer-?review|reviewer|referee|decision-?letter|carousel|teaser", re.I)


# The article's history and copyright lines printed in the abstract's block (APS: '... Received 15 February 2005 DOI:
# https://doi.org/... ©2005 American Physical Society'): not abstract text.
# So are the keyword line and a trailing download link ("... Keywords : Tumor immune microenvironment, ...", "... Download").
_ARTICLE_HISTORY_TAIL = re.compile(
    r"\s(?=(?:Received|Accepted|Published)(?: online)?:? \d{1,2} [A-Z][a-z]+ \d{4}|©\s?\d{4}|DOI: https?://"
    r"|Key ?words?\s*:|Download(?: PDF| full text| article)?$)", re.I)


def _trim_article_tail(text):
    """`text` up to the first history / copyright / keyword / download tail that starts after its 100th character."""
    m = _ARTICLE_HISTORY_TAIL.search(text, 100)
    return (text[:m.start()] if m else text).strip()


def _in_other_works_block(el):
    """True when an ancestor of `el` (not `el` itself) names itself a block of other works. Run after
    _in_page_chrome, which already rules out <aside>."""
    node = el.parent
    while node is not None and node.name not in ("body", "html", "[document]"):
        if _OTHER_WORKS.search(_ident(node)):
            return True
        node = node.parent
    return False


_CLOSING = tuple(".!?)]\"”’'。")


def _is_cut_preview(text):
    """A preview cut short: it ends in "..." / "…" or mid-sentence. A chapter's or article's opening, not its
    abstract (World Scientific: 275 of 277 real abstracts in its sample end with closing punctuation)."""
    text = text.rstrip("\n")  # as "$" would: it also matches before a final newline
    return text.endswith(("…", "….", "...")) or not text.endswith(_CLOSING)


def _is_author_bio_block(block, text):
    """True when `block` is the authors' biographies: its class says so (OJS: <section class="item author_bios">) or
    it opens with a heading that does ("Biografia do Autor", "Author Biographies", "About the Author(s)")."""
    if _AUTHOR_BIO_CLASS.search(_ident(block)):
        return True
    if not _AUTHOR_BIO_START.match(text):
        return False  # both tests below need the text to open with such a wording: no search for a heading
    if _AUTHOR_BIO_HEADING.match(text):
        return True  # the block is that heading alone ("<p><strong>Author Biography</strong></p>")
    head = block.find(_HEADING_TAG)
    label = head.get_text(" ", strip=True) if head is not None else ""
    return len(label) <= 60 and text.startswith(label) and bool(_AUTHOR_BIO_HEADING.match(label))


def _is_label_wrapper(node, heading):
    """True when `node` holds the label `heading` and nothing else printed (a wrapper around a wrapper)."""
    if node.name in ("body", "html", "[document]"):
        return False
    label, seen = heading.get_text(" ", strip=True), ""
    for string in node.stripped_strings:  # stops at the first text past the label: `node` may be the whole page
        seen = f"{seen} {string}".strip()
        if len(seen) > len(label):
            return False
    return seen == label


def _text_under_label(heading, block=None):
    """The text `heading` labels: what follows it, or, when it sits alone in a label wrapper, what follows the wrapper;
    the wrapper may sit in one more that holds the label and nothing else ("<p><strong><em>Abstract</em></strong></p>").
    Never from outside `block`, the abstract's own container when the caller knows it: what follows that is another
    section (#2239 round 4). None and '' as _text_after gives them."""
    text, wrapper = _text_after(heading), heading.parent
    if text is None and wrapper is not block:
        text = _text_after(wrapper)
        if text is None and wrapper.parent is not block and _is_label_wrapper(wrapper.parent, heading):
            text = _text_after(wrapper.parent)
    return text


def _is_keyword_list(el):
    """True for a block element named for the keyword list and not for the abstract too ("abstract-and-keywords")."""
    names = f"{el.name} {_ident(el)}"
    return el.name not in _INLINE_RUN and bool(_KEYWORDS_NAME.search(names)) and not _ABSTRACT_NAME.search(names)


def _text_without_keywords(block):
    """`block`'s text without the keyword list printed inside it, when one of its children is named for one (Esploro:
    <esp-description-and-keywords><mulo-keywords>...</mulo-keywords><mulo-expandable class="abstract">...), else all
    of its text."""
    # shortcut: direct children that are blocks only (a <span class="keyword"> inside a sentence is a highlighted
    # word, and stays); a keyword list nested deeper in the block, or in a <span>, is still read.
    if not any(_is_keyword_list(el) for el in block.find_all(True, recursive=False)):
        return block.get_text(" ", strip=True)
    block = copy.copy(block)  # never edit the page other readers use
    for el in block.find_all(True, recursive=False):
        if _is_keyword_list(el):
            el.decompose()
    return block.get_text(" ", strip=True)


def _text_after(anchor):
    """The block that follows `anchor`: its first non-empty sibling (bare text runs until the next element), plus
    the paragraphs that continue it. None when `anchor` has no following element (look one level up); '' when the
    value it labels is empty (a label/value row with no value: never read on into the next field)."""
    parts, first = [], None
    # the heading's own container says "abstract": every <section> beside the heading is part of it (#2239)
    structured = anchor.parent is not None and "abstract" in _ident(anchor.parent).lower()
    # the value is bare text with inline markup in it ("<strong>Abstract:</strong> ... 5/0 Vicryl<sup>®</sup> sutures
    # ..."): it runs on through the text and inline elements that follow, to the next block (#2239: Dove Press)
    inline_run = skipped = empty_block = div_parts = False
    first_attrs = None
    for sib in anchor.next_siblings:
        name = getattr(sib, "name", None)
        if name is None:
            if isinstance(sib, Comment):
                continue  # not printed: PubMan's "<!-- Iterator for abstracts -->" opened every MPG abstract (#2239)
            t = str(sib).strip()
            if t and (first is None or inline_run):
                parts.append(t)
            continue
        if name in _SECTION_STOP or name in ("script", "style", "noscript", "template"):
            break
        # the block the text starts in may print the keyword list too: never abstract text (#2239 round 4)
        t = _text_without_keywords(sib) if first is None else sib.get_text(" ", strip=True)
        if name == "tr" and sib.find("th") is not None and sib.find("td") is not None:
            # a label / value row (WEKO repositories: <th>Description</th><td>the abstract</td> in the row after
            # the one that types it "Abstract"): the value cells are the text, not the row's own label (#2239)
            t = " ".join(td.get_text(" ", strip=True) for td in sib.find_all("td")).strip()
            if not t and first is None:
                return ""  # the labelled value is empty
        if name == "section" and structured and t:
            # a part of the abstract's container with its own heading: a lay summary is not the abstract (the
            # rubric leaves plain-language summaries out; PMC prints MDPI's "Simple Summary" first), and the
            # part headed "Abstract" is, without that label (#2239)
            part_heading = sib.find(_HEADING_TAG)
            label = part_heading.get_text(" ", strip=True) if part_heading is not None else ""
            if _LAY_SUMMARY_HEADING.match(label):
                skipped = True
                continue
            if _ABSTRACT_HEADING.match(label) and t.startswith(label):
                t = t[len(label):].strip()
        if first is None:
            if not t:
                if name in ("td", "dd") or "value" in " ".join(sib.get("class") or []):
                    return ""  # the labelled value is empty
                # an empty paragraph is where the text would be; an empty <div> may be a rule under the heading
                empty_block = empty_block or (name == "p" and sib.find(True) is None)
                continue
            if _ABSTRACT_HEADING.match(t):
                break
            if _is_author_bio_block(sib, t):
                # the authors' biographies, where the abstract's value was empty or its heading stood in a wrapper
                # of its own (OJS: <section class="item abstract"> then <section class="item author_bios">): never
                # the abstract, and nothing after it is (#2239 round 4)
                return ""
            # a list of links (tabs, downloads, related items) is not an abstract; a short link line between the
            # heading and the text ("Read online" on DOAJ records) is skipped
            if sum(len(a.get_text(strip=True)) for a in sib.find_all("a")) > 0.5 * len(t):
                if "abstract" in _ident(sib).lower():
                    return ""  # the abstract's own block holds a link and nothing else (RSNA: "Supplemental material
                    # is available for this article."): it is empty, and the text after its wrapper is the body
                if len(t) <= 40:
                    continue
                break
            # ... once real prose has started: after a bare ":" the first inline element is the whole value
            inline_run = sum(map(len, parts)) >= 40 and name in _INLINE_RUN
            first = name
            parts.append(t)
            # a structured abstract, one <div> per part (pjph.eu: "<div><strong>Introduction.</strong> ...</div>
            # <div><strong>Aim.</strong> ...</div>"): the blocks marked up like the first one are its other parts
            div_parts = name == "div" and bool(_PART_LABEL.match(t)) and sib.find(_HEADING_TAG) is None
            first_attrs = sib.attrs
        elif inline_run and (name in _INLINE_RUN or name == "br"):
            if t:
                parts.append(t)
        elif name == "p" and first == "p" and t:
            if _ABSTRACT_HEADING.match(t) or _SUMMARY_HEADING.match(t):
                break  # a paragraph that is the next version's heading ("<p><b>RESUMEN</b></p>")
            if _KEYWORD_LINE.match(t) or _AUTHOR_BIO_HEADING.match(t):
                break  # the keyword line ("<p><strong>Palavras-chave</strong>: ...</p>") or the next section's heading
            parts.append(t)  # a multi-paragraph abstract
        elif div_parts and name == "div" and t and sib.attrs == first_attrs and sib.find(_HEADING_TAG) is None:
            parts.append(t)
        elif name == "section" and first == "section" and t and structured:
            # a structured abstract, one <section> per part (PMC: Introduction / Case Report / Conclusion); its
            # keyword group is the last of them
            if "kwd" in _ident(sib).lower() or re.match(r"key ?words?\b", t, re.I):
                break
            parts.append(t)
        else:
            break
    if first is None and not parts:
        # only a lay summary, or an empty paragraph in the abstract's own block (Royal Holloway: <div class="abstract">
        # <h4>Abstract</h4><p></p></div>): the abstract is empty, never the text after its container. (APA's
        # <div id="articleAbstract_..."><h2>Abstract</h2><div class="topLevelHeadingRule"><br></div></div> is a
        # heading wrapper: its text follows the wrapper.)
        return "" if skipped or (empty_block and structured) else None
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def _alnum(text):
    """Letters and digits only, lower case: a key that ignores markup, spacing, punctuation and entities."""
    return re.sub(r"[\W_]+", "", re.sub(r"<[^<>]*>", " ", text or "")).lower()


# Words too common in titles and abstracts to say two texts are about the same item.
_COMMON_WORDS = frozenset(
    "this that with from into over under their which were have been between among about after before during within "
    "without study analysis effect effects using based case cases review research article paper results pour dans "
    "avec sobre entre como para with über eine einer dans des".split())


def _content_words(text):
    """Words of four or more letters, lower case, without the most common ones (a 'what is it about' set)."""
    return {w for w in re.findall(r"[^\W\d_]{4,}", (text or "").lower()) if w not in _COMMON_WORDS}


class Parser(ABC):

    @abstractmethod
    def parse(self):
        pass

    @staticmethod
    @abstractmethod
    def no_authors_output():
        pass


# Figures in the front matter are never abstract text: JACC's graphical abstract is a figure with an "Open in
# Viewer / Download figure / Download PowerPoint" toolbar and nothing else (oxjob #1794, 26 Oct).
_FRONTMATTER_FIGURES = '[id^="graphical-abstract"], figure, .core-figure-tools, .figure-wrap'
# Bare paragraphs carry no heading saying "abstract". On meeting-abstract pages that show no abstract they hold one
# short line instead: a disclosure ("I understand."), a presenter or affiliation line, a session title, a date.
# Real ones (a purpose or background sentence) start at ~100 characters; the junk that is longer is caught by
# is_not_abstract's patterns (oxjob #1794: of the 22K first abstracts the 26 Oct End 2 End gave Elsevier society
# works, 1.8K were under 100 characters besides presenter lines, nearly all junk).
_BARE_PARAGRAPH_FLOOR = 100


def frontmatter_abstract(soup):
    """The abstract in Atypon's ``<div id="abstracts" data-extent="frontmatter">`` block, or None.

    Atypon sites (Elsevier society sites, RSNA, Neurology, CABI ...) put the full abstract there: either sections
    (``#abstract`` / ``#author-abstract`` beside editor summaries, highlights and graphical abstracts) or, for
    meeting abstracts and research letters, bare paragraphs with no heading. Their meta tags cut it to the first
    200 characters or first section (oxjob #1794 for Elsevier, #1800 for the rest).
    """
    block = soup.select_one('#abstracts[data-extent="frontmatter"]')
    if block is None:
        return None
    block = copy.copy(block)  # never edit the page other parsers read
    for figure in block.select(_FRONTMATTER_FIGURES):  # also CABI chapters whose "Abstract" is a figure caption
        figure.decompose()
    sections = block.find_all("section")
    if sections:
        chosen = next((s for s in sections if s.get("id") in ("author-abstract", "abstract")), None)
        if chosen is None:
            return None
        text = chosen.get_text(" ", strip=True)
        heading = chosen.find(re.compile("^h[1-6]$"))
        heading_text = heading.get_text(" ", strip=True) if heading is not None else ""
        if heading_text and text.startswith(heading_text):
            text = text[len(heading_text):]
    else:
        text = block.get_text(" ", strip=True)
        if len(re.sub(r"\s+", " ", text).strip()) < _BARE_PARAGRAPH_FLOOR:
            return None
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def silverchair_abstract(soup):
    """The abstract in a Silverchair article page's ``section.abstract`` (AIP, OUP, Karger, Emerald ...), or None.

    Silverchair meta descriptions stop at ~160 characters, under the parsers' 200-character floor, so a page no
    publisher parser claims (the new pubs.aip.org) came out with no abstract (oxjob #1800). Paragraph text is
    joined as Oxford's parser does it (tag.text keeps CO<sub>2</sub> as CO2).
    """
    section = soup.select_one("div.widget-ArticleFulltext section.abstract")
    if section is None:
        return None
    paras = [p.text.strip() for p in section.find_all("p") if p.text and p.text.strip()]
    text = "\n".join(paras) if paras else " ".join(section.text.split())
    text = re.sub(r"^abstract[:.]?\s*", "", text.strip(), flags=re.I)
    return text or None


# World Scientific's stand-ins under its "Abstract:" heading (oxjob #2145, 550 sampled pages read by #1800's judge):
# a section list for chapters with no abstract ("The following sections are included: Introduction ..."), a book's
# contents list for proceedings, a front- or back-matter heading alone ("Index", "PREFACE.") and a notice.
_WS_STAND_IN = re.compile(
    r"^(?:the following (?:[\w-]+ )*(?:sections?|articles?|chapters?|topics?|papers?|items?) (?:is|are) included"
    r"|the table of contents for the book is as follows"
    r"|no abstract (?:received|available)\.?$"
    r"|please refer to (?:the )?full text\.?$"
    r"|(?:(?:author|subject|name|name and subject|cumulative)\s+)?index\.?$"
    r"|(?:table of )?contents\.?$"
    r"|(?:preface|foreword|prologue|epilogue|list of (?:participants|contributors|authors)|program(?:me)?"
    r"|(?:organizing |program(?:me)? |scientific )?committees?|acknowledge?ments?|editorial board)\.?$)",
    re.I)


def _ws_heading_list(text):
    """A proceedings volume's front matter as a list of headings ("PREFACE.\nCONTENTS.", "Program.\nList of
    Participants."): two or more lines, each a short heading (oxjob #2145 pilot: 6 of 968 gains). ASCII only: a short
    sentence in Chinese or Japanese has no spaces to count words by, so it would look like a heading."""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return len(lines) >= 2 and all(len(line.split()) <= 5 and len(line) <= 40 and line.isascii() for line in lines)


def world_scientific_abstract(soup):
    """The abstract on a World Scientific (worldscientific.com) page, or None.

    Older pages hold it in ``div.NLM_abstract`` after a bold "Abstract:", newer ones in
    ``div.abstractSection.abstractInFull``. No publisher parser read either: the World Scientific parser looks only
    for the new block and its author code throws on most pages, so ~0.3% of stored pages yielded an abstract and
    ~104K book chapters and proceedings papers showed none (oxjob #2145). Stand-ins (section or contents lists,
    headings, notices) are not abstracts (charter 24 Oct 14:17), nor is a chapter's opening paragraph cut off with
    "…" or mid-sentence, World Scientific's preview of a chapter that has no abstract (24 of 32 texts ending in "…"
    read as the chapter's opening, not a summary).
    """
    context = soup.select_one('meta[name="pbContext"]')
    if context is None or "wspc-site" not in (context.get("content") or ""):
        return None
    block = soup.select_one("div.NLM_abstract") or soup.select_one("div.abstractSection.abstractInFull")
    if block is None:
        return None
    paras = [p.get_text(" ", strip=True) for p in block.find_all("p")]
    paras = [p for p in paras if p]
    text = "\n".join(paras) if paras else block.get_text(" ", strip=True)
    text = re.sub(r"^abstract\s*[:.]?\s*", "", re.sub(r"[ \t\r\f\v]+", " ", text).strip(), flags=re.I)
    # a preview cut at "…" or at an equation the page drops ("It is easy to see that") is not an abstract
    if not text or _WS_STAND_IN.match(text) or _ws_heading_list(text) or _is_cut_preview(text):
        return None
    return text


_WS_CORRESPONDING = re.compile(
    r"\W*(?:corresponding authors?|authors? for correspondence|correspond(?:ence|ing) to)\b", re.I)


def world_scientific_corresponding_names(soup):
    """Names of the authors a World Scientific (worldscientific.com) page marks as corresponding, in byline order.

    Each author of the byline accordion (``div.loa-wrapper``) has an info card (``div.author-info``) with the
    affiliations, e-mail and, for the corresponding author, a paragraph that reads "Corresponding author." The World
    Scientific parser reads it but is claimed on few pages and throws on most, so the winning parser marked no one on
    ~14% of stored pages (oxjob #2211, from #2145's sample). Older pages word it "Author for correspondence." or
    "Correspondence to: Dr. ..." in the same card (9 of 48 marked pages). Only a paragraph that opens with such a
    label counts: an e-mail alone is not a mark here (many cards carry one).
    """
    context = soup.select_one('meta[name="pbContext"]')
    if context is None or "wspc-site" not in (context.get("content") or ""):
        return []
    wrapper = soup.select_one("div.loa-wrapper")
    if wrapper is None:
        return []
    names = []
    for tab in wrapper.select("div.accordion-tabbed__tab-mobile"):
        info = tab.select_one("div.author-info")
        name_tag = tab.select_one("a.author-name")
        if info is None or name_tag is None:
            continue
        if not any(_WS_CORRESPONDING.match(p.get_text(" ", strip=True)) for p in info.find_all("p")):
            continue
        name = name_tag.get("title") or name_tag.get_text(" ", strip=True)
        name = re.sub(r"\s+", " ", name).strip(" *†‡§,;")
        if name and name not in names:
            names.append(name)
    return names


# What a Silverchair author card's correspondence block holds when it is not a correspondence note (#2239)
_SILVERCHAIR_ADDRESS_NOTE = re.compile(r"\W*(?:present|current)\s+(?:address|affiliation)\b", re.I)
_SILVERCHAIR_EMAIL_ONLY = re.compile(
    r"\W*(?:e-?mail\W*)?(?:\[email\s*protected\]|[\w.+-]+@[\w-]+(?:\.[\w-]+)+)\W*", re.I)


def silverchair_corresponding_cards(cards):
    """The cards among a Silverchair byline's author cards (one ``.al-author-name`` or ``.info-card-author`` per
    author) that mark their author as corresponding.

    A card marks its author with the "Corresponding author note" link (``a.xref-corresp``) or an
    ``.info-author-correspondence`` block. Silverchair prints an author's other notes in the same block, so (#2239):
    a block that opens "Present address" is not a mark (Brain, 10.1093/brain/awaa011); and a block that holds only
    an e-mail address is a mark while it singles its author out. When every author of the byline has a block or
    link, an e-mail alone marks no one: ASME prints each author's address there (10.1115/1.4070429) and OUP a sole
    author's, and an address shown for every author is not a mark.
    """
    kinds = []
    for card in cards:
        notes = [re.sub(r"\s+", " ", block.get_text(" ", strip=True))
                 for block in card.select(".info-author-correspondence")]
        notes = [n for n in notes if not (_SILVERCHAIR_ADDRESS_NOTE.match(n) and "@" not in n
                                          and not re.search(r"correspond|email\s*protected", n, re.I))]
        if card.select_one("a.xref-corresp"):
            kinds.append("link")
        elif not notes:
            kinds.append(None)
        else:
            kinds.append("email" if all(_SILVERCHAIR_EMAIL_ONLY.fullmatch(n) for n in notes) else "note")
    singled_out = not all(kinds)
    return [card for card, kind in zip(cards, kinds) if kind in ("link", "note") or (kind == "email" and singled_out)]


def silverchair_corresponding_names(soup):
    """Names of the authors a Silverchair article page marks as corresponding, in byline order ([] if none).

    Silverchair bylines hold one ``.al-author-name`` per author; a corresponding author carries the
    "Corresponding author note" link (``a.xref-corresp``) and/or an ``.info-author-correspondence`` block in its
    info card. ACS and RSC moved to Silverchair in 2025-26; no publisher parser claims their new pages, so the
    winning parser reads meta tags and marked no one (oxjob #1805).
    """
    names = []
    for tag in silverchair_corresponding_cards(soup.select(".al-author-name")):
        name_tag = tag.select_one(".info-card-name") or tag.select_one("a.linked-name")
        if name_tag is not None:
            # the card name may carry a footnote label ("Nien-Hui Ge a)" on AIP) or a trailing '*'
            text = " ".join(s for s in name_tag.find_all(string=True)
                            if s.find_parent(class_="info-card-footnote") is None and s.find_parent("sup") is None)
            names.append(re.sub(r"\s+", " ", text).strip(" *†‡§,;"))
    return names


class PublisherParser(Parser, ABC):
    def __init__(self, soup):
        self.soup = soup

    @property
    @abstractmethod
    def parser_name(self):
        pass

    @abstractmethod
    def is_publisher_specific_parser(self):
        pass

    @abstractmethod
    def authors_found(self):
        pass

    @staticmethod
    def no_authors_output():
        return {"authors": [], "abstract": None, "published_date": None,
                "genre": None}

    def domain_in_canonical_link(self, domain):
        canonical_link = self.soup.find("link", {"rel": "canonical"})
        return (
                canonical_link
                and canonical_link.get("href")
                and domain in canonical_link.get("href")
        )


    def domain_in_meta_og_url(self, domain):
        meta_og_url = self.soup.find("meta",
                                     property="og:url") or self.soup.select_one(
            'meta[name="og:url"]')
        return (meta_og_url
                and meta_og_url.get("content")
                and domain in meta_og_url.get("content")
                )

    def substr_in_citation_journal_title(self, substr):
        if tag := self.soup.select_one('meta[name="citation_journal_title"]'):
            content = tag.get('content')
            return substr.lower() in content.lower()
        return False

    def substr_in_citation_publisher(self, substr):
        if tag := self.soup.select_one('meta[name="citation_publisher"]'):
            content = tag.get('content')
            return substr.lower() in content.lower()
        return False

    def text_in_meta_og_site_name(self, txt):
        meta_og_site_name = self.soup.find('meta',
                                           property='og:site_name') or self.soup.select_one(
            'meta[name="og:site_name"]')
        return (meta_og_site_name
                and meta_og_site_name.get("content")
                and txt in meta_og_site_name.get("content")
                )

    def parse_author_meta_tags(self, corresponding_tag=None,
                               corresponding_class=None):
        results = []
        metas = self.soup.findAll("meta")

        corresponding_text = None
        if corresponding_tag and corresponding_class:
            corresponding_text = self.get_corresponding_text(
                corresponding_tag, corresponding_class
            )

        author_meta_keys = {'citation_author', 'dc.Creator', 'bepress_citation_author'}

        result = None
        for meta in metas:
            if 'name' in meta.attrs and meta['name'] in author_meta_keys or 'property' in meta.attrs and meta['property'] in author_meta_keys:
                if result:
                    # reset for next author
                    results.append(result)
                    result = None
                if not (name := meta.get('content')):
                    continue
                if corresponding_text and name.lower() in corresponding_text:
                    is_corresponding = True
                elif corresponding_text and name.lower() not in corresponding_text:
                    is_corresponding = False
                else:
                    is_corresponding = None
                result = {
                    "name": name.strip(),
                    "affiliations": [],
                    "is_corresponding": is_corresponding,
                }
            if meta.get("name", None) and meta[
                "name"] in ("citation_author_institution", "bepress_citation_author_institution"):
                # An institution with no named author open has no one to attach to: an empty
                # citation_author (OJS sites with blank author names, e.g. in-academy.uz) or a
                # tag before the first author. Drop it rather than crash the whole page
                # (Sentry PARSELAND-2, ~590 pages/day; oxjob #1794).
                if result is not None and meta.get("content") and meta["content"].strip():
                    result["affiliations"].append(meta["content"].strip())

        # append name from last loop
        if result:
            results.append(result)

        return results

    def parse_abstract_meta_tags(self, include_seo_tags: bool = True):
        # citation_abstract / dc.description are article-level metadata.
        # og:description and description are page-level SEO tags: on many
        # institutional repositories they carry the same site blurb on every
        # record page, not the paper's abstract (oxjob #23518 — 48,180 UTokyo
        # works published the repository description as their abstract, and
        # 42,928 of them were then given topics derived from it). Callers that
        # know their publisher emits an article-specific og:description keep
        # the default; the generic parser opts out.
        # DSpace and EPrints repositories hold the record's abstract in dcterms.abstract / dc.description.abstract,
        # with dc.description often a note ("Thesis (M.A.)...") (#2239)
        # eprints.abstract last: EPrints repeats it in DC.description; cyberleninka.ru has no other abstract tag
        meta_tag_names = ["citation_abstract", "dcterms.abstract", "dc.description.abstract", "dc.description",
                          "eprints.abstract"]
        if include_seo_tags:
            meta_tag_names = [
                "citation_abstract",
                "og:description",
                "dc.description",
                "description",
            ]
        meta_property_names = ["property", "name"]

        # The first matching tag decides, as before, with two exceptions. A page can carry a journal blurb in its
        # first DC.Description and the article's abstract in the next one, so a candidate that is not an abstract
        # hands over to the next tag of the same name (oxjob #1800). And when the first is in another language,
        # an English version in a later tag wins (#2239: the rubric gives the English version; see _english_tag).
        first = None  # (the first abstract found, its tag, its tag name)
        for meta_tag_name in meta_tag_names:
            for meta_property_name in meta_property_names:
                for meta_tag in self.soup.find_all(
                        "meta", {
                            meta_property_name: re.compile(f"^{meta_tag_name}$",
                                                           re.I)}
                ):
                    description = meta_tag.get("content", '').strip()
                    if not (
                            len(description) > 200
                            and not description.endswith(_CUT_ENDS)
                            and not description.startswith("http")
                    ):
                        if first is None:
                            break
                        continue  # looking for an English version: a note in an earlier DC.description is skipped
                    if is_not_abstract(description):
                        continue
                    if first is None:
                        if not is_other_language(description):
                            return _LEADING_LABEL.sub("", description)
                        first = (description, meta_tag, meta_tag_name)
                    elif self._english_tag(description, meta_tag, meta_tag_name, *first):
                        return _LEADING_LABEL.sub("", description)

        return _LEADING_LABEL.sub("", first[0]) if first else None

    @staticmethod
    def _english_tag(text, tag, name, first_text, first_tag, first_name):
        """True when `text`, from a later abstract tag, is the English version of `first_text` (#2239).

        Repositories give each language version its own tag: two DCTERMS.abstract tags (DSpace, the USP thesis
        library), DCTERMS.abstract beside DC.description, two eprints.abstract tags. The page's own language
        attributes decide when they differ ('pt-br' / 'en'); DSpace mostly stamps one xml:lang on every tag (UnB:
        "en" on the Portuguese text), so otherwise the text must read as English. A tag of another name counts only
        from the article-level names (a description or og:description tag may be the site's English blurb), and
        any tag only at a translation's length: DC.description also holds notes and journal blurbs.

        A version that is only in the tags counts as shown (Open Journal Systems and Cairn print one language and
        list the others in DC.Description / citation_abstract): on the dev pages of that kind the gold gives the
        English tag 11 times (9 with a note saying the page prints only the other version) and the printed version
        twice, a split left to the loop's owner.
        """
        if name != first_name and name not in _ABSTRACT_VERSION_TAGS:
            return False
        if not _translation_length(text, first_text):
            return False
        if is_english(text):
            return True
        lang, first_lang = (_tag_language(t) for t in (tag, first_tag))
        return lang.startswith("en") and not first_lang.startswith("en") and bool(first_lang) and not \
            is_other_language(text)

    def parse_printed_seo_description(self):
        """og:description / description / twitter:description, kept only when the page also prints that text.

        The generic parser skips these page-level SEO tags (9c1dc07: on many repositories they hold the same site
        blurb on every record page). But on most repository and small-publisher record pages (DSpace, Digital
        Commons, figshare, Zenodo, OJS-like sites) they are the only tags that hold the record's abstract, and
        dropping them cost ~5% of stored pages their abstract (oxjob #2239; #2215 EXPLORE § 4). A record's
        abstract is printed on its record page; a site blurb sits in the head. So a tag counts when its text
        (letters and digits, from the 20th) is in the page's body text, scripts and styles left out, and is not
        printed inside the work's full text or a post's body: there the description is the text's opening
        paragraph (JAMA case reports, Cell Press commentaries, news and blog posts), and the gold says such pages
        have no abstract.
        """
        for name in ("og:description", "description", "twitter:description"):
            for attr in ("property", "name"):
                for tag in self.soup.find_all("meta", {attr: re.compile(f"^{name}$", re.I)}):
                    text = (tag.get("content") or "").strip()
                    # over 10,000 characters it is the work's text, not its abstract (a short story's whole text)
                    if (len(text) <= 200 or len(text) > 10_000 or text.endswith(("...", "…"))
                            or text.startswith("http") or is_not_abstract(text)):
                        continue
                    key = _alnum(text)[20:160]
                    at = self._body_text()[0].find(key) if len(key) >= 60 else -1
                    if at >= 0 and not self._inside_full_text(at):
                        return re.sub(r"^abstract[:.]?\s*", "", text, flags=re.I)
        return None

    def parse_titled_seo_description(self):
        """og:description / description about this item, for pages that render their abstract with JavaScript.

        DSpace 7 (Angular), Redalyc, Cureus and IEEE Xplore print no abstract in the stored HTML: the description tag
        is the only place it is (oxjob #2215 EXPLORE § 5: 85 of the 155 sampled abstracts 9c1dc07 dropped). A site
        blurb is the same on every record page and says nothing about the item, so the tag counts when it shares at
        least two content words with the item's title, and is not a citation line (one that carries the whole title:
        "Walbank, Greek Inscriptions from the Athenian Agora, Hesperia ...", PANGAEA's "(2010): <title> [dataset]").
        """
        if self.soup.find("link", href=re.compile("bloomsbury_assets/")):
            return None  # Bloomsbury's encyclopedias and books describe an entry with its opening (the gold: none)
        title = self._item_title()
        # the site's and journal's own names say nothing about the item ("Kalliope-Verbund", a journal in og:title)
        site_words, site_words_source = set(), []
        for name in ("og:site_name", "citation_journal_title", "dc.publisher", "citation_publisher"):
            for attr in ("property", "name"):
                for tag in self.soup.find_all("meta", {attr: re.compile(f"^{re.escape(name)}$", re.I)}):
                    site_words |= _content_words(tag.get("content"))
                    site_words_source.append((tag.get("content") or "").strip())
        title_words = _content_words(title) - site_words
        # Materials Project record pages are an unrendered app shell whose og:description is the record's own
        # description; their title is a formula ("mp-732041: Mo3Br6O (Tetragonal, I4/m, 87)"), which shares no
        # words with it (#2239 phase 2, round 3: gold keeps it on 4 of 4 pages)
        formula_title = "Materials Project" in site_words_source and re.match(r"mp-\d+:", title) is not None
        if len(title_words) < 2 and not formula_title:
            return None
        title_start = _alnum(title)[:40]
        for name in ("og:description", "description"):
            for attr in ("property", "name"):
                for tag in self.soup.find_all("meta", {attr: re.compile(f"^{name}$", re.I)}):
                    text = (tag.get("content") or "").strip()
                    if (len(text) <= 200 or len(text) > 10_000 or text.endswith(("...", "…"))
                            or text.startswith("http") or is_not_abstract(text)):
                        continue
                    if len(title_words & _content_words(text)) < 2 and not formula_title:
                        continue  # not about this item: a site blurb
                    key = _alnum(text)[20:160]
                    if len(key) < 60 or key in self._body_text()[0]:
                        continue  # printed: parse_printed_seo_description decided (an opening paragraph, JAMA, Science)
                    # a citation line names the authors, then the title ("Walbank, Greek Inscriptions ..., Hesperia",
                    # "Galgani, Luisa; ... (2019): <title> [dataset]"); an abstract may use the title's words later
                    head = _alnum(text)[:150 + len(title_start)]
                    if (len(title_start) >= 20 and title_start in head) or re.search(r"doi[:.]\s?(?:org/)?10\.", text[:400], re.I):
                        continue  # ... or a bibliographic line ("Review Article | doi:10.5530/...")
                    return re.sub(r"^abstract[:.]?\s*", "", text, flags=re.I)
        return None

    def _printed_at(self, text):
        """The element that prints `text` (the parent of the text node where its 20th letter stands), or None."""
        probe = _alnum(text)[20:160]
        if len(probe) < 60:
            return None
        body, starts, nodes = self._body_text()
        at = body.find(probe)
        return nodes[max(bisect.bisect_right(starts, at) - 1, 0)].parent if at >= 0 else None

    def whole_printed_abstract(self, chosen):
        """The whole abstract, when `chosen` is a meta tag's text and only a part of the abstract the page prints in a
        block named for it; else None (#2239 phase 2, round 3).

        PubMed's description tag holds the last part of a structured abstract ("Conclusions: ..."), RAND's
        citation_abstract the first two sentences of three: the tag is a cut, the printed block is the abstract.
        Only for a text that is a meta tag's content as it stands (a site parser's own reading of a block is left
        alone), and only when the block holds the abstract and nothing else, in one of two shapes: a block whose id
        or class says "abstract" and whose children are paragraphs of one kind (after an "Abstract" heading), or one
        such element with nothing but inline markup in it. A block that also holds a title, a byline, a notice, keywords
        or a citation box is not read (Frontiers' abstract panel, JAMA's "only available in the PDF format" widget,
        Tech Science's <div id="section_abstract"> with "Keywords" and "Cite This Article" in it).
        """
        key = _alnum(chosen)
        if len(key) < 80 or not any(
                _alnum(m.get("content")).endswith(key) for m in self.soup.find_all("meta")
                if _PART_SOURCE_TAGS.match(m.get("name") or m.get("property") or "")):
            return None
        para = self._printed_at(chosen)
        while para is not None and para.name in _INLINE_RUN:
            para = para.parent
        if para is None or para.name in ("body", "html", "[document]"):
            return None
        if "abstract" in _ident(para).lower():
            block, children = para, [para]
        else:
            block = para.parent
            if block is None or "abstract" not in _ident(block).lower() or any(
                    getattr(c, "name", None) is None and not isinstance(c, Comment) and str(c).strip()
                    for c in block.children):
                return None
            children = block.find_all(recursive=False)
        if _in_page_chrome(block) or _in_other_works_block(block):
            return None
        parts = []
        for child in children:
            text = " ".join(child.get_text(" ", strip=True).split())
            if not text or (_HEADING_TAG.match(child.name) and _ABSTRACT_HEADING.match(text) and not parts):
                continue
            # a paragraph like the one that prints the text (<p>, MDPI's <div class="html-p">), prose only: a
            # label, a heading, a list or a box inside it says it holds something else
            if child.name != para.name or child.get("class") != para.get("class") or any(
                    c.name not in _INLINE_RUN and c.name != "br" for c in child.find_all(True)):
                return None
            parts.append(text)
        whole = _LEADING_LABEL.sub("", " ".join(parts))
        whole_key = _alnum(whole)
        if not 1.2 * len(chosen) <= len(whole) <= 10_000 or key not in whole_key or is_not_abstract(whole):
            return None
        # What the block adds must be new text. Behind a "Show more" toggle it prints the abstract twice, a cut copy
        # and then the whole one (Leiden's repository: <span>cut copy...<a class="toggler">Show more</a></span><span>
        # the whole text<a>Show less</a></span>): the tag already holds it all (#2239 round 4; round 3 doubled these)
        rest = whole_key.replace(key, "", 1)
        middle = len(rest) // 2
        if rest[max(middle - 30, 0):middle + 30] in key:
            return None
        if is_english(chosen) and not is_english(whole):
            return None
        return _trim_article_tail(whole)

    def english_sibling_version(self, chosen):
        """The English version printed beside `chosen` as another value of the same field; else None (#2239 phase
        2, round 3).

        Record pages print each language version of the abstract in an element of its own and put only the first
        in the description and citation_abstract tags: DSpace 7 one <span class="dont-break-out ..."> per value
        under the one "Abstract" heading, some DSpace themes one <div class="abstract-text"> per value, DergiPark
        one <div class="article-abstract data-section"> per language tab. The twin is an element with the same tag
        name and classes as the one that holds `chosen`: a sibling of it, or, when the classes say "abstract", any
        such block of the page. It counts when it is as long as a translation would be and reads as English.
        """
        el, key = self._printed_at(chosen), _alnum(chosen)
        for _ in range(4):  # up to the element that holds the whole value (a value may have paragraphs in it)
            if el is None or el.name in ("body", "html", "[document]"):
                return None
            if len(_alnum(el.get_text())) >= 0.8 * len(key):
                break
            el = el.parent
        else:
            return None
        twins = []
        if el.get("class"):  # bare <p> siblings are a text's paragraphs, not a field's values
            twins = [t for t in el.find_next_siblings(el.name) + el.find_previous_siblings(el.name)
                     if t.get("class") == el.get("class")]
        block = el
        while block is not None and "abstract" not in " ".join(block.get("class") or []).lower():
            block = block.parent if block.parent is not None and block.parent.name not in (
                "body", "html", "[document]") else None
        if block is not None:
            twins += [t for t in self.soup.find_all(block.name, class_=block["class"][0])
                      if t is not block and t.get("class") == block["class"] and not _in_other_works_block(t)]
        for twin in twins:
            label = twin.find(_HEADING_TAG)  # the block's own heading ("Abstract", DergiPark's "Öz") is not its text
            text = " ".join(twin.get_text(" ", strip=True).split())
            if label is not None and text.startswith(heading := label.get_text(" ", strip=True)):
                text = text[len(heading):].strip()
            if len(text) > 100 and _translation_length(text, chosen) and is_english(text):
                return text
        return None

    def _item_title(self):
        for name in ("citation_title", "dc.title", "DC.title", "og:title"):
            for attr in ("name", "property"):
                tag = self.soup.find("meta", {attr: name})
                if tag and (tag.get("content") or "").strip():
                    return tag["content"].strip()
        return self.soup.title.get_text(" ", strip=True) if self.soup.title else ""

    def _body_text(self):
        """(the body's visible text as one letters-and-digits key, where each text node starts in it, the nodes)."""
        if getattr(self, "_body_text_cache", None) is None:
            body = self.soup.body or self.soup
            starts, nodes, parts, n = [], [], [], 0
            for s in body.find_all(string=True):
                if s.parent is None or s.parent.name in ("script", "style", "noscript", "template"):
                    continue
                if k := _alnum(s):
                    starts.append(n)
                    nodes.append(s)
                    parts.append(k)
                    n += len(k)
            self._body_text_cache = ("".join(parts), starts, nodes)
        return self._body_text_cache

    def _inside_full_text(self, at):
        """True when the text at offset `at` of _body_text() sits in the work's full text or a post body rather
        than an abstract block: the nearest container that names itself an abstract wins; otherwise one named
        full text / body matter / article body / entry content, or an <article class="post">, means the text is
        the work's opening."""
        _, starts, nodes = self._body_text()
        node = nodes[max(bisect.bisect_right(starts, at) - 1, 0)].parent
        while node is not None and node.name not in ("body", "html", "[document]"):
            ident = _ident(node)
            if "abstract" in ident.lower():
                return False
            if _BODY_CONTAINER.search(ident) or (node.name == "article" and re.search(r"\bpost\b", ident)):
                return True
            node = node.parent
        return False

    def parse_headed_abstract_section(self, main_article=False):
        """The text a page prints under its own "Abstract" heading, read the way a person reads it (#2239).

        Repository and small-journal record pages (DOAJ, PMC, Elsevier Pure portals, Redalyc, DergiPark ...) often
        print the abstract under a heading or label ("Abstract", "Resumen", "Özet" ...) while their meta tags hold
        a cut snippet or nothing. The heading is a short element whose whole text is such a word, outside
        navigation, menus, footers and links (tabs); the abstract is the text that follows it, up to the next
        heading, from its siblings, or from its wrapper's siblings when the heading sits alone in a label wrapper
        (or in two: see _text_under_label).
        """
        # under an English "Abstract" heading / under another language's heading / under "Abstract", in another language
        found = other = foreign = None
        for node in self.soup.find_all(string=_ABSTRACT_HEADING):
            text = self._text_under_heading(node, main_article)
            if text is None:
                continue
            # "If several language versions are shown, give the English one, else the first": the text under an
            # English "Abstract" heading wins over one under "Resumen" / "Résumé" / "Аннотация" (#2239)
            if not _ENGLISH_HEADING.match(str(node)):
                if other is None:
                    other = text
                elif main_article and text != other:
                    other = ""  # two different texts in other languages: as below, no telling
                continue
            if not main_article:
                # several texts typed "Abstract" (WEKO repositories: one row per language version, each typed
                # "Abstract"): the first, unless it is in another language and a later one is its English version
                if foreign is None:
                    if not is_other_language(text):
                        return text
                    foreign = text
                elif _translation_length(text, foreign) and is_english(text):
                    return text
                continue
            # publisher pages: one abstract only. Two different texts under "Abstract" headings mean the page also
            # shows other works' abstracts (a listing, an issue's table of contents): no telling which is this one.
            if found is not None and text != found:
                return None
            found = text
        if found is None and foreign is None and other and is_other_language(other):
            # ... and the English version may stand under "Summary" (see _SUMMARY_HEADING)
            for node in self.soup.find_all(string=_SUMMARY_HEADING):
                text = self._text_under_heading(node, main_article)
                if text and _translation_length(text, other) and is_english(text):
                    return text
        return found or foreign or other or None

    def _text_under_heading(self, node, main_article):
        """The text under the heading whose label is the text node `node`, or None when the heading is page chrome,
        or what follows it is not an abstract (see parse_headed_abstract_section)."""
        heading = node.parent
        if heading is None or heading.name in ("a", "button", "option", "title", "script", "style", "label"):
            return None
        if len(heading.get_text(" ", strip=True)) > 40 or _in_page_chrome(heading):
            return None
        if main_article and _in_other_works_block(heading):
            return None
        text = _text_under_label(heading) or ""
        if main_article:  # publisher pages: history, keyword and download tails off; no cut previews
            text = _trim_article_tail(text)
            if _is_cut_preview(text):
                return None
        if not 100 <= len(text) <= 10_000 or is_not_abstract(text):
            return None
        # not a link or another section's text (the value under "Abstract" was empty), nor the item's own
        # title printed again, alone or with its author (Digital Commons, IRIS "Titolo: ...")
        if text.startswith("http") or _OTHER_SECTION_START.match(text):
            return None
        if getattr(self, "_title_key", None) is None:
            self._title_key = _alnum(self._item_title())
        title = self._title_key
        if len(title) >= 20 and title in (key := _alnum(text)) and len(title) >= 0.6 * len(key):
            return None
        return text

    @staticmethod
    def format_name(name):
        return " ".join(reversed(name.split(", ")))

    @staticmethod
    def merge_authors_affiliations(authors, affiliations):
        results = []
        for author in authors:
            author_affiliations = []
            if not isinstance(author, Author):
                results.append(author)
                continue

            # scenario 1 affiliations with ids
            for aff_id in author.aff_ids:
                for aff in affiliations:
                    if aff_id == aff.aff_id:
                        author_affiliations.append(str(aff.organization))

            # scenario 2 affiliations with no ids (applied to all authors)
            for aff in affiliations:
                if (len(author.aff_ids) == 0 and aff.aff_id is None) or (
                        len(affiliations) == 1 and len(
                    author_affiliations) == 0):
                    author_affiliations.append(str(aff.organization))

            results.append(
                AuthorAffiliations(
                    name=author.name,
                    affiliations=author_affiliations,
                    is_corresponding=author.is_corresponding,
                )
            )
        return results

    def format_ids(self, ids, chars_to_ignore=None):
        ids_cleaned = ids.strip()
        if chars_to_ignore:
            for char in chars_to_ignore:
                ids_cleaned = ids_cleaned.replace(f",{char}", "").replace(
                    f"{char}", "")
        ids_split = ids_cleaned.split(",")
        aff_ids = []
        for aff_id in ids_split:
            if aff_id and aff_id.isdigit():
                aff_ids.append(int(aff_id))
        return aff_ids

    def fallback_mark_corresponding_authors(self, authors):
        def func(tag):
            for attr, value in tag.attrs.items():
                if ('author' in str(value).lower() and
                        tag.select_one('a[href*=mailto]')):
                    return True
            return False

        tags = self.soup.find_all(func)

        # Return only smallest tags, we don't want any tags with class*= authors that may contain multiple author names
        final_tags = remove_parents(tags)

        for tag in final_tags:
            tag_str = str(tag)
            for author in authors:
                if author['name'] in tag_str:
                    author['is_corresponding'] = True
                elif ',' in author['name']:
                    if all([name.strip(' ') in tag_str for name in
                            author['name'].split(',')]):
                        author['is_corresponding'] = True
        return authors

    def fallback_parse_abstract(self):
        blacklisted_words = {'download options', 'please wait',
                             'copyright clearance center', 'procite',
                             'food funct', 'rsc publication'}
        startswith_blacklist = {'download'}
        for tag in self.soup.find_all():
            for attr, value in tag.attrs.items():
                if 'abstract' in str(value).lower() or (
                        tag.text.lower() == 'abstract' and is_h_tag(tag)):
                    for desc in tag.descendants:
                        abs_txt = strip_seq(r'\s',
                                            strip_prefix('abstract', desc.text,
                                                         flags=re.IGNORECASE))
                        if len(desc.text) > 100 and desc.name in {'p', 'div',
                                                                  'span',
                                                                  'section',
                                                                  'article'} \
                                and not any(
                            [abs_txt.lower().startswith(word) for word in
                             startswith_blacklist]) \
                                and not any([word in abs_txt.lower() for word in
                                             blacklisted_words]):
                            return abs_txt
        return None

    def parse_fulltext_locations(self):
        return parse_publisher_fulltext_location(self.soup, cleanup_soup(copy.deepcopy(self.soup)))


    test_cases = []
