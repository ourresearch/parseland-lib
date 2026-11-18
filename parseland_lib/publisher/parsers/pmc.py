"""Corresponding authors on PubMed Central article pages, pmc.ncbi.nlm.nih.gov (oxjob #2239, round 8).

PMC pages go to the meta-tag parser, which reads no correspondence mark from them: on check1's random sample 10 of 16
PMC pages had a corresponding author in the gold and none from the parser. PMC prints every article in one template:
the byline (``section.front-matter div.cg``) gives each author a link and then the author's marks as ``<sup>`` labels
(affiliation numbers or letters, and a symbol such as ✉, * or †); the author notes under "Author information"
(``div.author-notes``) are footnotes, each opened by its symbol in a ``<sup>``: "✉Corresponding author.",
"*Correspondence: Name, e-mail", "#Contributed equally.". PMC prints ✉ (an envelope) for the correspondence footnotes.
"""
import re

from bs4 import NavigableString, Tag

from parseland_lib.publisher.parsers.utils import _fold_name

ENVELOPE = "✉"  # PMC's envelope
# a footnote's own symbol, printed at the start of its text after PMC's envelope: "✉*Correspondence: ...",
# "⁎⁎Corresponding author"
_LEADING_SYMBOLS = re.compile(r"\s*([*∗⁎†‡§¶#‖✉]+)")
_CORRESPONDENCE = re.compile(
    r"\bcorrespond(?:ence|ing|encia|ência|ance|enz)\b|\bto\s+whom\b|\breprints?\b|^\W*contact\b", re.I)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+|\be-?mail\b", re.I)
_EMAIL_ADDRESS = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# a footnote about something else, even when it says "correspondent": "†These authors had equal contribution to the
# first and correspondent authors", "#Contributed equally.", "Present address: ..."
_OTHER_NOTE = re.compile(
    r"contributed\s+equally|equal(?:ly)?\s+contribut|equal\s+contribution|joint\s+(?:first|senior|last)|\bco-?first\b|"
    r"share\s+(?:first|senior|last)|these\s+authors|present(?:ed)?\s+address|current\s+address|\bdeceased\b", re.I)
_NOTE_MAX_CHARS = 1500  # a correspondence footnote is a few lines; longer text is some other block


def is_pmc_page(soup):
    """A PubMed Central article page: NCBI's own <meta name="ncbi_db" content="pmc"> and the article's front matter."""
    meta = soup.find("meta", attrs={"name": "ncbi_db"})
    return bool(meta and (meta.get("content") or "").strip().lower() == "pmc") and \
        soup.select_one("section.front-matter") is not None


def _byline(front):
    """[(name, {marks})] in byline order: each author's link, then the <sup> labels printed after it. A run of text
    between them ("on behalf of the X group") ends the author: the labels after it are not that author's."""
    byline = next((cg for cg in front.select("div.cg") if cg.find("a", recursive=False)), None)
    if byline is None:
        return []
    entries, current = [], None
    for node in byline.children:
        if isinstance(node, NavigableString):
            if re.search(r"\w", str(node)):
                current = None
            continue
        if not isinstance(node, Tag):
            continue
        if node.name == "a" and node.find("span", class_="name"):
            current = (node.find("span", class_="name").get_text(" ", strip=True), set())
            entries.append(current)
        elif node.name == "sup":
            if current is not None:
                current[1].update(m.strip() for m in node.get_text("", strip=True).split(",") if m.strip())
        elif node.name == "div" and node.has_attr("hidden"):
            continue  # the author's pop-up (affiliations, roles)
        elif re.search(r"\w", node.get_text(" ", strip=True)):
            current = None
    return entries


