"""RSIS International (rsisinternational.org: IJRISS, IJRSI, IJRIAS and the society's other journals, DOI prefixes
10.47772, 10.51244, 10.51584) article pages (oxjob #2338).

Two templates, both claimed by the og:url tag in <head> naming rsisinternational.org/journals/:

- The WordPress theme (".../journals/<journal>/articles/<slug>/", most papers to 2025). The theme's info list
  (ul.sj-articles_info) names the authors, one <li> with an icon-user each; no citation_* meta tags. The paper's full
  text follows in div.sj-article-detail_content, a Word document pasted into WordPress: its first paragraphs, before
  the "DOI:" and "Received:" lines, print the title, the byline (with <sup> numbers when the authors have different
  affiliations, and a "*" that a "*Corresponding author" line explains when the paper names one) and the
  affiliations, one per line or paragraph, each opening with its <sup> number(s) when the byline carries numbers.
  The reference list is one <ol> under a "REFERENCES" heading.
- The PHP template (".../journals/<journal>/article.php?id=N", 2026): citation_author tags, and an "Authors" section
  with one card per author (the name, then one affiliation line); a "References" section prints one <p> per entry,
  "N. text", followed by Google Scholar and Crossref search links. No corresponding-author marks.

The abstract is the generic reader's own (both templates print it under an "Abstract" heading it already reads).
Acknowledgments are left to parse_page's headed back-matter reader, which already reads the WordPress pages'
"ACKNOWLEDGEMENTS" heading; a funding statement is printed under its own label on too few pages to read (2 of 76).
"""
import re

from bs4 import Comment, NavigableString, Tag

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

CLAIM = "rsisinternational.org/journals/"
# where the front matter ends: the DOI line, the history line, the abstract
FRONT_END = re.compile(r"^\W*(?:doi\b|received\b|abstract\b|keywords?\b)", re.I)
# "*Corresponding author", "* Correspondent Author", "*Corresponding Author:": the line that explains the byline's star
CORR_NOTE = re.compile(r"^\W*\*\s*correspond(?:ing|ent)\s+authors?\b", re.I)
EMAIL_LINE = re.compile(r"@|^\W*e-?mails?\b", re.I)
# a number typed (not superscripted) before an affiliation: "1 Faculty of ...", "2,3 Nkumba University"
PLAIN_MARK = re.compile(r"^\s*(\d{1,2}(?:\s*[,&]\s*\d{1,2})*)\s*[.)]?\s*(?=[^\W\d_]|\()")
MARK_IDS = re.compile(r"\d{1,2}|(?<![^\W\d_])[a-z](?![^\W\d_])")
INITIALS_END = re.compile(r"(?<![^\W\d_])[A-Z]{1,3}\.$")  # a name that ends in an initial: "Alejandro, David T."
HONORIFIC = re.compile(r"^(?:dr|prof|engr|mr|mrs|ms|miss|atty|rev)\.?\s+", re.I)
DEGREE = re.compile(r"[,\s]*\(?\b(?:ph\.?\s?d|ed\.?\s?d|d\.?\s?phil|m\.?\s?d|m\.?\s?sc|mba|ll\.?\s?m|dba|rn|cpa)\.?\)?$",
                    re.I)
# a degree programme printed where the affiliation goes ("Bachelor of Science in Psychology (BSPsy)"): not an
# employer or institute, unless the line names one too ("Master of Arts in ..., Sultan Kudarat State University")
PROGRAMME = re.compile(r"^(?:bachelor|master|doctor)(?:'?s)?\s+(?:of|in)\b", re.I)
ORG_WORD = re.compile(r"universi|college|institut|school|facult|department|dept\b|hospital|cent(?:er|re)|ministry|"
                      r"academy|polytechnic|laborator|company|council|agency|foundation|office|government", re.I)
REF_HEADING = re.compile(r"^(?:references?|refrences?|bibliograph\w*|literaturecited|workscited|listofreferences)$")
LIST_NUMBER = re.compile(r"^\s*(\d{1,4})\.\s+")
SEARCH_LINK = re.compile(r"^\s*\[(?:google scholar|crossref|pubmed)\]\s*$", re.I)
DOI_LINK = re.compile(r"doi\.org/10\.")
HEADINGS = ("h1", "h2", "h3", "h4", "h5", "h6")
MARK = "\x00"  # stands for one byline mark (a <sup> run or a typed "*") in the byline's flat text


