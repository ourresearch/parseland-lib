"""Lexxion journal article pages (lexxion.eu and its journals' subdomains: core., estal., epppl., edpl. ...) (oxjob #2339).

The site prints the abstract only in the "Abstract" tab of its tab strip (section.data, div#abstract_de whatever the
language), with a "Keywords:" line at its end; no meta tag holds it whole (twitter:description is cut at 200
characters). The authors are in citation_author tags and a plain byline the generic parser already reads, so this
parser returns the generic parser's authors and adds the tab's abstract.

On older articles the tab holds a first-page preview instead: an image, the opening of the body cut off mid-word
("I. Introduction There is no ... or implem"), or scanned front matter ("© Lexxion Verlagsgesellschaft ..."). Those are
not abstracts (label-v1), and neither is a lone "Annotation on the Judgment of ..." line naming the case a note is on.

Affiliations, correspondence e-mails and thanks sit only in free-text biographies in the "Author Info" tab ("X is a
PhD Student at University of Zurich ... For correspondence: ..."): not read here.

Claimed by the citation_publisher tag ("Lexxion Publisher", "Lexxion Verlag") together with the abstract tab.
"""
import copy
import re

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

_BREAK = " "
_KEYWORDS = r"(?:key\s?words?|schlüsselwörter|schlagwörter|stichwörter)\s*:"
_KEYWORD_LINE = re.compile(r"^" + _KEYWORDS, re.I)
# ... or the same line run on after the abstract's last sentence, when the page left out the <br>
_KEYWORDS_RUN_ON = re.compile(r"(?<=[.!?…\"”’)\]])\s+" + _KEYWORDS, re.I)
# A body section's heading where an abstract would start: the tab holds the first page's text
_BODY_HEADING = re.compile(r"^(?:I|1)\.\s+[A-Z]")
_LONE_ANNOTATION = re.compile(r"^Annotation (?:on|of)\b")
# How a whole abstract ends; a preview of the body stops mid-sentence or mid-word
_ENDS = tuple('.!?…"”’\')]»')


class Lexxion(PublisherParser):
    parser_name = "lexxion"

    def __init__(self, soup):
        super().__init__(soup)
        self._claimed = None
        self._parsed = None

    def is_publisher_specific_parser(self):
        # Every DOI page asks every parser (#2239's CPU rule): first the <head>'s own meta tags only, and only a
        # Lexxion page goes on to look for the tab strip.
        if self._claimed is None:
            self._claimed = bool(self._publisher_is_lexxion()
                                 and self.soup.select_one('section.data div.tab-pane[id^="abstract"]'))
        return self._claimed

    def _publisher_is_lexxion(self):
        head = self.soup.head
        if head is None:
            return False
        tag = head.find("meta", attrs={"name": "citation_publisher"}, recursive=False)
        return bool(tag) and "lexxion" in (tag.get("content") or "").lower()

    def authors_found(self):
        # Unclaimed pages: the generic parser returns the same authors and abstract, so False changes no output.
        if not self.is_publisher_specific_parser():
            return False
        parsed = self.parse()
        return bool(parsed.get("authors") or parsed.get("abstract"))

    def parse(self):
        if self._parsed is None:
            parsed = dict(GenericPublisherParser(self.soup).parse())
            parsed["abstract"] = self.parse_abstract()
            self._parsed = parsed
        return self._parsed

    def parse_abstract(self):
        pane = self.soup.select_one('section.data div.tab-pane[id^="abstract"]')
        if pane is None:
            return None
        pane = copy.copy(pane)  # never edit the page
        for tag in pane.find_all(["xref", "img", "script", "style"]):
            tag.decompose()  # footnote markers, the preview image
        for br in pane.find_all("br"):
            br.replace_with(_BREAK)
        for p in pane.find_all("p"):
            p.append(_BREAK)
        lines = []
        for line in pane.get_text().split(_BREAK):
            if not (line := squash(line)):
                continue
            if _KEYWORD_LINE.match(line):
                break
            if run_on := _KEYWORDS_RUN_ON.search(line):
                lines.append(line[:run_on.start()])
                break
            lines.append(line)
        if not lines:
            return None
        text = "\n".join(lines)
        if text.startswith("©") or _BODY_HEADING.match(text) or not text.endswith(_ENDS):
            return None
        if len(lines) == 1 and _LONE_ANNOTATION.match(text) and len(text) < 400:
            return None
        return text
