"""AME Publishing Company journals (jtd.amegroups.org, atm.amegroups.org, amegroups.com, theajo.com, annalscts.com ...).

AME's own platform: OJS-like /article/view/ addresses without OJS markup. The full-text page prints the byline as text
in <p class="authors"> (a <sup> after a name holds its affiliation numbers and its #, *, ^ notes), the affiliations as
<aff> tags in <p class="affiliation">, a "Correspondence to:" note, the abstract in div#abstract, an Acknowledgments
section (often holding only a "Funding:" paragraph; newer pages print "Funding:" in the Footnote section instead) and
the reference list as ol.ref-item.

Oxjob #2289 (template "ojs-like"): the back matter (#2215's contract), a claim cheap enough to run on every page, and
pages with one unnumbered affiliation, which crashed this parser. Oxjob #2338 (amegroups.org, 16-17 Nov 2026), on top
of it: the correspondence note matched on whole names, accents folded; one <aff> holding several affiliations behind
<target> marks split into them, departments before a shared institution given its institution and address; the claim
on the word AME ("Notre Dame Press" is not AME); the soup left as it was for the parsers that read it after this one.
"""
import copy
import re
import unicodedata

from bs4 import Comment, NavigableString, Tag

from parseland_lib.elements import Author, Affiliation
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

# Every AME journal (amegroups.org and .com, theajo.com, annalscts.com ...) loads its styles and scripts from AME's
# own CDN; some pages carry no citation_publisher tag (actr.amegroups.org), none lacks the CDN (oxjob #2289)
_ASSET_HOST = "amegroups.cn"
_PUBLISHER = re.compile(r"\bAME\b", re.I)  # "AME Publishing Company"; not "University of Notre Dame Press" (#2338)
_FUNDING_LABEL = re.compile(r"^funding\s*:?$", re.I)
_LABEL_END = re.compile(r"^\s*:?\s*")
_BUTTONS = re.compile(r"(?:\s*\[\s*(?:Crossref|PubMed)\s*\])+\s*$")  # each entry's link buttons, after its text
_ENTRY_ID = re.compile(r"^B(\d+)$")
# "None.", "Funding: None.": a section that says there is nothing (parse.py's headed reader uses the same bar)
_MIN_STATEMENT = 20
_NUMBER = re.compile(r"\d+")
_NAME_SEPARATOR = re.compile(r",|;|\band\b|&")
_NAME_SUFFIX = re.compile(r"^(?:Jr|Sr|II|III|IV)\.?$")  # "John Smith, Jr." is one name (#2338)
_ABSTRACT_LABEL = re.compile(r"^Abstract\s*:\s*", re.I)  # older pages: "<strong>Abstract:</strong> ..."
_BLOCKS = ["p", "div", "h1", "h2", "h3", "h4", "h5", "h6"]
_ADDRESS = ["addr-line", "country"]  # a <target> segment that names these is a whole affiliation (#2338)


def _label_after(name_node):
    """The affiliation numbers in the <sup> after a byline name, before the next name ("^", "#" marks: none)."""
    for sibling in name_node.next_siblings:
        if isinstance(sibling, Comment):
            continue
        if isinstance(sibling, NavigableString):
            if _NAME_SEPARATOR.sub("", squash(sibling)).strip():
                return []  # the next name: this one has no label
        elif sibling.name == "sup":
            return _NUMBER.findall(sibling.get_text())
    return []


def _fold(text):
    """Lower case, accents off, whitespace squashed: for finding a byline name in the correspondence note."""
    text = unicodedata.normalize("NFKD", text or "")
    return squash("".join(c for c in text if not unicodedata.combining(c))).casefold()


def _is_ame_page(soup):
    """AME's assets or its publisher tag in <head>: the cheap first test of the claim. Every parser's authors_found()
    runs on every DOI page (#2239: under 0.5 ms a page it does not claim), so <head> is reached through direct
    children and searched alone; nothing walks the whole tree until this passes. SciEngine and elpub pages print a
    <p class="authors"> byline too. Only <head>'s own children are read: 0.01 ms a page against find_all's 0.08, and
    the same answer on 300 other sites' pages and 101 AME pages (#2338, 17 Nov)."""
    html = soup.find("html", recursive=False)
    head = (html or soup).find("head", recursive=False)
    if head is None:
        return False
    for tag in head.children:
        name = tag.name
        if name == "meta":
            if tag.get("name") == "citation_publisher" and _PUBLISHER.search(tag.get("content") or ""):
                return True
        elif name in ("link", "script") and _ASSET_HOST in (tag.get("href") or tag.get("src") or ""):
            return True
    return False


