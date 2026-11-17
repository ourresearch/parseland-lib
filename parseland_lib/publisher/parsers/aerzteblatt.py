"""Deutsches Ärzteblatt archive pages: aerzteblatt.de, DOI prefix 10.3238 (oxjob #2339).

The archive's article layout (Deutsches Ärzteblatt International, the German edition's "Medizin" section and its
"Perspektiven" supplements) has no citation_* meta tags. Its byline sits under the citation line as
<h4><span class="author"><a>Family, Initial</a></span>; ...</h4>, and the page states affiliations in one of these
places, all read here:
  - reviews and original articles: <div id="autoren">, "Affiliation: Prof. Dr. med. Name, ...<br/>Affiliation: ...";
  - letters and research letters: <p class="Anschrift_der_Verfasser"> paragraphs, a bold name line followed by its
    address lines (research letters name each affiliation's authors in parentheses);
  - supplement articles: <span class="Autor_nach_Artikel"> name lines, each followed by
    <span class="Autor_Taetigkeit"> affiliation lines (later supplements: <p class="Autor_nach_Artikel"> and
    <p class="Autor_nach_Artikel_Taetigkeit">);
  - 2008-2010 letters, with no such classes: plain <BR> lines after the article's own "DOI: ..." line.
Every line of an address belongs to it (the town under the institution too); a bare town alone is not an affiliation.
The address paragraphs name every signatory: when each byline author is found there, a titled name the byline lacks
("In Reply" letters often carry only the first) is added as a co-author with the address under it.
The "Corresponding author" address block (bold label, or plain <BR> lines on 2008-2010 pages) marks that author.
Names are matched to the byline by family name. The site's newer layout (aerzteblatt.de/archiv/<slug>-<uuid>) has no
such byline and is not claimed.
"""
import re
import unicodedata

from bs4 import NavigableString, Tag
from bs4.element import Comment

from parseland_lib.publisher.parsers.parser import PublisherParser

_BOLD_CLASSES = {"Anschrift_fett", "Autor_fett", "Autor_nach_Artikel"}
_EMAIL = re.compile(r"\S+@\S+")
_TITLE_ONLY = re.compile(r"^(?:(?:univ\.-)?prof\.|dr\.(?:-ing\.)?|med\.|dent\.|phil\.|rer\.|nat\.|pd|habil\.|[,;\s])*$",
                         re.I)
_CORR_LABEL = re.compile(r"^(?:correspond\w*\s+authors?|address\s+for\s+correspondence|korrespondenzadresse)\b\s*:?\s*(.*)$",
                         re.I)
_ON_BEHALF = re.compile(r"^(?:on behalf of|im namen|for the )|\bon behalf of\b", re.I)
_ORG = re.compile(r"universit|klinik|clinic|hospital|spital|krankenhaus|institut|zentrum|center|centre|praxis|practice|"
                  r"department|abteilung|fakult|faculty|school|college|gmbh|\bag\b|e\.\s?v\.|gesellschaft|society|"
                  r"lehrstuhl|labor|foundation|stiftung|akadem|academy|ministeri|\bamt\b|office|\bunit\b|research|"
                  r"hochschule|charit|redaktion|verband|association|kammer|bundeswehr", re.I)
_TITLED = re.compile(r"^(?:univ\.-)?prof\.|^dr\.|^pd\b|^priv\.-doz", re.I)
_OPEN_END = re.compile(r"(?:\b(?:für|fur|of|and|und|der|des|for|the|de)|[-,])$", re.I)
_DEGREE_TOKENS = {"nat", "rer", "med", "dent", "phil", "dr", "prof", "pd", "habil"}
# the end of the address lines: the statements and lists printed after them
_STOP = re.compile(r"^(?:cite this as|zitierweise|conflicts? of interest|interessenkonflikt|literatur\b|references?$)",
                   re.I)
_CONTACT = re.compile(r"^(?:or|oder|and|und|e-?mail|mail|tel(?:efon)?|fax|phone)\.?$", re.I)  # left when an e-mail goes
_INLINE = {"b", "strong", "i", "em", "span", "a", "font", "sup", "sub", "u"}
_C1 = re.compile("[\x80-\x9f]")
_POSTCODE = re.compile(r"\b\d{4,5}\s+[A-ZÄÖÜ]")


