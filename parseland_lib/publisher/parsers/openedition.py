import re

from bs4 import Comment, NavigableString, Tag

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

# OpenEdition (journals.openedition.org, books.openedition.org) prints each author's note next to their name, in one
# of four layouts (oxjob #2219):
#   journals:   #authors > h3 (name), then the note: p.description.directionltr, span.directionltr wrapping one or more
#               p.description / p.descriptionauteur (multi-author pages), or p/div.description (older pages whose
#               section lacks the "authors" class); "Articles du même auteur" (h4 + ul.documents) ends the note;
#   books:      #authors > div.author > div.name + div.description ("Du même auteur" sits in div.fromsameauthor);
#   books 2025: #anchor-persons > ul.persons > li > a > strong (name) + .tab__values__value__person__value notes.
# A note is an affiliation ("Université de Lille, laboratoire CIREL") or a biography ("X est professeure à ...
# Elle a publié ..."). Only affiliations count (label rubric label-v1: employers, departments, institutes and their
# addresses, never biographies), so a note's sentences are kept up to the first that reads as a biography, and
# e-mail addresses, links and identifier lines (IdRef, ORCID) are dropped.

ROLE_SKIP = re.compile(r"(?i)tradu|transl|übersetz")
EMAIL = re.compile(r"\(?\s*(?:courriel|e-?mail|mail|correo(?: electrónico)?)?\s*:?\s*"
                   r"[\w.+'-]+\s*(?:@|\[at\]|\(at\)|\[arobase\])\s*[\w-]+(?:\.[\w-]+)+\s*\)?", re.I)
URL = re.compile(r"\(?\s*(?:https?://|www\.)\S+", re.I)
ID_LINE = re.compile(r"(?i)^(?:idref|orcid|isni|viaf|idhal|hal|google scholar|researchgate|academia\.edu)\b")
# a sentence ends at '.', '!' or '?' after a word of 3+ letters, a number or a ')', and the next starts with a capital
# ("Ph. D. sociologie" stays one sentence)
SENTENCE_END = re.compile(r"(?:(?<=[a-zà-ÿ]{3}[.!?])|(?<=\d\d[.!?])|(?<=\)[.!?])|(?<=[.!?]\)))\s+(?=[A-ZÀ-Ý«])")
# what a sentence about the person (rather than their employer) uses: verbs, pronouns, birth, books, years
BIO = re.compile(
    r"^(?:Ses|Son|Sa|Leurs?|Sus?|Seus?|Suas?|I suoi|Le sue|La sua|Il suo"
    r"|Est|Était|Es|Fue|Foi|É|È|Is|Was|Ist|War)\s"
    r"|(?<![\w-])(?:est|était|sont|fut|avait|is|was|has|have|had|ist|war|es|fue|ha|é|foi|è)\s"
    r"|\b(?:[Ii]l|[Ee]lle)s? (?:a|est|était|enseigne|travaille|dirige|mène|participe|prépare|consacre|poursuit|"
    r"vit|s'|s’)"
    r"|[,;] (?:il|elle)s? "
    r"|\b(?:[Hh]e|[Ss]he|[Hh]is|[Hh]er|[Tt]heir)\s"
    r"|\b(?:[Nn]ée?|[Bb]orn|[Nn]aci(?:da|do)|[Nn]ato|[Nn]ata) (?:en|in|a|à|le|on)\b"
    r"|(?i:\b(?:auteure?|autrice|co-?auteur|author|co-?author|autora?|autore) (?:de|of|di|du|des|d’|d')"
    r"|\ba (?:publié|soutenu|dirigé|codirigé|co-dirigé|mené|enseigné|travaillé|consacré|obtenu|été)"
    r"|\bses (?:recherches|travaux)|\bson (?:travail|parcours)|\bresearch (?:interests|focuses)"
    r"|\bsus (?:investigaciones|trabajos)|\bdiplômée? (?:de|d’|d')|\bgraduated)"
    r"|\b(?:en|in) (?:1[89]|20)\d\d\b")
# an affiliation is short; a longer note sentence is a CV line ("Professeur de ..., titulaire de la chaire ... et
# membre du comité ...") that the gold leaves out (every kept note over 200 characters in #2219's sample was one)
MAX_AFFILIATION = 200


