import re

from bs4 import Tag

from parseland_lib.publisher.parsers.parser import PublisherParser

# A note line that names a corresponding author: "Corresponding author:", "Correspondence:", French "correspondance".
_CORRESPONDING = re.compile(r"correspond", re.I)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# A note mark printed as text rather than in a <sup>: "* Corresponding author: ...".
_TEXT_MARK = re.compile(r"^\s*([*\u2020\u2021\u00a7\u00b6#]+)\s*")


def _mark_key(text):
    return text.strip().strip("()").strip()


def _name_key(name):
    return re.sub(r"\s+", " ", name).strip(" ,;*").casefold()


def _edp_publisher(soup):
    """EDP Sciences' citation_publisher tag ("EDP Sciences", "Éditions EDK, Groupe EDP Sciences"), looked for among
    <head>'s direct children only: every parser's claim runs on every DOI page (#2239: under 0.5 ms a page it does
    not claim), so nothing walks the whole tree. On all 68 sampled EDP pages that carry it, the tag sits there."""
    html = soup.find("html", recursive=False)
    head = (html or soup).find("head", recursive=False)
    if head is None:
        return False
    return any(meta.get("name") == "citation_publisher" and "EDP Sciences" in (meta.get("content") or "")
               for meta in head.find_all("meta", recursive=False))


class EDPSciences(PublisherParser):
    parser_name = "edp_sciences"

    def __init__(self, soup):
        super().__init__(soup)
        self._claimed = None

    def is_publisher_specific_parser(self):
        if self._claimed is None:
            self._claimed = _edp_publisher(self.soup)
        return self._claimed

    def authors_found(self):
        # Pages this parser does not claim answer False before any whole-page search (oxjob #2330): the generic
        # parser runs first on them anyway.
        return bool(self.is_publisher_specific_parser()
                    and self.soup.find("meta", {"name": "citation_author"})
                    and self.soup.select('.article-authors'))

    def parse_abstract(self):
        if abs_heading := self.soup.select_one("a[name='abs']"):
            return abs_heading.parent.find_next_sibling('p').text

    def _byline(self):
        """[(name, {marks})] in byline order: each span.author and the superscripts after it, up to the next author
        ("Name<sup>1</sup><sup>,3</sup><sup>*</sup>" -> {"1", "3", "*"})."""
        byline = []
        for span in self.soup.select(".article-authors span.author"):
            marks = set()
            sib = span.next_sibling
            while sib is not None and not (isinstance(sib, Tag) and sib.name == "span"
                                           and "author" in (sib.get("class") or [])):
                if isinstance(sib, Tag) and sib.name == "sup":
                    marks.update(k for m in re.split(r"[,\s]+", sib.get_text()) if (k := _mark_key(m)))
                sib = sib.next_sibling
            byline.append((span.get_text(" ", strip=True), marks))
        return byline

    def _notes(self):
        """[(mark or None, text)]: one per line of p.corresp; the mark is the line's leading <sup> (or symbol)."""
        notes = []
        for p in self.soup.select("p.corresp"):
            mark, text = None, ""
            for child in list(p.children) + [None]:
                if child is None or (isinstance(child, Tag) and child.name == "br"):
                    if mark is None and (m := _TEXT_MARK.match(text)):
                        mark, text = m.group(1), text[m.end():]
                    if mark or text.strip():
                        notes.append((mark, re.sub(r"\s+", " ", text).strip()))
                    mark, text = None, ""
                elif isinstance(child, Tag) and child.name == "sup" and mark is None and not text.strip():
                    mark = _mark_key(child.get_text())
                else:
                    text += child.get_text(" ") if isinstance(child, Tag) else str(child)
        return notes

    def _corresponding_names(self):
        """Byline names label-v1 counts as corresponding: a mark the note calls a corresponding author, a mark tied to
        that author's e-mail (unless every author has one), or a name the "Corresponding author:" line spells out.
        A mark that also numbers an affiliation in p.aff is ambiguous and not read; a bare mark with no note is not
        a mark."""
        byline = self._byline()
        notes = self._notes() if byline else []
        if not notes:
            return set()
        aff_marks = {_mark_key(sup.get_text()) for sup in self.soup.select("p.aff sup")}
        names, emailed = set(), set()
        for mark, text in notes:
            if mark:
                if mark in aff_marks:
                    continue
                who = {name for name, marks in byline if mark in marks}
                if _CORRESPONDING.search(text):
                    names |= who
                elif _EMAIL.search(text):
                    emailed |= who
            elif _CORRESPONDING.search(text):
                names |= {name for name, _ in byline
                          if re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", text)}
        if emailed and len(emailed) < len(byline):
            names |= emailed
        return names

    def parse(self):
        authors = self.parse_author_meta_tags()
        if corresponding := {_name_key(n) for n in self._corresponding_names()}:
            for author in authors:
                if _name_key(author["name"]) in corresponding:
                    author["is_corresponding"] = True
        return {'authors': authors, 'abstract': self.parse_abstract()}

    test_cases = [
        {
            "doi": "10.1051/e3sconf/202126102087",
            "result": [
                {
                    "name": "Yunwu He",
                    "affiliations": [
                        "Shenzhen Tagen<group> Co., Ltd, 518034, Shenzhen, China"
                    ],
                    "is_corresponding": None,
                },
                {
                    "name": "Tao Liu",
                    "affiliations": [
                        "Shenzhen Yuetong Construction Engineering Co., Ltd, 518019, Shenzhen, China"
                    ],
                    "is_corresponding": None,
                },
                {
                    "name": "Tao Wang",
                    "affiliations": [
                        "Shenzhen Yuetong Construction Engineering Co., Ltd, 518019, Shenzhen, China"
                    ],
                    "is_corresponding": None,
                },
                {
                    "name": "Xiayi Liang",
                    "affiliations": [
                        "Shenzhen Yuetong Construction Engineering Co., Ltd, 518019, Shenzhen, China"
                    ],
                    "is_corresponding": None,
                },
                {
                    "name": "Hanxin Wei",
                    "affiliations": [
                        "Shenzhen Yuetong Construction Engineering Co., Ltd, 518019, Shenzhen, China"
                    ],
                    "is_corresponding": None,
                },
                {
                    "name": "Zhigang Zheng",
                    "affiliations": [
                        "Shenzhen Yuetong Construction Engineering Co., Ltd, 518019, Shenzhen, China"
                    ],
                    "is_corresponding": None,
                },
                {
                    "name": "Xin Xiao",
                    "affiliations": ["Foshan University, 528000, Foshan, China"],
                    "is_corresponding": None,
                },
            ],
        },
        {
            "doi": "10.1051/shsconf/20207301023",
            "result": [
                {
                    "name": "Pavel Rousek",
                    "affiliations": [
                        "Institute of Technology and Business, School of Expertness and Valuation, Okružní 517/10, 37001 české Budějovice Czech Republic"
                    ],
                    "is_corresponding": None,
                },
                {
                    "name": "Simona Hašková",
                    "affiliations": [
                        "Institute of Technology and Business, School of Expertness and Valuation, Okružní 517/10, 37001 české Budějovice Czech Republic"
                    ],
                    "is_corresponding": None,
                },
            ],
        },
    ]
