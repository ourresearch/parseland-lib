"""Korean society journals' JATS full-text pages (oxjob #2289, census template korean-jats, "part-rule"): two vendors'
renderings of the journals' JATS XML, each claimed by its own marks, never by a site's domain.

KoreanJatsPreview, the "/archive/view_article?pid=" sites (foodnlife.org, ejce.org, ekosfop.or.kr, e-fas.org, ...): the
citation_author tags name the authors but carry no affiliation, so the generic parser read none. The page prints
div#article-front with div.contrib-group (span.citation_author, each followed by its markers: <sup>1</sup>, a bare
"1," or "*"), then div.author-aff: div.affiliation lines (led by a <sup> number, or by none: then every author's) and
div.corresponding-author notes (led by the marker of the author each is for). Bilingual pages print a Korean and an
English contrib-group and both languages' affiliation lines under the same numbers: the English byline is kept (unless
the other names more authors), and under a number the line in the byline's script; e-mails and phone numbers printed
on an affiliation line are left off. A note that says 제1저자 / 주저자 / first author is not a
corresponding author's. Everything else (abstract, licence, PDF) stays the generic parser's reading.

NurimediaXmlViewer, Nurimedia's JATS viewer (the "/_common/do.php?a=full" sites: kpaj.or.kr, jkros.org, ksae.org,
dcs.or.kr, ...): no citation_* tags at all, so the base read no author. div.NURIMEDIAXML holds a table: a byline per
language (div#enNameColon and div#krNameColon, whose ids the vendor swaps: the Korean names sit in "en"), each followed
by its affiliation rows (a td, led by span.au-label when numbered), and one "Correspondence to :" note (span#cor1) led
by the marker of the author it is for; the byline links that author's marker to #cor1.
"""
import copy
import re
from urllib.parse import unquote

from bs4 import Tag

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser

_MARK = re.compile(r"\d+|\b[a-z]\b|\*+|†+|‡+|§+|¶+|#+")
_LEAD_SYMBOL = re.compile(r"^\s*([*†‡§¶#]+)")
_HANGUL = re.compile(r"[가-힣]")
_LATIN = re.compile(r"[A-Za-z]")
_FIRST_AUTHOR_NOTE = re.compile(r"제\s*1\s*저자|주\s*저자|공동\s*제?\s*1?\s*저자|first\s+author|"
                                r"equal(?:ly)?\s+contribut|contributed\s+equally", re.I)
_CORRESPONDING = re.compile(r"correspond|교신|reprint", re.I)
_DOI = re.compile(r"doi\.org/(10\.\d{4,9}/\S+)", re.I)
_NUMBER = re.compile(r"^\s*\[?(\d{1,4})\]?\s*[.)]?\s*$")  # "1.", "[1].", "1)"
_REF_HEADING = re.compile(r"^(?:references?|참고\s*문헌|bibliography)$", re.I)
_ACK_HEADING = re.compile(r"^(?:acknowledge?ments?|사사|감사의\s*글)$", re.I)
_FUNDING_HEADING = re.compile(r"^(?:funding(?:\s+information)?|financial\s+support)$", re.I)
_CONTACT_TAIL = re.compile(r"\s*[,;]?\s*\b(?:Tel|Phone|Fax|E-?\s?mail)\b\s*[:：.].*$", re.I)  # "..., Tel: +82-51-..."
# "..., India, a@b.com" / "..., Korea, +82-010-9583-1966, a@b.com .": bare e-mails and "+" phone numbers at a line's end
# (and the ", ." an e-mail link leaves behind)
_BARE_CONTACT_TAIL = re.compile(r"(?:(?:[\s,;]*(?:[\w.+-]+@[\w-]+(?:\.[\w-]+)+|\+\d[\d\s()-]{6,}\d))+[\s.,;]*"
                                r"|[\s,;]*[,;]\s*\.\s*)$")


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _marks(text):
    """Markers in a superscript or after a name: '1,2,*' -> {'1', '2', '*'}; '**' -> {'**'}."""
    return set(_MARK.findall(text or ""))


def _is_latin(text):
    return len(_LATIN.findall(text or "")) > len(_HANGUL.findall(text or ""))


def _head_urls(soup):
    """href/src of the <head>'s link and script tags: the claims' cheap first test (#2239: every parser's claim runs
    on every DOI page, so nothing walks the body before the head says the page may be this template's)."""
    head = soup.head
    if head is None:
        return []
    return [t.get("href") or t.get("src") or "" for t in head.find_all(("link", "script"))]


def _contact_free(tag):
    """An affiliation line's text without its e-mail links and the contact details printed after the address."""
    line = copy.copy(tag)
    for mail in line.find_all("a", href=re.compile(r"^mailto:", re.I)):
        mail.extract()
    return _BARE_CONTACT_TAIL.sub("", _CONTACT_TAIL.sub("", _clean(line.get_text()))).strip(" ,;")


