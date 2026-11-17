"""University of Szczecin Press journals (Wydawnictwo Naukowe Uniwersytetu Szczecińskiego: wnus.usz.edu.pl, formerly
wnus.edu.pl; DOI prefix 10.18276), oxjob #2339.

The press runs its own journal system (a Symfony app, not Open Journal Systems). Each article page is a stack of
Bootstrap panels: the byline in an "Autorzy:" table row, the abstract in an "Abstrakt" panel (often only the Polish
version; the English one is in a DC.Description xml:lang="en" tag), and the reference list in a "Bibliografia" /
"Bibliography" / "Bibliographie" panel (the title follows the page's interface language): one table row per entry, its
number ("1.") in the first cell and the entry in <td class="td-wrap">.

The citation_* tags carry the byline and each author's affiliation, and the generic parser reads them and the abstract
right, so this parser returns the generic parser's authors and abstract unchanged and adds only the reference list.
It takes only pages that print one. The pages mark no corresponding author and print no acknowledgments or funding
section.
"""
import re

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

_HOME = re.compile(r"^https?://wnus(?:\.usz)?\.edu\.pl/", re.I)  # the article's own address, in its citation tag
_LIST_TITLE = re.compile(r"^(?:bibliografia|bibliography|bibliographie)$", re.I)
_NUMBER = re.compile(r"^(\d+)\.$")
_MORE = re.compile(r"\b(?:show|load|view|see) (?:more|all)\b|\bpoka[żz] (?:więcej|wszystk)", re.I)


class UniversityOfSzczecinPress(PublisherParser):
    parser_name = "usz_edu_pl"

    def is_publisher_specific_parser(self):
        # one tag in <head>: every PublisherParser is asked on every DOI page (#2239's per-page budget)
        if getattr(self, "_claim", None) is None:
            head = self.soup.head
            tag = head.find("meta", attrs={"name": "citation_abstract_html_url"}) if head is not None else None
            self._claim = bool(tag is not None and _HOME.match(tag.get("content") or ""))
        return self._claim

    def authors_found(self):
        return bool(self.is_publisher_specific_parser() and self._reference_table() is not None
                    and GenericPublisherParser(self.soup).authors_found())

    def parse(self):
        result = dict(GenericPublisherParser(self.soup).parse())
        references, complete = self._references()
        result.update(acknowledgments=None, funding_statement=None, references=references,
                      references_complete=complete)
        return result

    def _reference_table(self):
        """The reference list's panel, or None."""
        if getattr(self, "_panel", False) is False:
            self._panel = None
            if self.is_publisher_specific_parser():
                for title in self.soup.select("div.panel-heading h3.panel-title"):
                    if _LIST_TITLE.match(squash(title.get_text())):
                        panel = title.find_parent("div", class_="panel")
                        if panel is not None and panel.find("td", class_="td-wrap") is not None:
                            self._panel = panel
                            break
        return self._panel

    def _references(self):
        """(references, references_complete). Whole only when every row is a number and an entry, the numbers run
        1..n with no gap, nothing in the panel says there are more, and parse_page's own test of a whole list agrees
        (some lists put an entry's link on a numbered row of its own: "2. Dudka K. (red.). Kodeks ..., LEX 2023," then
        "https://sip-1lex-...")."""
        # imported here: back_matter and parse import this package, which imports every parser module
        from parseland_lib.back_matter import _printed_doi
        from parseland_lib.parse import _entries_look_whole

        panel = self._reference_table()
        if panel is None:
            return None, False
        refs, numbers, odd = [], [], False
        for row in panel.find_all("tr"):
            cells = row.find_all("td", recursive=False)
            entry = cells[-1] if cells and "td-wrap" in (cells[-1].get("class") or []) else None
            raw = squash(entry.get_text(" ")) if entry is not None else ""
            if len(cells) != 2 or not raw:
                odd = True
                if not raw:
                    continue
            found = _NUMBER.match(squash(cells[0].get_text())) if len(cells) == 2 else None
            numbers.append(int(found.group(1)) if found else None)
            refs.append({"position": len(refs) + 1, "raw": raw, "doi": _printed_doi(raw)})
        if not refs:
            return None, False
        whole = (not odd and numbers == list(range(1, len(numbers) + 1))
                 and panel.find(string=_MORE) is None and _entries_look_whole([r["raw"] for r in refs]))
        return refs, whole
