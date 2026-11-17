"""Yektaweb (oxjob #2289): the journal platform of about 70 Iranian journal sites (journal.muq.ac.ir, hrjbaq.ir,
jogcr.com, sanru.ac.ir's journals, ...), one template on all of them, marked by <meta name="GENERATOR"
content="Yektaweb 4547">. Two layouts of the article page: the older prints it in table rows (td.abstract,
td.abstractsmall, td.abstractmed), the newer in div.yw_text_small blocks; both print the same things the same way.

What the generic parser misses on these pages, and this parser reads:
- the abstract, printed under a bold "Abstract:" row (Yektaweb's description tags are cut short, so no meta tag holds
  it). Some journals print key words, funding, conflicts and "How to cite" in the same box: the abstract stops there;
- the reference list (div.text_med entries in .articles_ref, numbered "1." to "n.");
- the corresponding author where the byline's <sup>*</sup> is explained: the page prints the e-mail address on that
  author's affiliation line (and on no other), or the line says "Corresponding Author".
Authors and affiliations stay what the generic parser reads from the citation_author tags, and so does any
corresponding mark it finds; a bare star with nothing on the page to explain it adds no mark here.
"""
import copy
import re

from bs4 import Tag

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import EMAIL_RE, same_person, squash

_GENERATOR = re.compile(r"^generator$", re.I)
_AUTHOR_LINK = re.compile(r"search\.php\?[^#]*?[?&](?:amp;)?(?:author|auth)=")
_NUMBERED_LINE = re.compile(r"^(\d{1,2})\s*[-–.)]\s*(.*)$", re.S)
_CORRESPONDING = re.compile(r"correspond", re.I)
_ABSTRACT_HEADING = re.compile(r"^\s*(?:abstract|چکیده)\s*:?\s*$", re.I)
# what some journals print after the abstract in its own box (J Rafsanjan Univ Med Sci: "Key words:", "Funding:",
# "Conflict of interest:", "Ethical approval:", "How to cite this article:")
_AFTER_ABSTRACT = re.compile(r"^(?:key ?words?|funding|financial support|conflicts? of interests?|ethical (?:approval|"
                             r"considerations?)|ethics|how to cite|citation|acknowledge?ments?|authors?'? contributions?|"
                             r"paper type)\s*:", re.I)
# a heading the journal typed into the box itself: "Abstract", "ABSTRACT.", "Extended Abstract", "Abstract ITP is ..."
_OWN_HEADING = re.compile(r"^(?i:(?:extended\s+)?(?:abstract|summary))(?:[\s.:-]*\n|\s*[.:-]\s*|\s+(?=[A-Z]))")
_BLOCKS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr"}
_REF_NUMBER = re.compile(r"^(\d{1,4})\s*[.)-]\s*")
_MORE = re.compile(r"show (?:all|more)|load (?:all|more)|see all", re.I)
_LINE_BREAK = "\u2028"  # a line separator no page text holds
# the link buttons the platform adds after a reference (counted on the sample's 37 lists)
_BUTTON = re.compile(r"^(?:pmid|pmcid|doi|pubmed|google scholar|view at \w+|link|article|url|crossref)?$", re.I)