def _fullest(bylines):
    """bylines: [(item, names)], one per language. The English byline, unless another names more authors: a
    language's byline can drop one (e-lca.org, 2005: the English byline lists 5 of the Korean byline's 6 names)."""
    most = max(len(names) for _, names in bylines)
    full = [b for b in bylines if len(b[1]) == most]
    return next((b for b in full if _is_latin(" ".join(b[1]))), full[0])


def _tokens(name):
    return set(re.findall(r"\w+", (name or "").casefold()))


def _assign_affiliations(authors, affs, latin_byline):
    """affs: [(marks, text)]. Numbered lines go to the authors carrying their marker (preferring, among several lines
    under one marker, those in the byline's script); unnumbered lines, when no line is numbered, to every author."""
    numbered = any(m for m, _ in affs)
    for au in authors:
        if not numbered:
            hits = [t for _, t in affs]
        else:
            hits = [t for m, t in affs if m & au["marks"]]
            if not hits and len(authors) == 1:
                hits = [t for _, t in affs]
            same = [t for t in hits if _is_latin(t) == latin_byline]
            hits = same or hits
        au["affiliations"] = list(dict.fromkeys(hits))


def _mark_corresponding(authors, mark, text, other_names=()):
    """The authors a corresponding-author note is for: by its marker, else by a name it prints, else the only one."""
    hits = [a for a in authors if mark and mark in a["marks"]]
    if not hits:
        names = list(other_names) or [None] * len(authors)
        hits = [a for a, other in zip(authors, names)
                if (a["name"] and a["name"] in text) or (other and other in text)]
    if not hits and len(authors) == 1:
        hits = authors
    for a in hits:
        a["is_corresponding"] = True


def _reference(position, cell):
    """One reference: its text without the link icons, and the DOI the page links or tags it with."""
    cell = copy.copy(cell)
    doi = None
    for tag in cell.find_all(["a", "img"]):
        target = tag.get("href") or tag.get("doi") or ""
        if doi is None and (m := _DOI.search(target)):
            doi = unquote(m.group(1)).rstrip(".")
        if tag.name == "img" or not _clean(tag.get_text()):
            tag.extract()
    raw = _clean(cell.get_text(" "))
    return {"position": position, "raw": raw, "doi": doi} if raw else None


def _whole(labels, refs):
    """Positive evidence the list is whole: every entry kept and numbered, the numbers running 1..n."""
    numbers = [int(m.group(1)) if (m := _NUMBER.match(label or "")) else None for label in labels]
    return bool(refs) and len(refs) == len(labels) and numbers == list(range(1, len(numbers) + 1))


def _output(authors):
    return [{"name": a["name"], "affiliations": a["affiliations"], "is_corresponding": a["is_corresponding"]}
            for a in authors]