def _target_affs(aff):
    """One <aff> holding several affiliations, each opened by <target id="affN"><sup>N</sup></target> (#2338). A
    segment that ends in a comma and names no address (<addr-line>, <country>) shares the institution and address of
    the segment that closes its group: "1Department of Geriatrics, 2Department of Cardiology, <institution>The First
    Affiliated Hospital</institution>, Nanjing, China" is two departments of that hospital. A ';' closes a group."""
    parts = []  # [number, text, its text from its first <institution> on or None, it names an address]
    for node in aff.children:
        if isinstance(node, Tag) and node.name == "target":
            parts.append(["".join(_NUMBER.findall(node.get_text())) or None, "", None, False])
            continue
        if not parts or isinstance(node, Comment):
            continue
        part, text = parts[-1], node.get_text() if isinstance(node, Tag) else str(node)
        if isinstance(node, Tag):
            if part[2] is None and node.name == "institution" and node.get("content-type") != "dept":
                part[2] = ""
            part[3] = part[3] or node.name in _ADDRESS or node.find(_ADDRESS) is not None
        part[1] += text
        if part[2] is not None:
            part[2] += text
    shares = [not address and text.strip().endswith(",") for _, text, _, address in parts]
    out = []
    for i, (aff_id, text, _, _) in enumerate(parts):
        if shares[i]:
            closing = next((parts[j] for j in range(i + 1, len(parts)) if not shares[j]), None)
            if closing is not None and closing[2]:
                text = text.rstrip() + " " + closing[2]
        if text := squash(text).strip(" ;,"):
            out.append(Affiliation(text, aff_id))
    return out


def _labelled_funding(p):
    """The text of a run-in "<em>Funding:</em> ..." paragraph after its label, or None when the paragraph is not one."""
    first = next((c for c in p.children if not (isinstance(c, NavigableString) and not c.strip())), None)
    if not isinstance(first, Tag) or first.name not in ("em", "strong", "b") or \
            not _FUNDING_LABEL.match(squash(first.get_text())):
        return None
    label = squash(first.get_text())
    return _LABEL_END.sub("", squash(p.get_text())[len(label):])


def _section_paragraphs(heading):
    """The <p>s after an h2, up to the rule or heading that ends its section."""
    paragraphs = []
    for sibling in heading.find_next_siblings():
        if sibling.name in ("hr", "h1", "h2", "h3"):
            break
        if sibling.name == "p":
            paragraphs.append(sibling)
    return paragraphs


def _statement(text):
    return text if text and len(text) >= _MIN_STATEMENT else None