def _clean_name(raw):
    """A name from the theme's info list: no list number, honorific or degree, "Family, Given" turned round."""
    name = squash(raw).lstrip("0123456789* ").strip(" ,;")
    while (cut := HONORIFIC.sub("", name)) != name:
        name = cut
    while (cut := DEGREE.sub("", name).rstrip(" ,;")) != name:
        name = cut
    if name.endswith(".") and not INITIALS_END.search(name):
        name = name[:-1].rstrip(" ,;")  # "Donath Asiimire." (not "David T." or "Jaskie Raselle DC.")
    if name.count(",") == 1:
        family, given = (part.strip() for part in name.split(","))
        if family and given:
            name = f"{given} {family}"
    return name


def _in_sup(node, top):
    parent = node.parent
    while parent is not None and parent is not top:
        if parent.name == "sup":
            return True
        parent = parent.parent
    return False


def _lines(el):
    """`el`'s lines, split at <br>: each a list of (is_sup, text) runs."""
    lines, current = [], []
    for node in el.descendants:
        if isinstance(node, Tag):
            if node.name == "br":
                lines.append(current)
                current = []
        elif isinstance(node, NavigableString) and not isinstance(node, Comment) and str(node):
            current.append((_in_sup(node, el), str(node)))
    lines.append(current)
    return [line for line in lines if squash("".join(text for _, text in line))]


def _line_text(line):
    return squash("".join(text for _, text in line))


class _Affiliation:
    def __init__(self, ids, text):
        self.ids, self.text = ids, text


