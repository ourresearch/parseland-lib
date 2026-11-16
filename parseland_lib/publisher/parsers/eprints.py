import re

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser

_EPRINTS_GENERATOR = re.compile(r"^\s*EPrints\b", re.I)


def is_eprints_page(soup):
    """A page served by the EPrints repository software: <meta name="Generator" content="EPrints 3.3.15">. Journal
    platforms that copy EPrints' eprints.* meta tags for Google Scholar (IATED's digital library, some WordPress
    journal themes) print no such generator and are not EPrints."""
    return any(_EPRINTS_GENERATOR.match(meta.get("content") or "")
               for meta in soup.find_all("meta", attrs={"name": re.compile(r"^generator$", re.I)}))


class EPrints(PublisherParser):
    """EPrints repository record pages reached by DOI (oxjob #2268): REAL (mtak.hu), TUprints, AMS Acta (unibo.it),
    UCL Discovery, LSHTM, Open Research Online and the long tail of university repositories.

    The summary page prints its byline from the record's creators, which EPrints also gives in eprints.creators_name
    (and DC.creator) tags. Most EPrints sites print no citation_author tags, so no parser read a byline on the DOI
    path: the Dublin Core reader in parse.py runs on repository (pmh) pages only. This parser reads that byline with
    the same reader. Pages that do print citation_author tags (ZORA at uzh.ch) stay with the generic parser.
    EPrints pages state no affiliations and no corresponding author (eprints.creators_id holds depositors' e-mails,
    never shown as a mark); the abstract is whatever the generic parser reads, as before.
    """
    parser_name = "eprints"

    def is_publisher_specific_parser(self):
        return is_eprints_page(self.soup)

    def _citation_authors(self):
        return [meta for meta in self.soup.find_all("meta", attrs={"name": "citation_author"})
                if (meta.get("content") or "").strip()]

    def _creators(self):
        # imported here: parse.py imports this package, so a module-level import would be circular
        from parseland_lib.parse import dublin_core_authors
        return dublin_core_authors(self.soup)

    def authors_found(self):
        return self.is_publisher_specific_parser() and not self._citation_authors() and bool(self._creators())

    def parse(self):
        authors = [{"name": author["name"], "affiliations": [], "is_corresponding": False}
                   for author in self._creators()]
        return {"authors": authors, "abstract": GenericPublisherParser(self.soup).parse()["abstract"]}
