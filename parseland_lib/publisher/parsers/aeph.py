"""Academic Education Publishing House (aeph.press) article pages (oxjob #2210).

The site runs its own small CMS with no citation meta tags. Each field sits in a `div.s4_9` right after a `div.s4_8`
label: "Author(s)", "Affiliation(s)", "Abstract", "Keywords", "References". Bylines carry plain-text markers
("Juanjuan Tan1,2,*, Jianhong Dong2"), affiliations are one per line with a leading number when the byline has numbers,
and a last "*Corresponding Author" line explains the star. Pages show no acknowledgments or funding section.
"""
import re

from parseland_lib.publisher.parsers.parser import PublisherParser

PUBLISHER = "Academic Education Publishing House"
# a comma that starts the next author, not one inside a marker run such as "1,2,*"
AUTHOR_SPLIT = re.compile(r",\s*(?=[^\d\s,*])")
NAME_AND_MARKS = re.compile(r"^(.*?)([\d\s,*]*)$")
CORR_NOTE = re.compile(r"^\*?\s*correspond", re.I)
NUMBERED_AFF = re.compile(r"^(\d+)\s*(\S.*)$")
REF_NUMBER = re.compile(r"^[ \t]*\[(\d+)\][ \t]*", re.M)
DOI = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+)")
MORE_MARKER = re.compile(r"show more|load more|view more|show all|more references", re.I)


def _clean(text):
    return " ".join(text.split())


class AEPH(PublisherParser):
    parser_name = "aeph"

    def is_publisher_specific_parser(self):
        footer = self.soup.select_one("div.s2_2")
        return bool(footer and PUBLISHER in footer.get_text() and self.soup.select_one("div.s4_8"))

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._sections().get("Author(s)", "").strip())

    def _sections(self):
        sections = {}
        for label in self.soup.select("div.s4_8"):
            value = label.find_next_sibling("div")
            if value is not None and "s4_9" in (value.get("class") or []):
                sections.setdefault(label.get_text(strip=True), value.get_text())
        return sections

    @staticmethod
    def _byline(text):
        out = []
        for part in AUTHOR_SPLIT.split(_clean(text)):
            name, marks = NAME_AND_MARKS.match(part.strip()).groups()
            if name := name.strip(" ,"):
                out.append((name, re.findall(r"\d+", marks), "*" in marks))
        return out

    def _authors(self, sections):
        byline = self._byline(sections.get("Author(s)", ""))
        lines = [_clean(line) for line in re.split(r"[\r\n]+", sections.get("Affiliation(s)", ""))]
        lines = [line for line in lines if line]
        has_note = any(CORR_NOTE.match(line) for line in lines)
        aff_lines = [line for line in lines if not CORR_NOTE.match(line)]

        numbered = {}
        if any(nums for _, nums, _ in byline):
            for line in aff_lines:
                if m := NUMBERED_AFF.match(line):
                    numbered.setdefault(m.group(1), m.group(2).strip())

        starred = any(star for _, _, star in byline)
        authors = []
        for name, nums, star in byline:
            if numbered:
                affs = [numbered[n] for n in nums if n in numbered]
            else:
                affs = list(aff_lines)  # unlinked: every author gets the whole list
            # a star counts only with the page's note; a lone author with the note and no star is the one it means
            corresponding = has_note and (star if starred else len(byline) == 1)
            authors.append({"name": name, "affiliations": affs, "is_corresponding": corresponding})
        return authors

    @staticmethod
    def _doi(raw):
        # only a DOI that ends the entry: some pages break a DOI with spaces ("DOI: 10.19738/j.cnki. psy.2022.14.061"),
        # and the part before the space is not the DOI
        m = DOI.search(raw)
        if not m or raw[m.end():].strip(" .,;)]"):
            return None
        return m.group(1).rstrip(".,;)]")

    @staticmethod
    def _references(text):
        if not text or not text.strip():
            return [], False
        marks = list(REF_NUMBER.finditer(text))
        if not marks:
            lines = [_clean(line) for line in re.split(r"[\r\n]+", text) if line.strip()]
            entries = [(None, line) for line in lines]
        else:
            entries = [(int(m.group(1)), _clean(text[m.end():nxt.start() if nxt else len(text)]))
                       for m, nxt in zip(marks, marks[1:] + [None])]
        refs = [{"position": i, "raw": raw, "doi": AEPH._doi(raw)} for i, (_, raw) in enumerate(entries, start=1)]
        numbers = [n for n, _ in entries]
        complete = (bool(marks) and not text[:marks[0].start()].strip()
                    and numbers == list(range(1, len(numbers) + 1)) and not MORE_MARKER.search(text))
        return refs, complete

    def parse(self):
        sections = self._sections()
        abstract = _clean(sections.get("Abstract", "")) or None
        references, complete = self._references(sections.get("References", ""))
        return {
            "authors": self._authors(sections),
            "abstract": abstract,
            "acknowledgments": None,
            "funding_statement": None,
            "references": references or None,
            "references_complete": complete,
        }
