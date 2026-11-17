"""Les Classiques des sciences sociales (classiques.uqac.ca, DOIs 10.1522/...): the byline of a record page and the
affiliation line under it (oxjob #2339).

UQAC's digital library of French-language social science books and articles. Each record page is hand-made HTML
(generator "WebExpert 6") whose <meta name="author"> is the library's founder and maintainer, Jean-Marie Tremblay, as is
its Dublin Core creator: so no meta tag names the work's author, and Parseland read no byline here. The page prints the
author under the collection's title (<div class="titrecollection">): the name in a size-5 font, life dates beside it,
then a small-font line saying who the author is. That line is an affiliation when it names an employer ("sociologue,
departement de sociologie, UQAM" -> "departement de sociologie, UQAM"); a role, a biography, a former employer
("retraite de l'UQAM"), a degree or the time someone taught somewhere is not (label-v1: employers, never biographies).
Two authors share one line ("X et Y" over "sociologues, Departement de sociologie, ..."): both get it.

Not read: the abstract (the page links to a separate "Resume" or "Quatrieme de couverture" page and prints none; the
description tags hold the site's own blurb), references, acknowledgments and funding (none printed), and a
corresponding author (the e-mail under the reproduction-permission note, with the site's mailbox icon that it puts
beside every address, its own included, is a contact, not a mark).

Constellation (UQAC's EPrints repository) and UQAC's Open Journal Systems journals share the 10.1522 prefix and keep
their own parsers (eprints.py, the OJS readers).
"""
import re

from parseland_lib.publisher.parsers.parser import PublisherParser

_MAINTAINER = "Jean-Marie Tremblay"

# A word that starts an employer's name. Capitalised where the lower-case word is a role ("professeur des
# universites"), either case for "departement" ("professeur au departement de sociologie").
_EMPLOYER = re.compile(
    r"\b[Dd][ée]partements?\b|\bDepartment\b|\bFacult[ée]\b|\bFaculty\b|\bUniversit(?:[éeày]|at)\w*|\b[ÉE]cole\b"
    r"|\bInstitut(?:e)?\b|\bLaboratoire\b|\bLaboratory\b|\bCentre\b|\bCenter\b|\bMinist[èe]re\b|\bMinistry\b"
    r"|\bService d|\bCNRS\b|\bINRS\b|\bINSERM\b|\bEHESS\b|\bUQ[AÀ]M\b|\bUQAC\b|\bUQTR\b|\bUQAR\b|\bUQAT\b|\bUQO\b"
    r"|\bT[ÉE]LUQ\b|\bC[ée]gep\b|\bColl[èe]ge\b|\bCollege\b|\bH[ôo]pital\b|\bHospital\b|\bMus[ée]e\b|\bChaire\b")
# A line about the past or a degree: a former employer is biography, not an affiliation.
_NOT_EMPLOYER = re.compile(
    r"(?i)\bretrait[ée]e?s?\b|\bretired\b|\bd[ée]c[ée]d[ée]e?\b|\bancien(?:ne)?s?\b|\bex-|\ba enseign|\ba [ée]t[ée]\b"
    r"|\bfut\b|\b[ée]tait\b|^\W*docteur|\bdoctorat\b|\bdipl[ôo]m|\bPh\.?\s?D\b")
_DATES = re.compile(r",?\s*\(?\[?\s*\d{3,4}\s*[-–—]\s*(?:\d{2,4})?\s*\)?\]?")
_BRACKETED = re.compile(r"\([^)]*\)|\[[^\]]*\]")
_HONORIFIC = re.compile(r"^(?:Dr|Pr|Prof|Mgr)\.?\s+")
_NAME_SPLIT = re.compile(r"\s+et\s+|\s+and\s+|\s*&\s*|\s*,\s*|\s*;\s*")
_NAME_TOKEN = re.compile(r"^(?:[dl]['’])?[A-ZÀ-ÖØ-Þ][\w.'’-]*$")
_PARTICLES = {"de", "du", "des", "la", "le", "van", "von", "der", "den", "da", "di", "dos", "das", "y", "e", "ibn", "ben",
              "al", "el"}


def _unmojibake(text):
    """The record pages declare iso-8859-1, but a stored body can be UTF-8: repair what the decoding garbled."""
    if "Ã" in text or "â€" in text or "â\x80" in text or "Â" in text:
        for codec in ("cp1252", "latin-1"):
            try:
                return text.encode(codec).decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
    return text


