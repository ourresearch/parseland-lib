"""Longwoods Publishing (longwoods.com: Healthcare Quarterly, Healthcare Policy, HealthcarePapers, CJNL ...), oxjob #2339.

Every article page has the same in-house template: citation_author meta tags in which the LAST tag joins the last two
names with " and " ("Eileen Patterson and Sharon Brown"; one tag on a two-author page), an "About the Author(s)"
section of biographies (<h4 id="abtAuthor">), and back matter as <h4> sections ("Acknowledgment", "References") whose
content follows the heading as sibling paragraphs or bare text. Without this parser the generic one read the
biographies as a byline ("PhD", "MSc", "is currently working on ...") with reference titles as affiliations.

What it reads: the authors from the meta tags (split), the one author named after "Correspondence may be directed to"
(or "Principal author and contact:") as corresponding, the acknowledgments and the reference list. Affiliations: none;
the page gives only biographies, which label-v1 does not count as affiliations. Abstract: left to parse_page's own
readers, as before (the description a paywalled page prints, then the "Abstract" heading).
"""
import html
import re

from bs4 import Comment, NavigableString, Tag

from parseland_lib.publisher.parsers.parser import PublisherParser

_SPLIT = re.compile(r"\s*,\s+|\s+and\s+")
_CORRESPONDENCE = re.compile(r"(?:Correspondence (?:may|should|can) be (?:directed|addressed|sent) to|"
                             r"Address correspondence to|Principal author and contact)\s*:?\s*(.{0,160})", re.I | re.S)
_TITLE = re.compile(r"^(?:Dr|Prof|Professor|Mr|Mrs|Ms)\.?\s+", re.I)
_DOI = re.compile(r"\b(10\.\d{4,9}/\S+[^\s.,;)\]>])")


def _clean(text):
    text = html.unescape(html.unescape(text or ""))  # the tags hold "O&amp;#39;Neill"
    if "Ã" in text or "â" in text:  # UTF-8 bytes read as Latin-1 ("JosÃ©e"): the page declares iso-8859-1
        try:
            text = text.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return " ".join(text.split())


def _section_end(node):
    """True at the node that ends an <h4> section: the next heading or the template's next section comment."""
    if isinstance(node, Comment):
        return True
    return isinstance(node, Tag) and (node.name in ("h3", "h4") or node.find("h4") is not None)


class Longwoods(PublisherParser):
    parser_name = "longwoods"
    prefer_publisher_authors_over_generic = True

    def _head_meta(self, name):
        # direct children of <head> only: the claim runs on every DOI page, so never a document-wide search
        head = self.soup.head
        tag = head.find("meta", attrs={"name": name}, recursive=False) if head is not None else None
        return (tag.get("content") or "") if tag is not None else ""

    def is_publisher_specific_parser(self):
        return ("longwoods.com/content/" in self._head_meta("og:url")
                and "Longwoods" in self._head_meta("og:site_name"))

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._author_names())

    def _author_names(self):
        names = []
        head = self.soup.head
        for tag in head.find_all("meta", attrs={"name": "citation_author"}, recursive=False) if head else []:
            for name in _SPLIT.split(_clean(tag.get("content"))):
                if name.strip():
                    names.append(name.strip())
        if names:
            return names
        # no names in the tags (an interview, a column): the bold names that open each biography
        heading = self.soup.find("h4", id="abtAuthor")
        for node in heading.find_next_siblings() if heading else []:
            if _section_end(node):
                break
            for bold in node.find_all("b") if isinstance(node, Tag) else []:
                text = _clean(bold.get_text(" ")).strip(" ,")
                if text and not text.lower().startswith(("correspond", "principal")):
                    names.append(_TITLE.sub("", text))
        return names

    def _corresponding_index(self, names):
        match = _CORRESPONDENCE.search(_clean(self.soup.get_text(" ")))
        if not match:
            return None
        named = _TITLE.sub("", match.group(1))[:80]
        best = None
        for i, name in enumerate(names):
            parts = name.replace(".", ". ").split()
            if not parts:
                continue
            at = re.search(r"(?<!\w)" + re.escape(parts[-1]) + r"(?!\w)", named, re.I)
            if not at:
                continue
            same_surname = sum(1 for n in names if n.split() and n.split()[-1].lower() == parts[-1].lower())
            if same_surname > 1 and not re.search(r"(?<!\w)" + re.escape(parts[0]) + r"(?!\w)", named, re.I):
                continue
            if best is None or at.start() < best[0]:
                best = (at.start(), i)
        return best[1] if best else None

    def _section(self, starts):
        """The sibling nodes after the first <h4> whose text starts with one of `starts`."""
        for heading in self.soup.find_all("h4"):
            if _clean(heading.get_text(" ")).lower().startswith(starts):
                nodes = []
                for node in heading.next_siblings:
                    if _section_end(node):
                        break
                    nodes.append(node)
                return nodes
        return []

    def _acknowledgments(self):
        paragraphs, loose = [], []
        for node in self._section(("acknowledg",)):
            if isinstance(node, NavigableString):
                loose.append(str(node))
                continue
            if loose:
                paragraphs.append(_clean(" ".join(loose)))
                loose = []
            paragraphs.append(_clean(node.get_text(" ")))
        if loose:
            paragraphs.append(_clean(" ".join(loose)))
        # a correspondence line the template sometimes prints at the section's end is not an acknowledgment
        text = "\n".join(p for p in paragraphs if p and not _CORRESPONDENCE.match(p))
        return text or None

    def _references(self):
        refs = []
        for node in self._section(("references",)):
            if not (isinstance(node, Tag) and node.name == "p"):
                continue
            raw = _clean(node.get_text(" "))
            if not raw:
                continue
            doi = None
            for link in node.find_all("a", href=True):
                if found := _DOI.search(link["href"]):
                    doi = found.group(1)
                    break
            refs.append({"position": len(refs) + 1, "raw": raw, "doi": doi})
        return refs

    def parse(self):
        names = self._author_names()
        corresponding = self._corresponding_index(names)
        authors = [{"name": name, "affiliations": [], "is_corresponding": i == corresponding}
                   for i, name in enumerate(names)]
        refs = self._references()
        return {"authors": authors,
                # the generic parser's readers, as before this parser: a paywalled page prints its abstract's opening
                # as the description; parse_page's own readers then take the "Abstract" heading on open pages
                "abstract": self.parse_abstract_meta_tags(include_seo_tags=False) or self.parse_printed_seo_description(),
                "acknowledgments": self._acknowledgments(),
                "funding_statement": None,
                # unnumbered paragraphs: no positive evidence that the list is whole (#2215 contract)
                "references": refs or None,
                "references_complete": False}