class KoreanJatsPreview(PublisherParser):
    parser_name = "korean_jats_preview"
    prefer_publisher_authors_over_generic = True

    def _front(self):
        """div#article-front of the view_article JATS preview, found once per parser; the <head> test comes first."""
        if "_front_found" not in self.__dict__:
            self._front_found = None
            head = self.soup.head
            if head is not None and any(u.endswith("/include/js/js_common.js") for u in _head_urls(self.soup)) and any(
                    "/archive/view_article" in (m.get("content") or "") for m in head.find_all("meta")):
                front = self.soup.select_one("div.article_wrapper div#article-front")
                if front and front.select_one("div.contrib-group span.citation_author") \
                        and front.select_one("div.author-aff"):
                    self._front_found = front
        return self._front_found

    def is_publisher_specific_parser(self):
        return self._front() is not None

    def authors_found(self):
        return self._front() is not None

    def _byline(self, front):
        groups = [(g, [n for s in g.find_all("span", class_="citation_author") if (n := _clean(s.get_text()))])
                  for g in front.select("div.contrib-group") if g.find("span", class_="citation_author")]
        group, names = _fullest(groups)
        authors = []
        for span in group.find_all("span", class_="citation_author"):
            after = []
            for sib in span.next_siblings:
                if isinstance(sib, Tag):
                    if "citation_author" in (sib.get("class") or []):
                        break
                    if sib.name == "a":  # the ORCID icon
                        continue
                    after.append(sib.get_text())
                else:
                    after.append(str(sib))
            authors.append({"name": _clean(span.get_text()), "marks": _marks(" ".join(after)),
                            "affiliations": [], "is_corresponding": False})
        return [a for a in authors if a["name"]], _is_latin(" ".join(names))

    @staticmethod
    def _lead_mark(div):
        """The <sup> a line or note starts with (named anchors and whitespace before it), else a leading symbol."""
        for child in div.children:
            if isinstance(child, Tag):
                if child.name == "a" and not _clean(child.get_text()):
                    continue
                if child.name == "sup":
                    return _clean(child.get_text()), child
                break
            elif _clean(str(child)):
                break
        m = _LEAD_SYMBOL.match(div.get_text())
        return (m.group(1), None) if m else (None, None)

    def _authors(self):
        front = self._front()
        authors, latin = self._byline(front)
        if not authors:
            return []
        box = front.select_one("div.author-aff")
        affs = []
        for div in box.find_all("div", class_="affiliation", recursive=False):
            mark, sup = self._lead_mark(div)
            line = copy.copy(div)
            if sup is not None:
                line.find("sup").extract()
            text = _contact_free(line)
            if sup is None and mark:
                text = text[len(mark):].strip()
            if text:
                affs.append((_marks(mark) if mark else set(), text))
        _assign_affiliations(authors, affs, latin)
        for note in box.find_all("div", class_="corresponding-author", recursive=False):
            text = _clean(note.get_text(" "))
            if _FIRST_AUTHOR_NOTE.search(text) and not _CORRESPONDING.search(text):
                continue
            mark, _ = self._lead_mark(note)
            _mark_corresponding(authors, mark, text)
        return authors

    def parse(self):
        out = copy.deepcopy(GenericPublisherParser(self.soup).parse())
        authors = self._authors()
        if authors:
            if not any(a["is_corresponding"] for a in authors):
                # no note the byline explains: keep the generic reading's (citation_author_email) by name
                flagged = [_tokens(a.get("name")) for a in out.get("authors") or [] if a.get("is_corresponding")]
                for a in authors:
                    a["is_corresponding"] = any(t and t == _tokens(a["name"]) for t in flagged)
            out["authors"] = _output(authors)
        if not out.get("references"):  # acknowledgments: the shared back_matter reader already reads this template's
            out["references"], out["references_complete"] = self._references()
        return out

    def _references(self):
        """div.section.ref-list > div.ref-list: one div per entry (p.ref-label "1. ", div.ref-content). A second
        list on the page (a competing one) means the first can't be called whole."""
        lists = self.soup.select("div.section.ref-list > div.ref-list")
        if not lists:
            return None, False
        labels, refs = [], []
        for entry in lists[0].find_all("div", recursive=False):
            content = entry.find("div", class_="ref-content")
            if content is None:
                continue
            label = entry.find(class_="ref-label")
            labels.append(_clean(label.get_text()) if label else "")
            if ref := _reference(len(refs) + 1, content):
                refs.append(ref)
        return refs or None, len(lists) == 1 and _whole(labels, refs)


