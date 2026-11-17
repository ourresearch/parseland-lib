"""Xinlan International (欣澜国际, qikanby.com and lw.qikanby.com) article pages (oxjob #2339).

The site runs WordPress (a journal_article post type). Its byline block (div#authorString) is always empty, and the
page has no citation_* meta tags: the whole article is pasted from a Word file into div#articleFullText >
div.showtext as WordPress blocks, in this order:
  the title; the byline (one line, often with "1"/"2" markers, or "姓名：" before it); the affiliation lines
  ("1.", "（1." or an <ol> when numbered; an address or "邮编：" postcode line after them; or an ID-card number where
  the affiliation would go, which is never read); "摘要：" with the abstract (or a bare "摘要" heading and the
  abstract in the next block); "关键词："; the body; "参考文献" and the references, one "[n]" paragraph each or one
  WordPress list.
The text is clamped by CSS (height: 100vh); the "阅读全文" button only lifts the clamp, so the stored markup holds the
whole article, reference list included.

What it reads, as both blind labellers read the build pages (label-v1):
- authors: the byline line's names, in order ("姓名：" dropped). A byline may share its line with the affiliation
  ("王莹莹 百色市政协文史馆 533000") or follow it ("合肥上华工程设计有限公司 陈红薇").
- affiliations: numbered lines by the byline's markers; otherwise every affiliation and address line joined into one
  string, given to every author. Never an ID-card number, a biography (作者简介), or a funding line.
- corresponding: an author followed by "通讯作者" only (a bare △ or * is never explained on the page).
- abstract: the text after "摘要" up to "关键词".
- references: the list after the last "参考文献" heading; whole when its numbers run 1..n (or it is one HTML list)
  and nothing that is not an entry follows it.
Not read (left alone): a title, byline and affiliation pasted into one line with no break; a reference list in
EndNote's multi-line style; funding lines (on too few pages to ship).
"""
import re
from urllib.parse import urlsplit

from bs4 import Comment, NavigableString, Tag

from parseland_lib.publisher.parsers.parser import PublisherParser

DOMAIN = "qikanby.com"
WS = re.compile(r"[\s 　]+")
ZERO_WIDTH = re.compile(r"[​‌‍﻿]")
ABSTRACT_LABEL = re.compile(r"^[【\[]?\s*摘\s*要\s*[】\]]?\s*[:：]?\s*")
KEYWORDS_LABEL = re.compile(r"^[【\[]?\s*关\s*键\s*词")
KEYWORDS_INLINE = re.compile(r"[【\[]?\s*关\s*键\s*词\s*[】\]]?\s*[:：]")
REFS_HEADING = re.compile(r"^[【\[]?\s*参\s*考\s*文\s*献\s*[】\]]?\s*[:：]?$")
REF_NUM = re.compile(r"^[\[［【]\s*(\d{1,3})\s*[\]］】]\s*")
LIST_END = re.compile(r"^(作者简介|课题来源|基金|本文系|项目|收稿日期|通讯作者|致谢)")  # after the list, not an entry
REF_CONTINUATION = re.compile(r"^(https?://|doi[:：\s])", re.I)
DOI = re.compile(r"(?:doi\s*[:：]?\s*|doi\.org/)(10\.\d{4,9}/[^\s，。；]+)", re.I)
# An ID-card number (masked or not, with or without its label): printed where the affiliation goes; never read.
ID_NUMBER = re.compile(r"(?:身份证(?:号码|号)?\s*[:：]?\s*)?\d[\d*＊]{9,}[xX]?|身份证(?:号码|号)?\s*[:：]?")
SKIP_LINE = re.compile(r"^(作者简介|基金|本文系|项目|课题|收稿|中图分类号|文献标识码|文章编号)")
CORR_LINE = re.compile(r"^通讯作者\s*[:：]\s*(.+)$")
SUBTITLE = re.compile(r"^[—–\-－]{1,2}")
NAME_LABEL = re.compile(r"姓\s*名\s*[:：]\s*")
UNIT_LABEL = re.compile(r"单\s*位\s*[:：]\s*")
AFF_NUM_MARKED = re.compile(r"^(\d{1,2})\s*[.、．,，]?\s*(?=\D)")
AFF_NUM = re.compile(r"^(\d{1,2})\s*[.、．]\s*(?=\D)")
WRAPPED = re.compile(r"^[（(](.+)[)）]$")
INST = re.compile(r"公司|医院|大学|学院|学校|中学|小学|中心|研究院|研究所|集团|局|站|厂|馆|委员会|办公室|卫生院|幼儿园|"
                  r"政府|银行|设计院|部队|协会|所$|院$|校$|处$|科$|室$|队$|社$|会$")
