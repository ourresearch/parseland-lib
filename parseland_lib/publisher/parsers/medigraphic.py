"""Medigraphic article pages, medigraphic.com (oxjob #2339): Mexican medical journals, DOI prefix 10.35366. Every page
carries <meta name="citation_publisher" content="Medigraphic"> and the byline in citation_author tags.

The generic reader already gets the byline and the abstract from the meta tags and the page; this parser keeps those as
they are and adds what only the page's own markup says: the corresponding author, whom the full-text pages name in a
"CORRESPONDENCIA" section after the affiliations ("<p><strong>CORRESPONDENCIA</strong></p><strong>Dra. Ana Gabriela
Gallardo-Hernández</strong>. E-mail: ..."). The section's name is matched to the byline: the visible text and the meta
tags each sometimes drop accented letters ("Dez-Ulloa" / "Díez-Ulloa"), and the tags may give given names as initials
("PS Vaca-Prez" for "Paul Santiago Vaca-Prez").
Left to other readers: affiliations (the "AFILIACIONES" list; too few works lack them to earn code by #2339's floor),
the "REFERENCIAS" list (the works already have their references) and the "Financiamiento" lines (they say "no funding").
"""
import re

import unidecode

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import same_person, squash

# honorifics before the correspondent's name: "Dr.", "Dra.", "Mtro.", "M.C.", "Dr. en C."
_TITLES = re.compile(
    r"^(?:(?:dr|dra|drs|mtro|mtra|lic|prof|profa|ing|m\.?\s?c|msc|enf|psic|biol|q\.?f\.?b|c\.?d|mvz)\.?\s+"
    r"(?:en\s+c(?:iencias)?\.?\s+)?)+", re.I)
# where the name ends: its e-mail label or address, a phone, an address, or punctuation
_NAME_END = re.compile(r"\s*(?:\(?e-?\s?mail|correo|email|tel[ée]?f|tel\.|direcci[oó]n|[\w.+-]+@|[,;:(])", re.I)
_WORD_SPLIT = re.compile(r"[\s\-‐‑–.]+")


def _tokens(name):
    """A name's words, lower-case ASCII letters only; given names run together as capitals ("PS", "JCV") become one
    initial each. Markup inside a tag's value ("Yesid Alexander<sup>1</sup> Cetina-Daz") is dropped."""
    words = []
    for word in _WORD_SPLIT.split(re.sub(r"<[^>]+>|\d+", " ", name or "")):
        if 2 <= len(word) <= 3 and word.isalpha() and word.isupper():
            words.extend(c.lower() for c in word)
        elif folded := re.sub(r"[^a-z]", "", unidecode.unidecode(word).lower()):
            words.append(folded)
    return words


def _is_subsequence(short, long):
    letters = iter(long)
    return all(c in letters for c in short)


def _same_word(a, b):
    """Equal, or one is the other with up to two letters dropped (an accented letter the page lost: "sal" / "saul")."""
    if a == b:
        return True
    short, long = sorted((a, b), key=len)
    return len(short) >= 3 and len(long) - len(short) <= 2 and _is_subsequence(short, long)


def _same_or_initial(a, b):
    return _same_word(a, b) or (len(a) == 1 and b.startswith(a)) or (len(b) == 1 and a.startswith(b))


def _pick(names, wanted):
    """The index of the one byline name that is the wanted person, or None: an exact match first, then word by word
    (dropped letters, initials), then the shared same_person rule; a tie at a level marks no one."""
    key = _tokens(wanted)
    if not key:
        return None
    keys = [_tokens(n) for n in names]
    tests = (lambda i: keys[i] == key,
             lambda i: len(keys[i]) == len(key) and all(map(_same_or_initial, keys[i], key)),
             lambda i: same_person(names[i], wanted))
    for test in tests:
        hits = [i for i in range(len(names)) if keys[i] and test(i)]
        if hits:
            return hits[0] if len(hits) == 1 else None
    return None


class Medigraphic(PublisherParser):
    parser_name = "medigraphic"

    def is_publisher_specific_parser(self):
        # Every page is offered to this parser, so the claim looks at one meta tag in the small <head> only (#2239's
        # per-page CPU rule); the answer is kept, since authors_found() and the caller both ask.
        if not hasattr(self, "_claimed"):
            head = self.soup.head
            tag = head.find("meta", attrs={"name": "citation_publisher"}) if head is not None else None
            self._claimed = bool(tag is not None and squash(tag.get("content") or "").lower() == "medigraphic")
        return self._claimed

    def _generic(self):
        if not hasattr(self, "_generic_parser"):
            self._generic_parser = GenericPublisherParser(self.soup)
        return self._generic_parser

    def authors_found(self):
        # exactly when the generic reader, whose byline and abstract this parser keeps, would have answered
        return self.is_publisher_specific_parser() and bool(self._generic().authors_found())

    def correspondent(self):
        """The name the "CORRESPONDENCIA" section gives, without honorifics, or None."""
        for strong in self.soup.find_all("strong"):
            if squash(strong.get_text()).upper() != "CORRESPONDENCIA":
                continue
            heading = strong.find_parent("p") or strong
            parts = []
            for sibling in heading.next_siblings:
                if getattr(sibling, "name", None) in ("br", "p", "div"):
                    if squash(" ".join(parts)):
                        break
                    continue
                parts.append(sibling.get_text(" ") if getattr(sibling, "name", None) else str(sibling))
            name = _NAME_END.split(squash(" ".join(parts)), 1)[0].strip(" .,")
            return _TITLES.sub("", name).strip(" .,") or None
        return None

    def parse(self):
        generic = self._generic().parse()
        authors = [dict(a) for a in generic.get("authors") or []]
        if authors and (name := self.correspondent()):
            chosen = _pick([a["name"] for a in authors], name)
            if chosen is not None:
                authors = [dict(a, is_corresponding=(i == chosen)) for i, a in enumerate(authors)]
        return {"authors": authors, "abstract": generic.get("abstract")}
