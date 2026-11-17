"""Pensoft's ARPHA journal platform: affiliations and corresponding authors from the author cards (oxjob #2289).

ARPHA serves pensoft.net's journals, *.arphahub.com, riojournal.com, mab-online.nl, lib.jucs.org and other white-label
sites. The article body renders in an iframe (article_preview.php), so a stored page holds the byline only in its
citation_author tags, with no affiliations. Many pages also print the "Article Info" panel: one card per author
(div.AOF-Single-Author-Preview) with the name, a "- Corresponding author" note and one <div> per affiliation. The
cards come in their own order with fuller names ("Ana Cristina Teixeira Bonecker" for the tag's "Ana Cristina
Bonecker"), so each card is matched to the byline by name. The academic editor's card (AOF-Single-SE-Preview) is not
an author's.

Scope (#2289 sizing, 22 pages weighted by works): affiliations, and the corresponding flags the same cards carry
(the generic parser's guess marked the wrong author on one page). Pages without the panel print no affiliation or
correspondence at all and are not claimed. Acknowledgments and the reference list live in the iframe, not on the
stored page; the panel's "Supporting agencies" list is a funder list, not a funding statement, and not read.
"""
from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import _fold_name, same_person

# Every ARPHA page loads its journal's stylesheet from this path; no other template's stored page does (#2289: 0 of
# 7,250 pages of 70 other templates and sites, 20 of 22 ARPHA pages).
_JOURNAL_CSS = "/lib/css/journals/journal_"


def _same_author(byline_name, card_name):
    """The card's fuller name is the byline's: same_person, or the same first and last word ("Márcia Castro" /
    "Márcia Salustiano de Castro", which same_person reads as surname "de Castro")."""
    if same_person(byline_name, card_name):
        return True
    a, b = _fold_name(byline_name).split(), _fold_name(card_name).split()
    return bool(a and b) and a[0] == b[0] and a[-1] == b[-1]


class PensoftArpha(PublisherParser):
    parser_name = "pensoft_arpha"

    def is_publisher_specific_parser(self):
        # Cheap claim first (#2239: every parser's claim runs on every page): the <head>'s own <link> children only,
        # never the whole tree; cached, since the dispatcher asks authors_found() and then this.
        claim = self.__dict__.get("_claim")
        if claim is None:
            head = self.soup.head
            claim = self._claim = head is not None and any(
                _JOURNAL_CSS in (link.get("href") or "") for link in head.find_all("link", recursive=False))
        return claim

    def _cards(self):
        cards = self.__dict__.get("_card_tags")
        if cards is None:
            cards = self._card_tags = [c for c in self.soup.select(".P-Authors-List > .AOF-Single-Author-Preview")
                                       if "AOF-Single-SE-Preview" not in c.get("class", [])]
        return cards

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._cards())

    @staticmethod
    def _read_card(card):
        """(name, affiliations, is_corresponding) from one author card."""
        name_box = card.select_one(".AOF-Author-Name")
        name_tag = name_box and (name_box.select_one("a.AOF-Author-Email") or name_box)
        corr = card.select_one(".AOF-Author-Corr")
        if name_tag is name_box and corr is not None:
            name = name_box.get_text(" ", strip=True).replace(corr.get_text(" ", strip=True), "")
        else:
            name = name_tag.get_text(" ", strip=True) if name_tag else ""
        aff_box = card.select_one(".AOF-Author-Affiliation")
        affs = []
        if aff_box is not None:
            affs = [t for d in aff_box.find_all("div", recursive=False) if (t := " ".join(d.get_text(" ").split()))]
            if not affs and (t := " ".join(aff_box.get_text(" ").split())):
                affs = [t]
        corresponding = corr is not None and "corresponding" in corr.get_text().lower()
        return " ".join(name.split()), affs, corresponding

    def parse(self):
        generic = GenericPublisherParser(self.soup).parse()
        cards = [c for c in map(self._read_card, self._cards()) if c[0]]
        authors = [dict(a, affiliations=list(a["affiliations"])) for a in generic["authors"]]
        if not authors:
            authors = [{"name": n, "affiliations": affs, "is_corresponding": corr} for n, affs, corr in cards]
        else:
            matched = {}
            for name, affs, corr in cards:
                hits = [i for i, a in enumerate(authors) if _same_author(a["name"], name)]
                if len(hits) == 1 and hits[0] not in matched:
                    matched[hits[0]] = (affs, corr)
            if matched:  # the cards decide who is corresponding, over the generic parser's guess
                for i, a in enumerate(authors):
                    affs, corr = matched.get(i, ([], False))
                    if not a["affiliations"]:
                        a["affiliations"] = affs
                    a["is_corresponding"] = corr
        return {"authors": authors, "abstract": generic["abstract"]}
