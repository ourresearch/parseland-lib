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
"""
import re

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


_OJS_GENERATOR_META_RE = re.compile(r"<meta\b[^>]*\bname=[\"']?generator\b[^>]*>", re.I)


def is_ojs_markup(lp_content):
    """is_ojs_page on the raw markup alone (no soup): PKP's template markers, or a generator meta tag naming OJS."""
    if any(raw_has(lp_content, m) for m in _OJS_RAW_MARKERS):
        return True
    if not _raw_search(r"open journal systems", lp_content):
        return False
    text = lp_content.decode("utf-8", "replace") if isinstance(lp_content, (bytes, bytearray)) else lp_content
    return any(_OJS_GENERATOR_RE.search(m.group(0)) for m in _OJS_GENERATOR_META_RE.finditer(text))


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


def ojs_corresponding_marks(soup, lp_content):
    """Text snippets, one per author an OJS page marks as corresponding, strongest form first; [] if not an OJS page."""
    if not is_ojs_page(soup, lp_content):
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
