"""indianjournals.com's article pages on its ijor.aspx template (oxjob #2330).

The page prints the byline as <p class="authorNames">: names separated by commas, each followed by a link to its
affiliation paragraph (<a href="#aff001"><sup>1</sup></a>, stars on some journals) and, for the corresponding author,
a link to the correspondence note (<a href="#cor001">*</a>). Affiliations are <p class="authorAffiliation"> paragraphs,
each after its <a name="aff001"> anchor; the note is <p class="correspondingAuthorAffiliation">. The citation_* tags
(citation_authors, one semicolon list) carry no affiliations, and no parser read the byline: about 45,000 of the site's
107,000 works had no affiliations and 64,000 no corresponding author (17 Nov 2026 sample of 80 pages).
The site's newer template (indianjournals.com/article/..., Next.js) is not this one and is left to the generic parser.
"""
import re

from bs4 import NavigableString, Tag

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

# The template's stylesheet and script, linked from <head> by a relative path on every page of the old template.
_ASSET = "ijor_css/"
_HONORIFIC = re.compile(r"^(?:(?:dr|mr|mrs|ms|miss|prof|smt|shri|sri)\.?\s+)+", re.I)
# "..., Email id: x", ". E mail: x", "E-mail: x, 9051057134": the e-mail and what follows it are not the affiliation
_EMAIL_LABEL = re.compile(r"[\s,.;:(]*\b(?:e[\s-]?mail)\b(?:\s*id)?\s*[:-]?.*$", re.I | re.S)
_EMAIL = re.compile(r"\S+@\S+")
_ORCID = re.compile(r"\(?\s*ORCID(?:\s*i?D)?\s*:?\s*\d{4}-\d{4}-\d{4}-\d{3}[\dX]\s*\)?", re.I)
# A comma-separated part that is the author's position or degree, not the organisation ("Associate Professor",
# "Research Scholar", "Doctor of philosophy PhD", "MDS 3rd year").
# shortcut: the positions and degrees the 17 Nov sample prints; another one stays in the string (the gate's matcher
# still pairs it with a label that drops it when the rest names an organisation)
_TITLE = re.compile(
    r"^(?:(?:assistant|associate|assoc\.?|additional|adjunct|visiting|emeritus|honorary|senior|junior|guest)\s+)*"
    r"(?:prof(?:essor|\.)?|lecturer|reader|tutor|teacher|principal|director(?:\s+of\s+research)?|dean|hod|"
    r"research\s+(?:scholar|supervisor|fellow)|(?:ph\.?\s?d\.?|m\.?\s?phil\.?)\s+(?:scholar|student)|"
    r"(?:post\s?graduate\s+|pg\s+|ug\s+)?student|(?:scientific\s+|independent\s+)?researcher|scientist|"
    r"(?:\w+\s+)?doctoral\s+fellow|doctor\s+of\s+philosophy(?:\s+\(?ph\.?\s?d\.?\)?)?|ph\.?\s?d\.?|m\.?\s?pharm\.?|"
    r"(?:mds|bds|mbbs)(?:\s+\d+\s*(?:st|nd|rd|th)\s+year)?)"
    r"(?:\s*(?:and|&)\s*(?:head|hod))?(?:\s*\([^)]*\))?\.?$", re.I)
# What a remainder must name for a position before it to be dropped: an organisation, or a unit of one.
_ORG = re.compile(r"\b(?:universi\w*|univ|institut\w*|college|academ\w*|cent(?:er|re|ro)|laborat\w*|hospital\w*|"
                  r"school|council|ministr\w*|foundation|company|corporation|ltd|inc|icar|vidyapeeth|vidyalaya|"
                  r"campus)\b", re.I)
_UNIT_START = re.compile(r"^(?:dept\b\.?|department|division|faculty|school|centre|center|chair)\b", re.I)
_CORRESPOND = re.compile(r"correspond", re.I)


def _strip_positions(text):
    """Drop leading position or degree parts when what is left still names an organisation or a unit of one: both
    labellers dropped "Associate Professor, Doctor of philosophy PhD, " before "Department of ...", and kept
    "Research Scholar, " before "IKG PTU, Jalandhar, India", which names no organisation by itself."""
    parts = [p.strip() for p in text.split(",")]
    i = 0
    while i < len(parts) - 1 and _TITLE.match(parts[i]):
        i += 1
    rest = ", ".join(parts[i:])
    if i and (_UNIT_START.match(rest) or _ORG.search(rest)):
        return rest
    return text


def _aff_text(p):
    """An affiliation paragraph's text: no leading marker (<sup>1</sup>, "*"), e-mail, ORCID note or position."""
    nodes = list(p.children)
    while nodes and (isinstance(nodes[0], Tag) and nodes[0].name == "sup"
                     or isinstance(nodes[0], NavigableString) and not nodes[0].strip()):
        nodes.pop(0)
    text = squash("".join(n.get_text() if isinstance(n, Tag) else str(n) for n in nodes))
    text = text.lstrip("*† ")
    text = _ORCID.sub("", text)
    text = _EMAIL_LABEL.sub("", text)
    text = _EMAIL.sub("", text)
    text = squash(text).strip(" ,;:.")
    if not text or text[0] in "\"“‘'":  # a quoted title is a footnote citing a work, not an affiliation (1 page in 52)
        return None
    return _strip_positions(text)


def _anchor(p):
    prev = p.find_previous_sibling()
    return prev.get("name") if prev is not None and prev.name == "a" and prev.get("name") else None


def _name_tokens(name):
    return [t for t in re.findall(r"[a-z]+", name.lower()) if len(t) >= 4]


