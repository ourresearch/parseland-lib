"""doiSerbia, the National Library of Serbia's DOI platform (doiserbia.nb.rs; oxjob #2338).

Its article pages carry citation_author / citation_abstract meta tags, which the generic parser already reads, but
mark no corresponding author there. The visible byline prints one author a line ("<b>Family Given</b> (affiliation),
e-mail") and shows an e-mail for the corresponding author only. Gold v1.3 marks the author(s) whose e-mail the author
list shows when the others have none; an e-mail printed for every author, or for a sole author, is not a mark
(label-v1). Everything else is the generic parser's output, unchanged.
"""
import re

from bs4 import Comment, NavigableString, Tag

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser

_BYLINE_ID = "ContentPlaceHolder1_ArticleDetails2_labelArticleAuthors"
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def _key(name):
    return tuple(sorted(re.findall(r"\w+", (name or "").lower())))


class DOISerbia(PublisherParser):
    parser_name = "doiserbia"

    def is_publisher_specific_parser(self):
        # Cheap on every other page (#2239): og:url among <head>'s direct children, no document-wide search.
        root = self.soup.find("html", recursive=False)
        head = root.find("head", recursive=False) if root is not None else None
        tag = head.find("meta", property="og:url", recursive=False) if head is not None else None
        return bool(tag is not None and "doiserbia.nb.rs" in (tag.get("content") or ""))

    def authors_found(self):
        return self.is_publisher_specific_parser() and self.soup.find(id=_BYLINE_ID) is not None

    def _byline_entries(self):
        """(name, line text) for each author line of the byline, in order."""
        entries, name, text = [], None, []
        for node in self.soup.find(id=_BYLINE_ID).descendants:
            if isinstance(node, Tag):
                if node.name == "br":
                    entries.append((name, "".join(text)))
                    name, text = None, []
                elif name is None and node.name == "span" and "bold" in (node.get("style") or ""):
                    name = node.get_text(" ", strip=True)
            elif isinstance(node, NavigableString) and not isinstance(node, Comment):
                text.append(str(node))
        entries.append((name, "".join(text)))
        return [(n, t) for n, t in entries if n]

    def mark_corresponding(self, authors):
        entries = self._byline_entries()
        emailed = [i for i, (_, text) in enumerate(entries) if _EMAIL.search(text)]
        if len(entries) < 2 or not emailed or len(emailed) == len(entries):
            return authors
        keys = [_key(a.get("name")) for a in authors]
        marked = set()
        for i in emailed:
            key = _key(entries[i][0])
            if key in keys:
                marked.add(keys.index(key))
            elif len(entries) == len(authors):
                marked.add(i)
        if marked:
            for i, author in enumerate(authors):
                author["is_corresponding"] = i in marked
        return authors

    def parse(self):
        generic = GenericPublisherParser(self.soup).parse()
        authors = [dict(a) for a in generic.get("authors") or []]
        return {"authors": self.mark_corresponding(authors), "abstract": generic.get("abstract")}
