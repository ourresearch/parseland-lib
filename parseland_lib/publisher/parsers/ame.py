"""AME Publishing Company journals (jtd.amegroups.org, atm.amegroups.org, tcr.amegroups.org, qims.amegroups.org, ...).

AME's own platform: OJS-like /article/view/ addresses without OJS markup. The full-text page prints the byline as text
in <p class="authors"> (a <sup> after a name holds its affiliation numbers and its #, *, ^ notes), the affiliations as
<aff> tags in <p class="affiliation">, a "Correspondence to:" note, the abstract in div#abstract, an Acknowledgments
section (often holding only a "Funding:" paragraph; newer pages print "Funding:" in the Footnote section instead) and
the reference list as ol.ref-item. Oxjob #2338 (16-17 Nov 2026): pages with one affiliation print it without a number,
which crashed this parser on about a third of its pages, so they lost their corresponding author; the byline's names
without a <sup> were read as one name; one <aff> holding every affiliation behind <target> marks was read as one.
"""
import copy
import re
import unicodedata

from bs4 import Comment, NavigableString, Tag

from parseland_lib.elements import Author, Affiliation
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

_PUBLISHER = re.compile(r"\bAME\b", re.I)  # "AME Publishing Company"; not "Notre Dame Press"
_NAME_SPLIT = re.compile(r",|;|\s+and\s+")
_NAME_SUFFIX = re.compile(r"^(?:Jr|Sr|II|III|IV)\.?$")
_ACK_TITLE = re.compile(r"^acknowledge?ments?$", re.I)
_FUNDING_LABEL = re.compile(r"^Funding(?: sources?| information)?\s*:\s*")
_NOTHING = re.compile(r"^(?:none|n/?a|not applicable)\.?$", re.I)  # "Acknowledgments: None." acknowledges no one
_LINK_LABELS = {"crossref", "pubmed", "pmc", "google scholar", "full text"}  # a reference's [Crossref] [PubMed] buttons


def _fold(text):
    """Lower case, accents off, whitespace squashed: for finding a byline name in the correspondence note."""
    text = unicodedata.normalize("NFKD", text or "")
    return squash("".join(c for c in text if not unicodedata.combining(c))).casefold()


