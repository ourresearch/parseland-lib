"""Tomsk State University's research library, vital.lib.tsu.ru (oxjob #2339): VTLS Vital record pages that TSU's own
DOIs (prefix 10.17223, its journals and conference volumes) resolve to.

A record page lists the item's creators in citation_authors tags, one person per tag as "Family, Given Patronymic"
("Выродова, Анна Вячеславовна"), and prints them again under "Creator"; its meta author tag names the university, not a
person. The Dublin Core reader in parse.py reads such tags on repository (pmh) pages only, so on the DOI path no parser
read this byline and the conference papers whose works have no authors kept none. This parser reads it with the same
reader, so both paths give the same names. The pages show no affiliations and no corresponding author.
Left to the other readers: the abstract (meta "abstract" and the "Description" entry, often cut mid-sentence; too few
works lack it to earn code by #2339's floor). The pages show no acknowledgments, funding statement or reference list.
"""
from parseland_lib.publisher.parsers.parser import PublisherParser

_RECORD_URL = "vital.lib.tsu.ru/vital/access/manager/Repository/"


class TsuVital(PublisherParser):
    parser_name = "tsu_vital"
    # the page's own byline beats any other parser's guess: it shows no affiliations to lose
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        # Every DOI page is offered to every parser (#2239's per-page CPU rule): look at one tag in the small <head>,
        # the record's dc.Identifier ("koha:000720381; DOI:...; https://vital.lib.tsu.ru/vital/access/manager/
        # Repository/koha:000720381"). Kept, since authors_found() and the dispatcher both ask.
        if not hasattr(self, "_claimed"):
            head = self.soup.head
            tag = head.find("meta", attrs={"name": "dc.Identifier"}) if head is not None else None
            self._claimed = tag is not None and _RECORD_URL in (tag.get("content") or "")
        return self._claimed

    def _creators(self):
        if not hasattr(self, "_names"):
            # imported here: parse.py imports this package, so a module-level import would be circular
            from parseland_lib.parse import dublin_core_authors
            self._names = [author["name"] for author in dublin_core_authors(self.soup)]
        return self._names

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._creators())

    def parse(self):
        authors = [{"name": name, "affiliations": [], "is_corresponding": False} for name in self._creators()]
        return {"authors": authors, "abstract": None}
