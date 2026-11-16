import re

from bs4 import NavigableString, Tag

from parseland_lib.publisher.parsers.parser import PublisherParser


# Korean society journal sites on the shared "article.php?code=" template (rjcc.or.kr, kosomes.or.kr, ksie.ne.kr,
# joie.or.kr, ... ~70 sites; oxjob #2268, template korean-article-php). The pages carry no citation_* meta tags; the
# byline is div.fulltext-wrap > #engInfo / #korInfo: div.ft-author (names, comma separated, each followed by
# superscript markers, a dagger or star, an empty mailto link, an ORCID link), div.ft-author-aff (one affiliation per
# <br>, led by a <sup> marker when there are several) and div.ft-author-cor / div.ft-author-note (the corresponding
# author note). The reference list is div.ft-reference > ol > li; acknowledgments are the JATS div.ack section.
_MARK = re.compile(r"[0-9]+|[A-Za-z]|\*+|†+|‡+|§+|¶+|#+")
_SYMBOLS = re.compile(r"[*†‡§¶#]+")
_DEGREE = re.compile(r"^(PT|OT|RN|MD|PhD|Ph\.?\s?D\.?|M\.?D\.?|MS|MSc|M\.?S\.?|BS|BSc|MA|MPH|DDS|DMD|DVM|PharmD|"
                     r"RPh|DrPH|MBA|CNS|APRN|NP)$", re.I)
_CORRESPONDING = re.compile(r"correspond|reprint|교신", re.I)
_EMAIL = re.compile(r"\s*[;,]?\s*(?:e-?mail|email)\s*[:：.]?\s*\S+@\S+", re.I)
_EMAIL_IN_PARENS = re.compile(r"\s*[(（][^()（）]*@[^()（）]*[)）]")
_DOI = re.compile(r"doi\.org/(10\.\S+)", re.I)
_MAIL, _OPEN, _CLOSE = "\x03", "\x01", "\x02"


def _marks(text):
    """Markers in a superscript or after a name: '1*' -> {'1', '*'}, '1,2)' -> {'1', '2'}, '***' -> {'***'}."""
    return set(_MARK.findall(text or ""))


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _lines(tag):
    """The tag's children split at <br>, each line a list of nodes."""
    lines, line = [], []
    for child in tag.children:
        if isinstance(child, Tag) and child.name == "br":
            lines.append(line)
            line = []
        else:
            line.append(child)
    lines.append(line)
    return lines


def _line_text(nodes):
    return _clean("".join(n.get_text() if isinstance(n, Tag) else str(n) for n in nodes))


