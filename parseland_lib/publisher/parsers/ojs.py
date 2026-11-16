"""Open Journal Systems (PKP) article pages: the corresponding author the page marks (oxjob #2166).

OJS runs ~14.5K long-tail journal sites and no publisher parser claims them, so the meta-tag parser wins and reads
citation_author tags, which carry no correspondence flag. The article page marks one author in one of four ways,
depending on the site's theme (all four are what gold v1.3 labels as the corresponding author, #1791):

- primary contact: OJS 3 themes print the submission's primary contact under that author, `<div class="primary_contact">`
  with an envelope icon and the e-mail ("(Primary Contact)" on some);
- lone e-mail: themes that print an e-mail in the OJS author list (`ul.authors > li`) show it for the primary contact
  only, so exactly one author item of two or more with an e-mail (a `mailto:` link, or Cloudflare's protected-e-mail
  link on sites behind it) is that author;
- starred byline: OJS 2 bylines put `<sup>(2*)</sup>` after a name and say "(*) Corresponding Author" below it (some
  themes: `<span>*</span>` and "*Author to whom correspondence should be addressed");
- "Author for correspondence.": the "About the authors" tab of OJS 2 sites (Eco-Vector's Russian journals) says it under
  that author's heading.

parse_page reads the marks before the parsers run (some edit the soup) and fills the flag only when the winning parser
marked no one; pick_ojs_corresponding ties each mark to the one parsed author whose name it holds.

ojs_abstract reads the abstract an OJS theme prints in its own block, for pages whose meta tags hold none (#2267).
"""
import re

from parseland_lib.not_abstract import is_not_abstract
from parseland_lib.publisher.parsers.parser import _ABSTRACT_HEADING, _ident, _is_cut_preview, _text_after, \
    _trim_article_tail
from parseland_lib.publisher.parsers.utils import name_position, raw_has, squash

_OJS_RAW_MARKERS = ("/lib/pkp/", "pkp_structure", 'class="pkp_', "pkp_brand_footer")
_OJS_GENERATOR_RE = re.compile(r"open journal systems", re.I)
_STAR_NOTE_RE = re.compile(r"(?:\(\s*\d*\s*\*\s*\)|\*)\s*(?:corresponding\s+author|author\s+to\s+whom\s+correspondence"
                           r"\s+should\s+be\s+addressed)", re.I)
_STAR_SUP_RE = re.compile(r"\(?\s*\d*\s*\*\s*\)?")
_LINE_BREAKS = {"br", "div", "p", "hr", "li", "ul", "ol", "table", "tr", "td", "h1", "h2", "h3", "h4", "h5", "h6"}
_FOR_CORRESPONDENCE_RE = re.compile(r"\bauthor\s+for\s+correspondence\b", re.I)
# an e-mail link, or Cloudflare's stand-in for one on sites behind its e-mail obfuscation
_MAIL_SELECTOR = ('a[href^="mailto:"]:not([href^="mailto:?"]), a[href*="/cdn-cgi/l/email-protection"], '
                  '.__cf_email__, .email')
_TRAILING_SEPARATOR_RE = re.compile(r"[\s,;.\-–—]+$")  # "Erna Prasetya Ningrum -"


def _raw_search(pattern, lp_content):
    """Case-blind regex over the raw page (bytes or str), before any whole-tree search."""
    if isinstance(lp_content, (bytes, bytearray)):
        return re.search(pattern.encode(), lp_content, re.I)
    return re.search(pattern, lp_content, re.I)


def _text(node):
    return squash(node.get_text(" "))


def is_ojs_page(soup, lp_content):
    """An Open Journal Systems page: it loads PKP's own templates and styles, or its generator meta tag names OJS."""
    if any(raw_has(lp_content, m) for m in _OJS_RAW_MARKERS):
        return True
    if not _raw_search(r"open journal systems", lp_content):
        return False
    return any(_OJS_GENERATOR_RE.search(meta.get("content") or "")
               for meta in soup.find_all("meta", attrs={"name": re.compile(r"^generator$", re.I)}))


