"""Corresponding authors on Atypon Literatum pages: one rule for every site on the platform (oxjob #2220).

Literatum serves ~480 publisher sites (Wiley, T&F, Sage, AHA, APS Physiology, ASCE, ATS, APA Psychiatry, ...). Most
society sites have no parser of their own, so a parser that recognizes Literatum's author list (acs.py's ``ul.loa``,
aaas.py's ``div[property=author]``) wins without claiming the page, and it reads authors and affiliations but not the
note that names the corresponding author. Literatum renders that note in two templates:

- the older one: JATS ``<corresp>`` as ``.NLM_corresp`` (in ``div.NLM_author-notes`` or in an author's info card),
  or as an ``ul.author-notes`` item: "Correspondence to Dr Joseph C. Obunike, Division of ...", "Send correspondence
  to Dr. Thomas-Ollivier; e-mail: ...", "Address for reprint requests and other correspondence: M. C. Bellingham, ...";
- the 2022 "core" template: a footnote in ``section.core-authors-notes`` ("Corresponding author: W Janssens, ...",
  "Address correspondence to Atsushi Iguchi, ..."), or the label inside the author's own block
  (``div[property=author]``: ASCE writes "... Changsha 410114, China (corresponding author). Email: ...").

Only an explicit correspondence label counts (rubric label-v1): "Address reprint requests to Dr. X" alone, an e-mail
alone, or "To whom correspondence may be addressed. Email: ..." with no name mark no one here.
"""
import re

from parseland_lib.publisher.parsers.utils import _fold_name, name_position, raw_has, same_person

# Markers Literatum's page builder leaves in the page's assets and markup (as #2214's template census detects it)
_LITERATUM_MARKERS = ("/pb-assets/", "data-pb-dropzone", "/action/showCitFormats", "/wro/", "/templates/jsp/")

# A note that opens with an explicit correspondence label, then names the author
_NOTE_LABEL = re.compile(
    r"^[\W\d_]{0,6}(?:[a-z]\s*[).]\s*)?"  # a footnote symbol, number or letter: "*", "†", "1", "a)"
    r"(?:(?:send|address|direct)\s+(?:all\s+)?)?"
    r"(?:"
    r"(?:reprint\s+requests?\s+and\s+(?:other\s+)?)?correspondence"
    r"(?:\s+and\s+(?:requests?\s+for\s+reprints?|reprint\s+requests?))?"
    r"|address\s+for\s+(?:reprint\s+requests?\s+and\s+(?:other\s+)?)?correspondence"
    r"|corresponding\s+authors?"
    r")"
    r"(?:\s+(?:should|may|can)\s+be\s+(?:addressed|sent|directed))?"
    r"\s*(?:to\b\s*:?|:|\.)\s*",
    re.I,
)
_TITLES = re.compile(r"^(?:(?:dr|drs|prof|professor|mr|mrs|ms|mx|miss)\b\.?\s*)+", re.I)
_OWN_LABEL = re.compile(r"\bcorresponding\s+author\b", re.I)


def is_literatum_page(content):
    return any(raw_has(content, m) for m in _LITERATUM_MARKERS)


def _text(tag):
    return re.sub(r"\s+", " ", tag.get_text(" ", strip=True)).strip()


def literatum_corresponding_marks(soup):
    """What a Literatum page says about its corresponding author, or None: {"names": clean names the core template's
    author blocks label, "heads": the text that follows each correspondence note's label}. Read it before the parsers
    run (the fulltext step changes the soup)."""
    names = []
    for block in soup.select("section.core-authors div[property=author]"):
        given = block.select_one("[property=givenName]")
        family = block.select_one("[property=familyName]")
        if not family or not _OWN_LABEL.search(_text(block)):
            continue
        name = " ".join(t for t in (_text(given) if given else "", _text(family)) if t)
        if name and name not in names:
            names.append(name)
    heads = []
    for note in soup.select(".NLM_corresp, section.core-authors-notes [role=doc-footnote], ul.author-notes > li"):
        text = _text(note)
        m = _NOTE_LABEL.match(text)
        if not m:
            continue
        head = text[m.end():m.end() + 160]
        if head and head not in heads:
            heads.append(head)
    if not names and not heads:
        return None
    return {"names": names, "heads": heads}


def _surname_tokens(name):
    tokens = _fold_name(name.split(",")[0] if "," in name else name.split()[-1] if name.split() else "").split()
    return [t for t in tokens if len(t) >= 3]


def _author_in_head(author_names, head):
    """The one author a note's head names first ("Dr Joseph C. Obunike, Division of ...", "M. C. Bellingham, School of
    ...", "Dr. Thomas-Ollivier; e-mail: ..."), or None."""
    head = _TITLES.sub("", head.strip())
    found = sorted((p, n) for n in author_names if (p := name_position(n, head)) is not None)
    if found and found[0][0] <= 12 and (len(found) == 1 or found[1][0] > found[0][0]):
        return found[0][1]
    # "Dr. Thomas-Ollivier": the surname alone, right after the label and its title
    lead = _fold_name(head).split()[:4]
    hits = []
    for n in author_names:
        sur = _surname_tokens(n)
        if sur and lead[:len(sur)] == sur:
            hits.append(n)
    return hits[0] if len(hits) == 1 else None


def pick_literatum_corresponding(author_names, marks):
    """Names among author_names that literatum_corresponding_marks marks as corresponding. A label on every one of two
    or more authors marks no one."""
    if not marks or not author_names:
        return []
    picked = [n for n in author_names if any(same_person(n, m) for m in marks["names"])]
    if not picked:
        for head in marks["heads"]:
            n = _author_in_head(author_names, head)
            if n and n not in picked:
                picked.append(n)
    if len(author_names) > 1 and len(picked) == len(author_names):
        return []
    return picked
