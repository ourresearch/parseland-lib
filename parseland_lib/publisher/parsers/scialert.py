"""Science Alert (scialert.net: the Asian Network for Scientific Information journals, DOI prefix 10.3923) abstract
pages (oxjob #2338).

The site runs its own PHP / Bootstrap template with no citation_* meta tags; its <head> carries twitter:site
"@scialert". The abstract is the text of <article class="sidebar text-justify"> up to its <hr>, after which come the
PDF / Fulltext / References buttons. Words inside it may be keyword links (ascidatabase.com searches) and structured
abstracts bold their part labels. A few pages print only "." there (no abstract).

Only the abstract is read. The byline (names linked to ascidatabase.com) is not output: the live works already carry
these authors from Crossref (0 of 80 sampled works lack them), and the pages show no affiliations (the sidebar gives
"Country: ..." per author only), no corresponding-author marks, no acknowledgments or funding statement, and no
reference list (the References button links to the separate full-text page).
"""
import re

from bs4 import Comment, NavigableString, Tag

from parseland_lib.publisher.parsers.parser import PublisherParser

MIN_WORDS = 5  # a block holding "." or a stray word is no abstract


class ScienceAlert(PublisherParser):
    parser_name = "scialert"

    def is_publisher_specific_parser(self):
        # Every parser's claim runs on every DOI page (#2239: under 0.5 ms a page it does not claim): read one meta tag
        # among <head>'s direct children, reached through direct children only (never a whole-tree search).
        if not hasattr(self, "_claim"):
            html = self.soup.find("html", recursive=False)
            head = html.find("head", recursive=False) if html else None
            tag = head.find("meta", attrs={"name": "twitter:site"}, recursive=False) if head else None
            self._claim = bool(tag) and (tag.get("content") or "").strip().lower() == "@scialert"
        return self._claim

    def _abstract_block(self):
        if not hasattr(self, "_block"):
            self._block = self.soup.select_one("article.sidebar.text-justify")
        return self._block

    def authors_found(self):
        # True on the pages this parser reads (an abstract page of the site), although it outputs the abstract only.
        return self.is_publisher_specific_parser() and self._abstract_block() is not None

    def parse_abstract(self):
        block = self._abstract_block()
        if block is None:
            return None
        parts = []
        for node in block.children:
            if isinstance(node, Tag):
                if node.name == "hr" or "btn" in (node.get("class") or []):
                    break
                parts.append(node.get_text())
            elif isinstance(node, NavigableString) and not isinstance(node, Comment):
                parts.append(str(node))
        text = re.sub(r"\s+", " ", "".join(parts)).strip()
        return text if len(text.split()) >= MIN_WORDS else None

    def parse(self):
        return {"authors": [], "abstract": self.parse_abstract()}