def _utf8(text):
    """Undo UTF-8 read as windows-1252: the pages declare charset windows-1252, the stored bodies are UTF-8 ("GÃ¼sgen"
    -> "Güsgen"). Text that is not such mojibake comes back unchanged, but for stray windows-1252 bytes that came through
    as C1 control characters (U+0096 -> "–")."""
    if not text or text.isascii():
        return text
    return _C1.sub(lambda m: m.group().encode("latin-1").decode("cp1252", "ignore"), _undo_mojibake(text))


def _undo_mojibake(text):
    raw = bytearray()
    for ch in text:
        try:
            raw += ch.encode("cp1252")
        except UnicodeEncodeError:
            if ord(ch) > 255:
                return text
            raw.append(ord(ch))  # the five bytes cp1252 leaves undefined come through as U+0081 etc.
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return text


def _fold(text):
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c)).casefold()


def _clean(text):
    text = _EMAIL.sub(" ", text or "")
    text = re.sub(r"\(\s*\)", " ", text)
    return re.sub(r"\s+", " ", text).strip(" ,;:")


def _author(name, family, given=""):
    return {"name": name, "family": _fold(family), "initial": _fold(given)[:1], "affiliations": [],
            "is_corresponding": False}


def _person(text):
    """'Prof. Dr. jur. Thomas Gutmann, MHBA' -> 'Thomas Gutmann': titles and degrees off; an initial ('J.') stays."""
    tokens = text.split(",")[0].split()
    while tokens and (tokens[0].casefold() in ("pd", "prof", "dr")
                      or tokens[0].endswith(".") and not re.match(r"^[A-ZÄÖÜ]\.(?:-?[A-ZÄÖÜ]\.)*$", tokens[0])):
        tokens.pop(0)
    return " ".join(tokens)


def _lines(el):
    """The element's text as lines: split at <br> and where bold (name) markup starts or ends."""
    lines, buf, buf_bold = [], [], None

    def flush():
        text = _utf8(re.sub(r"\s+", " ", "".join(buf)).strip())
        if text:
            lines.append((text, bool(buf_bold)))
        buf.clear()

    for node in el.descendants:
        if isinstance(node, Tag) and node.name == "br":
            flush()
        elif isinstance(node, NavigableString) and not isinstance(node, Comment):
            bold = False
            for parent in node.parents:
                if parent is el:
                    break
                if parent.name in ("b", "strong") or _BOLD_CLASSES & set(parent.get("class") or []):
                    bold = True
                    break
            if buf and bold != buf_bold:
                flush()
            buf.append(str(node))
            buf_bold = bold
    flush()
    return lines


