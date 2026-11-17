"""SISSA Medialab's Proceedings of Science (pos.sissa.it) contribution pages (oxjob #2338, Parseland swarm).

A PoS page (DOIs 10.22323/1.<volume>.<number>) prints its byline in div#landing-page div.authors, one span.au per
author ("T.W. Chiu"), and marks the corresponding author on a page with two or more authors with
<span class="au corresponding" title="Corresponding author">, a "*" after it and, on newer pages, a
"*: corresponding author" note. The citation_author tags list the same authors in the same order in fuller form
("Chiu, Ting-Wai") and mark no one, so the generic parser marked no corresponding author on these pages.

This parser keeps everything the generic parser reads from these pages (the tag names, the abstract) and adds the
byline's corresponding mark. The pages show no affiliations, acknowledgments, funding statement or reference list.
SISSA Medialab's journals (JCOM on jcom.sissa.it, Drupal) share the citation_publisher tag but not PoS's
dcterms.identifier, and are not claimed.
"""
from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import _fold_name

_IDENTIFIER = "pos.sissa.it/"  # PoS's dcterms.identifier: "https://pos.sissa.it/<volume>/<number>"


def is_pos_page(soup):
    """The claim's cheap first test: every parser is asked about every DOI page (#2239: under 0.5 ms a page it does
    not claim), so only <head>'s own <meta> children are looked at, reached through direct children."""
    html = soup.find("html", recursive=False)
    head = (html or soup).find("head", recursive=False)
    if head is None:
        return False
    return any(meta.get("name") == "dcterms.identifier" and _IDENTIFIER in (meta.get("content") or "")
               for meta in head.find_all("meta", recursive=False))


def _family(name):
    """The folded family name of a tag name: 'Barbosa Martins, Victor' -> 'barbosa martins'; no comma: last word."""
    if "," in name:
        return _fold_name(name.split(",")[0])
    words = _fold_name(name).split()
    return words[-1] if words else ""


def _span_names(byline_text, name):
    """True when the byline span's text carries the tag name's family name as whole words."""
    family = _family(name)
    return bool(family) and f" {family} " in f" {_fold_name(byline_text)} "


class SissaPoS(PublisherParser):
    parser_name = "sissa_pos"
    # the byline's mark is the page's own; no other parser's reading of these pages beats it
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        return is_pos_page(self.soup)

    def authors_found(self):
        return is_pos_page(self.soup) and bool(self._byline())

    def _byline(self):
        """[(text, is_marked)] for each span.au of the landing page's byline, in order."""
        landing = self.soup.find("div", id="landing-page")
        block = landing.find("div", class_="authors") if landing else None
        if block is None:
            return []
        return [(span.get_text(" ", strip=True), "corresponding" in (span.get("class") or []))
                for span in block.select("span.au")]

    def mark_corresponding(self, authors):
        """Mark the tag author each marked byline span names: the one at the same place when the byline and the tags
        list as many authors (all 73 sampled pages), else the one tag author with that family name."""
        byline = self._byline()
        marked = [i for i, (_, is_marked) in enumerate(byline) if is_marked]
        if not marked or not authors:
            return authors
        hits = set()
        for i in marked:
            text = byline[i][0]
            if len(byline) == len(authors) and _span_names(text, authors[i]["name"]):
                hits.add(i)
                continue
            same = [j for j, author in enumerate(authors) if _span_names(text, author["name"])]
            if len(same) == 1:
                hits.add(same[0])
        if hits:
            for j, author in enumerate(authors):
                author["is_corresponding"] = j in hits
        return authors

    def parse(self):
        parsed = GenericPublisherParser(self.soup).parse()  # its own instance: nothing shared to copy
        parsed["authors"] = self.mark_corresponding(parsed.get("authors") or [])
        return parsed