class KoreanArticlePhp(PublisherParser):
    parser_name = "korean_article_php"
    prefer_publisher_authors_over_generic = True

    def _wrap(self):
        wrap = self.soup.select_one("div.fulltext-wrap")
        if wrap and wrap.select_one("div.ft-author") and wrap.select_one("div.ft-author-aff"):
            return wrap
        return None

    def is_publisher_specific_parser(self):
        return self._wrap() is not None

    def _byline_block(self):
        """The English byline block when it names anyone, else the Korean one."""
        wrap = self._wrap()
        if wrap is None:
            return None
        blocks = [wrap.select_one("#engInfo"), wrap.select_one("#korInfo")]
        for block in [b for b in blocks if b is not None] or [wrap]:
            author = block.select_one("div.ft-author")
            if author and _clean(author.get_text()):
                return block
        return None

    def authors_found(self):
        return self._byline_block() is not None

    def _parse_byline(self, author_tag):
        # the first line that names anyone: a second line repeats the byline in Korean (adj.or.kr)
        for nodes in _lines(author_tag):
            flat = ""
            for node in nodes:
                if isinstance(node, NavigableString):
                    flat += str(node)
                elif node.name == "sup":
                    flat += _OPEN + node.get_text().replace(",", " ") + _CLOSE
                elif node.name == "a" and (node.get("href") or "").lower().startswith("mailto:"):
                    flat += _MAIL
                elif node.name == "a" and "orcid.org" in (node.get("href") or ""):
                    continue
                else:
                    flat += node.get_text()
            authors = []
            for piece in flat.split(","):
                marks = set()
                for sup in re.findall(_OPEN + "(.*?)" + _CLOSE, piece):
                    marks |= _marks(sup)
                text = re.sub(_OPEN + ".*?" + _CLOSE, "", piece)
                mail = _MAIL in text
                text = text.replace(_MAIL, "")
                marks |= set(_SYMBOLS.findall(text))
                name = _clean(_SYMBOLS.sub("", text))
                name = re.sub(r"^and\s+", "", name).strip(" .;")
                if not name or _DEGREE.match(name):
                    if authors:  # "Hojin Jeong, PT, PhD<sup>a</sup>": the markers after a degree are the author's
                        authors[-1]["marks"] |= marks
                        authors[-1]["mail"] |= mail
                    continue
                authors.append({"name": name, "marks": marks, "mail": mail})
            if authors:
                return authors
        return []

    @staticmethod
    def _parse_affiliations(aff_tag):
        """[(markers, text)] per affiliation line; a line ending in a comma runs on into the next unmarked line."""
        rows = []
        for nodes in _lines(aff_tag):
            marks, rest = set(), []
            for node in nodes:
                if isinstance(node, Tag) and node.name == "sup" and not _line_text(rest):
                    marks |= _marks(node.get_text())
                else:
                    rest.append(node)
            text = _line_text(rest)
            if not text:
                continue
            if rows and not marks and rows[-1][1].endswith(","):
                rows[-1] = (rows[-1][0], rows[-1][1] + " " + text)
            else:
                rows.append((marks, text))
        out = []
        for marks, text in rows:
            text = _EMAIL_IN_PARENS.sub("", _EMAIL.sub("", text)).strip(" ,;")
            if text:
                out.append((marks, text))
        return out

    def _corresponding_notes(self, block):
        """(markers, lines) of the note lines that say 'corresponding' (or 'reprint', 교신)."""
        wrap = self._wrap()
        notes = block.select("div.ft-author-cor, div.ft-author-note") or wrap.select(
            "div.ft-author-cor, div.ft-author-note")
        marks, lines = set(), []
        for note in notes:
            for nodes in _lines(note):
                text = _line_text(nodes)
                if not _CORRESPONDING.search(text):
                    continue
                lines.append(text)
                for node in nodes:
                    if isinstance(node, Tag) and node.name == "sup":
                        marks |= _marks(node.get_text())
                if lead := re.match(r"\s*([*†‡§¶#]+)", text):
                    marks.add(lead.group(1))
        return marks, lines

    @staticmethod
    def _named_in(name, lines):
        """The note prints the name, in byline order or surname first ('Kim, Hwan')."""
        tokens = re.findall(r"\w+", name.lower().replace("-", ""))
        if len(tokens) < 2:  # one word ("Kim") would match too much
            return False
        for line in lines:
            words = re.findall(r"\w+", line.lower().replace("-", ""))
            for seq in (tokens, tokens[-1:] + tokens[:-1]):
                n = len(seq)
                if any(words[i:i + n] == seq for i in range(len(words) - n + 1)):
                    return True
        return False

    def parse_authors(self):
        block = self._byline_block()
        if block is None:
            return []
        byline = self._parse_byline(block.select_one("div.ft-author"))
        aff_tag = block.select_one("div.ft-author-aff")
        affs = self._parse_affiliations(aff_tag) if aff_tag else []
        marked = [(m, t) for m, t in affs if m]
        unmarked = [t for m, t in affs if not m]
        aff_marks = set().union(*[m for m, _ in marked]) if marked else set()

        cor_marks, cor_lines = self._corresponding_notes(block)
        cor_marks -= aff_marks  # a marker that also links an affiliation can't tell us who corresponds
        every_mail = all(a["mail"] for a in byline)

        authors = []
        for i, a in enumerate(byline):
            if marked:
                mine = [t for m, t in marked if m & a["marks"]] or list(unmarked)
            elif len(unmarked) == len(byline):
                mine = [unmarked[i]]
            else:
                mine = list(unmarked)  # one shared affiliation, or a list the page does not link to anyone
            corresponding = bool(cor_lines) and (bool(a["marks"] & cor_marks) or self._named_in(a["name"], cor_lines)
                                                 or len(byline) == 1)
            if a["mail"] and not every_mail:  # a mail icon on this author only
                corresponding = True
            authors.append({"name": a["name"], "affiliations": mine, "is_corresponding": corresponding})
        return authors

    def parse_references(self):
        box = self.soup.select_one("div.ft-reference")
        if box is None:
            return [], False
        lists = box.find_all("ol")
        items = lists[0].find_all("li", recursive=False) if lists else []
        refs = []
        for i, li in enumerate(items, 1):
            doi = None
            for a in li.find_all("a", href=True):
                if m := _DOI.search(a["href"]):
                    doi = m.group(1).rstrip(".")
                    break
            raw = _clean(li.get_text(" "))
            if raw:
                refs.append({"position": i, "raw": raw, "doi": doi})
        start = lists[0].get("start") if lists else None
        complete = bool(refs) and len(lists) == 1 and len(refs) == len(items) and (
            start is None or str(start).strip() in ("", "1"))
        return refs, complete

    def parse_acknowledgments(self):
        texts = []
        for ack in self.soup.select("div.fulltext-wrap div.ack, div#article-body div.ack"):
            for p in ack.find_all("p"):
                if text := _clean(p.get_text(" ")):
                    texts.append(text)
            if texts:
                break
        return "\n".join(texts) or None

    def parse(self):
        references, complete = self.parse_references()
        return {
            "authors": self.parse_authors(),
            # the abstract is left to parse_page's readers (div.ft-abstract under its "Abstract" heading), as before
            "abstract": None,
            "acknowledgments": self.parse_acknowledgments(),
            "references": references or None,
            "references_complete": complete,
        }