def _cp1252(ch):
    try:
        return ch.encode("latin-1").decode("cp1252")
    except UnicodeDecodeError:
        return " "


_C1 = re.compile(r"[\x80-\x9f]")


def _clean(text):
    # "&#151;" and "&#146;", the old pages' Windows dash and apostrophe, decode as C1 control characters
    text = _C1.sub(lambda m: _cp1252(m.group(0)), _unmojibake(text))
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


_PAIR = {")": "(", "]": "[", "(": ")", "[": "]"}
_EDGE = " ,;.\"«»"


def _trim(text):
    """Strip edge punctuation and any edge bracket that opens or closes nothing, keeping one that does ("CNRS
    (langues, langages, discours)"; "[Professeur associe, Universite du Quebec en Outaouais]" -> "Universite ...")."""
    text = text.strip(_EDGE)
    while text and text[-1] in ")]" and text.count(text[-1]) > text.count(_PAIR[text[-1]]):
        text = text[:-1].strip(_EDGE)
    while text and text[0] in "([" and text.count(text[0]) > text.count(_PAIR[text[0]]):
        text = text[1:].strip(_EDGE)
    return text


def _lines(block):
    """The block's text, one string per line as the page shows it (split at <br> and <p>)."""
    parts = []
    for node in block.descendants:
        if getattr(node, "name", None) in ("br", "p"):
            parts.append("\n")
        elif node.name is None and type(node).__name__ == "NavigableString":
            parts.append(str(node))
    return [line for line in (_clean(x) for x in "".join(parts).split("\n")) if line]


def _names(line):
    line = _BRACKETED.sub(" ", line.replace("†", " ").replace("*", " "))
    line = _DATES.sub(" ", line)
    names = []
    for piece in _NAME_SPLIT.split(line):
        name = _HONORIFIC.sub("", piece.strip(" .,;:-–—\"'«»"))
        tokens = name.split()
        # a person: at least two words, each capitalised but for particles ("Alexis de Tocqueville"); a work's title
        # in the name slot ("Tchou-Tchou-Ki-Nien") is one word, and "sous la direction de" is lower case
        if (len(tokens) >= 2 and len(name) <= 80 and _NAME_TOKEN.match(tokens[0]) and _NAME_TOKEN.match(tokens[-1])
                and all(_NAME_TOKEN.match(t) or t in _PARTICLES for t in tokens)):
            names.append(name)
    return names


def _affiliations(lines):
    affs, joins_next = [], False
    for line in lines:
        if len(line) > 250 or _NOT_EMPLOYER.search(line):
            joins_next = False
            continue
        match = _EMPLOYER.search(line)
        if not match:
            joins_next = False
            continue
        aff = _trim(line[match.start():])
        if joins_next and match.start() == 0:
            affs[-1] = f"{affs[-1]}, {aff}"  # "Laboratoire d'Ecologie humaine,<br> Universite d'Aix-Marseille"
        elif aff:
            affs.append(aff)
        joins_next = line.rstrip().endswith(",")
    return affs


class ClassiquesUQAC(PublisherParser):
    parser_name = "classiques_uqac"
    # the byline beats the meta tags: the page's author and creator tags name the site's maintainer
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        if not hasattr(self, "_claim"):
            # Every parser's claim runs on every DOI page (#2239): look only at the <head>'s own children, never the
            # whole document.
            html = self.soup.find("html", recursive=False)
            head = html.find("head", recursive=False) if html is not None else None
            self._claim = head is not None and head.find(
                "meta", attrs={"name": "author", "content": _MAINTAINER}, recursive=False) is not None
        return self._claim

    def _byline(self):
        if not hasattr(self, "_block"):
            self._block = None
            title = self.soup.find("div", class_="titrecollection")
            block = title.find_next("center") if title is not None else None
            if block is not None and block.find("font", attrs={"size": "5"}) is not None:
                self._block = block
        return self._block

    def authors_found(self):
        return self.is_publisher_specific_parser() and self._byline() is not None

    def parse(self):
        block = self._byline() if self.is_publisher_specific_parser() else None
        lines = _lines(block) if block is not None else []
        names = _names(lines[0]) if lines else []
        affs = _affiliations(lines[1:]) if names else []
        return {"authors": [{"name": name, "affiliations": list(affs), "is_corresponding": False} for name in names],
                "abstract": None}
