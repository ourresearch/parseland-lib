"""SCIndeks article pages (oxjob #2338): CEON/CEES's Serbian Citation Index, scindeks.ceon.rs (journals) and
scindeks-zbornici.ceon.rs (proceedings), where most DOIs under the prefix 10.5937 land. Every page carries the index's
og:image (".../images/scindeks-logo_fb_sr.png") and prints the article in an ASP.NET table: div.cl_aut (the byline),
div.cl_afil (affiliations), a "Projekat" row and a reference table.

The generic reader already gets the byline (citation_author, the same names and order as div.cl_aut) and the abstract
(citation_abstract, the English version when the page has one); this parser keeps those as they are and adds what only
the page's own markup says:
- affiliations: lines of div.cl_afil, tied to authors by the byline's superscript letters, or shared by every author
  when the page prints them without letters. " + " joins two affiliations of one author. The "e-adresa" line after
  them is one unattributed address, not a corresponding-author mark (label-v1), and "nema" ("none") is no affiliation.
- the funding statement: the text under the label "Projekat" (the work's funding projects), one line per project.
- the reference list: the table's rows, in page order, each with the DOI its text prints.
"""
import copy
import re

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

_OG_IMAGE = re.compile(r"^https?://scindeks(?:-zbornici)?\.ceon\.rs/images/scindeks-logo")
_LINE = " "  # a <br> while the affiliation block is read
_MARK = "⁣"  # opens a superscript letter while the affiliation block is read
_FUNDING_LABELS = {"projekat", "project"}
_NO_AFFILIATION = re.compile(r"^(?:nema|none|-+)\.?$", re.I)


class SCIndeks(PublisherParser):
    parser_name = "scindeks"

    def is_publisher_specific_parser(self):
        # one meta tag in the head: cheap on the pages of every other site (#2239's claim-cost rule)
        head = self.soup.head
        if head is None:
            return False
        tag = head.find("meta", attrs={"property": "og:image"})
        return bool(tag and _OG_IMAGE.match(tag.get("content") or ""))

    def authors_found(self):
        return self.is_publisher_specific_parser() and self.soup.find("div", class_="cl_aut") is not None

    # ---- affiliations ----

    def _affiliation_lines(self):
        """[(letter or None, [affiliation, ...])] for each line of div.cl_afil, the e-mail line left out."""
        block = self.soup.find("div", class_="cl_afil")
        if block is None:
            return []
        block = copy.copy(block)  # never edit the page
        for tag in block.select("span.boldGrey, span.cl_indent, div.cl_other_cr, a[href^='mailto:'], "
                                "a[href*='email-protection'], span.__cf_email__"):
            tag.decompose()
        for br in block.find_all("br"):
            br.replace_with(_LINE)
        for div in block.find_all("div", class_="cl_afil_mrg"):
            div.insert_after(_LINE)
        for sup in block.find_all("sup"):
            sup.replace_with(_MARK + sup.get_text(strip=True) + _MARK)
        lines = []
        for line in block.get_text().split(_LINE):
            letter = None
            if (m := re.match(rf"\s*{_MARK}([^{_MARK}]*){_MARK}(.*)$", line, re.S)) is not None:
                letter, line = m.group(1).strip(), m.group(2)
            affs = [squash(a) for a in squash(line.replace(_MARK, "")).split(" + ")]
            affs = [a for a in affs if re.search(r"\w", a) and not _NO_AFFILIATION.match(a)]
            if affs or letter:
                lines.append((letter, affs))
        return lines

    def _byline_letters(self):
        """The superscript letters after each byline name, in byline order."""
        byline = self.soup.find("div", class_="cl_aut")
        letters = []
        for tag in byline.find_all(["a", "sup"]):
            if tag.name == "a" and "artaun=" in (tag.get("href") or ""):
                letters.append([])
            elif tag.name == "sup" and letters:
                letters[-1] += [x.strip() for x in tag.get_text().split(",") if x.strip()]
        return letters

    def _affiliations(self, n_authors):
        lines = self._affiliation_lines()
        letters = self._byline_letters()
        if not lines or len(letters) != n_authors:
            return None
        by_letter = {letter: affs for letter, affs in lines if letter}
        if not by_letter:  # printed without letters: every author has every line
            shared = [a for _, affs in lines for a in affs]
            return [list(shared) for _ in letters]
        return [[a for letter in mine for a in by_letter.get(letter, [])] for mine in letters]

    # ---- funding and references ----

    def _funding_statement(self):
        byline = self.soup.find("div", class_="cl_aut")
        cell = byline.find_parent("td") if byline else None
        for label in cell.select("span.boldGrey") if cell else []:
            if label.get_text(strip=True).lower() not in _FUNDING_LABELS:
                continue
            value = label.parent.find_next_sibling("div") if label.parent.name == "div" else None
            if value is None:  # <span class="cl_indent"><span class="boldGrey">Projekat</span>: text</span>
                value = copy.copy(label.parent)
                value.find("span", class_="boldGrey").decompose()
            else:
                value = copy.copy(value)
            for br in value.find_all("br"):
                br.replace_with(_LINE)
            text = "\n".join(p for p in (squash(x) for x in value.get_text().split(_LINE)) if p)
            text = re.sub(r"^:\s*", "", text)
            return text or None
        return None

    def _references(self):
        # imported here: back_matter imports the parsers package, which imports this module
        from parseland_lib.back_matter import _printed_doi, _without_list_numbers
        table = self.soup.find(id="ctl00_cph1_Details1_ReferencesCont")
        cells = table.select("td.cl_ref1, td.cl_ref2") if table is not None else []
        texts = [t for t in (squash(c.get_text(" ")) for c in cells) if t]
        if not texts:
            return None, False
        texts, numbered = _without_list_numbers(texts)
        refs = [{"position": i, "raw": t, "doi": _printed_doi(t)} for i, t in enumerate(texts, 1)]
        # The table prints every reference the index holds for the work, one per row from its database, with no
        # "show more" or pages: whole unless a row is empty or numbers the work's author typed skip one. Not
        # back_matter's broken-line test for typed lists: no row of the 72 stored pages was a fragment, and that test
        # misreads the index's order (Serbian "Đ" sorts after "Z") and book entries that end on a publisher's name.
        return refs, numbered and len(texts) == len(cells)

    def parse(self):
        generic = GenericPublisherParser(self.soup).parse()
        authors = [dict(a, affiliations=list(a.get("affiliations") or [])) for a in generic.get("authors") or []]
        affiliations = self._affiliations(len(authors))
        if affiliations is not None:
            for author, affs in zip(authors, affiliations):
                author["affiliations"] = affs or author["affiliations"]
        references, complete = self._references()
        return {"authors": authors, "abstract": generic.get("abstract"), "acknowledgments": None,
                "funding_statement": self._funding_statement(), "references": references,
                "references_complete": complete}
