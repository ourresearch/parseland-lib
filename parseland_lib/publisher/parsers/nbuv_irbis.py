"""Article pages of the IRBIS journal system on the Vernadsky National Library of Ukraine's Drupal sites (oxjob #2338).

Journals of Kyiv institutes with DOI prefix 10.15407 (np.nbuv.gov.ua, rksu.nbuv.gov.ua, kraieznavstvo.history.org.ua):
a Drupal 7 page whose content is an IRBIS64 record (`cgi-bin/<journal>/jrn.exe`). IRBIS prints the citation_* meta
tags inside the article block, with the authors in Ukrainian ("Потіха, А."), and nothing else on the page names an
affiliation. The visible byline is English, and its "Author(s) citation:" list gives each author with their affiliation
in brackets, then on some pages an e-mail address and an ORCID iD:
    <ul><li><a href="...scholar...">Dzyra Olesia</a><span> (<i>V. I. Vernadskyi National Library of Ukraine, Ukraine,
    Kyiv, <a href="mailto:...">...@gmail.com</a></i>) <strong>ORCID</strong>: ...</span></li></ul>
This parser reads that list (English names, which the works' Crossref names match, and their affiliations) and the
"References:" <ol>. An e-mail address shown for the only author is not a corresponding-author mark (label-v1), so no
one is marked. The abstract stays the generic reader's.
"""
import re

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

# citation_abstract_html_url of an IRBIS record: ".../cgi-bin/np/jrn.exe?I21DBN=LINK&P21DBN=NP&..."
IRBIS_RECORD = re.compile(r"/jrn\.exe\?I21DBN=", re.I)
AUTHORS_LABEL = re.compile(r"^\s*Author\(s\) citation:?\s*$", re.I)
REFERENCES_LABEL = re.compile(r"^\s*References:?\s*$", re.I)
EMAIL = re.compile(r"\S+@\S+")
MORE = re.compile(r"\b(show|view|see) (all|more)\b|\bmore references\b", re.I)


class NbuvIrbis(PublisherParser):
    parser_name = "nbuv_irbis"
    prefer_publisher_authors_over_generic = True

    def _page(self):
        """The element holding the page: these sites open with a broken doctype ("<DOCTYPE HTML PUBLIC ...>", no "!"),
        which lxml reads as a <doctype> element, the first child of <body>, holding everything after it."""
        body = self.soup.body
        first = body.find(True, recursive=False) if body is not None else None
        return first if first is not None and first.name == "doctype" else None

    def is_publisher_specific_parser(self):
        # Every parser's claim runs on every DOI page (#2239's CPU rule): look at <body>'s first element only, and
        # walk for the IRBIS meta tag only inside a page that opens with this template's broken doctype. Once per
        # instance.
        if not hasattr(self, "_claim"):
            self._claim = False
            if (page := self._page()) is not None:
                meta = page.find("meta", attrs={"name": "citation_abstract_html_url"})
                self._claim = bool(meta is not None and IRBIS_RECORD.search(meta.get("content") or ""))
        return self._claim

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._authors())

    def _label(self, pattern):
        return self.soup.find("b", string=pattern)

    def _authors(self):
        if hasattr(self, "_found"):
            return self._found
        self._found = []
        label = self._label(AUTHORS_LABEL)
        listing = label.find_next("ul") if label is not None else None
        if listing is None:
            return self._found
        for item in listing.find_all("li"):
            link = item.find("a")
            name = squash(link.get_text()) if link is not None else squash(item.get_text()).split(" (")[0]
            if not name:
                continue
            affiliations = []
            if (aff := item.find("i")) is not None:
                # no separator: the site's search highlight splits words in <font>, as in the references
                text = squash("".join(EMAIL.sub(" ", s) for s in aff.find_all(string=True)
                                      if not (s.parent.name == "a" and "mailto:" in (s.parent.get("href") or ""))))
                text = text.strip(" ,;")
                if text:
                    affiliations.append(text)
            self._found.append({"name": name, "affiliations": affiliations, "is_corresponding": False})
        return self._found

    def _references(self):
        # imported here: back_matter imports the parsers package, which imports this module
        from parseland_lib.back_matter import _clean_doi, _pick_doi, _printed_doi
        label = self._label(REFERENCES_LABEL)
        listing = label.find_next("ol") if label is not None else None
        if listing is None:
            return None, False
        refs = []
        for item in listing.find_all("li"):
            # no separator: the site's search highlight splits words in <font> ("wo<font>rks</font>")
            if not (raw := squash(item.get_text())):
                continue
            link = item.find("a", href=re.compile(r"doi\.org/10\."))
            doi = _pick_doi(_clean_doi(link["href"]) if link is not None else None, _printed_doi(raw))
            refs.append({"position": len(refs) + 1, "raw": raw, "doi": doi})
        if not refs:
            return None, False
        # one <ol> numbered from 1, with no "show more" in it or after it
        after = " ".join(s.get_text(" ") for s in listing.find_next_siblings())
        whole = (listing.get("start") in (None, "", "1") and listing.find("ol") is None
                 and not MORE.search(listing.get_text(" ") + " " + after))
        return refs, whole

    def parse(self):
        authors = [dict(a, affiliations=list(a["affiliations"])) for a in self._authors()]
        refs, whole = self._references()
        return {
            "authors": authors,
            "abstract": GenericPublisherParser(self.soup).parse()["abstract"],
            "acknowledgments": None,
            "funding_statement": None,
            "references": refs,
            "references_complete": bool(refs) and whole,
        }