class AMEPublishing(PublisherParser):
    parser_name = "ame_publishing"

    def is_publisher_specific_parser(self):
        # one meta tag in <head>: production asks every parser this on every DOI page (#2239's CPU rule, 16 Nov)
        if getattr(self, "_claim", None) is None:
            head = self.soup.head
            tag = head.find("meta", attrs={"name": "citation_publisher"}) if head is not None else None
            self._claim = bool(tag is not None and _PUBLISHER.search(tag.get("content") or ""))
        return self._claim

    def authors_found(self):
        return self.is_publisher_specific_parser() and self.soup.find("p", class_="authors") is not None

    # ---- byline

    def _byline(self):
        """[name, [affiliation numbers]] in byline order. A text run can hold several names ("A, B, C"); a <sup>
        belongs to the name just before it."""
        entries, last_has_sup = [], True
        for node in self.soup.find("p", class_="authors").children:
            if isinstance(node, NavigableString) and not isinstance(node, Comment):
                for part in _NAME_SPLIT.split(str(node)):
                    part = squash(part)
                    if not part:
                        continue
                    if _NAME_SUFFIX.match(part) and entries:
                        entries[-1][0] += ", " + part
                    else:
                        entries.append([part, []])
                        last_has_sup = False
            elif isinstance(node, Tag) and node.name == "sup" and entries and not last_has_sup:
                entries[-1][1] = re.findall(r"\d+", node.get_text())
                last_has_sup = True
        return entries

    def parse_affs(self):
        """Affiliation(text, number or None). One <aff> per affiliation, its number in a <sup> (none when the page has
        one affiliation), or one <aff> holding them all, each opened by <target id="affN"><sup>N</sup></target>."""
        affs = []
        for aff in self.soup.select("p.affiliation aff"):
            if aff.find("target") is not None:
                parts = []
                for node in aff.children:
                    if isinstance(node, Tag) and node.name == "target":
                        parts.append(["".join(re.findall(r"\d+", node.get_text())) or None, ""])
                    elif parts and not isinstance(node, Comment):
                        parts[-1][1] += node.get_text() if isinstance(node, Tag) else str(node)
                affs += [Affiliation(text, aff_id) for aff_id, text in parts]
                continue
            aff = copy.copy(aff)  # other parsers read this soup after this one
            aff_id = None
            if (sup := aff.find("sup")) is not None:
                aff_id = "".join(re.findall(r"\d+", sup.get_text())) or None
                sup.decompose()
            affs.append(Affiliation(aff.get_text(), aff_id))
        cleaned = [(squash(a.organization).strip(" ;,"), a.aff_id) for a in affs]
        return [Affiliation(text, aff_id) for text, aff_id in cleaned if text]

    def parse_authors(self):
        authors = [Author(name=name, aff_ids=ids) for name, ids in self._byline()]
        return self.merge_authors_affiliations(authors, self.parse_affs())

    def _mark_corresponding(self, authors):
        notes = [_fold(tag.get_text(" ")) for tag in self.soup.select("div[class*=corr] [id*=cor]")]
        for author in authors:
            name = _fold(author.name)
            if name and any(re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", note) for note in notes):
                author.is_corresponding = True

    # ---- abstract and back matter

    def parse_abstract(self):
        block = self.soup.select_one("#abstract")
        if block is None:
            return None
        paragraphs = [squash(p.get_text()) for p in block.find_all("p")] or [squash(block.get_text())]
        return "\n".join(p for p in paragraphs if p) or None

    @staticmethod
    def _section(heading):
        """The paragraphs after a section heading, up to the next <hr> or heading."""
        paragraphs = []
        for sibling in heading.find_next_siblings():
            if sibling.name in ("hr", "h2"):
                break
            if sibling.name == "p" and (text := squash(sibling.get_text())):
                paragraphs.append(text)
        return paragraphs

    def _acknowledgments_and_funding(self):
        """The Acknowledgments section's text, and the "Funding:" paragraph's text without its label (in the
        Acknowledgments section, or the Footnote section on newer pages)."""
        acknowledgments, funding = [], None
        for heading in self.soup.find_all("h2", class_="section-title"):
            title = squash(heading.get_text())
            is_ack = bool(_ACK_TITLE.match(title))
            if not (is_ack or title == "Footnote"):
                continue
            for text in self._section(heading):
                if label := _FUNDING_LABEL.match(text):
                    funding = funding or text[label.end():] or None
                elif is_ack and not _NOTHING.match(text):
                    acknowledgments.append(text)
        return "\n".join(acknowledgments) or None, funding

    @staticmethod
    def _reference_text(item):
        item = copy.copy(item)  # other parsers read this soup after this one
        for link in item.find_all("a"):
            if squash(link.get_text()).lower() in _LINK_LABELS:
                link.decompose()
        return squash(re.sub(r"\[\s*\]", "", item.get_text()))

    def _references(self):
        """(entries, whole). Whole only when the page has one list, numbered B1..Bn with no gap."""
        # imported here: back_matter imports this package's utils, whose package imports every parser
        from parseland_lib.back_matter import _entry_doi
        lists = self.soup.select("ol.ref-item")
        if not lists:
            return None, False
        items = lists[0].find_all("li", recursive=False)
        refs = []
        for item in items:
            if raw := self._reference_text(item):
                refs.append({"position": len(refs) + 1, "raw": raw, "doi": _entry_doi(item, raw)})
        whole = (len(lists) == 1 and bool(refs) and len(refs) == len(items) and lists[0].get("start") in (None, "1")
                 and [item.get("id") for item in items] == [f"B{i}" for i in range(1, len(items) + 1)])
        return refs or None, whole

    def parse(self):
        authors = self.parse_authors()
        self._mark_corresponding(authors)
        acknowledgments, funding = self._acknowledgments_and_funding()
        references, whole = self._references()
        return {"authors": authors,
                "abstract": self.parse_abstract(),
                "acknowledgments": acknowledgments,
                "funding_statement": funding,
                "references": references,
                "references_complete": whole}
