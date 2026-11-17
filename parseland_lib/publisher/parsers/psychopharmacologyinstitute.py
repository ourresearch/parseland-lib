"""Psychopharmacology Institute (psychopharmacologyinstitute.com and its language subdomains, DOI prefix 10.64239),
oxjob #2339.

WordPress pages of CME lessons ("Quick Take" podcasts, slide lectures) and publications (drug guides, interviews), with
no citation_* meta tags. A lesson or publication page prints its byline in <section class="author-details">: one card
per author, the name with degrees in h2.author-name, then "<job title> - <institution>" with the institution in
span.author-affiliation-name. The byline is read from those cards: the Yoast JSON-LD author is sometimes another
person (a stale "Experts" entry). No byline marks a corresponding author.

The abstract is left to parse_page's readers (they read what they read before this parser), and the pages show no
acknowledgments, funding statement or reference list of the work's own (a Quick Take's "Reference" is the one paper it
discusses). The home page, where many DOIs of the site resolve, shows author cards in its publication listings
(div.author-details): it presents no one work, and the parser never reads it.
"""
from parseland_lib.publisher.parsers.parser import PublisherParser

_SITE_NAME = "Psychopharmacology Institute"
_DOMAIN = "psychopharmacologyinstitute.com"


def _clean(text):
    return " ".join((text or "").split())


def _head_meta(soup, prop):
    """The content of <meta property=prop> among <head>'s own children: a few dozen nodes, never a walk of the
    whole page (production asks every parser about every DOI page, oxjob #2239)."""
    html = soup.find("html", recursive=False)
    head = html.find("head", recursive=False) if html else None
    tag = head.find("meta", attrs={"property": prop}, recursive=False) if head else None
    return (tag.get("content") or "").strip() if tag else ""


class PsychopharmacologyInstitute(PublisherParser):
    parser_name = "psychopharmacologyinstitute"

    def is_publisher_specific_parser(self):
        if _head_meta(self.soup, "og:site_name") != _SITE_NAME:
            return False
        url = _head_meta(self.soup, "og:url").split("//", 1)[-1].split("/", 1)[0].lower()
        return url == _DOMAIN or url.endswith("." + _DOMAIN)

    def _cards(self):
        return self.soup.select("section.author-details .author-info")

    def authors_found(self):
        return self.is_publisher_specific_parser() and any(c.select_one(".author-name") for c in self._cards())

    def parse(self):
        authors = []
        for card in self._cards():
            name_tag = card.select_one(".author-name")
            # "Paul S. Links, M.D., F.R.C.P.C.": the degrees follow the first comma.
            # shortcut: a suffix such as "Jr." after a comma would be cut too; none on the sampled pages.
            name = _clean(name_tag.get_text(" ")).split(",")[0].strip() if name_tag else ""
            if not name:
                continue
            aff = _clean(t.get_text(" ")) if (t := card.select_one(".author-affiliation-name")) else ""
            authors.append({"name": name, "affiliations": [aff] if aff else [], "is_corresponding": False})
        return {
            "authors": authors,
            "abstract": None,
            "acknowledgments": None,
            "funding_statement": None,
            "references": None,
            "references_complete": False,
        }