POSTAL = re.compile(r"邮\s*编|(?<!\d)\d{6}(?!\d)")
BYLINE_TOKEN = re.compile(
    r"(?P<corr>[（(]?\s*通讯作者\s*[）)]?)"
    r"|(?P<paren>[（(][^）)]*[）)])"
    r"|(?P<num>(?<!\d)\d{1,2}(?:\s*[,，]\s*\d{1,2})*(?!\d))"
    r"|(?P<long>\d+)"
    r"|(?P<mark>[△▲*＊★☆#†‡]+)"
    r"|(?P<name>(?:(?!通讯作者)[^\s\d,，、;；*＊（）()△▲★☆#†‡])+)"
)
CJK_NAME = re.compile(r"^[㐀-鿿]{2,4}$|^[㐀-鿿]+[·•][㐀-鿿·•]+$")
ADMIN_END = re.compile(r"[省市县区镇乡村旗]$")
NOT_NAMES = {"摘要", "关键词", "目录", "引言", "前言", "单位", "姓名", "作者", "邮编"}
HEADER_LINES = 14  # the abstract label comes within this many lines of the title, or the header is not this layout


def _clean(s):
    return WS.sub(" ", ZERO_WIDTH.sub("", s)).strip()


def _lines(block, spaced=False):
    """A block's text split at its <br> tags. `spaced`: a space between text nodes too, for a byline pasted as
    <strong>name</strong><strong>affiliation</strong> with no space between them."""
    sep, parts, cur = " " if spaced else "", [], []
    for el in block.descendants:
        if isinstance(el, Tag) and el.name == "br":
            parts.append(sep.join(cur))
            cur = []
        elif isinstance(el, NavigableString) and not isinstance(el, Comment):
            cur.append(str(el))
    parts.append(sep.join(cur))
    return [t for t in (_clean(p) for p in parts) if t]


def _is_name(piece):
    return bool(CJK_NAME.match(piece)) and piece not in NOT_NAMES and not INST.search(piece) \
        and not ADMIN_END.search(piece)


def _byline(text):
    """[{name, marks, is_corresponding}] when every name-like token of `text` is a person's name, else None."""
    authors = []
    for m in BYLINE_TOKEN.finditer(text):
        if m.group("corr"):
            if not authors:
                return None
            authors[-1]["is_corresponding"] = True
        elif m.group("paren") or m.group("long"):
            return None
        elif m.group("num"):
            if not authors:
                return None
            authors[-1]["marks"] += re.findall(r"\d+", m.group("num"))
        elif m.group("mark"):
            continue
        elif name := m.group("name"):
            if not _is_name(name):
                return None
            authors.append({"name": name, "affiliations": [], "is_corresponding": False, "marks": []})
    return authors if 0 < len(authors) <= 40 else None


def _split_byline(line):
    """(authors, the affiliation text sharing the line) when `line` holds the byline, else None."""
    if m := NAME_LABEL.search(line):
        rest = line[m.end():]
        unit = UNIT_LABEL.search(rest)
        names, aff = (rest[:unit.start()], rest[unit.end():]) if unit else (rest, "")
        if not unit and (post := re.search(r"邮\s*编", names)):
            names, aff = names[:post.start()], names[post.start():]
        authors = _byline(names)
        return (authors, aff.strip()) if authors else None
    if UNIT_LABEL.match(line):
        return None
    if authors := _byline(line):
        return authors, ""
    tokens = line.split(" ")
    for k in range(len(tokens) - 1, 0, -1):  # names first, then the affiliation: "王莹莹 百色市政协文史馆 533000"
        rest = " ".join(tokens[k:])
        if (INST.search(rest) or POSTAL.search(rest)) and (authors := _byline(" ".join(tokens[:k]))):
            return authors, rest
    if len(tokens) > 1 and _is_name(tokens[-1]):  # the affiliation, then one name: "合肥上华工程设计有限公司 陈红薇"
        rest = " ".join(tokens[:-1])
        if INST.search(rest) and not POSTAL.search(rest):
            return _byline(tokens[-1]), rest
    return None