def _primary_contact_items(soup):
    texts = []
    for mark in soup.select(".primary_contact"):
        item = mark.find_parent("li") or mark.find_parent(class_=re.compile(r"author", re.I))
        if item is not None:
            texts.append(_text(item))
    return texts


def _lone_mail_item(soup):
    items = soup.select("ul.authors > li") or soup.select(".item.authors li")
    if len(items) < 2:
        return []
    mailed = [li for li in items if li.select_one(_MAIL_SELECTOR)]
    return [_text(mailed[0])] if len(mailed) == 1 else []


def _starred_byline_names(soup, lp_content):
    lp_text = lp_content.decode("utf-8", "replace") if isinstance(lp_content, (bytes, bytearray)) else lp_content
    if not _STAR_NOTE_RE.search(re.sub(r"<[^>]+>", " ", lp_text)):
        return []
    texts = []
    for star in soup.find_all(["sup", "span"]):
        mark = star.get_text()
        if "*" not in mark or not _STAR_SUP_RE.fullmatch(squash(mark)):
            continue
        prev = star.previous_sibling
        while prev is not None and prev.name not in _LINE_BREAKS and not _text(prev).strip(",;"):
            prev = prev.previous_sibling
        # the "(*) Corresponding author" note's own star starts a line: no name sits before it
        if prev is None or prev.name in _LINE_BREAKS:
            continue
        parts = [p.strip() for p in re.split(r"[,;]", _text(prev))]
        name = parts[-1]
        if len(parts) > 1 and not re.search(r"[^\W\d_]{3,}", name):
            name = f"{parts[-2]}, {name}"  # "Priyadarshini, V. M": a family name, then initials
        if name:
            texts.append(name)
    return texts


def _about_authors_names(soup):
    texts = []
    for label in soup.find_all(string=_FOR_CORRESPONDENCE_RE):
        heading = label.find_previous(["h3", "h4"])
        if heading is not None:
            texts.append(_text(heading))
    return texts


def ojs_corresponding_marks(soup, lp_content, ojs_page=None):
    """Text snippets, one per author an OJS page marks as corresponding, strongest form first; [] if not an OJS page.
    `ojs_page`: is_ojs_page's answer when the caller already has it."""
    if not (is_ojs_page(soup, lp_content) if ojs_page is None else ojs_page):
        return []
    marks = (_primary_contact_items(soup) if raw_has(lp_content, "primary_contact") else []) or _lone_mail_item(soup)
    # the last two forms both need the word on the page
    if marks or not _raw_search(r"correspond", lp_content):
        return marks
    return _starred_byline_names(soup, lp_content) or _about_authors_names(soup)


def pick_ojs_corresponding(author_names, marks):
    """Names among author_names that ojs_corresponding_marks marks: each mark names exactly one parsed author (the one
    whose name it holds earliest). A mark on every one of two or more authors marks no one."""
    cleaned = [(_TRAILING_SEPARATOR_RE.sub("", n), n) for n in author_names]
    picked = []
    for text in marks:
        found = sorted((p, n) for c, n in cleaned if (p := name_position(c, text)) is not None)
        if found and (len(found) == 1 or found[1][0] > found[0][0]) and found[0][1] not in picked:
            picked.append(found[0][1])
    if len(author_names) > 1 and len(picked) == len(author_names):
        return []
    return picked


# The abstract an OJS theme prints (#2267). OJS 3's default theme and its children print it in `section.item.abstract`
# under an `h2.label`; OJS 2 in `div#articleAbstract` under an h4; custom themes under an "Abstract" heading in the
# article column (omniscient.sg: `h4.art_h4` in `div.Article_the`). The generic heading reader skips all of them:
# OJS 3 wraps the article column in `pkp_structure_content has_sidebar`, which its chrome rule reads as a sidebar, and
# some themes leave the site header open around the whole page. So on OJS pages the article column is found by OJS's
# own container names, and only real navigation, sidebars and footers inside it are chrome.
_OJS_ABSTRACT_BLOCK = ".item.abstract, #articleAbstract"
_OJS_MAIN = re.compile(r"(?:^|\s)(?:pkp_structure_main|pkp_content_main|content|main)(?:$|\s)", re.I)
_OJS_CHROME = re.compile(r"(?:^|\s)(?:pkp_structure_sidebar|pkp_structure_footer|pkp_navigation_\w+|pkp_site_nav_\w+|"
                         r"sidebar|sidebar_\w+|navbar\w*|nav-tabs|tabs?|tablist|block_\w+)(?:$|\s)", re.I)
