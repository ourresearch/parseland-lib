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
"""
import html
import re

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

# A footnote label: "1", "12", "a", "*", "†". Longer <sup> text is an affiliation set in superscript (1960s pages).
_LABEL = re.compile(r"[0-9]{1,3}|[a-z]|[*†‡§¶#]{1,3}")
_SUP = re.compile(r"<sup\b[^>]*>(.*?)</sup>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")
# the "and" joining the last two names, or the last two affiliations of a numbered list
_AND = re.compile(r"[\s,;]+and$")


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


class JCI(PublisherParser):
    parser_name = "jci"

    def is_publisher_specific_parser(self):
        return self.substr_in_citation_journal_title('JCI Insight')

    def authors_found(self):
        return bool(self.soup.select_one('.author-list'))

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
        return {'authors': self.parse_authors(), 'abstract': self.parse_abstract_meta_tags()}
