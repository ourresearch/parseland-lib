"""nanoGe conference abstracts (nanoge.org proceedings, Fundació Scito; oxjob #2339).

Each contribution's page prints its whole abstract in <div id="abst-content">. The og:description tag holds a cut
copy ("..."), the page has no citation_abstract, so no reader took the abstract: 0 of 80 sampled pages, while about
4,900 of the site's 6,320 works lack one. This parser adds that abstract and nothing else: the authors stay what the
citation_author tags give (the generic parser's; the works already have their authors and affiliations, so the
byline would gain no work), and the reference list some authors print at the end of the block is cut off.
"""
import re

from bs4 import Comment, NavigableString, Tag

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser

_BLOCK_TAGS = {"p", "div", "ul", "ol", "li", "table", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6", "pre"}
# a line that opens a reference entry: "(1) Jeon et al.", "[1] B. B. Yu", "1 Li, Z.", "1. Lee"
_REF_NUMBER = re.compile(r"^(?:\[(\d{1,3})\]\s*|\((\d{1,3})\)\s*|(\d{1,3})(?:[.)]\s*|\s+))(?=\S)")
# ... and looks like a citation: a year, "et al", a DOI, or a stated status
_CITATION_LOOK = re.compile(r"\b(?:1[89]|20)\d\d\b|\bet\.? ?al\b|\b10\.\d{4,9}/|\b(?:in press|in revision|submitted)\b",
                            re.I)
_REF_HEADING = re.compile(r"^(?:references?|bibliography|literature(?: cited)?|refs?\.?)\s*:?$", re.I)


def _lines(el):
    """The text of an element as lines: <br> breaks a line, the source's own line breaks are spaces."""
    parts = []
    for node in el.descendants if isinstance(el, Tag) else [el]:
        if isinstance(node, Comment):
            continue
        if isinstance(node, NavigableString):
            if node.parent is not None and node.parent.name in ("script", "style"):
                continue
            parts.append(str(node).replace("\n", " "))
        elif node.name == "br":
            parts.append("\n")
    return [line for line in (" ".join(part.split()) for part in "".join(parts).split("\n")) if line]


def _blocks(content):
    """The block's paragraphs, each a list of lines; inline text between paragraphs is a paragraph of its own."""
    blocks, run = [], []
    for child in content.children:
        if isinstance(child, Tag) and child.name in _BLOCK_TAGS:
            if run:
                blocks.append(run)
                run = []
            blocks.append(_lines(child))
        else:
            run.extend(_lines(child))
    if run:
        blocks.append(run)
    return [b for b in blocks if b]


def _is_reference_run(lines):
    """True when lines are a numbered reference list: each opens with a number, the first with 1, and at least half
    look like citations (a year, "et al", a DOI)."""
    numbers = [_REF_NUMBER.match(line) for line in lines]
    if not lines or not all(numbers):
        return False
    first = next(g for g in numbers[0].groups() if g)
    return first == "1" and 2 * sum(bool(_CITATION_LOOK.search(line)) for line in lines) >= len(lines)


def _cut_references(blocks):
    """The paragraphs before the reference list at the block's end: a "References" heading and all after it, then
    any trailing numbered entries (whole paragraphs, or the last lines of the last one)."""
    for i, block in enumerate(blocks):
        if i and len(block) == 1 and _REF_HEADING.match(block[0]):
            blocks = blocks[:i]
            break
    blocks = [list(b) for b in blocks]
    # trailing entries: the numbered lines at the end, back to the one numbered 1
    lines = [(i, j, line) for i, b in enumerate(blocks) for j, line in enumerate(b)]
    for k in range(len(lines) - 1, 0, -1):
        tail = [line for _, _, line in lines[k:]]
        if _is_reference_run(tail):
            i, j, _ = lines[k]
            return [b for b in blocks[:i] + ([blocks[i][:j]] if j else []) if b]
    return blocks


class NanoGe(PublisherParser):
    parser_name = "nanoge"

    def is_publisher_specific_parser(self):
        # Cheap: the og:url tag in <head> only (every parser's claim runs on every DOI page, oxjob #2239). Every
        # stored nanoGe contribution page has one naming nanoge.org; its proceedings listings have none.
        claim = self.__dict__.get("_claim")
        if claim is None:
            head = self.soup.head
            tag = head.find("meta", attrs={"property": "og:url"}) if head is not None else None
            claim = self._claim = bool(tag is not None and "nanoge.org" in (tag.get("content") or "").lower())
        return claim

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._abstract())

    def _abstract(self):
        if "_abstract_text" not in self.__dict__:
            content = self.soup.find("div", id="abst-content")
            text = None
            if content is not None:
                blocks = _cut_references(_blocks(content))
                text = " ".join(" ".join(block) for block in blocks).strip() or None
                if text and len(text) < 50:
                    text = None
            self._abstract_text = text
        return self._abstract_text

    def parse(self):
        # the authors (citation_author tags) and every other key stay the generic parser's
        result = dict(GenericPublisherParser(self.soup).parse())
        result["abstract"] = self._abstract()
        return result
