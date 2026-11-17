"""ISCA Archive (www.isca-archive.org, DOI prefix 10.21437: Interspeech and other speech-communication proceedings),
oxjob #2338.

Each paper's page is a static W3.CSS card: the title in <h3>, the byline in <h5> (names only), then the abstract.
- The current template, titled "ISCA Archive - <paper title>", has citation_* tags and prints the abstract in
  <div id="abstract">, as bare text or as <p> paragraphs.
- The older one (most stored pages), titled "ISCA Archive", mostly has no meta tags and prints the abstract as <p>
  paragraphs right after the byline, before the PDF link and the "Cite as" line (<p class="w3-text">).
Neither has an "Abstract" heading or an abstract meta tag, so the generic readers found no abstract on any page. An
"Index Terms:" paragraph after the abstract is the paper's keywords. No page shows affiliations, a corresponding mark,
acknowledgments, funding or references.

Authors stay the generic parser's reading, the citation_author tags: the works these pages stand for already have
their authors (the #2338 sizing found 0 works the byline would add), so the byline is not read.
"""
import re

from parseland_lib.publisher.parsers.parser import PublisherParser

_KEYWORDS = re.compile(r"\s*(?:index terms|key ?words)\s*:", re.I)


def _text(tag):
    return " ".join(tag.get_text().split())


class ISCAArchive(PublisherParser):
    parser_name = "isca_archive"

    def is_publisher_specific_parser(self):
        # the <title> first (cheap: it stands near the top of every page), then the archive's card
        title = self.soup.title
        if title is None or not title.get_text().lstrip().startswith("ISCA Archive"):
            return False
        return self._byline() is not None

    def _byline(self):
        card = self.soup.find("div", class_="w3-card")
        if card is None or card.find("h3") is None:
            return None
        return card.find("h5")

    def _abstract_paragraphs(self):
        block = self.soup.find("div", id="abstract")
        if block is not None:
            return block.find_all("p") or [block]
        byline = self._byline()
        paragraphs = []
        for tag in byline.find_next_siblings() if byline is not None else []:
            if tag.name != "p" or "w3-text" in (tag.get("class") or []):
                break  # the <br> before the PDF link, or the "Cite as" line
            paragraphs.append(tag)
        return paragraphs

    def _abstract(self):
        texts = [text for p in self._abstract_paragraphs() if (text := _text(p)) and not _KEYWORDS.match(text)]
        return " ".join(texts) or None

    def authors_found(self):
        return self.is_publisher_specific_parser() and self._abstract() is not None

    def parse(self):
        return {
            "authors": self.parse_author_meta_tags(),
            "abstract": self._abstract(),
            "acknowledgments": None,
            "funding_statement": None,
            "references": None,
            "references_complete": False,
        }
