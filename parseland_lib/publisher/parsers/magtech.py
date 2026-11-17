"""Magtech (Beijing Magtech, 北京玛格泰克) journal platform, used by ~60 mostly Chinese journal sites (oxjob #2289).

Journal of Inorganic Materials (jim.org.cn), Chinese Journal of Organic Chemistry (sioc-journal.cn), Biodiversity
Science, Progress in Geography, Resources Science, Acta Psychologica Sinica, Chemical Journal of Chinese Universities
and many more print the same Bootstrap article page:

    <h3 class="abs-tit">TITLE</h3>
    <p data-toggle="collapse" data-target="#divPanel"><span>
        NAME<sup>1</sup>, NAME<sup>1,2</sup><sup>*</sup>(<a href="mailto:EMAIL"><img src=".../email.png"></a>) ...
        <span data-placement="right">(the pop-up's toggle)</span></span></p>
    <div id="divPanel" class="collapse bs-callout">
      <address class="address"><ol><li><sup>1</sup>AFFILIATION<br/>2. AFFILIATION ...</li></ol></address>
      <ul class="code-style"><li><code>通讯作者:</code> NAME E-mail: ...</li> ...
          <li><code>基金资助:</code><div>FUNDING</div></li></ul></div>
    (then the same pair for #divPanelEn: the English byline, "Contact:" and "Supported by:")
    <div id="collapseOne"> <p><strong>摘要：</strong>TEXT</p> ... <p><strong>Abstract: </strong>TEXT</p>
    <div id="collapseThree"><table><tr><td>[1]</td><td><span class="magtech_ref_source">REFERENCE</span>
        <br/>doi: <a href="http://dx.doi.org/DOI">...</a></td></tr> ...

The page's meta tags carry only a comma-joined citation_authors list and the generic parser hung no affiliation, or
the whole address block, on each name, marked no corresponding author, and took the Chinese abstract with its label.
Bilingual pages print the byline twice (Chinese, then English); the page's byline is the first one, or the English
one on a page in English, as in the gold, and the English abstract is the abstract (label-v1). The tabbed layout (adearth.ac.cn, computmath.cjoe.ac.cn: div#zhaiyao) gives its abstract only. Not read: the
old pre-Bootstrap layout (magtech.com.cn and a few
others, no divPanel byline), and acknowledgments (in the full text only).
"""
import re

from bs4 import NavigableString, Tag

from parseland_lib.abstract_language import is_english
from parseland_lib.publisher.parsers.parser import PublisherParser

# the platform's generator tag: "Beijing Magtech Co., Ltd" or its Chinese name
_GENERATOR = re.compile(r"magtech|玛格泰克", re.I)
# a script every Magtech page loads from its own assets (rhhz.py's platform loads it too: the byline decides)
_ASSET = "js/modelDialog1.js"
# rhhz.py's marks (a citation_state tag, style/web/ assets): those pages are its own
_RHHZ_ASSET = "style/web/"
_PANELS = re.compile(r"^#divPanel(?:En)?$")
_SEPARATOR = re.compile(r"\s*(?:[,，;；、]|\band\b)\s*")
# what marks an author in the byline besides the affiliation labels
_SYMBOLS = "*∗△▲※"
_SYMBOL = re.compile(r"[*∗△▲※]")
_CONTACT = re.compile(r"^\s*(?:通[信讯]作者|联系人|contact|corresponding\s+authors?)\s*[:：]?\s*", re.I)
_FUNDING = re.compile(r"^\s*(?:基金资助|基金项目|资助项目|supported\s+by|funds?|fund\s+projects?)\s*[:：]\s*", re.I)
_EQUAL = re.compile(r"contributed equally|equal(?:ly)? contribut|共同第一作者|并列第一作者", re.I)
# where a named author ends in a contact line: the e-mail, a phone number, a bio's opening
_NAME_END = re.compile(r"\s*(?:e-?mail|tel|phone|电话|邮箱|[(（\[]).*$", re.I)
_NOT_NAME = re.compile(r"@|e-?mail|https?:|\d{3}|简介|男|女", re.I)
_ABSTRACT_LABEL = re.compile(r"^\s*(abstract|摘\s*要)\s*[:：]?\s*$", re.I)
# the labels that end the abstract's text: keywords, classification numbers, the "link to this article" line
_ABSTRACT_STOP = re.compile(r"^\s*(?:关键词|key\s*words?|中图分类号|clc|链接本文|url|trendmd|摘\s*要|abstract)\b", re.I)
_REF_NUMBER = re.compile(r"^\s*\[?\s*(\d{1,4})\s*\]?\s*\.?\s*$")
_DOI = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+)")


def _text(tag):
    return " ".join(tag.get_text(" ", strip=True).split()) if tag is not None else ""


