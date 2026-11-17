"""IUCN Red List of Threatened Species (iucnredlist.org): species assessments, DOI prefix 10.2305 (oxjob #2330).

The stored pages are the site's JavaScript app shell (an empty div#redlist-js): the assessment is never in the markup,
only the citation_* meta tags in <head>. There is no abstract, corresponding-author mark, acknowledgment, funding
statement or reference list on these pages (the assessment's rationale is not an abstract, and it is not on the page
anyway). What the generic reader gets wrong is the byline: every citation_author tag carries the assessor's
affiliation in a closing parenthetical ("Nigel Taylor (RBG Kew)", "Duniel Barrios (Jardín Botánico Nacional,
Universidad de La Habana, Cuba)"), which it keeps inside the name. This parser splits it off, as both blind labellers
do (label-v1), and:
- a group whose parenthetical only repeats its name ("BirdLife International (BirdLife International)") is one author
  with no affiliation;
- the split is at the last balanced parenthetical, so a group name with its own acronym keeps it
  ("Botanic Gardens Conservation International (BGCI) (Botanic Gardens ... (BGCI), Descanso House, ...)");
- an e-mail address written as an author ("false.email@globaltrees.org", a placeholder account) is not a name and is
  dropped; a page whose only author is one keeps the generic reader's output.
No author is marked corresponding (None, as the meta-tag reader leaves it): the page marks no one.
"""
import re

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

_JOURNAL = "IUCN Red List of Threatened Species"
_SITE = "iucnredlist.org/species/"
_EMAIL = re.compile(r"^\S+@\S+\.\S+$")


def _head(soup):
    """<head>, reached through direct children only: every parser's claim runs on every page (#2239: under 0.5 ms a
    page it does not claim), so nothing walks the whole tree."""
    html = soup.find("html", recursive=False)
    return (html or soup).find("head", recursive=False)


def _split(value):
    """'Name (Affiliation)' -> ('Name', 'Affiliation'); the affiliation is the last balanced parenthetical and is
    None when there is none, when it only repeats the name, or when nothing precedes it."""
    value = squash(value)
    if not value.endswith(")"):
        return value, None
    depth = 0
    for i in range(len(value) - 1, -1, -1):
        if value[i] == ")":
            depth += 1
        elif value[i] == "(":
            depth -= 1
            if depth == 0:
                break
    else:
        return value, None
    name, aff = value[:i].strip(), value[i + 1:-1].strip()
    if not name:
        return value, None
    if not aff or aff.casefold() == name.casefold():
        return name, None
    return name, aff


class IUCNRedList(PublisherParser):
    parser_name = "iucn_red_list"
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        head = _head(self.soup)
        if head is None:
            return False
        journal = head.find("meta", attrs={"name": "citation_journal_title"}, recursive=False)
        if not journal or (journal.get("content") or "").strip() != _JOURNAL:
            return False
        canonical = head.find("link", attrs={"rel": "canonical"}, recursive=False)
        return bool(canonical and _SITE in (canonical.get("href") or ""))

    def _raw_authors(self):
        return [m.get("content") or "" for m in
                _head(self.soup).find_all("meta", attrs={"name": "citation_author"}, recursive=False)]

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self.parse_authors())

    def parse_authors(self):
        authors = []
        for raw in self._raw_authors():
            name, aff = _split(raw)
            if not name or _EMAIL.match(name):
                continue
            authors.append({"name": name, "affiliations": [aff] if aff else [], "is_corresponding": None})
        return authors

    def parse(self):
        return {"authors": self.parse_authors(), "abstract": None}