class RSISInternational(PublisherParser):
    parser_name = "rsis_international"
    # the byline names every author; the generic reader's meta-tag authors carry no affiliations
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        # Every parser's claim runs on every DOI page (#2239: under 0.5 ms a page it does not claim): one meta tag
        # among <head>'s direct children, reached through direct children only (never a whole-tree search).
        if not hasattr(self, "_claim"):
            html = self.soup.find("html", recursive=False)
            head = html.find("head", recursive=False) if html else None
            tag = head.find("meta", attrs={"property": "og:url"}, recursive=False) if head else None
            self._claim = bool(tag) and CLAIM in (tag.get("content") or "")
        return self._claim

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._wordpress_names() or self._php_cards())

    # ---- the two templates' author blocks ----

    def _wordpress_names(self):
        if not hasattr(self, "_wp_names"):
            info = self.soup.select_one("div.sj-article-detail ul.sj-articles_info")
            names = [squash(li.get_text(" ")) for li in info.find_all("li") if li.select_one("i.icon-user")] if info else []
            self._wp_names = [name for name in names if name]
        return self._wp_names

    def _php_cards(self):
        if not hasattr(self, "_cards"):
            section = self.soup.find("section", attrs={"aria-labelledby": "authors-heading"})
            self._cards = section.select("div.grid > div") if section else []
        return self._cards

    def parse(self):
        if self._wordpress_names():
            authors = self._wordpress_authors()
            references, complete = self._wordpress_references()
        else:
            authors = self._php_authors()
            references, complete = self._php_references()
        if complete:
            # imported here: parse imports the parsers package. A URL or a sentence's end in an item of its own
            # (both templates print some lists so) is a list parse_page can't call whole either.
            from parseland_lib.parse import _entries_look_whole
            complete = _entries_look_whole([ref["raw"] for ref in references])
        generic = GenericPublisherParser(self.soup)
        abstract = (generic.parse_abstract_meta_tags(include_seo_tags=False)
                    or generic.parse_structured_abstract_section() or generic.parse_printed_seo_description())
        return {"authors": authors, "abstract": abstract, "acknowledgments": None, "funding_statement": None,
                "references": references, "references_complete": complete}

    # ---- PHP template ----

    def _php_authors(self):
        authors = []
        for card in self._php_cards():
            paragraphs = card.find_all("p", recursive=False)
            if not paragraphs or not (name := squash(paragraphs[0].get_text(" "))):
                continue
            affiliations = [text for p in paragraphs[1:] if (text := squash(p.get_text(" ")))]
            authors.append({"name": name, "affiliations": affiliations, "is_corresponding": False})
        return authors

    def _php_references(self):
        # imported here: back_matter imports the parsers package, which imports this module
        from parseland_lib.back_matter import _clean_doi, _pick_doi, _printed_doi
        section = self.soup.find("section", attrs={"aria-labelledby": "references-heading"})
        box = section.find("div") if section else None
        if box is None:
            return None, False
        refs, numbers, other = [], [], False
        for child in box.children:
            if not isinstance(child, Tag) or child.name != "p":  # anything else printed in the box: not whole
                if not isinstance(child, Comment):
                    other = other or bool(squash(child.get_text() if isinstance(child, Tag) else str(child)))
                continue
            parts = [str(s) for s in child.descendants if isinstance(s, NavigableString)
                     and not isinstance(s, Comment) and not (s.parent.name == "a" and SEARCH_LINK.match(str(s)))]
            text = squash("".join(parts))
            if not text:
                continue
            m = LIST_NUMBER.match(text)
            numbers.append(int(m.group(1)) if m else None)
            raw = text[m.end():] if m else text
            link = child.find("a", href=DOI_LINK)
            doi = _pick_doi(_clean_doi(link["href"]) if link is not None else None, _printed_doi(raw))
            refs.append({"position": len(refs) + 1, "raw": raw, "doi": doi})
        if not refs:
            return None, False
        return refs, numbers == list(range(1, len(refs) + 1)) and not other

    # ---- WordPress theme ----

    def _content(self):
        return self.soup.select_one("div.sj-article-detail div.sj-article-detail_content")

    def _front_lines(self, content):
        """The lines of the paragraphs that print the byline and the affiliations: after the title, before the DOI
        / history line or the first heading."""
        title = self.soup.select_one("div.sj-article-detail_title h1")
        title_key = re.sub(r"\W+", "", title.get_text()).lower() if title else ""
        lines, in_title = [], True
        for el in content.children:
            if not isinstance(el, Tag):
                continue
            text = squash(el.get_text(" "))
            if el.name in HEADINGS or FRONT_END.match(text):
                break
            if not text:
                continue
            key = re.sub(r"\W+", "", text).lower()
            if in_title and title_key and key and key in title_key:
                continue  # the title, in one or more paragraphs
            in_title = False
            lines.extend(_lines(el))
        return lines

    def _wordpress_authors(self):
        names = self._wordpress_names()
        content = self._content()
        lines = self._front_lines(content) if content is not None else []
        patterns = [self._name_pattern(name) for name in names]
        # the byline: the first lines that print an author's name. A line or two before it may repeat the title in
        # another language; with no byline found, where the affiliations start can't be told, and none is read.
        has_name = [any(p and p.search(_line_text(line)) for p in patterns) for line in lines]
        first = next((i for i, found in enumerate(has_name[:3]) if found), None)
        if first is None:
            return [{"name": _clean_name(raw), "affiliations": [], "is_corresponding": False} for raw in names]
        byline, end = [], first
        while end < len(lines) and has_name[end]:
            byline.extend(lines[end])
            end += 1
        lines = lines[end:]
        flat, marks = self._flatten(byline)
        spans = self._locate(flat, names, patterns)
        ids, starred = self._author_marks(flat, marks, spans)
        affiliations, explained = self._affiliations(lines, numbered=any(ids))
        authors = []
        for i, raw in enumerate(names):
            if not affiliations:
                mine = []
            elif any(a.ids for a in affiliations):
                mine = [a.text for a in affiliations if a.ids & ids[i]]
            else:
                mine = [a.text for a in affiliations]  # no numbers: the lines are every author's
            authors.append({"name": _clean_name(raw), "affiliations": mine,
                            "is_corresponding": bool(explained and starred[i])})
        return authors

    @staticmethod
    def _name_pattern(name):
        words = re.findall(r"[^\W_]+", name)
        if not words:
            return None
        # bounded by a non-letter: a <sup> number may touch the name in the line's text ("Chombo1*")
        return re.compile(r"(?<![^\W\d_])" + r"[^\w\x00]*".join(map(re.escape, words)) + r"(?![^\W\d_])", re.I)

    @staticmethod
    def _flatten(byline):
        """The byline's text with each mark (a run of <sup> text, or a typed "*") replaced by MARK, and the marks'
        texts in order."""
        flat, marks, in_mark = [], [], False
        for is_sup, text in byline:
            if is_sup:
                if in_mark:
                    marks[-1] += text
                else:
                    flat.append(MARK)
                    marks.append(text)
                    in_mark = True
                continue
            if not text.strip() and in_mark:
                continue  # a space between two <sup> runs
            in_mark = False
            for i, piece in enumerate(text.split("*")):
                if i:
                    flat.append(MARK)
                    marks.append("*")
                flat.append(piece)
        return "".join(flat), marks

    @staticmethod
    def _locate(flat, names, patterns):
        """Each author's (start, end) in the byline, in order, or None where the name isn't found."""
        spans, at = [], 0
        for name, pattern in zip(names, patterns):
            m = pattern.search(flat, at) if pattern else None
            if m is None:
                longest = max(re.findall(r"[^\W_]{3,}", name), key=len, default=None)
                m = re.search(r"(?<![^\W\d_])" + re.escape(longest) + r"(?![^\W\d_])", flat[at:], re.I) if longest else None
                m = (at + m.start(), at + m.end()) if m else None
            else:
                m = m.span()
            spans.append(m)
            if m:
                at = m[1]
        return spans

    @staticmethod
    def _author_marks(flat, marks, spans):
        """Per author, the affiliation ids and whether a star marks them. Numbers follow the name ("Name¹ ²") or,
        on some bylines, stand before it ("¹Name, ¹Name, ²Name"); a star sits next to its name either way."""
        n = len(spans)
        ids, starred = [set() for _ in range(n)], [False] * n
        found = [(i, s) for i, s in enumerate(spans) if s]
        if not found or not marks:
            return ids, starred
        positions = [i for i, c in enumerate(flat) if c == MARK]
        numeric = [p for p, text in zip(positions, marks) if MARK_IDS.search(text)]
        leading = bool(numeric) and numeric[0] < found[0][1][0]
        for p, text in zip(positions, marks):
            before = [(i, s) for i, s in found if s[1] <= p]
            after = [(i, s) for i, s in found if s[0] >= p]
            if MARK_IDS.search(text):
                owner = (after[0][0] if after else None) if leading else (before[-1][0] if before else None)
                if owner is not None:
                    ids[owner] |= set(MARK_IDS.findall(text))
                    starred[owner] = starred[owner] or "*" in text
                continue
            # a star alone: the name it touches (only spaces between), else the side the numbers are printed on
            if before and not flat[before[-1][1][1]:p].strip("  "):
                owner = before[-1][0]
            elif after and not flat[p + 1:after[0][1][0]].strip("  "):
                owner = after[0][0]
            elif leading:
                owner = after[0][0] if after else None
            else:
                owner = before[-1][0] if before else (after[0][0] if after else None)
            if owner is not None:
                starred[owner] = True
        return ids, starred

    @staticmethod
    def _affiliations(lines, numbered):
        """The affiliation lines after the byline, each with the ids it opens with (a <sup> run, or a typed number
        when the byline carries numbers), and whether a line explains the star as the corresponding author's.
        A line with no number after a numbered one continues it ("..., P.O. Box 237," then "Entebbe, Uganda")."""
        affiliations, explained = [], False
        for line in lines:
            text = _line_text(line)
            if CORR_NOTE.match(text):
                explained = True
                continue
            if EMAIL_LINE.search(text):
                continue
            mark, rest = "", list(line)
            while rest and (rest[0][0] or not rest[0][1].strip()):
                mark += rest.pop(0)[1]  # the <sup> runs (and spaces) the line opens with
            body = squash("".join(text for _, text in rest))
            ids = set(MARK_IDS.findall(mark))
            if not ids and numbered and (m := PLAIN_MARK.match(body)):
                ids, body = set(MARK_IDS.findall(m.group(1))), body[m.end():]
            body = body.lstrip(" ,;").rstrip(" ;")  # a trailing comma stays while the next line may continue it
            if "*" in mark and not ids and CORR_NOTE.match("*" + body):
                explained = True
                continue
            if not body.rstrip(",") or (PROGRAMME.match(body) and not ORG_WORD.search(body)):
                continue
            if not ids and affiliations and affiliations[-1].ids:
                affiliations[-1].text = f"{affiliations[-1].text} {body}"
                continue
            affiliations.append(_Affiliation(ids, body))
        for affiliation in affiliations:
            affiliation.text = affiliation.text.rstrip(" ,;")
        return affiliations, explained

    def _wordpress_references(self):
        """(references, complete) from the <ol> under the "REFERENCES" heading. Complete when the list (or lists,
        numbered on) is all the section prints: nothing but empty paragraphs beside it before the next heading."""
        from parseland_lib.back_matter import _clean_doi, _pick_doi, _printed_doi
        content = self._content()
        if content is None:
            return None, False
        children = [el for el in content.children if isinstance(el, Tag)]
        heads = [i for i, el in enumerate(children) if el.name in HEADINGS
                 and REF_HEADING.match(re.sub(r"[^a-z]", "", el.get_text().lower()))]
        if not heads:
            return None, False
        lists, stray = [], False
        for el in children[heads[-1] + 1:]:
            if el.name in HEADINGS:
                break
            if el.name == "ol":
                lists.append(el)
            elif squash(el.get_text()):
                stray = True
                break
        refs, whole, expected = [], bool(lists) and not stray, 1
        for ol in lists:
            start = ol.get("start", "1")
            if not start.isdecimal() or int(start) != expected:
                whole = False
            for li in ol.find_all("li", recursive=False):
                expected += 1
                raw = squash(li.get_text())
                if not raw:
                    continue
                link = li.find("a", href=DOI_LINK)
                doi = _pick_doi(_clean_doi(link["href"]) if link is not None else None, _printed_doi(raw))
                refs.append({"position": len(refs) + 1, "raw": raw, "doi": doi})
        if not refs:
            return None, False
        return refs, whole and len(refs) == expected - 1

    test_cases = []
