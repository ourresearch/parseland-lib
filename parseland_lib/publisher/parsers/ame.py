import re

from bs4 import NavigableString, Tag

from parseland_lib.elements import Author, Affiliation
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

# Every AME journal (amegroups.org and .com, theajo.com, annalscts.com ...) loads its styles and scripts from AME's
# own CDN; some pages carry no citation_publisher tag (actr.amegroups.org), none lacks the CDN (oxjob #2289)
_ASSET_HOST = "amegroups.cn"
_FUNDING_LABEL = re.compile(r"^funding\s*:?$", re.I)
_LABEL_END = re.compile(r"^\s*:?\s*")
_BUTTONS = re.compile(r"(?:\s*\[\s*(?:Crossref|PubMed)\s*\])+\s*$")  # each entry's link buttons, after its text
_ENTRY_ID = re.compile(r"^B(\d+)$")
# "None.", "Funding: None.": a section that says there is nothing (parse.py's headed reader uses the same bar)
_MIN_STATEMENT = 20
_NUMBER = re.compile(r"\d+")
_NAME_SEPARATOR = re.compile(r",|\band\b|&")
_ABSTRACT_LABEL = re.compile(r"^Abstract\s*:\s*", re.I)  # older pages: "<strong>Abstract:</strong> ..."


def _label_after(name_node):
    """The affiliation numbers in the <sup> after a byline name, before the next name ("^", "#" marks: none)."""
    for sibling in name_node.next_siblings:
        if isinstance(sibling, NavigableString):
            if _NAME_SEPARATOR.sub("", squash(sibling)).strip():
                return []  # the next name: this one has no label
        elif sibling.name == "sup":
            return _NUMBER.findall(sibling.get_text())
    return []


def _is_ame_page(soup):
    """AME's assets or its publisher tag in <head>: the cheap first test of the claim. Every parser's authors_found()
    runs on every DOI page (#2239: under 0.5 ms a page it does not claim), so <head> is reached through direct
    children and searched alone; nothing walks the whole tree until this passes. SciEngine and elpub pages print a
    <p class="authors"> byline too."""
    html = soup.find("html", recursive=False)
    head = (html or soup).find("head", recursive=False)
    if head is None:
        return False
    for tag in head.find_all(("link", "script", "meta")):
        if tag.name == "meta":
            if tag.get("name") == "citation_publisher" and "ame " in (tag.get("content") or "").lower():
                return True
        elif _ASSET_HOST in (tag.get("href") or tag.get("src") or ""):
            return True
    return False


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
        return self.substr_in_citation_publisher('AME ')

    def authors_found(self):
        return _is_ame_page(self.soup) and bool(self.soup.select('p.authors'))

    def parse_affs(self):
        affs = []
        aff_tags = self.soup.select('p.affiliation aff')
        for aff_tag in aff_tags:
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
        one affiliation labels no one ("A, B, C"): its names share one text node (oxjob #2289)."""
        authors = []
        authors_tag = self.soup.select_one('p.authors')
        for author_tag in authors_tag.children:
            if not isinstance(author_tag, NavigableString):
                continue
            names = [name for part in _NAME_SEPARATOR.split(str(author_tag)) if (name := squash(part))]
            if not names:
                continue
            authors.extend(Author(name=name, aff_ids=[]) for name in names[:-1])
            authors.append(Author(name=names[-1], aff_ids=_label_after(author_tag)))
        affs = self.parse_affs()
        return self.merge_authors_affiliations(authors, affs)

    def parse_abstract(self):
        if abs_tag := self.soup.select_one('#abstract'):
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
        corr_authors = self.soup.select('div[class*=corr] [id*=cor]')
        for corr_author in corr_authors:
            for author in authors:
                if author.name.lower() in corr_author.text.lower():
                    author.is_corresponding = True
        references, references_complete = self.parse_references()
        acknowledgments, funding_statement = self.parse_acknowledgments_and_funding()
        return {'authors': authors,
                'abstract': self.parse_abstract(),
                'acknowledgments': acknowledgments,
                'funding_statement': funding_statement,
                'references': references or None,
                'references_complete': references_complete}
