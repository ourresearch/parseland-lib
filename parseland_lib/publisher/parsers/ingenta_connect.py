"""Ingenta Connect article pages (www.ingentaconnect.com/content/<publisher>/<journal>/.../artNNNNN) (oxjob #2239 round 5).

No parser read these pages, so they parsed with no authors, affiliations or abstract: the page carries no
citation_author tags, only DC.creator, and prints the rest in its own blocks:
- byline: <div id="infoArticle"> ... <p><strong>Authors: </strong><a href="/search?option2=author&value2=Xing,+Manjiang"
  title="Search for articles by this author">Xing, Manjiang</a> <sup><a href="#aff_1">1</a></sup> ; ...</p>
- affiliations: <div id="Info"> ... <p><strong>Affiliations:</strong> either one text the page gives every author, or
  numbered entries <strong id="aff_1">1: </strong><span id="aff_..._contents">...</span> the byline links to
- abstract: <div id="Abst" class="tab-pane"> ("No Abstract" when there is none)
Names print "Family, Given"; we return "Given Family".

The same class reads Ingenta's other platform, pub2web (Ingenta Edify: UN, WTO and OECD iLibrary, EarthDoc, Intellect,
John Benjamins, Microbiology Society, NCTE, IET ...) (oxjob #2268). Its pages carry
<link rel="schema.CRAWLER" href="http://labs.ingenta.com/2006/06/16/crawler"> in their head. Journal pages give their
byline in citation_author tags, which the generic reader already reads; what they print and nobody read is the
reference list (<ol id="articlereference"> under a "References (N)" tab). Book, chapter and statistics pages carry no
citation_author tags, so their byline was lost: UN and WTO iLibrary print it in the item's own metadata box
(<div class="item-metadata__maindata"> ... <span class="authors_label">Author:</span> <span class="author-list__item">),
OECD iLibrary as "Author(s) OECD" (a sidebar block, or a meta-item line on a book page). Group authors ("United
Nations", "OECD") are authors by the labelling rubric.
"""
import copy
import re

from parseland_lib.not_abstract import is_not_abstract
from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

_AUTHOR_LINK = re.compile(r"[?&;]option2=author&")
_AFF_ID = re.compile(r"^aff_\d+$")
_AFF_REF = re.compile(r"^#aff_\d+$")
_PUB2WEB_CRAWLER = re.compile(r"^https?://labs\.ingenta\.com/")
_OECD_AUTHORS = re.compile(r"^Author\(s\)\s*:?\s*(.+)$")
_REFERENCE_COUNT = re.compile(r"^References\s*\((\d+)\)$")
_DOI = re.compile(r"\b(10\.\d{4,9}/\S+)")


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

    def __init__(self, soup):
        super().__init__(soup)
        self._pub2web_result = None

    def _is_pub2web(self):
        head = self.soup.head
        return head is not None and head.find(
            "link", attrs={"rel": "schema.CRAWLER", "href": _PUB2WEB_CRAWLER}) is not None

    def _byline(self):
        # Every Ingenta Connect page carries IC.identifier in its <head>: a look at the small head first, so the
        # other DOI pages never pay for a whole-page search for the byline block.
        head = self.soup.head
        if head is None or head.find("meta", attrs={"name": "IC.identifier"}) is None:
            return None
        return _labelled_paragraph(self.soup.find("div", id="infoArticle"), "Author")

    def is_publisher_specific_parser(self):
        if self._is_pub2web():
            # a byline only this reader finds (the generic one reads citation_author pages), or a reference list
            out = self._pub2web()
            return bool((out["authors"] and not self._has_author_tags()) or out.get("references"))
        return self._byline() is not None

    def authors_found(self):
        if self._is_pub2web():
            return bool(self._pub2web()["authors"])
        byline = self._byline()
        return bool(byline and byline.find("a", href=_AUTHOR_LINK))

    # pub2web (oxjob #2268)

    def _has_author_tags(self):
        return any((m.get("content") or "").strip() for m in self.soup.find_all("meta", attrs={"name": "citation_author"}))

    def _pub2web_byline(self):
        """The names a book, chapter or statistics page credits, from its printed byline."""
        names = []
        for box in self.soup.select(".item-metadata__maindata"):  # UN, WTO iLibrary; Intellect books
            for label in box.select(".authors_label"):
                li = label.find_parent("li")
                for a in li.select(".author-list__item a") if li else []:
                    if (name := _text(a)) and name not in names:
                        names.append(name)
            if names:
                return names
        # OECD iLibrary: "Author(s)" over the name in a sidebar block (tables, graphs, chapters), or "Author(s): OECD"
        # on a book page. Every sampled page credits one name ("OECD"); a list's separator is unseen, so one name only.
        lines = [_text(p) for p in self.soup.select(".block-infos-sidebar p")]
        lines += [_text(span) for span in self.soup.select("span.meta-item")]
        for line in lines:
            if match := _OECD_AUTHORS.match(line):
                name = match.group(1).strip()
                return [] if re.search(r"[,;&]|\band\b", name) else [name]
        return []

    def _pub2web_own_description(self):
        """An OECD iLibrary book page's description: the book's own abstract. Chapter, table and graph pages
        (/content/component/...) print their parent book's description there, which is not theirs."""
        stats = self.soup.find("meta", attrs={"name": "stats-meta"})
        if not stats or not (stats.get("data-itemid") or "").startswith("/content/publication/"):
            return None
        block = self.soup.select_one(".main-content div.description")
        text = _text(block) if block else ""
        return None if len(text) < 100 or is_not_abstract(text) else text

    def _pub2web_references(self):
        """The printed reference list: (references, complete). Complete only when the tab's stated count
        ("References (22)") matches the items listed."""
        ol = self.soup.select_one("#referenceContainer ol#articlereference, #references ol#articlereference")
        if ol is None:
            return None, False
        references = []
        for li in ol.find_all("li", class_="refbody", recursive=False):
            item = copy.copy(li)  # never edit the page: later readers share this soup
            for link in item.select("span.refExternalLink, a.js-externallink"):
                link.decompose()
            if not (raw := squash(item.get_text())):  # the markup carries its own spaces: "(<span>1996</span>)"
                continue
            doi = None
            for a in li.select("a.doilink, span.refExternalLink a.externallink"):
                if match := _DOI.search(a.get("href") or "") or _DOI.search(_text(a)):
                    doi = match.group(1).rstrip(".,;")
                    break
            references.append({"position": len(references) + 1, "raw": raw, "doi": doi})
        if not references:
            return None, False
        stated = None
        for tab in self.soup.select("li#references strong.titleIcon"):
            if match := _REFERENCE_COUNT.match(_text(tab)):
                stated = int(match.group(1))
        start = ol.get("start")
        complete = stated == len(references) and (not start or start.strip() == "1")
        return references, complete

    def _pub2web(self):
        if self._pub2web_result is None:
            # The generic reader's result is what these pages parse to today; keep it, and add what it misses.
            generic = GenericPublisherParser(self.soup).parse()
            authors = generic["authors"] if self._has_author_tags() else [
                {"name": name, "affiliations": [], "is_corresponding": None} for name in self._pub2web_byline()]
            out = {"authors": authors, "abstract": self._pub2web_own_description() or generic["abstract"]}
            references, complete = self._pub2web_references()
            if references:
                out["references"] = references
                out["references_complete"] = complete
            self._pub2web_result = out
        return self._pub2web_result

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
        if self._is_pub2web():
            return self._pub2web()
        return {"authors": self.parse_authors(), "abstract": self.parse_abstract()}
