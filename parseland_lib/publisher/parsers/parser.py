import bisect
import copy
import re
from abc import ABC, abstractmethod

from parseland_lib.elements import AuthorAffiliations, Author
from parseland_lib.legacy_parse_utils.fulltext import \
    parse_publisher_fulltext_location
from parseland_lib.legacy_parse_utils.strings import cleanup_soup
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
_SECTION_STOP = {"h1", "h2", "h3", "h4", "h5", "h6", "dt", "th", "header", "footer", "nav", "aside", "form", "button"}
# Site chrome, not content: a tab strip's labels, menus, footers. Not "tab-pane" / "article-header": abstracts live
# inside those (Zenodo prints its abstract in an HTML5 <header>).
_CHROME = re.compile(r"(?:^|[\s_-])(?:nav|navbar|menu|footer|site-header|page-header|masthead|breadcrumbs?|tabs|"
                     r"tablist|nav-tabs|toolbar|sidebar|modal|dropdown)(?:$|[\s_])", re.I)


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


def _text_after(anchor):
    """The block that follows `anchor`: its first non-empty sibling (bare text runs until the next element), plus
    the paragraphs that continue it. None when `anchor` has no following element (look one level up); '' when the
    value it labels is empty (a label/value row with no value: never read on into the next field)."""
    parts, first = [], None
    for sib in anchor.next_siblings:
        name = getattr(sib, "name", None)
        if name is None:
            t = str(sib).strip()
            if t and first is None:
                parts.append(t)
            continue
        if name in _SECTION_STOP or name in ("script", "style", "noscript", "template"):
            break
        t = sib.get_text(" ", strip=True)
        if first is None:
            if not t:
                if name in ("td", "dd") or "value" in " ".join(sib.get("class") or []):
                    return ""  # the labelled value is empty
                continue
            if _ABSTRACT_HEADING.match(t):
                break
            # a list of links (tabs, downloads, related items) is not an abstract; a short link line between the
            # heading and the text ("Read online" on DOAJ records) is skipped
            if sum(len(a.get_text(strip=True)) for a in sib.find_all("a")) > 0.5 * len(t):
                if len(t) <= 40:
                    continue
                break
            first = name
            parts.append(t)
        elif name == "p" and first == "p" and t:
            parts.append(t)  # a multi-paragraph abstract
        else:
            break
    if first is None and not parts:
        return None
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


def silverchair_corresponding_names(soup):
    """Names of the authors a Silverchair article page marks as corresponding, in byline order ([] if none).

    Silverchair bylines hold one ``.al-author-name`` per author; a corresponding author carries the
    "Corresponding author note" link (``a.xref-corresp``) and/or an ``.info-author-correspondence`` block in its
    info card. ACS and RSC moved to Silverchair in 2025-26; no publisher parser claims their new pages, so the
    winning parser reads meta tags and marked no one (oxjob #1805).
    """
    names = []
    for tag in soup.select(".al-author-name"):
        if not (tag.select_one("a.xref-corresp") or tag.select_one(".info-author-correspondence")):
            continue
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
        meta_tag_names = ["citation_abstract", "dcterms.abstract", "dc.description.abstract", "dc.description"]
        if include_seo_tags:
            meta_tag_names = [
                "citation_abstract",
                "og:description",
                "dc.description",
                "description",
            ]
        meta_property_names = ["property", "name"]

        # The first matching tag decides, as before, with one exception (oxjob #1800): a page can carry a
        # journal blurb in its first DC.Description and the article's abstract in the next one, so a
        # candidate that is not an abstract hands over to the next tag of the same name.
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
                            and not description.endswith("...")
                            and not description.endswith("…")
                            and not description.startswith("http")
                    ):
                        break
                    if is_not_abstract(description):
                        continue
                    return re.sub(
                        r"^abstract[:.]?\s*", "", description,
                        flags=re.I
                    )

        return None

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
        site_words = set()
        for name in ("og:site_name", "citation_journal_title", "dc.publisher", "citation_publisher"):
            for attr in ("property", "name"):
                for tag in self.soup.find_all("meta", {attr: re.compile(f"^{re.escape(name)}$", re.I)}):
                    site_words |= _content_words(tag.get("content"))
        title_words = _content_words(title) - site_words
        if len(title_words) < 2:
            return None
        title_start = _alnum(title)[:40]
        for name in ("og:description", "description"):
            for attr in ("property", "name"):
                for tag in self.soup.find_all("meta", {attr: re.compile(f"^{name}$", re.I)}):
                    text = (tag.get("content") or "").strip()
                    if (len(text) <= 200 or len(text) > 10_000 or text.endswith(("...", "…"))
                            or text.startswith("http") or is_not_abstract(text)):
                        continue
                    if len(title_words & _content_words(text)) < 2:
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
        heading, from its siblings, or from its parent's siblings when the heading sits in a label wrapper.
        """
        found = None
        for node in self.soup.find_all(string=_ABSTRACT_HEADING):
            heading = node.parent
            if heading is None or heading.name in ("a", "button", "option", "title", "script", "style", "label"):
                continue
            if len(heading.get_text(" ", strip=True)) > 40 or _in_page_chrome(heading):
                continue
            if main_article and _in_other_works_block(heading):
                continue
            text = _text_after(heading)
            if text is None:  # the heading sits alone in a label wrapper: the value follows the wrapper
                text = _text_after(heading.parent) or ""
            if main_article:  # publisher pages: history, keyword and download tails off; no cut previews
                text = _trim_article_tail(text)
                if _is_cut_preview(text):
                    continue
            if not 100 <= len(text) <= 10_000 or is_not_abstract(text):
                continue
            if not main_article:
                return text
            # publisher pages: one abstract only. Two different texts under "Abstract" headings mean the page also
            # shows other works' abstracts (a listing, an issue's table of contents): no telling which is this one.
            if found is not None and text != found:
                return None
            found = text
        return found

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