_CHROME_TAGS = ("nav", "footer", "aside", "menu", "select", "option", "a", "button", "label", "title", "script", "style")
_CJK = re.compile(r"[\u3400-\u9fff\uac00-\ud7af\u3040-\u30ff]")
_ENGLISH_HEADING = re.compile(r"^\s*abstracts?\s*[:.]?\s*$", re.I)


def _in_article_column(el):
    """True when `el` sits in the page's article column (OJS 3 pkp_structure_main, OJS 2 #content / #main) and in no
    navigation, tab strip, sidebar block or footer on the way up to it."""
    node = el
    while node is not None and node.name not in ("body", "html", "[document]"):
        if node.name in _CHROME_TAGS or node.get("role") in ("navigation", "tablist", "tab", "menu", "menubar"):
            return False
        ident = _ident(node)
        if _OJS_CHROME.search(ident):
            return False
        if _OJS_MAIN.search(ident) or node.get("role") == "main":
            return True
        node = node.parent
    return False


def _long_enough(text):
    return len(text) <= 10_000 and (len(text) >= 100 or len(_CJK.findall(text)) >= 50)


def _clean(text, whole=False):
    """`text` as an abstract, or None. `whole`: it must also end like a sentence (text under a custom theme's heading,
    where a rights box or a tab's label can follow "Abstract"); OJS's own abstract blocks need not."""
    text = _trim_article_tail(squash(text or ""))
    if not _long_enough(text) or text.endswith(("...", "…")) or is_not_abstract(text):
        return None
    return None if whole and _is_cut_preview(text) else text


def _is_list(el):
    """The abstract's first element is a list: a congress's titles or a table of contents, not an abstract."""
    return el is not None and el.name in ("ul", "ol")


def _block_body(block):
    """A heading-less abstract block's first element, past a label in another word ("Synopsis")."""
    first = block.find(True)
    if first is not None and first.name in ("h2", "h3", "h4") and "label" in (first.get("class") or []):
        first = first.find_next_sibling()
    return first


def _headings(root):
    """Elements whose whole text is an abstract label ("Abstract", "Resumen", "摘要" ...)."""
    return [n.parent for n in root.find_all(string=_ABSTRACT_HEADING)]


def ojs_abstract(soup, lp_content=b""):
    """The abstract an Open Journal Systems article page prints in its own block, or None. Run on OJS pages only, before
    the parsers edit the soup. Several language versions: the one headed "Abstract", else the first (gold rubric).
    Not on Open Monograph Press pages (also PKP software): a book's or chapter's synopsis is often the series' note."""
    if not raw_has(lp_content, "bstract") or _raw_search(r"open monograph press|obj_monograph_full", lp_content):
        return None
    found = []  # (headed "Abstract", text) in page order
    blocks = soup.select(_OJS_ABSTRACT_BLOCK)
    custom = not blocks  # no OJS abstract block: a custom theme's heading in the article column
    headings = _headings(soup) if custom else []
    for block in blocks:
        if own := _headings(block):
            headings += own
        elif not _is_list(_block_body(block)) and (text := _clean(block.get_text(" "))):
            found.append((False, text))  # a block with no heading of its own: all of it is the abstract
    for heading in headings:
        if heading.name in _CHROME_TAGS or len(heading.get_text(" ", strip=True)) > 40:
            continue
        if (custom and not _in_article_column(heading)) or _is_list(heading.find_next_sibling()):
            continue
        text = _text_after(heading)
        if text is None:  # the heading sits alone in a label wrapper: the value follows the wrapper
            text = _text_after(heading.parent)
        if text := _clean(text, whole=custom):
            found.append((bool(_ENGLISH_HEADING.match(heading.get_text(" ", strip=True))), text))
    return max(found, key=lambda f: f[0], default=(None, None))[1]  # max keeps the first of equals
