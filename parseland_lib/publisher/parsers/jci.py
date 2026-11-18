"""JCI and JCI Insight (jci.org) article pages.

The JCI class below wins only JCI Insight pages. On The Journal of Clinical Investigation's pages the meta-tag parser
wins, and jci.org writes no citation_author_institution tags, so every author came out without an affiliation
(oxjob #2252; ticket 25794 via #1062). The page shows each author's affiliations in a pop-up beside the byline: the
byline link ``a.author-affiliation[data-dropdown=author-affiliation-N]`` opens ``div#author-affiliation-N``, whose
``p.affiliations`` holds either that author's own affiliation (older articles: "Department of Medicine, Washington
University School of Medicine, St. Louis, Mo.") or the article's whole numbered list ("<sup>1</sup>Department of
Pathology ... <sup>2</sup>Department of Medicine ..."), in which case the byline's ``<sup>1,2</sup>`` picks the
author's. ``jci_affiliations`` reads those pairs; parse_page fills them in when the winning parser gave no author an
affiliation.

Since oxjob #2338 the JCI class claims both journals' pages on jci.org and adds their back matter, which no reader took
before: the "Acknowledgments" accordion (div#acknowledgments; its "Address correspondence to" note is not part of it,
and jci.org prints funding sentences there under no label of their own, so funding_statement stays None) and the
numbered reference list (div#references > ol > li.reference value="N", each entry followed by its "View this article
via" links, the CrossRef one a doi.org link to the cited work). On The Journal of Clinical Investigation's pages the
authors and abstract stay the generic reader's, as before.
"""
import copy
import html
import re

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

# A footnote label: "1", "12", "a", "*", "†". Longer <sup> text is an affiliation set in superscript (1960s pages).
_LABEL = re.compile(r"[0-9]{1,3}|[a-z]|[*†‡§¶#]{1,3}")
_SUP = re.compile(r"<sup\b[^>]*>(.*?)</sup>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")
# the "and" joining the last two names, or the last two affiliations of a numbered list
_AND = re.compile(r"[\s,;]+and$")
_ASCI = "American Society for Clinical Investigation"
_JCI_HTML_URL = re.compile(r"^https?://(?:[\w-]+\.)*jci\.org/", re.I)
# the correspondence note jci.org prints as the acknowledgments' last paragraph
_CORRESPONDENCE_NOTE = re.compile(r"^address (?:correspondence|reprint requests)\b", re.I)
_MORE_MARKER = re.compile(r"\b(?:show|load|view) (?:more|all)\b", re.I)


def _text(fragment):
    return squash(html.unescape(_TAG.sub(" ", fragment))).strip(" ,;")


def _labelled(block_html):
    """{label: affiliation} for a numbered list; {} when the block has no labels."""
    parts = _SUP.split(block_html)
    affs, label = {}, None
    for i, part in enumerate(parts):
        text = _text(part)
        if i % 2 and _LABEL.fullmatch(text):
            label = text
            affs.setdefault(label, "")
        elif label is not None:
            affs[label] = squash(f"{affs[label]} {text}")
    # "<sup>4</sup>Genetics Branch, NCI, and <sup>5</sup>NIDDK, NIH, Bethesda": the joining "and" is not part of it
    return {k: _AND.sub("", v) for k, v in affs.items() if v}


def _byline_name(link):
    return _AND.sub("", _text(_SUP.sub(" ", str(link)))).strip(" ,")


def jci_affiliations(soup):
    """[(byline name, [affiliations])] for each byline author whose pop-up holds a p.affiliations block.

    Every pop-up holds the article's whole list. Numbered, the byline labels pick each author's; one affiliation
    unnumbered is everyone's; several unnumbered (older articles) don't say who is where, so they go only to a sole
    author."""
    pairs = []
    links = soup.select("a.author-affiliation[data-dropdown]")
    boxes = {div["id"]: div for div in soup.select('div[id^="author-affiliation-"]')}
    read = {}  # every pop-up holds the same list: read each distinct one once
    for link in links:
        box = boxes.get(link["data-dropdown"])
        blocks = box.select("p.affiliations") if box is not None else []
        if not blocks:
            continue
        labels = [lbl.strip() for sup in link.find_all("sup") for lbl in sup.get_text().split(",") if lbl.strip()]
        block_html = " ".join(str(b) for b in blocks)
        if block_html not in read:
            read[block_html] = (_labelled(block_html), [t for t in (_text(str(b)) for b in blocks) if t])
        numbered, plain = read[block_html]
        if numbered:
            affs = [numbered[lbl] for lbl in labels if lbl in numbered]
            if not labels and len(numbered) == 1:
                affs = list(numbered.values())
        else:
            affs = plain if len(plain) == 1 or len(links) == 1 else []
        if affs:
            pairs.append((_byline_name(link), affs))
    return pairs