def _notes(front):
    """[(symbols, text)] per author footnote: the symbol in its opening <sup> and any symbol its text opens with."""
    notes = []
    for box in front.select("div.author-notes"):
        for note in box.find_all(True, recursive=False):
            sup = note.find("sup", recursive=False)
            symbols = set()
            if sup is not None and sup is note.find(True):
                symbols.add(sup.get_text("", strip=True))
                text = " ".join(child.get_text(" ", strip=True) if isinstance(child, Tag) else str(child)
                                for child in note.children if child is not sup)
            else:
                text = note.get_text(" ", strip=True)
            text = re.sub(r"\s+", " ", text).strip()
            if m := _LEADING_SYMBOLS.match(text):
                symbols.add(m.group(1))
            symbols.discard("")
            notes.append((symbols, text))
    return notes


def pmc_corresponding_names(soup):
    """Names of the byline authors a PubMed Central page marks as corresponding, in byline order, or [].

    An author is marked when (a) the byline gives them ✉, or a symbol whose footnote is a correspondence note
    ("Corresponding author", "Correspondence:", "To whom correspondence ...", T&F's "CONTACT"), or the page's one
    e-mail symbol when it is not on every author ("*Email: ..."); or (b) a correspondence footnote names them in full
    ("Address correspondence to: Dana Peralta, MD"). A symbol that is also an affiliation label, or that any footnote
    uses for something else (equal contribution, present address), marks no one; a footnote that names no byline
    author ties to no one.
    """
    if not is_pmc_page(soup):
        return []
    front = soup.select_one("section.front-matter")
    entries = _byline(front)
    if not entries:
        return []
    notes = [(symbols, text) for symbols, text in _notes(front) if len(text) <= _NOTE_MAX_CHARS]
    labels = {sup.get_text("", strip=True).strip(",") for sup in front.select('[id^="aff"] > sup')}

    def kind(symbols, text):
        if _OTHER_NOTE.search(text):
            return "other"
        if _CORRESPONDENCE.search(text) or ENVELOPE in symbols:
            return "correspondence"
        return "email" if _EMAIL.search(text) else None

    kinds = {}  # symbol -> the kinds of the footnotes it opens
    for symbols, text in notes:
        for symbol in symbols:
            kinds.setdefault(symbol, set()).add(kind(symbols, text))
    carriers = {}
    for _, marks in entries:
        for mark in marks:
            carriers[mark] = carriers.get(mark, 0) + 1
    # An e-mail footnote marks its author only when it is the page's one e-mail symbol and not on every author: the
    # rubric's "an e-mail address alone, shown for every author, is not a mark" (a sole author's, or "*Email: a",
    # "†Email: b", "‡Email: c" on three of four authors)
    email_symbols = {s for s, k in kinds.items() if "email" in k and not k & {"correspondence", "other"}}
    email_symbol = next(iter(email_symbols)) if len(email_symbols) == 1 else None

    marked = set()
    for i, (_, marks) in enumerate(entries):
        for mark in marks:
            found = kinds.get(mark, set())
            if mark == ENVELOPE:
                marked.add(i)
            elif mark in labels or "other" in found:
                continue
            elif "correspondence" in found:
                marked.add(i)
            elif mark == email_symbol and carriers[mark] < len(entries):
                marked.add(i)

    def has(text, name):
        return len(name.split()) >= 2 and re.search(r"\b" + re.escape(name) + r"\b", text)

    def bare(text):  # without one-letter words: "Melinda L. Furer" and "Melinda Furer" read alike
        return " ".join(w for w in text.split() if len(w) > 1)

    folded = [_fold_name(name) for name, _ in entries]
    bares = [bare(name) for name in folded]
    for symbols, text in notes:
        if kind(symbols, text) != "correspondence":
            continue
        note = _fold_name(_EMAIL_ADDRESS.sub(" ", text))
        for i, name in enumerate(folded):
            # the name as the byline prints it, or without its initials when no other author's reads the same
            if has(note, name) or (bares.count(bares[i]) == 1 and has(bare(note), bares[i])):
                marked.add(i)
    return [entries[i][0] for i in sorted(marked)]