class NurimediaXmlViewer(PublisherParser):
    parser_name = "nurimedia_xml_viewer"
    prefer_publisher_authors_over_generic = True

    def _viewer(self):
        """div.NURIMEDIAXML with a byline, found once per parser; the <head> test (the vendor's /_common/ assets)
        comes first."""
        if "_viewer_found" not in self.__dict__:
            self._viewer_found = None
            if any("/_common/" in u for u in _head_urls(self.soup)):
                box = self.soup.select_one("div.NURIMEDIAXML")
                if box and box.select_one("div#enNameColon span.capture-id, div#krNameColon span.capture-id"):
                    self._viewer_found = box
        return self._viewer_found

    def is_publisher_specific_parser(self):
        return self._viewer() is not None

    def authors_found(self):
        return self._viewer() is not None

    @staticmethod
    def _block_authors(block):
        authors = []
        for cap in block.find_all("span", class_="capture-id", recursive=False):
            gen = cap.find("span", class_="gen")
            name = _clean(gen.get_text()) if gen else ""
            if not name:
                continue
            marks, cor_link = set(), cap.select_one('a[href^="#cor"]') is not None
            for sup in cap.find_all("sup"):
                marks |= _marks(sup.get_text())
            for sib in cap.next_siblings:  # markers printed after the name's span: <sup>1</sup>, span.xref > sup > a
                if isinstance(sib, Tag):
                    if "capture-id" in (sib.get("class") or []):
                        break
                    for sup in [sib] if sib.name == "sup" else sib.find_all("sup"):
                        marks |= _marks(sup.get_text())
                    cor_link = cor_link or sib.select_one('a[href^="#cor"]') is not None
            authors.append({"name": name, "marks": marks, "cor_link": cor_link,
                            "affiliations": [], "is_corresponding": False})
        return authors

    @staticmethod
    def _block_affiliations(block):
        """The affiliation rows after a byline's row, up to the next title, byline, note or full-width row."""
        tr = block.find_parent("tr")
        affs = []
        for row in tr.find_next_siblings("tr") if tr is not None else []:
            td = row.find("td")
            if td is None or td.get("colspan") or row.find(class_="tl-document") or row.find(id="cor1") \
                    or row.find("div", id=re.compile("NameColon$")):
                break
            line = copy.copy(td)
            label = line.find("span", class_="au-label")
            mark = _clean(label.get_text()) if label else ""
            if label is not None:
                label.extract()
            text = _contact_free(line)
            if text:
                affs.append((_marks(mark), text))
        return affs

    def _authors(self):
        box = self._viewer()
        blocks = []
        for block_id in ("enNameColon", "krNameColon"):
            block = box.find("div", id=block_id)
            if block is not None and (authors := self._block_authors(block)):
                blocks.append((block, authors))
        if not blocks:
            return []
        block, _ = _fullest([(b, [x["name"] for x in a]) for b, a in blocks])
        authors = next(a for b, a in blocks if b is block)
        others = [a for b, a in blocks if b is not block]
        other = others[0] if others and len(others[0]) == len(authors) else None
        affs = self._block_affiliations(block)
        if not affs and other is not None:
            affs = self._block_affiliations(next(b for b, a in blocks if a is other))
        _assign_affiliations(authors, affs, _is_latin(" ".join(a["name"] for a in authors)))
        notes = self._corresponding_notes(box)
        linked = [a for a in authors if a["cor_link"]]
        if notes and linked:  # the byline links these authors' markers to the note
            for a in linked:
                a["is_corresponding"] = True
        else:
            for mark, text in notes:
                _mark_corresponding(authors, mark, text, [a["name"] for a in other] if other else ())
        return authors

    @staticmethod
    def _corresponding_notes(box):
        """[(marker, text)]: the "Correspondence to :" note (span#cor1, then the marker's <sup>), and any note led by
        a span.au-label marker whose text says corresponding author ("† Corresponding author: ...")."""
        notes = []
        label = box.find("span", id="cor1")
        if label is not None:
            sup = label.parent.find("sup")
            notes.append((_clean(sup.get_text()) if sup else None, _clean(label.parent.get_text(" "))))
        for au_label in box.find_all("span", class_="au-label"):
            after = au_label.next_sibling
            text = _clean(after.get_text(" ") if isinstance(after, Tag) else str(after or ""))
            if _CORRESPONDING.search(text[:60]):
                notes.append((_clean(au_label.get_text()) or None, text))
        return notes

    def _headed(self, heading):
        """The span.tl-main-part section titles matching heading."""
        return [t for t in self._viewer().find_all("span", class_="tl-main-part")
                if heading.match(_clean(t.get_text()).rstrip(":."))]

    def _section_text(self, heading):
        """A back-matter section's paragraphs (its div.capture-id under the title), joined by newlines."""
        for title in self._headed(heading):
            box = title.find_parent("div", class_="capture-id")
            if box is None:
                continue
            paragraphs = [_clean(p.get_text(" ")) for p in box.find_all("p")]
            text = "\n".join(p for p in paragraphs if p)
            if text:
                return text
        return None

    def _funding_box(self):
        """The front matter's "Funding Information" box: one line per funder (its name, then its grant numbers).
        A box that only lists funders and grant numbers is the record's funder list, not a statement (#2239 round 8)."""
        from parseland_lib.back_matter import funder_list  # here: back_matter imports this package
        box = self._viewer().find("div", id="funding_info")
        lines = [_clean(" ".join(li.get_text(" ") for li in ul.find_all("li"))) for ul in box.find_all("ul")] \
            if box is not None else []
        lines = [line for line in lines if line]
        return None if funder_list(lines, listed=True) else "\n".join(lines) or None

    def _references(self):
        """The table.bm after the "References" title: rows of a numbered td (id "..._B12") and the entry's td."""
        for title in self._headed(_REF_HEADING):
            table = title.find_next("table", class_="bm")
            if table is None:
                continue
            labels, refs = [], []
            for row in table.find_all("tr"):
                cells = row.find_all("td", recursive=False)
                if len(cells) != 2 or not re.search(r"_B\d+$", cells[0].get("id") or ""):
                    continue
                labels.append(_clean(cells[0].get_text()))
                if ref := _reference(len(refs) + 1, cells[1]):
                    refs.append(ref)
            if refs:
                return refs, len(self._headed(_REF_HEADING)) == 1 and _whole(labels, refs)
        return None, False

    def parse(self):
        # The byline and back matter: the abstract, licence and PDF link stay what parse_page's own readers find.
        references, complete = self._references()
        return {"authors": _output(self._authors()), "abstract": None,
                "acknowledgments": self._section_text(_ACK_HEADING),
                "funding_statement": self._section_text(_FUNDING_HEADING) or self._funding_box(),
                "references": references, "references_complete": complete}
