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
from parseland_lib.publisher.parsers.utils import _fold_name, raw_has, same_person, squash

# Markers HighWire's page builder leaves in the page (as #2214's template census detects it). Not the HW.* meta tags:
# Founder's Chinese journal cloud writes those too.
_HIGHWIRE_MARKERS = ("/sites/all/modules/highwire", "highwire-", "hwmd_", "hw-gen", "/shared/js/hw-",
                     "stanford.edu/hwp", "hw-make-citation")
# HighWire disguises addresses ("ptalbert{at}fredhutch.org"): keep the local part
_EMAIL = re.compile(r"([\w.+-]+)\s*(?:\{at\}|\[at\]|\(at\)|@)\s*[\w-]+(?:\.[\w-]+)+", re.I)


def is_highwire_page(content):
    return any(raw_has(content, m) for m in _HIGHWIRE_MARKERS)


def highwire_corresponding_marks(soup, raw):
    """What a HighWire page says about its corresponding author, or None: {"byline": names whose byline item links
    to a correspondence footnote, "heads": what follows each correspondence note's label, "emails": local parts of
    the notes' addresses, "emailed": names whose citation_author tag is followed by a citation_author_email tag}.
    raw is the page's bytes: each scan of the tree runs only when its marker is on the page."""
    byline = []
    for item in soup.select("ol.contributor-list > li") if raw_has(raw, "xref-corresp") else []:
        name = item.select_one("span.name") if item.select_one("a.xref-corresp") else None
        if name and (name := squash(name.get_text(" ", strip=True))) and name not in byline:
            byline.append(name)
    heads, emails = [], []
    for note in soup.select("li.corresp, li.fn-corresp") if raw_has(raw, "corresp") else []:
        text = squash(note.get_text(" ", strip=True))
        if "corresp" in note["class"] and (m := _NOTE_LABEL.match(text)):
            head = text[m.end():m.end() + 160]
            if head and not _EMAIL.match(head) and head not in heads:
                heads.append(head)
        for local in _EMAIL.findall(text):
            if local.lower() not in emails:
                emails.append(local.lower())
    emailed, current = [], None
    metas = soup.find_all("meta", attrs={"name": ["citation_author", "citation_author_email"]}) if raw_has(
        raw, "citation_author_email") else []
    for tag in metas:
        content = (tag.get("content") or "").strip()
        if tag.get("name") == "citation_author":
            current = content
        elif current is not None and content:
            emailed.append(current)
    if not (byline or heads or emails or emailed):
        return None
    return {"byline": byline, "heads": heads, "emails": emails, "emailed": emailed}


def _author_in_email(surnames, local):
    """The one author whose surname the address's local part holds ("ptalbert" -> Paul B. Talbert), or None.
    surnames: {author name: its surname tokens}."""
    folded = re.sub(r"[^a-z]", "", _fold_name(local))
    hits = [n for n, sur in surnames.items() if sur and all(t in folded for t in sur)]
    return hits[0] if len(hits) == 1 else None


def _named(author_names, names):
    return [n for n in author_names if any(same_person(n, m) for m in names)]


def pick_highwire_corresponding(author_names, marks):
    """Names among author_names that highwire_corresponding_marks marks as corresponding: the byline links first,
    then the correspondence notes, then the e-mail tags. A mark on every one of two or more authors marks no one."""
    if not marks:
        return []
    surnames = {n: _surname_tokens(n) for n in author_names} if marks["emails"] else {}
    from_notes = [_author_in_head(author_names, h) for h in marks["heads"]] + [
        _author_in_email(surnames, e) for e in marks["emails"]]
    picked = (_named(author_names, marks["byline"]) or list(dict.fromkeys(n for n in from_notes if n))
              or _named(author_names, marks["emailed"]))
    if len(author_names) > 1 and len(picked) == len(author_names):
        return []
    return picked
