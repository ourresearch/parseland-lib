"""Confex webprogram abstract pages (oxjob #2338, Parseland swarm).

Conference abstracts on Confex's "webprogram" (<society>.confex.com/<society>/<meeting>/webprogram/Paper<n>.html; the
stored DOI pages are the Geological Society of America's, 10.1130/abs/...). The page prints the whole byline in
div.paperauthors and the abstract in div.abstract. Its citation_author tags name only the presenting author, and pages
before 2018 have none, so the generic parser read one author (or none) and no abstract.

The byline comes in two styles, surnames always in capitals ("SURNAME, Given"):
  numbered    CHANG, Queenie<sup>1</sup>, HREN, Michael T.<sup>2</sup> and ..., (1)Affiliation, (2)Affiliation
  unnumbered  BROWN, Sarah R., Affiliation, ANDREWS, Graham D.M., Affiliation and MUSGRAVE, Robert, Affiliation
              (a run of authors that share an affiliation is followed by it once: "A, B and C, Affiliation")
One author's several affiliations are separated by semicolons; an e-mail address may end the byline. The bold name is
the presenting author, not a corresponding author, and nothing else on the page marks one.
"""
import copy
import re

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import EMAIL_RE, squash

_STYLESHEET = "webprogram.css"  # the webprogram's own stylesheet, linked from <head> on every page
_SUP = re.compile("\x01([^\x02]*)\x02")
_AFF_NUMBER = re.compile(r"\((\d{1,2})\)")
_PARAGRAPH = " "
_SUFFIX = re.compile(r"\s+(?:Jr\.?|Sr\.?|II|III|IV)$")
_PARTICLES = {"van", "von", "der", "den", "de", "da", "das", "dos", "di", "du", "del", "della", "la", "le", "y", "e",
              "al", "el", "bin", "ibn", "ten", "ter"}
# Capitals that open an affiliation part, not a surname ("NOAA, Boulder, CO 80305" must not read as an author).
# shortcut: a fixed list; an acronym it misses followed by a one-word place splits that author's affiliation in two
_ACRONYMS = {"USGS", "NOAA", "NASA", "NCAR", "NSF", "NPS", "BLM", "USDA", "NRCS", "EPA", "DOE", "USACE", "USFS", "CNRS",
             "IRD", "CSIC", "CSIRO", "INSTAAR", "UNAVCO", "IRIS", "LANL", "LLNL", "ORNL", "PNNL", "NETL", "CIRES", "BGS",
             "GSC", "GSA", "AGU", "USA", "UK", "UAE", "PRC", "CU", "UC", "MIT", "INC", "LLC", "LTD", "CEO", "PHD"}
# words that never stand in a given name, only in an organisation or a place
_NOT_GIVEN = {"university", "universidad", "universidade", "universite", "universität", "department", "dept",
              "institute", "instituto", "center", "centre", "survey", "museum", "college", "school", "laboratory",
              "laboratories", "lab", "labs", "society", "program", "programme", "division", "office", "service",
              "services", "agency", "foundation", "group", "inc", "llc", "ltd", "corp", "corporation", "company",
              "consulting", "consultants", "associates", "research", "science", "sciences", "geology", "geosciences",
              "engineering", "hall", "building", "road", "street", "st", "ave", "avenue", "drive", "blvd", "park",
              "city", "county", "state", "national", "natural", "history", "resources", "energy", "environmental",
              "earth", "water", "marine", "ocean", "geological", "geophysical", "technology", "polytechnic",
              "academy", "observatory", "station", "bureau", "commission", "council", "ministry", "authority",
              "district", "region", "campus", "faculty", "unit", "project", "network", "international", "republic",
              "of", "and", "for", "the"}