class IndianJournals(PublisherParser):
    parser_name = "indianjournals"
    # the byline is the page's own; nothing else on the page names the authors with their affiliations
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        # Every parser's claim runs on every DOI page (#2239: under 0.5 ms a page it does not claim): the template's
        # assets in <head>, reached through direct children only; nothing walks the whole tree until this passes.
        if getattr(self, "_claimed", None) is None:
            html = self.soup.find("html", recursive=False)
            head = (html or self.soup).find("head", recursive=False)
            self._claimed = head is not None and any(
                _ASSET in (tag.get("href") or tag.get("src") or "") for tag in head.find_all(("link", "script")))
        return self._claimed

    def _byline(self):
        if getattr(self, "_names", False) is False:
            self._names = self.soup.find("p", class_="authorNames") if self.is_publisher_specific_parser() else None
        return self._names

    def authors_found(self):
        return self._byline() is not None

    def _byline_entries(self, byline):
        """[(name, [link ids])] in byline order: the text between commas is a name, the links after it are its own."""
        entries = [["", []]]
        for node in byline.children:
            if isinstance(node, Tag):
                if "roledeg" in (node.get("class") or []):  # a position printed in the byline, not an author
                    continue
                if node.name == "a" and (node.get("href") or "").startswith("#"):
                    entries[-1][1].append(node["href"][1:])
                    continue
                if node.name == "sup":
                    continue
                text = node.get_text()
            else:
                text = str(node)
            first, *rest = text.split(",")
            entries[-1][0] += first
            entries.extend([part, []] for part in rest)
        out = []
        for raw, links in entries:
            name = _HONORIFIC.sub("", squash(raw)).strip(" ,;")
            name = re.sub(r"^and\s+", "", name)
            if name:
                out.append((name, links))
            elif links and out:  # a mark after a stray comma belongs to the name before it
                out[-1][1].extend(links)
        return out

    def parse_authors(self):
        byline = self._byline()
        entries = self._byline_entries(byline)
        linked, unlinked, notes = {}, [], []
        for p in byline.find_next_siblings("p", class_=["authorAffiliation", "correspondingAuthorAffiliation"]):
            anchor = _anchor(p)
            if "correspondingAuthorAffiliation" in p.get("class"):
                notes.append((anchor, squash(p.get_text(" "))))
            elif text := _aff_text(p):
                if anchor:
                    linked.setdefault(anchor, []).append(text)
                else:
                    unlinked.append(text)
        any_link = any(ref in linked for _, links in entries for ref in links)
        authors = []
        for name, links in entries:
            if any_link:
                affs = [a for ref in links for a in linked.get(ref, [])] or list(unlinked)
            else:  # no author is linked to one: the page lists them without saying who has which
                affs = [a for ref_affs in linked.values() for a in ref_affs] + unlinked
            authors.append({"name": name, "affiliations": list(dict.fromkeys(affs)), "is_corresponding": False})
        for i in self._corresponding(entries, notes):
            authors[i]["is_corresponding"] = True
        return authors

    @staticmethod
    def _corresponding(entries, notes):
        """Indexes of the corresponding authors. A starred author (a byline link to a note) is one when that note says
        "Corresponding ..." or, when no note says so, when the note gives the starred authors' e-mail and not every
        author is starred (an e-mail shown for the only author is not a mark). With no star, a "Corresponding author"
        note names the lone author, or the one author whose name its text or e-mail address carries."""
        said = [anchor for anchor, text in notes if _CORRESPOND.search(text)]
        note_ids = {anchor for anchor, _ in notes if anchor}
        starred = [i for i, (_, links) in enumerate(entries)
                   if any(ref in note_ids or ref.lower().startswith("cor") for ref in links)]
        if starred:
            said_ids = {a for a in said if a}
            if said_ids:
                return [i for i in starred if said_ids & set(entries[i][1])] or starred
            if said:
                return starred
            return starred if notes and len(starred) < len(entries) else []
        if not said:
            return []
        if len(entries) == 1:
            return [0]
        text = " ".join(t for a, t in notes if _CORRESPOND.search(t)).lower()
        haystack = re.sub(r"[^a-z]+", " ", text) + " " + re.sub(r"[^a-z]", "", " ".join(re.findall(r"(\S+)@", text)))
        hits = [i for i, (name, _) in enumerate(entries)
                if (toks := _name_tokens(name)) and all(t in haystack for t in toks)]
        return hits if len(hits) == 1 else []

    def _printed_abstract(self):
        """The text under the "Abstract" heading: one paragraph, or a structured abstract's parts (sectionHeading2
        label, section2paragraph text), each part on its own line with its label inline."""
        heading = next((p for p in self._byline().find_next_siblings("p", class_="sectionHeading1")
                        if squash(p.get_text()).lower() == "abstract"), None)
        if heading is None:
            return None
        lines, label = [], None
        for p in heading.find_next_siblings():
            cls = p.get("class") or []
            if p.name != "p" or "sectionHeading1" in cls or "linktotop" in cls:
                break
            text = squash(p.get_text())
            if "sectionHeading2" in cls:
                label = text.rstrip(":. ")
            elif text:
                lines.append(f"{label}: {text}" if label else text)
                label = None
        return "\n".join(lines) or None

    def parse(self):
        return {"authors": self.parse_authors(),
                # the tag first, as the page's own reader took it before this parser (no change on those pages);
                # the printed block when the tag is empty (structured abstracts)
                "abstract": self.parse_abstract_meta_tags(include_seo_tags=False) or self._printed_abstract()}