def _template_head(soup):
    """The claim's cheap first test: does <head> carry the platform's generator tag or one of its scripts? Every
    parser's claim runs on every page (#2239: under 0.5 ms a page it does not claim), so <head> is reached through
    direct children only and searched alone."""
    html = soup.find("html", recursive=False)
    head = (html or soup).find("head", recursive=False)
    if head is None:
        return False
    found = False
    for tag in head.find_all(("meta", "script", "link")):
        if tag.name == "meta":
            name = (tag.get("name") or "").lower()
            if name == "citation_state":
                return False  # rhhz.py's page
            if name == "generator" and _GENERATOR.search(tag.get("content") or ""):
                found = True
        else:
            src = tag.get("src") or tag.get("href") or ""
            if _RHHZ_ASSET in src:
                return False
            if src.endswith(_ASSET):
                found = True
    return found


def _norm_name(name):
    return re.sub(r"[\s.·・]+", "", name).casefold()


def _name_tokens(name):
    return frozenset(t for t in re.split(r"[\s.\-‐]+", name.casefold()) if t)


class Magtech(PublisherParser):
    parser_name = "magtech"
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        if not hasattr(self, "_claim"):  # authors_found asks too: the head test runs once per page
            self._claim = _template_head(self.soup) and bool(self._bylines())
        return self._claim

    def authors_found(self):
        return self.is_publisher_specific_parser()

    # ---- bylines

    def _bylines(self):
        """[(panel id, [author dicts])] for each byline with names, the page's own first."""
        if hasattr(self, "_bylines_cache"):
            return self._bylines_cache
        out = []
        for p in self.soup.find_all("p", attrs={"data-target": _PANELS}):
            span = p.find("span")
            authors = self._read_byline(span) if span is not None else None
            if authors:
                out.append((p["data-target"][1:], authors))
        if self._english_page():  # an English page that prints the Chinese byline first: the English one is the
            out.sort(key=lambda b: b[0] != "divPanelEn")  # page's (gold v1.3 dev, sioc-journal.cn/.../EN/)
        self._bylines_cache = out
        return out

    def _english_page(self):
        for tag in self.soup.find_all("meta"):
            name = (tag.get("name") or tag.get("http-equiv") or "").lower()
            if name in ("citation_language", "dc.language", "content-language"):
                return (tag.get("content") or "").strip().lower().startswith("en")
        return False

    @staticmethod
    def _read_byline(span):
        """[{"name", "labels", "symbols", "mail"}] from the byline's span, or None when it is not a byline (some
        pages print an author's biography there)."""
        entries = [{"name": "", "labels": [], "symbols": "", "mail": False}]

        def last():  # the entry a mark after a name belongs to: "Shen,<sup>a</sup>" marks Shen
            for e in reversed(entries):
                if e["name"].strip():
                    return e
            return entries[-1]

        def add_text(text):
            parts = _SEPARATOR.split(text)
            for i, part in enumerate(parts):
                if i and entries[-1]["name"].strip():
                    entries.append({"name": "", "labels": [], "symbols": "", "mail": False})
                symbols = "".join(_SYMBOL.findall(part))
                part = _SYMBOL.sub("", part).replace("(", " ").replace(")", " ").replace("（", " ").replace("）", " ")
                if part.strip():
                    entries[-1]["name"] += " " + part.strip()
                if symbols:
                    last()["symbols"] += symbols

        def walk(node):
            for child in node.children:
                if isinstance(child, NavigableString):
                    if type(child) is NavigableString:  # not a comment
                        add_text(str(child))
                elif isinstance(child, Tag):
                    if child.name == "span" and child.has_attr("data-placement"):
                        return False  # the pop-up toggle: the byline has ended
                    if child.name == "sup":
                        mark = child.get_text()
                        target = last()
                        target["symbols"] += "".join(_SYMBOL.findall(mark))
                        target["labels"] += [t for t in re.split(r"[\s,，、]+", _SYMBOL.sub("", mark)) if t]
                    elif child.name == "a":
                        if (child.get("href") or "").lower().startswith("mailto:"):
                            last()["mail"] = True
                    elif child.name not in ("img", "i", "br", "script"):
                        if walk(child) is False:
                            return False
            return True

        walk(span)
        authors = []
        for e in entries:
            name = " ".join(e["name"].split()).strip(" ,，;；.")
            if not name:
                continue
            if _NOT_NAME.search(name) or len(name) > 60:
                return None
            e["name"] = name
            authors.append(e)
        return authors or None

    # ---- the panel under a byline: affiliations, contact line, funding

    def _panel(self, panel_id):
        return self.soup.find(id=panel_id)

    def _info_lines(self, panel):
        lines = []
        if panel is None:
            return lines
        for li in panel.select("ul.code-style > li"):
            text = _text(li)
            if text:
                lines.append((li, text))
        return lines

    @staticmethod
    def _segments(li):
        """The <li>'s content split at <br>: [(sup label or "", text)]."""
        segs, label, buf = [], "", []

        def flush():
            text = " ".join("".join(buf).split())
            if text or label:
                segs.append((label, text))

        for child in li.children:
            if isinstance(child, Tag) and child.name == "br":
                flush()
                label, buf = "", []
            elif isinstance(child, Tag) and child.name == "sup" and not "".join(buf).strip() and not label:
                label = re.sub(r"[\s.:：、)）]", "", child.get_text())
            elif isinstance(child, Tag):
                buf.append(child.get_text(" "))
            elif type(child) is NavigableString:
                buf.append(str(child))
        flush()
        return segs

    @staticmethod
    def _split_labelled(text):
        """"1. X; 2. Y" / "a X b Y" / "(1. X；2. Y)" -> [(label, text)], labels in sequence; [] when the text opens
        with no label."""
        text = text.strip().lstrip("(（").strip()
        m = re.match(r"([0-9]{1,2}|[a-z])\s*[.．、]?\s*(?=[^\W\d_])", text)
        if not m:
            return []
        first = m.group(1)
        seq = [str(i) for i in range(int(first), 30)] if first.isdigit() else [chr(c) for c in range(ord(first), ord("z") + 1)]
        starts = [(first, 0, m.end())]
        pos = m.end()
        for label in seq[1:]:
            nxt = re.compile(r"(?:(?<=[\s;；,，。.(（])|(?<=))" + re.escape(label) +
                             r"\s*[.．、]?\s*(?=[^\W\d_])")
            hit = nxt.search(text, pos)
            if not hit:
                break
            starts.append((label, hit.start(), hit.end()))
            pos = hit.end()
        out = []
        for i, (label, _, body) in enumerate(starts):
            end = starts[i + 1][1] if i + 1 < len(starts) else len(text)
            out.append((label, text[body:end]))
        return out

    def _affiliations(self, panel):
        """[(label, text)] of the panel's address list."""
        items = []
        if panel is None:
            return items
        for li in panel.select("address li"):
            for label, text in self._segments(li):
                if label:
                    items.append((label, text))
                    continue
                listed = self._split_labelled(text)
                items += listed if listed else [("", text)]
        out = []
        for label, text in items:
            text = text.strip(" ;；,，。").rstrip(")）").lstrip("(（").strip(" ;；,，")
            if text and text not in ("-",) and (label, text) not in out:
                out.append((label, text))
        return out

    # ---- corresponding authors

    def _corresponding(self, authors, panel):
        """Indices of the authors this byline's panel marks as corresponding: named in its contact line or marked by
        the symbol that line (or a "Corresponding author" note) explains. Mail icons are read in parse_authors."""
        marked = set()
        lines = [text for _, text in self._info_lines(panel)]
        contact = [_CONTACT.sub("", t) for t in lines if _CONTACT.match(t)]
        contact = [t for t in contact if t and t != "-"]
        note = any(re.search(r"corresponding author|通[信讯]作者", t, re.I) for t in lines)
        equal = any(_EQUAL.search(t) for t in lines)
        by_name = {}
        for i, a in enumerate(authors):
            by_name.setdefault(_norm_name(a["name"]), i)
        for line in contact:
            for seg in re.split(r"[,，;；、]|\band\b", line):
                seg = _NAME_END.sub("", seg)
                seg = _SYMBOL.sub("", seg).strip(" :：")
                if not seg:
                    continue
                key = _norm_name(seg)
                if key in by_name:
                    marked.add(by_name[key])
                    continue
                toks = _name_tokens(seg)
                hits = [i for i, a in enumerate(authors) if len(toks) > 1 and _name_tokens(a["name"]) == toks]
                if len(hits) == 1:
                    marked.add(hits[0])
        if (contact or note) and not equal:
            symbols = set("".join(_SYMBOL.findall(" ".join(contact)))) or {"*", "∗"}
            for i, a in enumerate(authors):
                if set(a["symbols"]) & symbols:
                    marked.add(i)
        return marked

    @staticmethod
    def _mail_icons(authors):
        """Indices of the authors with a mail icon, unless every one of several authors has one."""
        mails = {i for i, a in enumerate(authors) if a["mail"]}
        return mails if len(mails) < len(authors) or len(authors) == 1 else set()

    # ---- the whole

    def parse_authors(self):
        bylines = self._bylines()
        if not bylines:
            return []
        panel_id, authors = bylines[0]
        others = [(pid, a) for pid, a in bylines[1:] if len(a) == len(authors)]
        affs = self._affiliations(self._panel(panel_id))
        if not affs:
            for pid, _ in others:
                if affs := self._affiliations(self._panel(pid)):
                    break
        corr = self._corresponding(authors, self._panel(panel_id))
        for pid, other in others:  # else the English panel's "Contact:" line names the same author by position
            corr = corr or self._corresponding(other, self._panel(pid))
        if not corr:  # no line names anyone: a mail icon tied to an author marks them (label-v1); a named
            # "通讯作者" wins over icons, which some journals also give the first author, whose biography has an e-mail
            corr = self._mail_icons(authors)
            for _, other in others:
                corr |= self._mail_icons(other)
        labelled = {label for label, _ in affs if label}
        any_author_label = any(set(a["labels"]) & labelled for a in authors)
        out = []
        for i, a in enumerate(authors):
            if any_author_label:
                mine = [t for label, t in affs if label in a["labels"]]
            else:
                mine = [t for _, t in affs]
            out.append({"name": a["name"], "affiliations": mine, "is_corresponding": i in corr})
        return out

    def parse_abstract(self):
        box = self.soup.find(id="collapseOne")
        if box is None:  # the tabbed layout: <div id="zhaiyao" class="tab-pane"><div class="zhaiyao">TEXT</div> ...
            tab = self.soup.find("div", id="zhaiyao")
            versions = [t for b in (tab.find_all("div", class_="zhaiyao") if tab is not None else [])
                        if len(t := _text(b)) > 20]
            return next((t for t in versions if is_english(t)), versions[0] if versions else None)
        labels = [s for s in box.find_all(["strong", "b"]) if _ABSTRACT_LABEL.match(s.get_text())]
        english = [s for s in labels if "abstract" in s.get_text().lower()]
        for label in english + [s for s in labels if s not in english]:
            if text := self._text_after_label(label):
                return text
        form = box.find("form", attrs={"name": "refForm"})  # an unlabelled abstract: its own paragraph in the form
        if form is not None:
            for p in form.find_all("p"):
                if p.find(["strong", "b"]) is None and len(text := _text(p)) > 100:
                    return text
        return None

    @staticmethod
    def _text_after_label(label):
        holder = label.parent
        own = _text(holder)
        lead = _text(label)
        if own.startswith(lead):
            own = own[len(lead):].strip()
        parts = [own] if own else []
        for sib in holder.next_siblings:
            if isinstance(sib, NavigableString):
                if type(sib) is NavigableString and sib.strip():
                    parts.append(sib.strip())
                continue
            if not isinstance(sib, Tag):
                continue
            stop = sib.find(["strong", "b"])
            if stop is not None and _ABSTRACT_STOP.match(stop.get_text()) or sib.name in ("form", "table", "script"):
                break
            if sib.name in ("p", "div", "span", "ol", "ul") and (t := _text(sib)):
                parts.append(t)
        text = "\n".join(parts).strip()
        return text if len(text) > 20 else None

    def parse_funding_statement(self):
        bylines = self._bylines()
        ids = [pid for pid, _ in bylines] + [pid for pid in ("divPanel", "divPanelEn") if pid not in [b[0] for b in bylines]]
        for pid in ids:
            for li, text in self._info_lines(self._panel(pid)):
                if _FUNDING.match(text):
                    value = _FUNDING.sub("", text).strip()
                    if value and value != "-" and len(value) > 5:
                        return value
        return None

    def parse_references(self):
        box = self.soup.find(id="collapseThree")
        if box is None:
            return [], False
        refs, numbers = [], []
        for tr in box.find_all("tr"):
            tds = tr.find_all("td", recursive=False)
            if len(tds) < 2:
                continue
            body = tds[1].select_one(".magtech_ref_source, .mag_xml_publish_ref")
            if body is None:
                continue
            raw = _text(body)
            link = tds[1].find("a", href=_DOI)
            doi = _DOI.search(link["href"]).group(1) if link is not None else None
            m = _REF_NUMBER.match(_text(tds[0]))
            if m is None and refs:  # a second part or a translation of the reference above
                refs[-1]["raw"] = f'{refs[-1]["raw"]} {raw}'.strip()
                refs[-1]["doi"] = refs[-1]["doi"] or doi
                continue
            if not raw:
                continue
            numbers.append(int(m.group(1)) if m else None)
            refs.append({"position": len(refs) + 1, "raw": raw, "doi": doi})
        badge = box.find_previous(class_="badge")
        stated = re.sub(r"\D", "", badge.get_text()) if badge is not None and box.find_previous(
            id="reference") is not None and badge.find_parent(id="reference") is not None else ""
        complete = bool(refs) and numbers == list(range(1, len(refs) + 1)) and stated == str(len(refs)) and all(
            len(r["raw"]) > 10 for r in refs)
        return refs, complete

    def parse(self):
        references, complete = self.parse_references()
        return {
            "authors": self.parse_authors(),
            "abstract": self.parse_abstract(),
            "funding_statement": self.parse_funding_statement(),
            "references": references,
            "references_complete": complete,
        }
