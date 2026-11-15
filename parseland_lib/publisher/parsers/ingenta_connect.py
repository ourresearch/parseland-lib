"""Ingenta Connect article pages (www.ingentaconnect.com/content/<publisher>/<journal>/.../artNNNNN) (oxjob #2239 round 5).

No parser read these pages, so they parsed with no authors, affiliations or abstract: the page carries no
citation_author tags, only DC.creator, and prints the rest in its own blocks:
- byline: <div id="infoArticle"> ... <p><strong>Authors: </strong><a href="/search?option2=author&value2=Xing,+Manjiang"
  title="Search for articles by this author">Xing, Manjiang</a> <sup><a href="#aff_1">1</a></sup> ; ...</p>
- affiliations: <div id="Info"> ... <p><strong>Affiliations:</strong> either one text the page gives every author, or
  numbered entries <strong id="aff_1">1: </strong><span id="aff_..._contents">...</span> the byline links to
- abstract: <div id="Abst" class="tab-pane"> ("No Abstract" when there is none)
Names print "Family, Given"; we return "Given Family".
"""
import re

from parseland_lib.not_abstract import is_not_abstract
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

_AUTHOR_LINK = re.compile(r"[?&;]option2=author&")
_AFF_ID = re.compile(r"^aff_\d+$")
_AFF_REF = re.compile(r"^#aff_\d+$")


def _labelled_paragraph(block, label):
    """The <p> in `block` whose leading <strong> starts with `label` ("Author", "Affiliation")."""
    for p in block.find_all("p") if block else []:
        strong = p.find("strong")
        if strong and strong.get_text(strip=True).startswith(label):
            return p
    return None


def _given_family(name):
    # not format_name(): it needs ", " exactly and reverses every part ("Smith, John, Jr." -> "Jr. John Smith")
    family, sep, given = name.partition(",")
    return f"{given.strip()} {family.strip()}" if sep and given.strip() else name.strip()


def _text(el):
    return squash(el.get_text(" "))


class IngentaConnect(PublisherParser):
    parser_name = "ingenta_connect"

    def _byline(self):
        # Every Ingenta Connect page carries IC.identifier in its <head>: a look at the small head first, so the
        # other DOI pages never pay for a whole-page search for the byline block.
        head = self.soup.head
        if head is None or head.find("meta", attrs={"name": "IC.identifier"}) is None:
            return None
        return _labelled_paragraph(self.soup.find("div", id="infoArticle"), "Author")

    def is_publisher_specific_parser(self):
        return self._byline() is not None

    def authors_found(self):
        byline = self._byline()
        return bool(byline and byline.find("a", href=_AUTHOR_LINK))

    def parse_affiliations(self):
        """{"aff_N": text} for numbered affiliations, or {None: text} for one the page gives every author."""
        p = _labelled_paragraph(self.soup.find("div", id="Info"), "Affiliation")
        if p is None:
            return {}
        numbered = {}
        for label in p.find_all("strong", id=_AFF_ID):
            value = label.find_next_sibling("span")
            if value and (text := _text(value)):
                numbered[label["id"]] = text
        if numbered:
            return numbered
        text = re.sub(r"^Affiliations?\s*:\s*", "", _text(p))  # not .extract(): later readers share this soup
        return {None: text} if text else {}

    def parse_authors(self):
        affiliations = self.parse_affiliations()
        shared = [affiliations[None]] if None in affiliations else []
        authors = []
        for el in self._byline().find_all(["a", "sup"]):
            if el.name == "a" and _AUTHOR_LINK.search(el.get("href", "")):
                if name := _given_family(_text(el)):
                    authors.append({"name": name, "affiliations": list(shared), "is_corresponding": None})
            elif el.name == "sup" and authors:
                for ref in el.find_all("a", href=_AFF_REF):
                    aff = affiliations.get(ref["href"][1:])
                    if aff and aff not in authors[-1]["affiliations"]:
                        authors[-1]["affiliations"].append(aff)
        return authors

    def parse_abstract(self):
        block = self.soup.find("div", id="Abst")
        if block is None:
            return None
        text = re.sub(r"^abstract\s*[:.]?\s*", "", _text(block), flags=re.I)
        return None if len(text) < 40 or is_not_abstract(text) else text  # "No Abstract" is the empty tab

    def parse(self):
        return {"authors": self.parse_authors(), "abstract": self.parse_abstract()}
