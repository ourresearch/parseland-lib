"""HighWire article pages: the corresponding author the page marks (oxjob #2252).

HighWire (Drupal "JCore" sites and the older template: BMJ, J Neurosci, ERS, ASPET, Springer Publishing, Anticancer
Research, CSHL Press journals, BPS, JRheum, SNMMI and ~40 more society sites) has no platform parser: outside BMJ,
PNAS and the rxiv servers the meta-tag parser wins, and it reads no correspondence mark. The page marks the
corresponding author in one of three ways:

- byline link: the author's byline item links to a correspondence footnote (``a.xref-corresp`` -> ``li.fn-corresp``);
- correspondence note: ``li.corresp`` names the author ("Correspondence to: Dr Jean-Pierre Raynauld, ...",
  "Correspondence should be addressed to Dr. Novraj S. Dhanjal, ...") or gives only e-mails ("Corresponding authors:
  ptalbert{at}fredhutch.org"), tied to the author whose surname the address holds;
- e-mail tag: HighWire writes ``citation_author_email`` after the ``citation_author`` it belongs to, only for the
  authors the article gives an address for (what gold v1.3 labels corresponding on bioRxiv, medRxiv and ERS pages).

A mark on every one of two or more authors marks no one. parse_page reads the marks before the parsers run and fills
the flag only when the winning parser marked no one.
"""
import re

from parseland_lib.publisher.parsers.literatum import _NOTE_LABEL, _author_in_head, _surname_tokens
from parseland_lib.publisher.parsers.utils import _fold_name, raw_has, same_person

# Markers HighWire's page builder leaves in the page (as #2214's template census detects it). Not the HW.* meta tags:
# Founder's Chinese journal cloud writes those too.
_HIGHWIRE_MARKERS = ("/sites/all/modules/highwire", "highwire-", "hwmd_", "hw-gen", "/shared/js/hw-",
                     "stanford.edu/hwp", "hw-make-citation")
_EMAIL = re.compile(r"([\w.+-]+)\s*(?:\{at\}|\[at\]|\(at\)|@)\s*[\w-]+(?:\.[\w-]+)+", re.I)


def is_highwire_page(content):
    return any(raw_has(content, m) for m in _HIGHWIRE_MARKERS)


def _text(tag):
    return re.sub(r"\s+", " ", tag.get_text(" ", strip=True)).strip()


def highwire_corresponding_marks(soup):
    """What a HighWire page says about its corresponding author, or None: {"byline": names whose byline item links
    to a correspondence footnote, "heads": what follows each correspondence note's label, "emails": local parts of
    the notes' addresses, "meta": (citation_author, has e-mail) in page order}."""
    byline = []
    for item in soup.select("ol.contributor-list > li"):
        if not item.select_one("a.xref-corresp"):
            continue
        name = item.select_one("span.name")
        name = _text(name) if name else ""
        if name and name not in byline:
            byline.append(name)
    heads, emails = [], []
    for note in soup.select("li.corresp, li.fn-corresp"):
        text = _text(note)
        m = _NOTE_LABEL.match(text)
        if m and note.name == "li" and "corresp" in (note.get("class") or []):
            head = text[m.end():m.end() + 160]
            if head and not _EMAIL.match(head) and head not in heads:
                heads.append(head)
        for local in _EMAIL.findall(text):
            if local.lower() not in emails:
                emails.append(local.lower())
    meta, current = [], None
    for tag in soup.find_all("meta", attrs={"name": ["citation_author", "citation_author_email"]}):
        if tag.get("name") == "citation_author":
            current = [(tag.get("content") or "").strip(), False]
            meta.append(current)
        elif current is not None and (tag.get("content") or "").strip():
            current[1] = True
    if not byline and not heads and not emails and not any(e for _, e in meta):
        return None
    return {"byline": byline, "heads": heads, "emails": emails, "meta": [tuple(m) for m in meta]}


def _author_in_email(author_names, local):
    """The one author whose surname the address's local part holds ("ptalbert" -> Paul B. Talbert), or None."""
    folded = re.sub(r"[^a-z]", "", _fold_name(local))
    hits = [n for n in author_names if (sur := _surname_tokens(n)) and all(t.replace(" ", "") in folded for t in sur)]
    return hits[0] if len(hits) == 1 else None


def pick_highwire_corresponding(author_names, marks):
    """Names among author_names that highwire_corresponding_marks marks as corresponding: the byline links first,
    then the correspondence notes, then the e-mail tags. A mark on every one of two or more authors marks no one."""
    if not marks or not author_names:
        return []
    picked = [n for n in author_names if any(same_person(n, m) for m in marks["byline"])]
    if not picked:
        for found in [_author_in_head(author_names, h) for h in marks["heads"]] + [
                _author_in_email(author_names, e) for e in marks["emails"]]:
            if found and found not in picked:
                picked.append(found)
    if not picked:
        emailed = [name for name, has_email in marks["meta"] if has_email]
        picked = [n for n in author_names if any(same_person(n, e) for e in emailed)]
    if len(author_names) > 1 and len(picked) == len(author_names):
        return []
    return picked
