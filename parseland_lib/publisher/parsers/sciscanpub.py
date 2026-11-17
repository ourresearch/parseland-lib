"""SciScan Publishing (三仓出版社 / 世刊出版平台, sciscanpub.com) article pages (oxjob #2339).

The site runs its own CMS. Every article page prints a `ul.article_abstract` list of labelled rows inside
`div.Main_articlescontents`:
- the byline: a "作者：" / "Authors:" row of one <a> per author, or (newest pages) an `h3.citation_author` above the
  list; names may end in ¹/² affiliation marks (now and then a plain digit) and an unexplained "*";
- the affiliations: a "单位：" / "Information:" row, one per line or "；"-separated, numbered "1．..." when the byline
  carries marks;
- the abstract: an "Abstract:" row with an English and a Chinese version, or a "摘要：" row (Chinese) followed by a
  row with no label (English).
Full-text pages add the article body (`div.article_content`) with one `p.ref` paragraph per reference ("[n] ...").
Older pages carry no citation_* meta tags, and newer pages put every author into one romanized citation_author tag
("Hao Linxuan Taoying"), so the generic parser read one author or none and no affiliation. The pages state no
corresponding author, funding or acknowledgments.

The claim reads only the <title> in <head> (the site's brand ends every title) before it looks for the list, so pages
of other sites cost a few top-level child scans.
"""
import re

from bs4 import Tag

from parseland_lib.abstract_language import foreign_share
from parseland_lib.publisher.parsers.parser import PublisherParser

TITLE_MARKS = ("sciscan", "三仓出版社", "世刊出版平台")
WS = re.compile(r"\s+")
AUTHORS_LABEL = re.compile(r"^(authors?|作\s*者)$", re.I)
AFFS_LABEL = re.compile(r"^(information|affiliations?|单\s*位)$", re.I)
ABSTRACT_LABEL = re.compile(r"^(abstract|摘\s*要)$", re.I)
SUPERSCRIPTS = str.maketrans("¹²³⁴⁵⁶⁷⁸⁹⁰", "1234567890")
NAME_TAIL = re.compile(r"[\d¹²³⁴⁵⁶⁷⁸⁹⁰*＊,，、\s]+$")
AFF_NUM = re.compile(r"(?:^|(?<=[\n;；]))\s*(\d{1,2})\s*[.．、](?!\d)\s*")
AFF_TRIM = " \t\r\n;；。,，"
REF_NUM = re.compile(r"^[\[［]\s*(\d{1,3})\s*[\]］]\s*")
DOI = re.compile(r"(?:doi\.org/|doi\s*[:：]\s*)(10\.\d{4,9}/[^\s，。；;）)\]］]+)", re.I)
MAX_AUTHORS = 60


def _text(node):
    return WS.sub(" ", node.get_text("")).strip()


def _child(tag, name):
    return next((c for c in tag.contents if isinstance(c, Tag) and c.name == name), None) if tag else None


