"""Hong Kong Anmai Publishing (香港安麦出版有限公司, anmaichuban.com) article pages (oxjob #2210).

The site runs its own CMS. Two skins (an older `div.container2` page, a newer `div.body_txt` page) share one article
body: a title <h2>; the byline in a second <h2>/<h4>, or after a <br> inside the title <h2>; one <p> per affiliation
(numbered "1...", "2..." when the byline carries 1/2 markers); a "摘要：" paragraph; "关键词："; then "参考文献" and one
"[n]" paragraph per reference. The pages carry no citation_* meta tags, canonical link or og:url, so the parser claims
them by the site's own stylesheet/icon links on www.anmaichuban.com.
"""
import re
from urllib.parse import urlsplit

from bs4 import Comment, NavigableString, Tag

from parseland_lib.publisher.parsers.parser import PublisherParser

HOSTS = {"www.anmaichuban.com", "anmaichuban.com"}
WS = re.compile(r"[\s 　]+")
ZERO_WIDTH = re.compile(r"[​‌‍﻿]")
ABSTRACT_LABEL = re.compile(r"^[【\[]?摘\s*要[】\]]?\s*[:：]?\s*")
KEYWORDS_LABEL = re.compile(r"^[【\[]?关\s*键\s*词")
KEYWORDS_INLINE = re.compile(r"关\s*键\s*词\s*[:：]")
REFS_HEADING = re.compile(r"^[【\[]?参\s*考\s*文\s*献[】\]]?\s*[:：]?$")
REF_NUM = re.compile(r"^[\[［](\d{1,3})[\]］]\s*")
REF_CONTINUATION = re.compile(r"^(https?://|doi[:：\s])", re.I)
DOI = re.compile(r"(?:doi\s*[:：]?\s*|doi\.org/)(10\.\d{4,9}/[^\s，。；]+)", re.I)
MASKED_ID = re.compile(r"^\d[\d*＊xX]{9,}$")  # a masked national ID number some pages print where the affiliation goes
AFF_NUM = re.compile(r"^(\d{1,2})\s*(?=\D)")
BYLINE_TOKEN = re.compile(
    r"(?P<corr>[（(]?\s*通讯作者\s*[）)]?)"
    r"|(?P<paren>[（(][^）)]*[）)])"
    r"|(?P<num>\d{1,2}(?:\s*[,，]\s*\d{1,2})*)"
    r"|(?P<name>[^\s\d,，、;；*＊（）()]+)"
)
HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
MAX_NAME_LEN = 20  # a longer "name" means the byline was not found (title text); shortcut, CJK bylines only


def _text(node):
    if isinstance(node, NavigableString):
        s = str(node)
    else:
        s = node.get_text("")
    return WS.sub(" ", ZERO_WIDTH.sub("", s)).strip()


def _text_after(container, mark):
    """The text inside `container` that follows `mark` (a <br> that may sit inside a <span>)."""
    parts = []
    for el in mark.next_elements:
        if not any(p is container for p in el.parents):
            break
        if isinstance(el, NavigableString) and not isinstance(el, Comment):
            parts.append(str(el))
    return WS.sub(" ", ZERO_WIDTH.sub("", "".join(parts))).strip()


class Anmaichuban(PublisherParser):
    parser_name = "anmaichuban"

    def is_publisher_specific_parser(self):
        for link in self.soup.find_all("link", href=True):
            try:
                if urlsplit(link["href"].strip()).netloc.lower() in HOSTS:
                    return True
            except ValueError:
                continue
        return False

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
        body = self.soup.select_one("div.body_txt") or self.soup.select_one("div.container.container2")
        if body is None:
            return out
        blocks = [b for b in body.find_all(recursive=False) if isinstance(b, Tag)]
        texts = [_text(b) for b in blocks]
        ai = next((i for i, t in enumerate(texts) if ABSTRACT_LABEL.match(t)), None)
        if ai is None or ai == 0 or blocks[0].name not in HEADINGS:
            return out
        out["authors"] = self._authors(blocks[:ai])
        out["abstract"] = self._abstract(texts, ai)
        out["references"], out["references_complete"] = self._references(texts, ai)
        return out

    def _authors(self, header):
        title = header[0]
        if len(header) > 1 and header[1].name in HEADINGS:
            byline, aff_blocks = _text(header[1]), header[2:]
        elif title.find("br"):
            byline, aff_blocks = _text_after(title, title.find_all("br")[-1]), header[1:]
        else:
            return []
        authors = self._byline(byline)
        if not authors:
            return []
        marked = any(a["marks"] for a in authors)
        lines = [t for t in (_text(b) for b in aff_blocks) if t and not MASKED_ID.match(t.replace(" ", ""))]
        numbered = marked or len(lines) > 1
        affs = []  # (number or None, text)
        for line in lines:
            num = None
            if numbered and (m := AFF_NUM.match(line)):
                num, line = m.group(1), line[m.end():]
            line = line.strip().rstrip("；;。，, ").strip()
            if line:
                affs.append((num, line))
        by_num = {n: t for n, t in affs if n}
        for a in authors:
            if marked and by_num:
                a["affiliations"] = [by_num[n] for n in a["marks"] if n in by_num]
                if not a["marks"] and len(affs) == 1:
                    a["affiliations"] = [affs[0][1]]
            else:
                a["affiliations"] = [t for _, t in affs]
            del a["marks"]
        return authors

    @staticmethod
    def _byline(text):
        authors = []
        for m in BYLINE_TOKEN.finditer(text):
            if m.group("corr"):
                if authors:
                    authors[-1]["is_corresponding"] = True
            elif m.group("num"):
                if authors:
                    authors[-1]["marks"] += re.findall(r"\d+", m.group("num"))
            elif name := m.group("name"):
                if not re.search(r"[㐀-鿿A-Za-z]", name):
                    continue
                if len(name) > MAX_NAME_LEN:
                    return []
                authors.append({"name": name, "affiliations": [], "is_corresponding": False, "marks": []})
        return authors if len(authors) <= 40 else []

    @staticmethod
    def _abstract(texts, ai):
        end = next((i for i in range(ai + 1, len(texts)) if KEYWORDS_LABEL.match(texts[i])
                    or REFS_HEADING.match(texts[i])), None)
        paras = texts[ai:end] if end is not None else texts[ai:ai + 1]
        paras = [ABSTRACT_LABEL.sub("", paras[0], count=1)] + paras[1:]
        paras = [KEYWORDS_INLINE.split(p)[0].strip() for p in paras]
        abstract = "\n".join(p for p in paras if p)
        return abstract or None

    @staticmethod
    def _references(texts, ai):
        ri = next((i for i in range(ai + 1, len(texts)) if REFS_HEADING.match(texts[i])), None)
        if ri is None:
            return None, False
        entries, numbers, stray = [], [], False
        for t in texts[ri + 1:]:
            if not t:
                continue
            if m := REF_NUM.match(t):
                numbers.append(int(m.group(1)))
                entries.append(t[m.end():].strip())
            elif entries and REF_CONTINUATION.match(t):
                entries[-1] = f"{entries[-1]} {t}"
            else:
                stray = True  # text after the list that is not a numbered entry: the list may not be whole
                break
        if not entries:
            return None, False
        refs = []
        for pos, raw in enumerate(entries, start=1):
            doi = DOI.search(raw)
            refs.append({"position": pos, "raw": raw,
                         "doi": doi.group(1).rstrip(".,;)") if doi else None})
        complete = not stray and numbers == list(range(1, len(numbers) + 1))
        return refs, complete