def _lines(el):
    """The element's text, one string per line: a <br> or a block element starts a new line."""
    out = [""]
    for node in el.descendants:
        if isinstance(node, Comment):
            continue
        if isinstance(node, NavigableString):
            out[-1] += str(node)
        elif node.name in ("br", "p", "div", "li"):
            out.append("")
    return [x for x in (squash(x) for x in out) if x]


def _is_role(el):
    """A heading or name that marks a translator, not an author."""
    return el is not None and bool(ROLE_SKIP.search(el.get_text()))


def _affiliation(line, name, surname):
    """(affiliation or None, whether the line went on into a biography). The affiliation is the line's sentences up
    to the first that reads as a biography (a verb about the person, the person's name, a year), at most
    MAX_AFFILIATION characters, without e-mail addresses or links. name and surname are lower case."""
    if ID_LINE.match(line):
        return None, False
    line = squash(URL.sub(" ", EMAIL.sub(" ", line)))
    kept, bio = [], False
    for sentence in SENTENCE_END.split(line):
        low = sentence.lower()
        if BIO.search(sentence) or name in low or (surname and low.startswith(surname)):
            bio = True
            break
        if len(" ".join(kept + [sentence])) > MAX_AFFILIATION:
            break
        kept.append(sentence)
    aff = " ".join(kept).strip(" ,;:-–|")
    return (aff if re.search(r"\w{2}", aff) else None), bio


class OpenEdition(PublisherParser):
    parser_name = "open_edition"
    # the page's own author section beats a generic reading of the same page (which takes the section heading,
    # "Auteurs", for an author on multi-author pages, and other books' titles from "Du même auteur" for authors)
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        return self.domain_in_meta_og_url('openedition.org')

    def authors_found(self):
        # every parser's authors_found runs on every page: one scan for the two author sections rejects almost all
        # of them; off OpenEdition, read only where main's claim did (a Lodel ".section.authors" block: none of the
        # gate's 2,018 dev pages off OpenEdition has one)
        if not self.soup.find(id=['authors', 'anchor-persons']):
            return False
        if not (self.is_publisher_specific_parser() or self.soup.select_one('.section.authors')):
            return False
        return bool(self.parse_authors())

    def _notes(self):
        """[(name, [note elements])] for every author in the page's author section(s)."""
        out = []
        for sec in self.soup.select('#authors'):
            if _is_role(sec.find('h2')):
                continue
            divs = sec.select('div.author')
            if divs:
                for d in divs:
                    nm = d.select_one('.name')
                    if nm and not _is_role(nm):
                        out.append((squash(nm.get_text(' ')), d.find_all('div', class_='description', recursive=False)))
                continue
            for h3 in sec.select('h3:not(.section)'):
                notes = []
                for sib in h3.next_siblings:
                    if not isinstance(sib, Tag):
                        continue
                    cls = sib.get('class') or []
                    if sib.name in ('h2', 'h3', 'h4') or (sib.name == 'ul' and 'documents' in cls):
                        break
                    if any(c.startswith('description') for c in cls) or (sib.name == 'span' and 'directionltr' in cls):
                        notes.append(sib)
                out.append((squash(h3.get_text(' ')), notes))
        for ul in self.soup.select('#anchor-persons ul.persons'):
            if _is_role(ul.find_previous_sibling('h1')):
                continue
            for li in ul.find_all('li', recursive=False):
                nm = li.find('strong')
                if nm:
                    out.append((squash(nm.get_text(' ')), li.select('.tab__values__value__person__value')))
        return [(n, notes) for n, notes in out if n]

    def parse_authors(self):
        if hasattr(self, '_authors'):
            return self._authors
        self._authors = []
        for name, notes in self._notes():
            low = name.lower()
            surname = next((p for p in reversed(low.split()) if len(p) > 2), None)
            affs = []
            for line in (x for note in notes for x in _lines(note)):
                aff, bio = _affiliation(line, low, surname)
                if aff and aff not in affs:
                    affs.append(aff)
                if bio:  # the rest of the note is about the person
                    break
            self._authors.append({'name': name, 'affiliations': affs, 'is_corresponding': None})
        return self._authors

    def parse(self):
        return {'authors': self.parse_authors(),
                'abstract': self.parse_abstract_meta_tags()}