class Aerzteblatt(PublisherParser):
    parser_name = "aerzteblatt"
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        if getattr(self, "_byline_spans", None) is None:
            self._byline_spans = self._claim()
        return bool(self._byline_spans)

    def authors_found(self):
        return self.is_publisher_specific_parser()

    def _claim(self):
        """The site's og:site_name in <head> first (one head scan on another site's page), then the archive byline."""
        head = self.soup.head
        site = head.find("meta", attrs={"property": "og:site_name"}) if head is not None else None
        content = (site.get("content") or "") if site is not None else ""
        # "Deutsches Ärzteblatt" (some stored pages lose or garble the Ä); not the regional Ärzteblatt journals
        if not (content.startswith("Deutsches ") and "rzteblatt" in content):
            return []
        first = self.soup.select_one("h4 > span.author")
        return first.parent.find_all("span", class_="author", recursive=False) if first is not None else []

    # ---- authors

    def _byline(self):
        authors = []
        for span in self._byline_spans:
            raw = _utf8(re.sub(r"\s+", " ", span.get_text(" ", strip=True)).strip(" ,;"))
            family, _, given = raw.partition(",")
            given = " ".join(t for t in given.split() if t.casefold().strip(".") not in _DEGREE_TOKENS)
            name = f"{given} {family.strip()}".strip()
            if name:
                authors.append(_author(name, family.strip(), given))
        return authors

    @staticmethod
    def _who(text, authors):
        """Indices of the byline authors whose family name the text names. When several share that family name
        ("Hünig, S" and "Hünig, G"), only those whose given initial starts the word before it."""
        folded = _fold(text)
        hits = {}
        for i, a in enumerate(authors):
            found = [m.start() for m in re.finditer(r"(?<!\w)" + re.escape(a["family"]) + r"(?!\w)", folded)] \
                if a["family"] else []
            if found:
                hits[i] = found
        who = set(hits)
        for family in {authors[i]["family"] for i in hits}:
            tied = {i for i in hits if authors[i]["family"] == family}
            if len(tied) < 2:
                continue
            keep = {i for i in tied if authors[i]["initial"] and any(
                (w := re.search(r"([\w.'-]+)\s+$", folded[:start])) and w.group(1).startswith(authors[i]["initial"])
                and w.group(1).strip(".") not in _DEGREE_TOKENS for start in hits[i])}
            if keep:
                who -= tied - keep
        return who

    @staticmethod
    def _add(author, aff):
        aff = _clean(aff)
        if aff and aff not in author["affiliations"]:
            author["affiliations"].append(aff)

    # ---- "Affiliation: names" block of reviews and original articles

    def _autoren(self, block, authors):
        groups, pending, current = [], [], None
        for text, _ in _lines(block):
            parts = text.split(": ") if ": " in text else [text]
            if text.endswith(":"):
                parts = text[:-1].split(": ") + [""]
            for k, part in enumerate(parts):
                ends_with_colon = k < len(parts) - 1
                if ends_with_colon and k > 0 and current is not None and not self._who(part, authors):
                    current["aff"] += ": " + part.strip()  # a colon inside the affiliation itself
                    continue
                if ends_with_colon:
                    who = self._who(part, authors) if current is not None else set()
                    if who:  # names of the group before, then (no line break) the next affiliation
                        ends = [m.end() for i in who for m in re.finditer(
                            r"(?<!\w)" + re.escape(authors[i]["family"]) + r"(?!\w)", _fold(part))]
                        cut = max(ends)
                        current["names"] |= who
                        part = part[cut:]
                    pending.append(part)
                    current = {"aff": " ".join(p.strip() for p in pending if p.strip()), "names": set()}
                    groups.append(current)
                    pending = []
                elif _TITLE_ONLY.match(part):
                    continue
                elif (who := self._who(part, authors)) and current is not None:
                    current["names"] |= who
                else:
                    pending.append(part)
        for g in groups:
            for i in sorted(g["names"]):
                self._add(authors[i], g["aff"])

    # ---- address paragraphs (letters, research letters) and supplement author lines

    def _address_lines(self, lines, authors):
        groups, current, last_was_name, skipping = [], None, False, False
        for text, bold in lines:
            text = _clean(text)
            if not text or _CORR_LABEL.match(text) or _CONTACT.match(text):
                continue
            if _STOP.match(text):
                break
            if text.startswith("*"):  # "*The authors share co-first authorship"
                continue
            if _ON_BEHALF.search(text):
                skipping = True  # "for the German Society of ..." and its continuation lines: not an affiliation
                continue
            who = self._who(text, authors)
            org = _ORG.search(text)
            if (who and (bold or not org)) or ((bold or _TITLED.match(text)) and not org):
                skipping = False
                if current is None or not last_was_name:
                    current = {"names": set(), "lines": [], "per": [], "others": []}
                    groups.append(current)
                current["names"] |= who
                if not who and _TITLED.match(text) and _person(text):
                    current["others"].append(_person(text))  # a signatory the byline leaves out
                last_was_name = True
                continue
            last_was_name = False
            if current is None or skipping:
                continue
            # research letters: "Affiliation (Family, Family), Affiliation (Family)"
            start, per = 0, []
            for m in re.finditer(r"\(([^()]*)\)", text):
                named = self._who(m.group(1), authors)
                if named:
                    per.append((text[start:m.start()], named))
                    start = m.end()
            if per:
                current["per"].extend(per)
                rest = _clean(text[start:])
                if rest:
                    current["lines"].append(rest)
            else:
                current["lines"].append(text)  # short lines too: a department or the town under the institution
        # The address paragraphs list every signatory. When each byline author is found there, a titled name the byline
        # lacks ("In Reply" letters often carry only the first) is a co-author, with the address under it.
        named = set().union(*(g["names"] for g in groups), *(n for g in groups for _, n in g["per"]))
        add_others = len(named) == len(authors)
        for g in groups:
            for aff, who in g["per"]:
                for i in sorted(who):
                    self._add(authors[i], aff)
            if g["per"]:
                continue
            members = sorted(g["names"])
            if add_others:
                for name in map(self._full_name, g["others"]):
                    authors.append(_author(name, name.split()[-1], name.split()[0] if " " in name else ""))
                    members.append(len(authors) - 1)
            if not g["lines"]:
                continue
            joined = g["lines"][0]
            for line in g["lines"][1:]:  # "Klinik für<br/>Gastroenterologie": one name broken over two lines
                joined += (" " if _OPEN_END.search(joined) else ", ") + line
            if not any(len(l.split()) > 3 or _ORG.search(l) for l in g["lines"]) \
                    and not (len(g["lines"]) > 1 and any(_POSTCODE.search(l) for l in g["lines"])):
                continue  # a bare town ("Hannover", "Fellbach, Germany") is not an affiliation; a postal address is
            for i in members:
                self._add(authors[i], joined)

    def _full_name(self, name):
        """A family name alone ('Prof. Dr. med. Chun'): its given name from the line naming the article replied to
        ('... by PD Dr. med. Marc Regier, Prof. Dr. med. Felix Chun in issue 24/2015')."""
        if " " in name:
            return name
        bezug = self.soup.select_one("div.bezug")
        text = _utf8(bezug.get_text(" ", strip=True)) if bezug is not None else ""
        m = re.search(r"((?:[A-ZÄÖÜ][\w'-]*\.?\s+){1,3})" + re.escape(name) + r"(?!\w)", text)
        given = _person(m.group(1)) if m else ""
        return f"{given} {name}".strip()

    def _plain_address(self, container):
        """2008-2010 letters: no address classes; the address lines follow the article's own "DOI: ..." line as plain
        <BR> lines, up to the conflict of interest statement or the end of the text."""
        citation = self.soup.select_one("div.citation")
        m = re.search(r"DOI:\s*(10\.3238/\S+)", citation.get_text(" ")) if citation is not None else None
        if not m:
            return []
        own = re.compile(r"DOI:\s*" + re.escape(m.group(1).rstrip(".,;")) + r"\s*$", re.I)
        nodes = container.find_all(string=own)
        if not nodes:
            return []
        lines, buf = [], []
        for node in nodes[-1].next_siblings:
            if isinstance(node, Tag) and node.name == "br":
                lines.append("".join(buf))
                buf = []
            elif isinstance(node, NavigableString) and not isinstance(node, Comment):
                buf.append(str(node))
            elif isinstance(node, Tag) and node.name in _INLINE:
                buf.append(node.get_text())
            else:
                break
        lines.append("".join(buf))
        return [(t, False) for t in (_utf8(re.sub(r"\s+", " ", l).strip()) for l in lines) if t]

    # ---- corresponding author

    def _mark_corresponding(self, container, authors):
        lines = [_utf8(l.strip()) for l in container.get_text("\n").split("\n")]
        lines = [l for l in lines if l]
        for k, line in enumerate(lines):
            m = _CORR_LABEL.match(line)
            if not m or len(line) > 60 + len(m.group(1)):
                continue
            target = m.group(1) or (lines[k + 1] if k + 1 < len(lines) else "")
            who = self._who(target, authors)
            if len(who) == 1:
                authors[who.pop()]["is_corresponding"] = True

    def parse(self):
        if not self.is_publisher_specific_parser():
            return self.no_authors_output()
        authors = self._byline()
        container = self.soup.find(id="artikel") or self.soup.body or self.soup
        autoren = self.soup.find(id="autoren")
        if autoren is not None:
            self._autoren(autoren, authors)
        else:
            lines, seen = [], set()
            for el in container.select(".Anschrift_der_Verfasser, .Autor_nach_Artikel, .Autor_Taetigkeit, "
                                       ".Autor_nach_Artikel_Taetigkeit"):
                if any(id(parent) in seen for parent in el.parents):
                    continue  # already read with the element around it
                seen.add(id(el))
                lines.extend((t, b or "Autor_nach_Artikel" in (el.get("class") or [])) for t, b in _lines(el))
            self._address_lines(lines or self._plain_address(container), authors)
        self._mark_corresponding(container, authors)
        return {"authors": [{"name": a["name"], "affiliations": a["affiliations"],
                             "is_corresponding": a["is_corresponding"]} for a in authors],
                "abstract": None}
