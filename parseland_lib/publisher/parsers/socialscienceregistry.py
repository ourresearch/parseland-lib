"""AEA RCT Registry (socialscienceregistry.org): trial registration pages (oxjob #2338).

A trial's current page and its history-version pages share one Rails layout: label/value rows
(<div class="field-label">, then <div class="field">) grouped in fieldsets headed <h3> (<legend> on older pages).
The authors are the "Primary Investigator" and "Other Primary Investigator(s)", in page order, each with one
affiliation field; the abstract is the trial's own "Abstract" row (<div class="row abstract">). The "Relevant Paper(s)"
fieldset prints a later paper's abstract under the same label, and every investigator has a "Contact" button, which
label-v1 does not read as a corresponding-author mark.
"""
import copy

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

_TAGLINE = "registry for randomized controlled trials"
_INVESTIGATOR_HEADINGS = ("primary investigator", "other primary investigator(s)")
_NAME_LABELS = ("name", "pi name")
_AFFILIATION_LABELS = ("affiliation", "pi affiliation")
_LINE = " "  # a mark for <br> while the abstract's text is read


def _is_registry_page(soup):
    """The site header's tagline, "The American Economic Association's registry for randomized controlled trials".
    Every parser's claim runs on every DOI page (#2239: under 0.5 ms a page it does not claim), so the header is
    reached through direct children only (html > body > div#header) and nothing walks the whole tree before it."""
    html = soup.find("html", recursive=False)
    body = (html or soup).find("body", recursive=False)
    header = body.find("div", id="header", recursive=False) if body is not None else None
    tagline = header.find("p", class_="tagline") if header is not None else None
    return tagline is not None and _TAGLINE in tagline.get_text().lower()


def _label(tag):
    return squash(tag.get_text(" ")).lower()


def _value(label_tag):
    field = label_tag.find_next_sibling("div", class_="field")
    return squash(field.get_text(" ")) if field is not None else ""


class AEARCTRegistry(PublisherParser):
    parser_name = "aea_rct_registry"
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        if not hasattr(self, "_claimed"):
            self._claimed = _is_registry_page(self.soup)
        return self._claimed

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._investigators())

    def _investigators(self):
        if hasattr(self, "_authors"):
            return self._authors
        authors = []
        for fieldset in self.soup.find_all("fieldset"):
            heading = fieldset.find(["h3", "legend"])
            if heading is None or _label(heading) not in _INVESTIGATOR_HEADINGS:
                continue
            current = None
            for label_tag in fieldset.find_all("div", class_="field-label"):
                label = _label(label_tag)
                if label in _NAME_LABELS:
                    current = None
                    if name := _value(label_tag):
                        current = {"name": name, "affiliations": [], "is_corresponding": False}
                        authors.append(current)
                elif label in _AFFILIATION_LABELS and current is not None and (aff := _value(label_tag)):
                    current["affiliations"] = [aff]
        self._authors = authors
        return authors

    def _abstract(self):
        row = self.soup.find("div", class_="abstract")  # <div class="row abstract">: the trial's own, never a paper's
        label_tag = row.find("div", class_="field-label") if row is not None else None
        field = label_tag.find_next_sibling("div", class_="field") if label_tag is not None else None
        if field is None or _label(label_tag) != "abstract":
            return None
        field = copy.copy(field)  # never edit the page: the readers after this parser see the same soup
        for br in field.find_all("br"):
            br.replace_with(_LINE)
        lines = (squash(line) for line in field.get_text().split(_LINE))
        return "\n".join(line for line in lines if line) or None

    def parse(self):
        return {"authors": [dict(a) for a in self._investigators()], "abstract": self._abstract()}