def _aff_text(text):
    return UNIT_LABEL.sub("", text, count=1).strip().rstrip("；;。，, ").strip()


class Qikanby(PublisherParser):
    parser_name = "qikanby"
    prefer_publisher_authors_over_generic = True  # the page has no author meta tags: its byline is the only one

    def is_publisher_specific_parser(self):
        # Every parser's claim runs on every DOI page (#2239: under 0.5 ms on pages it does not claim), so the
        # canonical link is looked for among <head>'s direct children only.
        html = self.soup.find("html", recursive=False)
        head = (html or self.soup).find("head", recursive=False)
        if head is None:
            return False
        link = head.find("link", rel="canonical", recursive=False)
        if link is None:
            return False
        try:
            host = urlsplit((link.get("href") or "").strip()).netloc.lower()
        except ValueError:
            return False
        return host == DOMAIN or host.endswith("." + DOMAIN)

    def authors_found(self):
        if not self.is_publisher_specific_parser():
            return False
        out = self._read()
        return bool(out["authors"] or out["abstract"])

    def parse(self):
        return self._read()

    # ---- reading ----

    def _read(self):
        if getattr(self, "_cache", None) is None:
            self._cache = self._read_page()
        return self._cache

    def _read_page(self):
        out = {"authors": [], "abstract": None, "references": None, "references_complete": False}
        box = self.soup.select_one("#articleFullText > div.showtext")
        if box is None:
            return out
        blocks = [b for b in box.find_all(recursive=False) if isinstance(b, Tag)]
        lines = []  # (block tag name, text, list number or None, the text with a space between text nodes)
        for block in blocks:
            if block.name in ("ol", "ul"):
                for k, li in enumerate(block.find_all("li")):
                    if t := _clean(li.get_text("")):
                        lines.append((block.name, t, k + 1 if block.name == "ol" else None, t))
            else:
                plain, spaced = _lines(block), _lines(block, spaced=True)
                if len(plain) != len(spaced):
                    spaced = plain
                lines.extend((block.name, t, None, sp) for t, sp in zip(plain, spaced))
        ti = self._title_index(lines)
        if ti is not None:
            ai, implicit = self._abstract_index(lines, ti)
            if ai is not None:
                out["authors"] = self._authors(lines[ti + 1:ai])
                out["abstract"] = self._abstract(lines, ai, implicit)
        out["references"], out["references_complete"] = self._references(blocks)
        return out

    def _title_index(self, lines):
        h = self.soup.select_one("#pdfDom h3.section-title")
        title = re.sub(r"\s+", "", h.get_text("")) if h else ""
        first = None
        for i, (_, t, _, _) in enumerate(lines[:HEADER_LINES]):
            flat = re.sub(r"\s+", "", t)
            if title and len(flat) >= 6 and (flat == title or title.startswith(flat) or flat.startswith(title)):
                return i
            if first is None and not SKIP_LINE.match(t) and not SUBTITLE.match(t):
                first = i
        return first

    @staticmethod
    def _abstract_index(lines, ti):
        window = lines[ti + 1:ti + 1 + HEADER_LINES]
        for i, (_, t, _, _) in enumerate(window, start=ti + 1):
            if ABSTRACT_LABEL.match(t):
                return i, False
        # no label: a long block right before "关键词" (a structured abstract that starts "目的 ...")
        for i, (_, t, _, _) in enumerate(window, start=ti + 1):
            if KEYWORDS_LABEL.match(t):
                if i - 1 > ti and len(lines[i - 1][1]) > 80:
                    return i - 1, True
                break
        return None, False

    @staticmethod
    def _abstract(lines, ai, implicit):
        first = lines[ai][1] if implicit else ABSTRACT_LABEL.sub("", lines[ai][1], count=1)
        paras, end = ([first] if first else []), None
        for i in range(ai + 1, min(len(lines), ai + 9)):
            t = lines[i][1]
            if KEYWORDS_LABEL.match(t) or REFS_HEADING.match(t):
                end = i
                break
        if end is not None:
            paras += [t for _, t, _, _ in lines[ai + 1:end]]
        elif not paras and ai + 1 < len(lines):
            paras = [lines[ai + 1][1]]
        paras = [KEYWORDS_INLINE.split(p)[0].strip().lstrip(":：").strip() for p in paras]
        return "\n".join(p for p in paras if p) or None

    @staticmethod
    def _authors(header):
        authors, affs, corr_names = None, [], set()  # affs: [number or None, text]
        for kind, t, num, spaced in header:
            if m := CORR_LINE.match(t):
                corr_names.update(re.split(r"[\s,，、;；]+", m.group(1)))
                continue
            if SKIP_LINE.match(t) or SUBTITLE.match(t):
                continue
            t = _clean(ID_NUMBER.sub(" ", t))
            if not t:
                continue
            if kind == "ol":
                affs.append([str(num), _aff_text(t)])
                continue
            if w := WRAPPED.match(t):
                t = w.group(1).strip()
            if authors is None and kind != "ul" and (
                    split := _split_byline(t) or _split_byline(_clean(ID_NUMBER.sub(" ", spaced)))):
                authors, rest = split
                if rest:
                    affs.append([None, _aff_text(rest)])
                continue
            affs.append([None, t])
        if not authors:
            return []
        marked = any(a["marks"] for a in authors)
        numbered = []  # [number, text], an unnumbered line after a numbered one is its address
        for num, text in affs:
            if num is None and (m := (AFF_NUM_MARKED if marked else AFF_NUM).match(text)):
                num, text = m.group(1), text[m.end():]
            text = _aff_text(text)
            if not text:
                continue
            if num is None and numbered and numbered[-1][0] is not None:
                numbered[-1][1] = f"{numbered[-1][1]} {text}"
            else:
                numbered.append([num, text])
        by_num = {n: t for n, t in numbered if n}
        if by_num:
            for a in authors:
                a["affiliations"] = [by_num[n] for n in dict.fromkeys(a["marks"]) if n in by_num]
                if not a["marks"] and len(by_num) == 1:
                    a["affiliations"] = list(by_num.values())
        elif numbered:
            joined = " ".join(t for _, t in numbered)
            for a in authors:
                a["affiliations"] = [joined]
        for a in authors:
            a["is_corresponding"] = a["is_corresponding"] or a["name"] in corr_names
            del a["marks"]
        return authors

    @staticmethod
    def _references(blocks):
        hi = None
        for i, b in enumerate(blocks):
            if b.name not in ("ol", "ul") and REFS_HEADING.match(_clean(b.get_text(""))):
                hi = i
        if hi is None:
            return None, False
        entries, numbers, stray, listed = [], [], False, False
        for b in blocks[hi + 1:]:
            if "p_more" in (b.get("class") or []):
                break  # the "..." under the CSS clamp: the end of the article
            if b.name in ("ol", "ul"):
                items = [t for t in (_clean(li.get_text("")) for li in b.find_all("li")) if t]
                if entries or not items or (b.name == "ol" and (b.get("start") or "1").strip() not in ("", "1")):
                    stray = True
                    break
                entries, numbers, listed = items, list(range(1, len(items) + 1)), True
                continue
            texts = _lines(b)
            if not texts:
                continue
            if LIST_END.match(texts[0]):
                break  # the author's biography or the funding line after the list
            if listed:
                stray = True  # text after the list
                break
            for t in texts:
                if m := REF_NUM.match(t):
                    numbers.append(int(m.group(1)))
                    entries.append(t[m.end():].strip())
                elif entries and REF_CONTINUATION.match(t):
                    entries[-1] = f"{entries[-1]} {t}"
                else:
                    stray = True  # text that is not a numbered entry: the list may not be whole
                    break
            if stray:
                break
        entries = [e for e in entries if e]
        if not entries:
            return None, False
        refs = []
        for pos, raw in enumerate(entries, start=1):
            doi = DOI.search(raw)
            refs.append({"position": pos, "raw": raw, "doi": doi.group(1).rstrip(".,;)") if doi else None})
        complete = not stray and len(entries) == len(numbers) and numbers == list(range(1, len(numbers) + 1))
        return refs, complete