def _has_webprogram_stylesheet(soup):
    """The claim's cheap first test: every parser is asked about every DOI page (#2239: under 0.5 ms a page it does
    not claim), so only <head>'s own <link> children are looked at, reached through direct children."""
    html = soup.find("html", recursive=False)
    head = (html or soup).find("head", recursive=False)
    if head is None:
        return False
    return any(_STYLESHEET in (link.get("href") or "") for link in head.find_all("link", recursive=False))


def _is_surname(text):
    """A byline surname: capitals ("TERRY Jr.", "FOUH MBINDI", "AL-KAABI", "van der PLUIJM"), no digits."""
    words = _SUFFIX.sub("", text).split()
    core = [w for w in words if w not in _PARTICLES]
    letters = [c for w in core for c in w if c.isalpha()]
    if len(letters) < 2 or not all(c.isupper() for c in letters) or " ".join(core) in _ACRONYMS:
        return False
    if len(letters) > 2 and not any(c in "AEIOUYÀÁÂÃÄÅÆÈÉÊËÌÍÎÏÒÓÔÕÖØÙÚÛÜÝ" for c in letters):  # "USGS", "NRCS"
        return False  # (a two-letter surname such as "NG" has none either)
    return all(re.fullmatch(r"[^\W\d_]+(?:['’.\-][^\W\d_]*)*\.?", w) for w in core)


def _is_initials(word):
    """'C.', 'D.M.', 'J.-P.', 'A'."""
    letters = [c for c in word if c.isalpha()]
    return bool(re.fullmatch(r"(?:[^\W\d_]\.?-?)+", word)) and all(c.isupper() for c in letters) and (
            len(letters) == 1 or "." in word)


def _is_capitalised(word):
    """'Kent', 'Md.', 'Suk-Joo', 'Michał': a capital, then small letters up to any hyphen; not 'CU'."""
    first = word[1:].split("-")[0]
    return word[0].isupper() and any(c.islower() for c in first) and not any(c.isupper() for c in first) and bool(
        re.fullmatch(r"[^\W\d_]+(?:['’.\-][^\W\d_]*)*\.?", word))


def _is_given(text):
    """A byline given name: "Kent C.", "Graham D.M.", "Nur Uddin Md. Khaled", "Michał", "J.-P."; not "CU Boulder"."""
    words = text.split()
    if not 1 <= len(words) <= 5:
        return False
    named = False
    for w in words:
        if w.lower().strip(".") in _NOT_GIVEN and w not in _PARTICLES:
            return False
        if w in _PARTICLES:
            continue
        if not (_is_initials(w) or _is_capitalised(w)):
            return False
        named = True
    return named


def _affiliations(text):
    """One author's affiliation text: several affiliations are separated by semicolons; no e-mail addresses."""
    text = squash(EMAIL_RE.sub("", text))
    return [part for p in text.split(";") if (part := squash(p).strip(" ,;"))]


def _split_name(text):
    """'CHANG, Queenie' -> 'Queenie CHANG'; None when the text is not a byline name."""
    surname, sep, given = text.partition(",")
    if sep and _is_surname(surname.strip()) and _is_given(given.strip()):
        return f"{given.strip()} {surname.strip()}"
    return None


def _numbered(text):
    """'NAME<1>, NAME<2> and NAME<1>, (1)Affiliation, (2)Affiliation' (sup marks as \\x01..\\x02)."""
    last = text.rfind("\x02")
    names_part, affs_part = text[:last + 1], text[last + 1:]
    affs, expected, cut = {}, 1, []
    for m in _AFF_NUMBER.finditer(affs_part):  # (1), (2) ... in order; any other "(n)" belongs to the text
        if int(m.group(1)) == expected:
            cut.append(m)
            expected += 1
    for i, m in enumerate(cut):
        end = cut[i + 1].start() if i + 1 < len(cut) else len(affs_part)
        affs[m.group(1)] = _affiliations(affs_part[m.end():end])
    if not cut or affs_part[:cut[0].start()].strip(" ,"):
        return None
    authors = []
    for m in re.finditer("([^\x01\x02]*)\x01([^\x02]*)\x02", names_part):
        raw = re.sub(r"^and\s+", "", m.group(1).strip(" ,"))
        if not (name := _split_name(raw)):
            return None
        own = [a for n in re.findall(r"\d+", m.group(2)) for a in affs.get(n, [])]
        authors.append({"name": name, "affiliations": own, "is_corresponding": None})
    return authors or None