class Yektaweb(PublisherParser):
    parser_name = "yektaweb"

    def __init__(self, soup):
        super().__init__(soup)
        self._claim = None
        self._result = None

    def is_publisher_specific_parser(self):
        # Every DOI page is offered to every parser: the generator tag is looked for in the small <head> only, so a
        # page of another template is turned down before anything walks its body (#2239's per-page CPU rule).
        if self._claim is None:
            head = self.soup.head
            tag = head.find("meta", attrs={"name": _GENERATOR}) if head is not None else None
            self._claim = bool(tag) and (tag.get("content") or "").strip().lower().startswith("yektaweb")
        return self._claim

    def authors_found(self):
        if not self.is_publisher_specific_parser():
            return False
        parsed = self.parse()
        return bool(parsed["authors"] or parsed["abstract"])

    def parse(self):
        if self._result is None:
            generic = GenericPublisherParser(self.soup).parse()
            authors = copy.deepcopy(generic.get("authors") or [])
            if authors and not any(a.get("is_corresponding") for a in authors):
                self._mark_explained_corresponding(authors)
            result = {"authors": authors, "abstract": self._abstract() or generic.get("abstract")}
            refs, complete = self._references()
            if refs:
                result.update(references=refs, references_complete=complete)
            self._result = result
        return self._result

    # ---- byline

    def _byline(self):
        """([(name, [affiliation numbers], starred)], [(number or None, line text)]) from the visible byline."""
        link = self.soup.find("a", href=_AUTHOR_LINK)
        cell = link.find_parent(["td", "div"]) if link else None
        if cell is None:
            return [], []
        names = []
        for node in cell.descendants:
            if not isinstance(node, Tag):
                continue
            if node.name == "a" and _AUTHOR_LINK.search(node.get("href") or ""):
                names.append([squash(node.get_text()), [], False])
            elif node.name == "sup" and names:
                text = squash(node.get_text())
                if text == "*":
                    names[-1][2] = True
                else:
                    names[-1][1] += [n.strip() for n in text.split(",") if n.strip().isdecimal()]
        return [tuple(n) for n in names], self._affiliation_lines(cell)

    @staticmethod
    def _affiliation_lines(cell):
        """The numbered lines ("1- Department of ..., e-mail") of the block right after the byline."""
        if cell.name == "td":
            row = cell.find_parent("tr")
            row = row.find_next_sibling("tr") if row is not None else None
            block = row.find("td", class_="abstractsmall") if row is not None else None
        else:
            block = cell.find_next_sibling("div")
            block = block if block is not None and "abstractsmall" in (block.get("class") or []) else None
        if block is None:
            return []
        block = copy.copy(block)  # never edit the page: other parsers read this soup
        for br in block.find_all("br"):
            br.replace_with(_LINE_BREAK)
        lines = []
        for line in block.get_text().split(_LINE_BREAK):
            line = squash(line)
            if line:
                m = _NUMBERED_LINE.match(line)
                lines.append((m.group(1), m.group(2)) if m else (None, line))
        return lines

    def _mark_explained_corresponding(self, authors):
        """Mark the byline's starred author when the page explains the star: the one e-mail address of the affiliation
        block sits on that author's own line, or the line says "Corresponding Author". A line that names a
        corresponding author marks the one author it belongs to even without a star."""
        byline, lines = self._byline()
        if not byline or not lines:
            return
        by_number = {number: text for number, text in lines if number}
        unnumbered = [text for number, text in lines if number is None]
        n_emails = sum(len(EMAIL_RE.findall(text)) for _, text in lines)

        def own_lines(numbers):
            if numbers:
                return [by_number[n] for n in numbers if n in by_number]
            return unnumbered if len(lines) == 1 else []

        marked = []
        starred = [entry for entry in byline if entry[2]]
        for name, numbers, star in byline:
            mine = own_lines(numbers)
            shared = any(n in other[1] for other in byline if other[0] != name for n in numbers)
            noted = not shared and numbers and any(_CORRESPONDING.search(t) for t in mine)
            emailed = star and len(starred) == 1 and n_emails == 1 and any(EMAIL_RE.search(t) for t in mine)
            if noted or emailed:
                marked.append(name)
        if not marked:
            return
        byline_names = [entry[0] for entry in byline]
        for name in marked:
            matches = [a for a in authors if same_person(a["name"], name)]
            if not matches and len(byline) == len(authors):  # names in another script than the citation tags'
                matches = [authors[byline_names.index(name)]]
            if len(matches) == 1:
                matches[0]["is_corresponding"] = True
        if any(a.get("is_corresponding") for a in authors):
            for a in authors:
                if a.get("is_corresponding") is None:
                    a["is_corresponding"] = False

    # ---- abstract

    def _abstract_block(self):
        for strong in self.soup.find_all("strong"):
            if not _ABSTRACT_HEADING.match(strong.get_text()):
                continue
            heading = strong.find_parent(["td", "div"])
            if heading is None:
                return None
            if heading.name == "td":
                row = heading.find_parent("tr")
                row = row.find_next_sibling("tr") if row is not None else None
                return row.find("td") if row is not None else None
            return heading.find_next_sibling("div")
        return None

    def _abstract(self):
        block = self._abstract_block()
        if block is None:
            return None
        block = copy.copy(block)
        for link in block.find_all("a"):
            if squash(link.get_text()) == (link.get("href") or "").strip():
                link.decompose()  # a file link printed as its own address ("./files/site1/files/64/12.pdf")
        for br in block.find_all("br"):
            br.replace_with(_LINE_BREAK)
        for tag in block.find_all(_BLOCKS):
            tag.append(_LINE_BREAK)
        kept = []
        for line in block.get_text().split(_LINE_BREAK):
            line = squash(line)
            if not line:
                continue
            if _AFTER_ABSTRACT.match(line):
                break
            kept.append(line)
        text = _OWN_HEADING.sub("", "\n".join(kept), count=1)
        return text if len(text) > 50 else None

    # ---- references

    def _references(self):
        """(references, references_complete): the entries of .articles_ref. The platform numbers each line it prints
        ("1." to "n."), so its numbers run 1..n even when a reference is broken over two lines (a URL on a line of its
        own): the list is whole only when those run 1..n with no gap, the numbers the author typed ("[12]") run 1..n
        too, and no line reads as the rest of the line before it (parse_page's own check)."""
        # imported here: back_matter and parse import this package, so a module-level import is circular
        from parseland_lib.back_matter import _entry_doi, _without_list_numbers
        from parseland_lib.parse import _entries_look_whole
        box = self.soup.find(class_="articles_ref")
        if box is None:
            return [], False
        entries, texts, numbers = [], [], []
        for entry in box.find_all("div", class_="text_med"):
            raw = self._entry_text(entry)
            if not raw:
                continue
            m = _REF_NUMBER.match(raw)
            numbers.append(int(m.group(1)) if m else None)
            entries.append(entry)
            texts.append(raw[m.end():] if m else raw)
        texts, typed_whole = _without_list_numbers(texts)
        refs = [{"position": i + 1, "raw": raw, "doi": _entry_doi(entry, raw)}
                for i, (entry, raw) in enumerate(zip(entries, texts))]
        outside = copy.copy(box)  # the list's own text outside its entries: a "show more" or pagination link
        for entry in outside.find_all("div", class_="text_med"):
            entry.decompose()
        complete = bool(refs) and numbers == list(range(1, len(refs) + 1)) and typed_whole \
            and not _MORE.search(outside.get_text(" ")) and _entries_look_whole(texts)
        return refs, complete

    @staticmethod
    def _entry_text(entry):
        """The entry as printed, without the platform's link buttons ("[PMID]", "[Google Scholar]", "[DOI]", and the
        linked copy "[<a>DOI:10.x/y</a>]" of a DOI the entry prints); a link whose text the entry doesn't print
        otherwise stays."""
        entry = copy.copy(entry)
        for link in entry.find_all("a"):
            text = squash(link.get_text())
            rest = squash(entry.get_text(" ")).replace(text, "", 1) if text else ""
            if _BUTTON.match(text) or text in rest:
                link.decompose()
        text = squash(entry.get_text(" "))
        text = re.sub(r"\[\s*\]", "", text)
        text = re.sub(r"\[\s+", "[", re.sub(r"\s+\]", "]", text))
        return squash(text)