class AMEPublishing(PublisherParser):
    parser_name = "ame_publishing"

    def is_publisher_specific_parser(self):
        tag = self.soup.select_one('meta[name="citation_publisher"]')
        return bool(tag is not None and _PUBLISHER.search(tag.get("content") or ""))

    def authors_found(self):
        return _is_ame_page(self.soup) and bool(self.soup.select('p.authors'))

    def parse_affs(self):
        affs = []
        aff_tags = self.soup.select('p.affiliation aff')
        for aff_tag in aff_tags:
            if aff_tag.find("target") is not None:
                affs += _target_affs(aff_tag)
                continue
            aff_tag = copy.copy(aff_tag)  # other parsers read this soup after this one (#2338)
            sup = aff_tag.select_one('sup')
            aff_id = None
            if sup:
                aff_id = m.group() if (m := _NUMBER.search(sup.text)) else sup.text.strip()
                sup.decompose()
            aff = aff_tag.text.strip()
            if sup is None and affs and affs[-1].aff_id is not None:
                # an unlabelled <aff> after a labelled one is the rest of it: "<sup>3</sup>Department of Surgery,"
                # then "University of Milan-Bicocca, ..." (oxjob #2289)
                affs[-1] = Affiliation(f"{affs[-1].organization} {aff}", affs[-1].aff_id)
                continue
            # a lone affiliation carries no label: every author's (merge_authors_affiliations)
            affs.append(Affiliation(aff, aff_id))
        return affs

    def parse_authors(self):
        """The byline's names in order, each with the affiliation numbers of the <sup> that follows it. A byline with
        one affiliation labels no one ("A, B, C"): its names share one text node (oxjob #2289). A suffix after a comma
        ("Jr.") stays with its name, and an HTML comment is no name (#2338)."""
        authors = []
        authors_tag = self.soup.select_one('p.authors')
        for author_tag in authors_tag.children:
            if not isinstance(author_tag, NavigableString) or isinstance(author_tag, Comment):
                continue
            names = []
            for part in _NAME_SEPARATOR.split(str(author_tag)):
                if not (name := squash(part)):
                    continue
                if _NAME_SUFFIX.match(name) and names:
                    names[-1] += ", " + name
                elif _NAME_SUFFIX.match(name) and authors:
                    authors[-1].name += ", " + name
                else:
                    names.append(name)
            if not names:
                continue
            authors.extend(Author(name=name, aff_ids=[]) for name in names[:-1])
            authors.append(Author(name=names[-1], aff_ids=_label_after(author_tag)))
        affs = self.parse_affs()
        return self.merge_authors_affiliations(authors, affs)

    def _mark_corresponding(self, authors):
        """The authors the "Correspondence to:" note names: whole names, accents and case folded ("Li Li" is not in
        "Beili Lin") (#2338)."""
        notes = [_fold(tag.get_text(" ")) for tag in self.soup.select("div[class*=corr] [id*=cor]")]
        for author in authors:
            name = _fold(author.name.split(",")[0])  # without a joined suffix: the note prints "John Smith Jr., MD"
            if name and any(re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", note) for note in notes):
                author.is_corresponding = True

    def parse_abstract(self):
        """div#abstract's text without an "Abstract:" label. Paragraphs printed back to back, with nothing between
        them, are kept apart by a line break ("...patients.</p><p>Methods: ..." ran together) (#2338)."""
        if abs_tag := self.soup.select_one('#abstract'):
            if any(isinstance(block.next_sibling, Tag) for block in abs_tag.find_all(_BLOCKS)):
                abs_tag = copy.copy(abs_tag)  # other parsers read this soup after this one
                for block in abs_tag.find_all(_BLOCKS):
                    if isinstance(block.next_sibling, Tag):
                        block.insert_after("\n")
            return _ABSTRACT_LABEL.sub("", abs_tag.text.strip())

    def parse_references(self):
        """(references, references_complete): the <ol class="ref-item"> right after the "References" heading. Whole
        when it is the page's only such list, starts at 1, and its entry ids run B1..Bn with no gap."""
        # imported here: back_matter and parse import this package, so a module-level import is circular
        from parseland_lib.back_matter import _entry_doi, _numbering_whole
        heading = self.soup.find("h2", id="references")
        ol = heading.find_next_sibling(["ol", "h2"]) if heading else None
        if ol is None or ol.name != "ol" or "ref-item" not in (ol.get("class") or []):
            return [], False
        refs, labels = [], []
        for li in ol.find_all("li", recursive=False):
            raw = _BUTTONS.sub("", squash(li.get_text()))
            if not raw:
                continue
            labels.append(m.group(1) if (m := _ENTRY_ID.match(li.get("id") or "")) else "")
            refs.append({"position": len(refs) + 1, "raw": raw, "doi": _entry_doi(li, raw)})
        complete = bool(refs) and all(labels) and _numbering_whole(labels) and \
            int(ol.get("start") or 1) <= 1 and len(self.soup.select("ol.ref-item")) == 1
        return refs, complete

    def parse_acknowledgments_and_funding(self):
        """(acknowledgments, funding_statement). The funding statement is a run-in "<em>Funding:</em>" paragraph, under
        the Acknowledgments heading or in the Footnote section; the acknowledgments are the other paragraphs under
        that heading."""
        ack_heading = self.soup.find("h2", id=["acknowledgments", "acknowledgements"])
        footnote = self.soup.find("h2", id="Footnote")
        ack, funding = [], None
        for p in _section_paragraphs(ack_heading) if ack_heading else []:
            if (text := _labelled_funding(p)) is not None:
                funding = funding or text
            elif text := squash(p.get_text()):
                ack.append(text)
        for p in _section_paragraphs(footnote) if footnote and funding is None else []:
            if (text := _labelled_funding(p)) is not None:
                funding = text
                break
        return _statement("\n".join(ack)), _statement(funding)

    def parse(self):
        authors = self.parse_authors()
        self._mark_corresponding(authors)
        references, references_complete = self.parse_references()
        acknowledgments, funding_statement = self.parse_acknowledgments_and_funding()
        return {'authors': authors,
                'abstract': self.parse_abstract(),
                'acknowledgments': acknowledgments,
                'funding_statement': funding_statement,
                'references': references or None,
                'references_complete': references_complete}