def _jci_head(soup):
    """jci.org's own article page: the American Society for Clinical Investigation's publisher tag and a
    citation_html_url on jci.org (a copy elsewhere, PubMed Central's, keeps the publisher tag). Read from <head>'s
    direct children only: every parser's claim runs on every DOI page (#2239: under 0.5 ms a page it does not claim)."""
    root = soup.find("html", recursive=False)
    head = (root or soup).find("head", recursive=False)
    if head is None:
        return False
    publisher = html_url = None
    for meta in head.find_all("meta", recursive=False):
        name = meta.get("name")
        if name == "citation_publisher":
            publisher = meta.get("content")
        elif name == "citation_html_url":
            html_url = meta.get("content")
    return publisher == _ASCI and bool(html_url and _JCI_HTML_URL.match(html_url))


def _acknowledgments(soup):
    """The Acknowledgments accordion's paragraphs, newline-joined, without the correspondence note; None without one."""
    block = soup.find("div", id="acknowledgments")
    if block is None:
        return None
    paragraphs = [text for p in block.find_all("p") if (text := squash(p.get_text()))
                  and not _CORRESPONDENCE_NOTE.match(text)]
    return "\n".join(paragraphs) or None


def _references(soup):
    """(references, references_complete) from the numbered list. Whole only when the one <ol> starts at 1, its
    value="N" labels run 1..n, every entry has text, and nothing outside the entries or a "show more" says otherwise."""
    # imported here: back_matter imports parsers.utils, whose package imports every parser, this one included
    from parseland_lib.back_matter import _linked_doi, _numbering_whole
    block = soup.find("div", id="references")
    lists = block.find_all("ol") if block is not None else []
    items = [li for ol in lists for li in ol.find_all("li", class_="reference")]
    if not items:
        return None, False
    references = []
    for item in items:
        entry = copy.copy(item)  # the other parsers still read this soup
        for links in entry.select("div.reference_linkouts"):
            links.decompose()
        if raw := squash(entry.get_text()):
            references.append({"position": len(references) + 1, "raw": raw, "doi": _linked_doi(item)})
    ol = lists[0]
    loose_text = any(squash(t) for node in (block, ol) for t in node.find_all(string=True, recursive=False))
    complete = (len(lists) == 1 and (ol.get("start") or "1").strip() == "1" and len(references) == len(items)
                and _numbering_whole([li.get("value") for li in items]) and not loose_text
                and not _MORE_MARKER.search(block.get_text(" ")))
    return references, complete


class JCI(PublisherParser):
    parser_name = "jci"

    def __init__(self, soup):
        super().__init__(soup)
        self._claimed = None
        self._parsed = None

    def is_publisher_specific_parser(self):
        if self._claimed is None:
            self._claimed = _jci_head(self.soup)
        return self._claimed

    def _is_insight(self):
        return self.substr_in_citation_journal_title('JCI Insight')

    def authors_found(self):
        if not self.is_publisher_specific_parser():
            return False
        if self._is_insight():
            return bool(self.soup.select_one('.author-list'))
        parsed = self.parse()
        return bool(parsed.get('authors') or parsed.get('abstract'))

    def parse_affs_map(self):
        affs_map = {}
        for tag in self.soup.select('p.affiliations'):
            if id_tag := tag.select_one('sup'):
                _id = id_tag.text.strip()
                id_tag.decompose()
                inst = tag.text.strip()
                affs_map[_id] = inst
        return affs_map

    def parse_authors(self):
        authors = []
        affs_map = self.parse_affs_map()
        for tag in self.soup.select('a.author-affiliation'):
            aff_ids = []
            if aff_ids_tag := tag.select_one('sup'):
                aff_ids = aff_ids_tag.text.strip().split(',')
                aff_ids_tag.decompose()
            name = tag.text.strip(' ,\t\n')
            affs = [affs_map[_id] for _id in aff_ids]
            authors.append({
                'name': name,
                'affiliations': affs,
                'is_corresponding': None
            })
        return authors

    def parse(self):
        # once per page: the JCI Insight byline reader removes the <sup> labels it reads
        if self._parsed is None:
            if self._is_insight():
                parsed = {'authors': self.parse_authors(), 'abstract': self.parse_abstract_meta_tags()}
            else:
                # The Journal of Clinical Investigation: the generic reader's authors and abstract, as before this
                # parser claimed its pages (parse_page still fills the byline pop-ups' affiliations, #2252)
                parsed = dict(GenericPublisherParser(self.soup).parse())
            references, complete = _references(self.soup)
            parsed.update(acknowledgments=_acknowledgments(self.soup), funding_statement=None,
                          references=references, references_complete=complete)
            self._parsed = parsed
        return self._parsed
