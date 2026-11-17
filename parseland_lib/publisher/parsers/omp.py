"""Open Monograph Press (PKP's book platform) book and chapter pages (oxjob #2289).

OMP runs ~140 university and small presses' book sites (usp.br, unesp.br, Baltija Publishing, uni-lj.si, liha-pres.eu,
...). No publisher parser claims them, so the meta-tag parser wins: it reads the citation_author tags, which on most
OMP sites carry no citation_author_institution. The page itself prints each author's affiliation in the monograph's
"item authors" block, in one of two forms:
- OMP 3.1 / 3.4 / 3.5 themes: one `div.sub_item` per author, the name in `div.label`, the affiliation in `div.value`
  (a value that only names a role, "(Author)", or holds a nested role and name, is not an affiliation);
- OMP 3.3: inline `<span class="label">Name</span>, <span class="value">Affiliation</span>; ...`.
This parser keeps the meta-tag parser's whole result (byline, abstract) and adds those affiliations, each to the one
tagged author whose name it matches (the block may write the family name first or a shorter public name). It never adds
or drops an author: the block may list only a chapter's authors or the volume editors, and the tags the whole book's.
A tagged author the block gives none gets the one OMP prints in the "about the authors" block, where each biography is
headed "Name, <span class="affiliation">Affiliation</span>" (an edited volume's block names only its editors, its
biographies every chapter's authors; a chapter DOI lands on the book's page). Biography text is never read.
It answers only on pages where no other parser gives an affiliation (the tags give none, nor does the Thieme parser,
which reads some themes' span.affiliation) and these blocks add at least one; on every other page the winning
parser's result stands as before, byline and abstract included.
"""
import copy
import re
import unicodedata

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

_OMP_GENERATOR = re.compile(r"^\s*Open Monograph Press\b", re.I)
_ROLE_ONLY = re.compile(r"^\(.*\)$")  # "(Author)", "(Editor)"


def _tokens(name):
    """A name's words, case- and accent-blind ("Lazo-Galán Juan Carlos" -> {lazo, galan, juan, carlos})."""
    text = unicodedata.normalize("NFKD", (name or "").casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return frozenset(t for t in re.split(r"[\W_]+", text) if t)


def _has_affiliations(parsed):
    authors = parsed.get("authors") if isinstance(parsed, dict) else parsed
    return any((a.get("affiliations") if isinstance(a, dict) else getattr(a, "affiliations", None))
               for a in authors or [])


def _matched(keys, entries):
    """{tagged author's index: affiliations} for the entries whose name matches one tagged author's (keys: _tokens)."""
    found = {}
    for name, affs in entries:
        block_key = _tokens(name)
        if not affs or not block_key:
            continue
        same = [i for i, k in enumerate(keys) if k == block_key]
        # else one name's words inside the other's ("Marta Ruiz" in "Marta Ruiz de la Vega"), two words at least
        near = same or [i for i, k in enumerate(keys) if min(len(k), len(block_key)) >= 2 and (
            block_key <= k or k <= block_key)]
        if len(near) == 1:
            found.setdefault(near[0], []).append(affs)
    # an author two entries claim is left alone
    return {i: a[0] for i, a in found.items() if len(a) == 1}


def _affiliation(value):
    if value.find(class_=("label", "role")) is not None:  # a role and a name, not an affiliation
        return None
    text = squash(value.get_text(" "))
    return None if not text or _ROLE_ONLY.match(text) else text


class OpenMonographPress(PublisherParser):
    parser_name = "Open Monograph Press"

    def is_publisher_specific_parser(self):
        # Every parser's claim runs on every DOI page (#2239's per-page CPU rule): the generator tag is looked for in
        # the small <head> only, and the answer is kept (authors_found() and the caller both ask).
        if not hasattr(self, "_claimed"):
            head = self.soup.head
            generator = head.find("meta", attrs={"name": "generator"}) if head is not None else None
            self._claimed = bool(generator and _OMP_GENERATOR.match(generator.get("content") or ""))
        return self._claimed

    def _block_entries(self):
        """[(name, [affiliation])] from the monograph's "item authors" block, in page order."""
        block = self.soup.select_one("div.item.authors")
        if block is None:
            return []
        entries = []
        subs = block.select(".sub_item")
        if subs:
            for sub in subs:
                label = next((l for l in sub.select(".label") if l.find_parent(class_="value") is None), None)
                if label is None:
                    continue
                affs = [a for v in sub.select(".value") if (a := _affiliation(v))]
                entries.append((squash(label.get_text(" ")), affs))
            return entries
        for node in block.find_all(class_=("label", "value")):
            classes = node.get("class") or []
            if "label" in classes:
                entries.append((squash(node.get_text(" ")), []))
            elif entries and (aff := _affiliation(node)):
                entries[-1][1].append(aff)
        return entries

    def _biography_entries(self):
        """[(name, [affiliation])] from the "about the authors" block's headings: "Name, <span class="affiliation">..."."""
        entries = []
        for label in self.soup.select("div.item.author_bios .sub_item > .label"):
            affs = [a for span in label.select(".affiliation") if (a := squash(span.get_text(" ")))]
            if not affs:
                continue
            name = "".join(t for t in label.find_all(string=True) if t.find_parent(class_="affiliation") is None)
            if name := squash(name).strip(" ,;"):
                entries.append((name, affs))
        return entries

    def _other_parser_gives_affiliations(self):
        """Whether any other parser that reads this page's byline gives an affiliation: without this parser, that one
        wins the page (parse_publisher_authors_abstract), and its answer stands. Run on a copy of the page, so that a
        parser that edits its soup changes nothing for the parsers the caller runs after this one.
        shortcut: one more pass of every parser, ~75 ms, on the OMP pages that get this far (the generator tag claims
        none of the others); read the winner from the caller instead if OMP pages ever weigh in the parse budget."""
        soup = copy.copy(self.soup)
        for cls in PublisherParser.__subclasses__():
            if cls is type(self) or cls is GenericPublisherParser:
                continue
            try:
                parser = cls(soup)
                if parser.authors_found() and _has_affiliations(parser.parse()):
                    return True
            except Exception:  # noqa: BLE001 (the caller skips a parser that fails the same way)
                continue
        return False

    def _with_affiliations(self):
        """The meta-tag parser's result with the blocks' affiliations added, or None when they add none."""
        if hasattr(self, "_result"):
            return self._result
        self._result = None
        generic = GenericPublisherParser(self.soup).parse()
        authors = generic.get("authors") or []
        if not authors or any(a.get("affiliations") for a in authors):
            return None
        keys = [_tokens(a.get("name")) for a in authors]
        added = _matched(keys, self._block_entries())
        # then the biographies' headings, for the tagged authors the block gave none
        added.update({i: a for i, a in _matched(keys, self._biography_entries()).items() if i not in added})
        if not added or self._other_parser_gives_affiliations():
            return None
        self._result = dict(generic, authors=[dict(a, affiliations=list(added.get(i, a.get("affiliations") or [])))
                                              for i, a in enumerate(authors)])
        return self._result

    def authors_found(self):
        return self.is_publisher_specific_parser() and self._with_affiliations() is not None

    def parse(self):
        return self._with_affiliations() or GenericPublisherParser(self.soup).parse()
