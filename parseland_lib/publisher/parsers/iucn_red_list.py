"""IUCN Red List of Threatened Species (iucnredlist.org): species assessments, DOI prefix 10.2305 (oxjob #2330).

The stored pages are the site's JavaScript app shell (an empty div#redlist-js): the assessment is never in the markup,
only the citation_* meta tags in <head>. There is no abstract, corresponding-author mark, acknowledgment, funding
statement or reference list on these pages (the assessment's rationale is not an abstract, and it is not on the page
anyway). What the generic reader gets wrong is the byline: every citation_author tag carries the assessor's
affiliation in a closing parenthetical ("Nigel Taylor (RBG Kew)", "Duniel Barrios (Jardín Botánico Nacional,
Universidad de La Habana, Cuba)"), which it keeps inside the name. This parser splits it off, as both blind labellers
do (label-v1), and:
- a group whose parenthetical only repeats its name or a part of it ("BirdLife International (BirdLife
  International)", "IUCN SSC Amphibian Specialist Group (IUCN SSC)") is one author with no affiliation;
- assessors also put a region ("Europe, North Africa, Africa"), a taxon group ("South American Marsupials"), an
  assessment project ("Global Mammal Assessment") or a role ("terrestrial mollusc assessor") in the parenthetical,
  and none of those is an affiliation (both blind labellers, fresh claimed set, #2330): the name is still split
  off, with no affiliation. A parenthetical naming an organisation is one even beside such words;
- the split is at the last balanced parenthetical, so a group name with its own acronym keeps it
  ("Botanic Gardens Conservation International (BGCI) (Botanic Gardens ... (BGCI), Descanso House, ...)");
- a tag naming several assessors in citation style ("Van Damme, D. & Ghamizi, M.", ~3% of pages) is split into
  one author each ("D. Van Damme", "M. Ghamizi"), with no affiliation;
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
# one tag naming several assessors in citation style: "Sheppard, A., Fenner, D., Abrar, M. & Ochavillo, D."
_CITED = re.compile(r"^([^\W\d_][^,&()]*), ((?:[^\W\d_]{1,2}\.\s?-?)+)$")
# shortcut: word lists, not a model, read off the parentheticals on ~165 stored pages. An organisation word wins
# ("SRLI Reptile Assessment / Vadodara Zoo"); otherwise an assessment project, a role or a run of place and taxon
# words ("Europe, North Africa, Africa", "South American Marsupials") is not an affiliation, and anything else is
# (a bare brand or acronym: "VALE", "SPUN", "Seriously Fish", as both labellers read them). Widen the lists if a
# later sample shows other kinds of parenthetical.
_ORG = re.compile(
    r"univers|universid|college|colegio|school|escola|escuela|institut|museum|museo|museu|herbari|botanic|botánic"
    r"|botânic|jard[ií]n|jardim|garden|arboretum|\bzoo|zoolog|biopark|aquarium|department|departamento|\bdept\b"
    r"|minist|government|gobierno|governo|office|agency|service|survey|centre|center|centro|foundation|fundaci"
    r"|funda[cç][aã]o|society|sociedad|sociedade|trust|council|consejo|conselho|research|academy|academ|laborator"
    r"|conservation|conservancy|smithsonian|\bkew\b|noaa|birdlife|\bbgci\b|\bwcs\b|specialist group|\bs?sg\b"
    r"|\brla\b|red list authority|iucn|association|asociaci|associa[cç][aã]o|station|estaci|fisheries|forestry"
    r"|wildlife|commission|national|nacional|biodiversity|natural history|\bngo\b|\bltd\b|\binc\b|company"
    r"|corporation", re.I)
_ROLE = re.compile(r"\bassessor", re.I)
_NOT_ORG = re.compile(r"assessment|\bproject\b|^independent\b|\berl\b", re.I)
_PLACE_OR_TAXON = set("""
    europe european africa african asia asian america american americas oceania australia australasia pacific atlantic
    indian ocean mediterranean caribbean arctic antarctic north south east west central northern southern eastern
    western global world and the of marsupials reptiles amphibians mammals birds fish fishes freshwater marine plants
    moths butterflies molluscs mollusks snails corals trees cacti insects dragonflies bats primates sharks rays crabs
    invertebrates fungi lichens mosses""".split())


def _is_affiliation(text):
    if _ROLE.search(text):
        return False
    if _ORG.search(text):
        return True
    if _NOT_ORG.search(text):
        return False
    words = [w.casefold() for w in re.findall(r"[^\W\d_]+", text)]
    return not (words and all(w in _PLACE_OR_TAXON for w in words))


def _cited_list(value):
    """'Sheppard, A., Fenner, D. & Ochavillo, D.' -> ['A. Sheppard', 'D. Fenner', 'D. Ochavillo']; None unless the
    whole tag is two or more 'Family, I.' items joined by ', ' and a final ' & '."""
    value = squash(value)
    if " & " not in value:
        return None
    items = re.split(r"\s+&\s+|(?<=\.),\s+", value)
    names = []
    for item in items:
        m = _CITED.match(item.strip())
        if not m:
            return None
        names.append(f"{m.group(2).strip()} {m.group(1).strip()}")
    return names if len(names) > 1 else None


def _head(soup):
    """<head>, reached through direct children only: every parser's claim runs on every page (#2239: under 0.5 ms a
    page it does not claim), so nothing walks the whole tree."""
    html = soup.find("html", recursive=False)
    return (html or soup).find("head", recursive=False)


def _split(value):
    """'Name (Affiliation)' -> ('Name', 'Affiliation'); the affiliation is the last balanced parenthetical and is
    None when there is none, when it only repeats (part of) the name, when it names no organisation, or when nothing
    precedes it."""
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
    if not aff or aff.casefold() in name.casefold() or not _is_affiliation(aff):
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
            cited = _cited_list(raw)
            if cited:
                authors.extend({"name": n, "affiliations": [], "is_corresponding": None} for n in cited)
                continue
            name, aff = _split(raw)
            if not name or _EMAIL.match(name):
                continue
            authors.append({"name": name, "affiliations": [aff] if aff else [], "is_corresponding": None})
        return authors

    def parse(self):
        return {"authors": self.parse_authors(), "abstract": None}
