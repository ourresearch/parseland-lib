"""Auctores (auctoresonline.com), a medical open-access publisher on its own PHP template (oxjob #2210).

The pages print no citation_* meta tags and a meta description cut to ~120 characters, so before this parser
Parseland read nothing from them. Everything is in the markup:

- byline: ``div.article-details div.u-list > ul > li``, the name followed by ``<sup><a>1,2*</a></sup>``;
- affiliations: ``<p>`` children of ``div.u-list`` (``1 Department ...``), sometimes one ``<p>`` split by ``<br>``;
  unnumbered paragraphs are not tied to anyone, so every author gets them all;
- corresponding author: the byline ``*``, explained by the ``*Corresponding Author: <name>, ...`` note in
  ``div.copyrights``; with no star in the byline, the note's name is matched to a byline name;
- abstract: ``div.parent-cls[data-for="abstract"]``;
- references: one ``<ol>`` of ``<li id="R0">`` ... under ``h4#references``, each followed by "View at Publisher |
  View at Google Scholar" links;
- acknowledgments and funding: an ``h4`` section, or a bold label paragraph ("Funding: ...") in the back matter.
"""
import copy
import re

from bs4 import NavigableString, Tag

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import same_person, squash

DOMAIN = "auctoresonline.com"
_CORR_NOTE = re.compile(r"^\W*corresponding\s+author\s*:?\s*", re.I)
_AFF_NUMBER = re.compile(r"^(\d{1,2}(?:\s*,\s*\d{1,2})*)\s*(\S.*)$")  # "1 Dept ...", "5,6,7 Dept ..."
_DOI = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+)")
_MORE = re.compile(r"\b(?:show|load|view|see)\s+(?:more|all)\b", re.I)
# Labels are matched whole (after section numbers and a trailing colon are dropped), so a body sub-heading such as
# "Funding sources in rural hospitals" is never taken for the article's own statement.
_ACK_LABEL = re.compile(r"acknowledge?ments?(?:\s*(?:and|&)\s*funding)?", re.I)
_FUNDING_LABEL = re.compile(
    r"(?:funding(?:\s+(?:statement|information|sources?))?|sources?\s+of\s+funding"
    r"|financial\s+support(?:\s+and\s+(?:sponsorship|protection))?|conflicts?\s+of\s+interest\s*/\s*funding\s+statement)",
    re.I)


def _label_key(text):
    text = squash((text or "").replace("\xa0", " "))
    text = re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", text)
    return text.rstrip(" :.-").strip()


def _clean(text):
    return squash((text or "").replace("\xa0", " "))