class SciScanPub(PublisherParser):
    parser_name = "sciscanpub"
    prefer_publisher_authors_over_generic = True  # the printed byline, not the one romanized citation_author tag

    def is_publisher_specific_parser(self):
        if getattr(self, "_claim", None) is None:
            self._claim = self._claims_page()
        return self._claim

    def _claims_page(self):
        # Cheap first: <html> -> <head> -> <title> by direct children only, never a search of the whole page.
        title = _child(_child(_child(self.soup, "html"), "head"), "title")
        if title is None:
            return False
        text = title.get_text().casefold()
        if not any(mark in text for mark in TITLE_MARKS):
            return False
        return self.soup.select_one("div.Main_articlescontents ul.article_abstract") is not None

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._read()["authors"])

    def parse(self):
        return self._read()

    # ---- reading ----

    def _read(self):
        if getattr(self, "_cache", None) is None:
            self._cache = self._read_page()
        return self._cache

    def _read_page(self):
        out = {"authors": [], "abstract": None, "acknowledgments": None, "funding_statement": None,
               "references": None, "references_complete": False}
        main = self.soup.select_one("div.Main_articlescontents")
        listing = main.select_one("ul.article_abstract") if main else None
        if listing is None:
            return out
        rows = []  # (label, li) in page order
        for li in listing.find_all("li", recursive=False):
            label = li.find("span", class_="abstract_title")
            rows.append((_text(label).rstrip(":：").strip() if label else "", li))
        out["authors"] = self._authors(main, rows)
        out["abstract"] = self._abstract(rows)
        out["references"], out["references_complete"] = self._references(main)
        return out

    @staticmethod
    def _contents(li):
        return li.find_all(class_="abstract_content", recursive=False)

    def _authors(self, main, rows):
        anchors = []
        for label, li in rows:
            if AUTHORS_LABEL.match(label):
                anchors = [a for c in self._contents(li) for a in c.find_all("a")]
                break
        if not anchors:
            anchors = main.select("h3.citation_author a.author_name")
        authors = []
        for a in anchors:
            raw = _text(a)
            tail = NAME_TAIL.search(raw)
            name = raw[:tail.start()].strip() if tail else raw
            marks = re.findall(r"\d", tail.group(0).translate(SUPERSCRIPTS)) if tail else []
            if not name:  # a mark printed in its own link ("刘海洪²" then "³") belongs to the name before it
                if authors:
                    authors[-1]["marks"] += marks
                continue
            authors.append({"name": name, "affiliations": [], "is_corresponding": False, "marks": marks})
        if len(authors) > MAX_AUTHORS:
            return []
        affs = self._affiliations(rows)
        by_num = {n: t for n, t in affs if n}
        linked = bool(by_num) and any(a["marks"] for a in authors)
        for author in authors:
            marks = author.pop("marks")
            if len(affs) == 1:
                author["affiliations"] = [affs[0][1]]
            elif linked:
                author["affiliations"] = [by_num[m] for m in dict.fromkeys(marks) if m in by_num]
            else:  # listed without saying who has which: every author gets the whole list (label-v1)
                author["affiliations"] = [t for _, t in affs]
        return authors

    @staticmethod
    def _affiliations(rows):
        """[(number or None, text)] from the affiliation row."""
        li = next((li for label, li in rows if AFFS_LABEL.match(label)), None)
        if li is None:
            return []
        text = "\n".join(c.get_text("") for c in SciScanPub._contents(li)).strip()
        starts = list(AFF_NUM.finditer(text))
        if starts and starts[0].start() == 0:
            parts = [(m.group(1), text[m.end():nxt.start() if nxt else len(text)])
                     for m, nxt in zip(starts, starts[1:] + [None])]
        else:
            parts = [(None, line) for line in text.split("\n")]
        affs = []
        for num, part in parts:
            part = WS.sub(" ", part).strip(AFF_TRIM)
            if part:
                affs.append((num, part))
        return affs

    def _abstract(self, rows):
        versions = []
        for i, (label, li) in enumerate(rows):
            if not ABSTRACT_LABEL.match(label):
                continue
            versions = [_text(c) for c in self._contents(li)]
            for next_label, next_li in rows[i + 1:]:  # "摘要：" pages print the English version in an unlabelled row
                if next_label:
                    break
                versions += [_text(c) for c in self._contents(next_li)]
            break
        versions = [v for v in versions if re.search(r"\w{2}", v)]
        if not versions:
            return None
        # "If several language versions are shown, give the English one, else the first" (label-v1)
        return next((v for v in versions if foreign_share(v) <= 0.05), versions[0])

    @staticmethod
    def _references(main):
        paras = main.select("div.article_content p.ref")
        if not paras:
            return None, False
        refs, numbers = [], []
        for p in paras:
            raw = _text(p)
            if m := REF_NUM.match(raw):
                numbers.append(int(m.group(1)))
                raw = raw[m.end():].strip()
            if not raw:
                continue
            doi = DOI.search(raw)
            refs.append({"position": len(refs) + 1, "raw": raw, "doi": doi.group(1).rstrip(".,;．") if doi else None})
        if not refs:
            return None, False
        # Positive evidence of the whole list: every entry numbered, 1..n with no gap
        complete = len(numbers) == len(refs) and numbers == list(range(1, len(refs) + 1))
        return refs, complete
