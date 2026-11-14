import re

from bs4 import Tag

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import EMAIL_RE, name_position, squash

# A note in Optica's Author Affiliations box that names the corresponding author (oxjob #2217):
# '<sup>*</sup>Corresponding author: x@y', older 'Corresponding author: Correspondence should be addressed to ...'.
# APS reads the same symbol-to-note convention (`aps.aps_corresponding_names`, #2146); a third site with it should share
# one helper in utils.py.
CORRESPONDING_NOTE_RE = re.compile(
    r"\bcorresponding\s+authors?\b|\bcorrespondence\s+(?:should|may|to)\b|\bto\s+whom\s+(?:any\s+)?correspondence",
    re.I)
EMAIL_LABEL_RE = re.compile(r"^e-?mail\s*(?:address)?\s*:?\s*", re.I)


def _is_email_only(text):
    """'x@y', 'e-mail: x@y.': a note that is only an e-mail address (a mark when it singles some authors out)."""
    return bool(EMAIL_RE.fullmatch(EMAIL_LABEL_RE.sub("", text).rstrip(".")))


def _norm_name(name):
    name = re.sub(r"\([^)]*\)", " ", name or "")
    return squash(re.sub(r"[^\w\s'-]", " ", name)).casefold()


def _surname(name):
    parts = _norm_name(name).split()
    return parts[-1] if parts else ""


class Optica(PublisherParser):
    parser_name = 'optica'

    def is_publisher_specific_parser(self):
        return self.domain_in_meta_og_url('optica.org')

    def authors_found(self):
        return bool(self.soup.select('#authorAffiliations'))

    @staticmethod
    def merge_authors(authors):
        authors_d = {}
        for author in authors:
            if author['name'] not in authors_d:
                authors_d[author['name']] = author
            else:
                authors_d[author['name']]['affiliations'].extend(
                    author['affiliations'])

        return list(authors_d.values())

    def parse_authors(self):
        meta_authors = self.parse_author_meta_tags()
        merged = self.merge_authors(meta_authors)
        for author in merged:
            for aff in author['affiliations']:
                if EMAIL_RE.search(aff):
                    author['is_corresponding'] = True
            author['affiliations'] = [aff for aff in author['affiliations'] if not EMAIL_RE.search(aff)]
        self._apply_corresponding_note(merged)
        return merged

    def _apply_corresponding_note(self, authors):
        """The Author Affiliations box's own corresponding-author note outranks the e-mail-in-affiliation guess."""
        names = self._noted_corresponding_names(len(authors))
        if not names:
            return
        wanted = {_norm_name(n) for n in names}
        matched = [a for a in authors if _norm_name(a['name']) in wanted]
        found = {_norm_name(a['name']) for a in matched}
        for surname in {_surname(n) for n in names if _norm_name(n) not in found}:
            hits = [a for a in authors if _surname(a['name']) == surname]
            if len(hits) == 1 and hits[0] not in matched:
                matched.append(hits[0])
        if not matched:
            return
        for author in authors:
            if author in matched:
                author['is_corresponding'] = True
            elif author.get('is_corresponding'):
                author['is_corresponding'] = False

    def _noted_corresponding_names(self, n_authors):
        box = self.soup.select_one('#authorAffiliations')
        byline = box.select_one('p > strong') if box else None
        if byline is None:
            return []
        marks = self._byline_marks(byline)
        phrase_symbols, email_symbols, unsymbolled = set(), set(), []
        for p in box.find_all('p'):
            if p.find(['strong', 'em']):
                continue
            first = next((c for c in p.children if isinstance(c, Tag) or c.strip()), None)
            symbol = first.get_text(strip=True) if isinstance(first, Tag) and first.name == 'sup' else ''
            body = squash(p.get_text(" ", strip=True).removeprefix(symbol))
            if CORRESPONDING_NOTE_RE.search(body):
                if symbol:
                    phrase_symbols.add(symbol)
                else:
                    unsymbolled.append(body)
            elif symbol and _is_email_only(body):
                email_symbols.add(symbol)
        names = [name for name, syms in marks if syms & phrase_symbols]
        if not names and email_symbols:
            names = [name for name, syms in marks if syms & email_symbols]
            if len(names) >= max(n_authors, 2):
                names = []
        if not names and unsymbolled:
            for note in unsymbolled:
                hits = [name for name, _ in marks if name_position(name, note) is not None]
                if len(hits) == 1:
                    names = hits
                    break
        return names

    @staticmethod
    def _byline_marks(byline):
        """[(name, {symbols})] from '<strong>A B,<sup>1,</sup><sup>*</sup> C D,<sup>1</sup> and E F<sup>2</sup></strong>'."""
        out, buffer = [], ''
        for child in byline.children:
            if isinstance(child, Tag) and child.name == 'sup':
                symbol = child.get_text(strip=True).strip(',').strip()
                name = re.sub(r"^\s*and\s+", "", buffer.strip().strip(',').strip())
                if name:
                    out.append((squash(name), set()))
                    buffer = ''
                if out and symbol:
                    out[-1][1].add(symbol)
            else:
                text = child.get_text() if isinstance(child, Tag) else str(child)
                buffer += text
        return out

    def parse(self):
        return {'authors': self.parse_authors(), 'abstract': self.parse_abstract_meta_tags()}