class Auctores(PublisherParser):
    parser_name = "auctores"

    def is_publisher_specific_parser(self):
        return bool(self.domain_in_meta_og_url(DOMAIN) or self.domain_in_canonical_link(DOMAIN))

    def _byline(self):
        return self.soup.select("div.article-details div.u-list > ul > li")

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._byline())

    # ---- authors
    @staticmethod
    def _name_and_marks(li):
        """(name, affiliation numbers, starred) for one byline item."""
        parts = [s for s in li.find_all(string=True) if s.find_parent(["sup", "a"]) is None]
        raw = _clean(" ".join(parts))
        marks = " ".join(sup.get_text("", strip=True) for sup in li.find_all("sup"))
        starred = "*" in marks or raw.endswith("*")
        name = raw.strip(" ,;*").strip()
        numbers = re.findall(r"\d+", marks)
        return name, numbers, starred

    def _affiliation_lines(self):
        lines = []
        for p in self.soup.select("div.article-details div.u-list > p"):
            line = []
            for node in p.descendants:
                if isinstance(node, Tag) and node.name == "br":
                    lines.append(_clean("".join(line)))
                    line = []
                elif isinstance(node, NavigableString):
                    line.append(str(node))
            lines.append(_clean("".join(line)))
        return [line for line in lines if line]

    def _corresponding_name(self):
        """The name the "*Corresponding Author:" note gives, or None when the page has no such note."""
        for p in self.soup.select("div.article-details div.copyrights p"):
            text = _clean(p.get_text(" "))
            if _CORR_NOTE.match(text):
                rest = _CORR_NOTE.sub("", text)
                return rest.split(",")[0].strip(" .;") or ""
        return None

    def parse_authors(self):
        byline = [self._name_and_marks(li) for li in self._byline()]
        byline = [b for b in byline if b[0]]
        lines = self._affiliation_lines()
        numbered = {}
        for line in lines:
            if m := _AFF_NUMBER.match(line):
                for number in re.findall(r"\d+", m.group(1)):
                    numbered.setdefault(number, m.group(2).strip())
        referenced = {n for _, numbers, _ in byline for n in numbers}
        linked = bool(set(numbered) & referenced)

        note_name = self._corresponding_name()
        any_star = any(starred for _, _, starred in byline)
        authors = []
        for name, numbers, starred in byline:
            if linked:
                affiliations = [numbered[n] for n in numbers if n in numbered]
            else:
                affiliations = list(lines)
            if note_name is None:
                corresponding = False  # a star the page never explains is no mark
            elif any_star:
                corresponding = starred
            else:
                corresponding = bool(note_name) and same_person(name, note_name)
            authors.append({"name": name, "affiliations": affiliations, "is_corresponding": corresponding})
        return authors

    # ---- abstract
    def parse_abstract(self):
        block = self.soup.find("div", class_="parent-cls", attrs={"data-for": re.compile(r"^abstract", re.I)})
        if block is None:
            return None
        paras = [_clean(p.get_text()) for p in block.find_all("p")]
        paras = [p for p in paras if p]
        text = "\n".join(paras) if paras else _clean(block.get_text(" "))
        text = re.sub(r"^abstract\s*[:.]?\s*", "", text, flags=re.I)
        return text or None

    # ---- references
    def parse_references(self):
        heading = self.soup.find("h4", id="references")
        container = heading.find_next_sibling("div", class_="ref-links") if heading else None
        if container is None:
            return None, False
        lists = container.find_all("ol")
        entries, empty = [], 0
        for li in container.select("ol > li"):
            item = copy.copy(li)
            for links in item.select("span.reflinks"):
                links.decompose()
            raw = _clean(item.get_text(" "))
            if len(re.sub(r"\W", "", raw)) < 5:  # "." or nothing: the template's empty placeholder
                empty += 1
                continue
            doi = None
            if m := _DOI.search(raw):
                doi = m.group(1)
            else:
                for a in li.find_all("a", href=True):
                    if m := re.search(r"doi\.org/(10\.\d{4,9}/\S+)", a["href"]):
                        doi = m.group(1)
                        break
            if doi:
                doi = doi.rstrip(".,;)]")
            entries.append((li.get("id"), raw, doi))
        if not entries:
            return None, False
        references = [{"position": i, "raw": raw, "doi": doi} for i, (_, raw, doi) in enumerate(entries, 1)]
        ids = [i for i, _, _ in entries]
        ids_run = all(i == f"R{n}" for n, i in enumerate(ids))
        outside = any(s.strip() for s in container.find_all(string=True) if s.find_parent("li") is None)
        start = lists[0].get("start") if lists else None
        complete = (len(lists) == 1 and (start is None or str(start).strip() in ("", "0", "1")) and not empty
                    and ids_run and not outside and not _MORE.search(container.get_text(" ")))
        return references, complete

    # ---- acknowledgments and funding
    @staticmethod
    def _bold_label(p):
        """(label, rest of the paragraph) when the paragraph opens with a bold label, else (None, None)."""
        first = next((c for c in p.children if not (isinstance(c, NavigableString) and not c.strip())), None)
        if not (isinstance(first, Tag) and first.name in ("strong", "b")):
            return None, None
        label = _clean(first.get_text())
        if not label or len(label) > 80:
            return None, None
        text = _clean(p.get_text())
        rest = text[len(label):] if text.startswith(label) else text
        return label, rest.lstrip(" :.-").strip()

    def _back_matter_blocks(self):
        """(label, [paragraph texts]) for every h4 section and every bold-labelled paragraph run in the article."""
        blocks = []
        for heading in self.soup.select("div.article-desc h4.article-det-header"):
            body = heading.find_next_sibling()
            if not (isinstance(body, Tag) and "parent-cls" in (body.get("class") or [])):
                continue
            current = (heading.get_text(" "), [])
            blocks.append(current)
            for p in body.find_all("p"):
                label, rest = self._bold_label(p)
                if label is not None and rest:
                    blocks.append((label, [rest]))
                    current = None  # an inline label holds its own text; what follows is not part of it
                elif label is not None:
                    current = (label, [])
                    blocks.append(current)
                elif current is not None and (text := _clean(p.get_text())):
                    current[1].append(text)
        return blocks

    def parse_back_matter(self):
        acknowledgments = funding = None
        for label, texts in self._back_matter_blocks():
            key = _label_key(label)
            text = "\n".join(texts).strip() or None
            if not text:
                continue
            if acknowledgments is None and _ACK_LABEL.fullmatch(key):
                acknowledgments = text
            elif funding is None and _FUNDING_LABEL.fullmatch(key):
                funding = text
        return acknowledgments, funding

    def parse(self):
        references, complete = self.parse_references()
        acknowledgments, funding = self.parse_back_matter()
        return {"authors": self.parse_authors(),
                "abstract": self.parse_abstract(),
                "acknowledgments": acknowledgments,
                "funding_statement": funding,
                "references": references,
                "references_complete": complete}