def _tokens(text):
    """The byline's comma-separated parts, with 'X and SURNAME' split where a surname follows the 'and'."""
    out = []
    for part in text.split(","):
        part = part.strip()
        for m in re.finditer(r"\s+and\s+", part):
            if _is_surname(part[m.end():]):
                out += [part[:m.start()].strip(), part[m.end():].strip()]
                break
        else:
            out.append(part)
    return [t for t in out if t]


def _unnumbered(text):
    """'SURNAME, Given, Affiliation, ..., SURNAME, Given and SURNAME, Given, Affiliation': an affiliation belongs to
    the run of authors before it."""
    tokens = _tokens(squash(EMAIL_RE.sub("", text)))
    authors, waiting, group, i = [], [], [], 0
    while i < len(tokens):
        if i + 1 < len(tokens) and _is_surname(tokens[i]) and _is_given(tokens[i + 1]):
            if group:
                for a in waiting:
                    a["affiliations"] = _affiliations(", ".join(group))
                waiting, group = [], []
            author = {"name": f"{tokens[i + 1]} {tokens[i]}", "affiliations": [], "is_corresponding": None}
            authors.append(author)
            waiting.append(author)
            i += 2
            continue
        if not authors:  # the byline must open with a name
            return None
        group.append(tokens[i])
        i += 1
    for a in waiting:
        a["affiliations"] = _affiliations(", ".join(group))
    return authors or None


def _block_lines(block):
    """The abstract's text, one line per paragraph (<p>, <div> or <br>), whitespace inside a line squashed."""
    block = copy.copy(block)  # the other parsers still read this soup
    for br in block.find_all("br"):
        br.replace_with(_PARAGRAPH)
    for p in block.find_all(["p", "div", "li"]):  # both ends: the page puts text before its first <p>
        p.insert(0, _PARAGRAPH)
        p.append(_PARAGRAPH)
    lines = [squash(line) for line in block.get_text().split(_PARAGRAPH)]
    return "\n".join(line for line in lines if line) or None


class Confex(PublisherParser):
    parser_name = "confex"
    prefer_publisher_authors_over_generic = True  # the byline lists every author; the meta tags only the presenter

    def __init__(self, soup):
        super().__init__(soup)
        self._byline = None
        self._claimed = None
        self._parsed = None

    def is_publisher_specific_parser(self):
        if self._claimed is None:
            self._byline = self.soup.find("div", class_="paperauthors") if _has_webprogram_stylesheet(self.soup) \
                else None
            self._claimed = self._byline is not None
        return self._claimed

    def authors_found(self):
        if not self.is_publisher_specific_parser():
            return False
        parsed = self.parse()
        return bool(parsed["authors"] or parsed["abstract"])

    def parse_byline(self):
        div = copy.copy(self._byline)
        for sup in div.find_all("sup"):
            sup.replace_with(f"\x01{sup.get_text()}\x02")
        text = squash(div.get_text())
        authors = _numbered(text) if "\x01" in text else _unnumbered(text)
        # a byline in neither style: the presenting author's meta tags, as before
        return authors or self.parse_author_meta_tags()

    def parse_abstract(self):
        block = self.soup.find("div", class_="abstract")
        return _block_lines(block) if block is not None else None

    def parse(self):
        if self._parsed is None:
            if not self.is_publisher_specific_parser():
                return self.no_authors_output()
            self._parsed = {"authors": self.parse_byline(), "abstract": self.parse_abstract()}
        return self._parsed
