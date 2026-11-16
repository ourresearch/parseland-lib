"""Rhhz (Beijing Renhe Huizhi) journal platform, used by ~60 mostly Chinese journal sites (oxjob #2268).

AIMS Press, AIMS Sciences, Maxapress, The Innovation, Acta Physica Sinica (wulixb.iphy.ac.cn), Acta Petrologica
Sinica (ysxb.ac.cn), Chinese Optics, Chinese Journal of Space Science and many more run the same article page:

    <ul class="article-author">
      <li><a class="mainColor" data-relate="EMAIL">NAME</a>
          <sup class="authorTag"><a|span class="com-num" data-tagVal="1,2">1,2</a|span>
              <a|span class="com-user" title="Corresponding Author: NAME, EMAIL"></a|span> ...</sup></li>
    </ul>
    <ul class="about-author|addresswrap">
      <li class="article-author-address"><span>1.</span><p|div class="lostOf">AFFILIATION</p|div></li>
    </ul>
    <h6 class="com-author-info"><b>通讯作者:</b> NAME, E-mail ...</h6>
    <li class="com-author-info article-fundPrjs"><div><b>基金项目:</b> FUNDING</div></li>
    <div class="References-wrap"><table class="reference-tab"><tr class="document-box">
      <td class="td1">[1]</td><td class="td2">REFERENCE</td></tr> ...

The page's meta tags list every citation_author before every citation_author_institution, unlinked (and AIMS pages
repeat the citation_author tags), so the generic parser hung all affiliations on the last author or none.
Bilingual pages print the byline twice (Chinese, then English); the first byline is the page's, as in the gold.
Not read: the hidden "author-box" pop-up (a template sample with a fixed name), the client-rendered variant
(zoores.ac.cn, ati.ac.cn: its byline carries no authorTag and no affiliations), and acknowledgments (a few
full-text pages, each marked up differently).
"""
import copy
import re

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser

_CORR_LABEL = re.compile(r"(?:通[信讯]作者|corresponding\s+authors?)\s*[:：]?", re.I)
# where a "通讯作者: ..." line ends: the next label in the author-info block
_LINE_END = re.compile(r"作者简介|基金项目|通[信讯]作者|corresponding\s+authors?|funds?\s*[:：]|fund project|"
                       r"about the authors?|收稿日期|received\s*[:：]|contributed equally|equal(?:ly)? contribut|"
                       r"共同第一作者", re.I)
_FUND_LABEL = re.compile(r"^\s*(?:基金项目|资助项目|funds?|fund projects?|funding|supported by)\s*[:：]\s*", re.I)
_CJK = re.compile(r"[\u3400-\u9fff]")
_LEADING_LABEL = re.compile(r"^\s*([0-9]{1,2}|[a-z])\s*[.\u3001)\uff09]\s*(?=\S)", re.I)  # "1. Institute ...": label in the text
# "Academic Editor: ...", "These authors contributed equally": notes printed in the address list
_NOT_AFFILIATION = re.compile(r"^\s*(?:(?:academic|handling|guest)?\s*editors?\s*[:\uff1a]|these authors contributed|"
                              r"contributed equally|equal(?:ly)? contribut)", re.I)
_INNER_LABEL = re.compile(r"[(\uff08](\d{1,2})[)\uff09]")  # old Acta Physica Sinica: "(1)X; (2)Y" in one item
# "1 X; 2 Y; 3 Z" in one item (Nuclear Physics Review): a bare number opening the item or following a semicolon
_LISTED_LABEL = re.compile(r"(?:^|[;\uff1b])\s*(\d{1,2})\s*[.\u3001]?\s+(?=[^\W\d_])")
_BARE_LABEL = re.compile(r"^\s*(\d{1,2})\s+(?=[^\W\d_])")  # "1 School of ...": a number and a space, no stop
_ET_AL = re.compile(r"^(?:et\.?\s*al\.?|\u7b49)$", re.I)  # "et al." / "等" closing a shortened byline: not an author
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_DOI = re.compile(r"\b(10\.\d{4,9}/\S+)")
_STATED_COUNT = re.compile(r"(?:参考文献|references)\s*[(（]\s*(\d+)\s*[)）]", re.I)
_MORE = re.compile(r"show more|load more|view all|更多", re.I)
# the link buttons each reference row ends with ("CrossRef", "Google Scholar"): site widgets, not the reference
_REF_BUTTON = re.compile(r"^\s*(?:cross\s?ref|google\s+scholar|pub\s?med|百度学术|cnki)\s*$", re.I)
# the platform's stylesheets and scripts (style/web/css/public/base/base.css, style/web/js/public/rhhz.js ...)
_ASSETS = "style/web/"


def _template_head(soup):
    """The claim's cheap first test: does <head> carry the platform's marks, a citation_state meta tag or a link or
    script from its assets? Each is on all 170 claimed pages of 1,892 stored ones (46 sites). Every parser's claim runs
    on every page (#2239: under 0.5 ms a page it does not claim), so <head> is reached through direct children only
    and searched alone. None when there is no <head>: such a page is searched whole, as before."""
    html = soup.find("html", recursive=False)
    head = (html or soup).find("head", recursive=False)
    if head is None:
        return None
    for tag in head.find_all(("meta", "link", "script")):
        if tag.name == "meta":
            if (tag.get("name") or "").lower() == "citation_state":
                return True
        elif _ASSETS in (tag.get("href") or tag.get("src") or ""):
            return True
    return False


def _text(tag):
    return " ".join(tag.get_text(" ", strip=True).split()) if tag is not None else ""


def _split_numbered(text):
    """[(label, text)] when one address item holds a numbered list ("(1)X; (2)Y", "1 X; 2 Y; 3 Z"), else None."""
    marks = list(_INNER_LABEL.finditer(text))
    if len(marks) < 2 or text[:marks[0].start()].strip(" ;\uff1b,\uff0c"):
        marks = list(_LISTED_LABEL.finditer(text))  # bare numbers: only a list numbered 1, 2, 3 ... from the start
        if len(marks) < 2 or marks[0].start() or [m.group(1) for m in marks] != [str(i) for i in range(1, len(marks) + 1)]:
            return None
    ends = [m.start() for m in marks[1:]] + [len(text)]
    return [(m.group(1), text[m.end():end]) for m, end in zip(marks, ends)]


class Rhhz(PublisherParser):
    parser_name = "rhhz"
    # the byline is better than the meta tags (repeated citation_author tags, unlinked institutions)
    prefer_publisher_authors_over_generic = True

    def _byline(self):
        """The page's first byline: a ul.article-author whose items carry a name and the template's authorTag."""
        if not hasattr(self, "_byline_found"):  # authors_found, parse and the claim each ask: look once per page
            self._byline_found = (None, [])
            for block in self.soup.select("ul.article-author"):
                if block.find_parent(class_="author-box"):
                    continue
                items = [li for li in block.find_all("li", recursive=False) if li.select_one("a.mainColor")]
                if items and block.select_one("li > sup.authorTag"):
                    self._byline_found = (block, items)
                    break
        return self._byline_found

    def is_publisher_specific_parser(self):
        if not hasattr(self, "_claim"):  # authors_found asks too: the head test runs once per page
            self._claim = _template_head(self.soup) is not False and self._byline()[0] is not None
        return self._claim

    def authors_found(self):
        return self.is_publisher_specific_parser()  # a byline is found only with its items

    # ---- authors and affiliations ----

    def _addresses(self, block):
        """[(label, text)] of the li.article-author-address items after this byline and before the next one."""
        items = []
        for el in block.find_all_next(["ul", "li"]):
            classes = el.get("class") or []
            if el.name == "ul" and "article-author" in classes:
                break
            if el.name != "li" or "article-author-address" not in classes or el.find_parent(class_="author-box"):
                continue
            span = el.find("span")
            label = re.sub(r"[\s.:：、)）]", "", span.get_text()) if span else ""
            body = el.select_one(".lostOf")
            if body is not None:
                text = _text(body)
            else:
                text = _text(el)
                if span is not None:
                    text = text.replace(_text(span), "", 1)
            items.append((label, text))
        lists = [_split_numbered(text) for _, text in items]
        bare = [_BARE_LABEL.match(text) for _, text in items]
        if (items and not any(lists) and not any(label for label, _ in items) and all(bare)
                and [m.group(1) for m in bare] == [str(i) for i in range(1, len(items) + 1)]):
            # "1 School of ...", "2 Bureau ...": every item opens with a bare number, 1, 2, 3 in order
            items = [(m.group(1), text[m.end():]) for m, (_, text) in zip(bare, items)]
        out = []
        for (label, text), listed in zip(items, lists):
            if listed:  # one item, several affiliations
                pairs = listed
            else:
                if not label and (m := _LEADING_LABEL.match(text)):
                    label, text = m.group(1), text[m.end():]
                pairs = [(label, text)]
            for label, text in pairs:
                text = text.strip(" ;；,，")
                if text and not _NOT_AFFILIATION.match(text) and (label, text) not in out:
                    out.append((label, text))
        return out

    @staticmethod
    def _tags(li):
        tokens = []
        for tag in li.select(".com-num"):
            value = tag.get("data-tagval") or tag.get("data-tagVal") or tag.get_text()
            tokens += [t for t in re.split(r"[\s,，;；]+", value) if t]
        return tokens

    @staticmethod
    def _emails(li):
        found = []
        name = li.select_one("a.mainColor")
        for value in [name.get("data-relate", "") if name else ""] + [t.get("title", "") for t in li.select(
                ".com-user, .com-mail")]:
            found += [e.lower() for e in _EMAIL.findall(value)]
        return found

    def parse_authors(self):
        block, items = self._byline()
        if block is None:
            return []
        addresses = self._addresses(block)
        by_label = {label: text for label, text in addresses if label}
        tags = [self._tags(li) for li in items]
        authors = []
        for li, tokens in zip(items, tags):
            name = " ".join(li.select_one("a.mainColor").get_text(" ", strip=True).split())
            if not name or _ET_AL.match(name):
                continue
            if len(addresses) == 1:
                affs = [addresses[0][1]]  # one affiliation: every author's, labelled or not
            elif not any(tags):
                affs = [text for _, text in addresses]  # no markers anywhere: unlinked, everyone gets the list
            else:
                affs = [by_label[t] for t in tokens if t in by_label]
            authors.append({"name": name, "affiliations": list(dict.fromkeys(affs)), "is_corresponding": None,
                            "_li": li})
        self._mark_corresponding(authors)
        for author in authors:
            del author["_li"]
        return authors

    def _corresponding_lines(self):
        """The text after each "通讯作者:" / "Corresponding author:" label in the author-info blocks."""
        lines = []
        for box in self.soup.select("ul.about-author, ul.about-article, .com-author-info"):
            if box.find_parent(class_="author-box"):
                continue
            text = _text(box)
            for m in _CORR_LABEL.finditer(text):
                rest = text[m.end():]
                end = _LINE_END.search(rest)
                rest = (rest[:end.start()] if end else rest)[:400].strip()
                if rest:
                    lines.append(rest)
        return lines

    def _mark_corresponding(self, authors):
        # 1. the template's corresponding icon, when its title says so ("Corresponding Author: NAME, EMAIL")
        for author in authors:
            for icon in author["_li"].select(".com-user"):
                if _CORR_LABEL.match((icon.get("title") or "").strip()):
                    author["is_corresponding"] = True
        # 2. a "通讯作者: NAME" / "Corresponding author: EMAIL" line naming the author (an icon without a label
        # is explained only by such a line)
        if not any(a["is_corresponding"] for a in authors):
            lines = self._corresponding_lines()
            if lines:
                text = " | ".join(lines)
                low = text.lower()
                for author in sorted(authors, key=lambda a: -len(a["name"])):
                    name = author["name"]
                    if _CJK.search(name):
                        hit = name in text
                    else:
                        hit = re.search(r"(?<!\w)" + re.escape(name.lower()) + r"(?!\w)", low) is not None
                    if hit:
                        text = text.replace(name, " ")
                        low = text.lower()
                    if hit or any(e in low for e in self._emails(author["_li"])):
                        author["is_corresponding"] = True
        # 3. no corresponding icon on the byline at all: an envelope (mailto icon) beside some authors, not every
        # author, is the page's mark
        if not any(a["is_corresponding"] for a in authors) and not any(a["_li"].select(".com-user") for a in authors):
            mailed = [a for a in authors if a["_li"].select(".com-mail")]
            if mailed and len(mailed) < len(authors):
                for author in mailed:
                    author["is_corresponding"] = True
        if any(a["is_corresponding"] for a in authors):
            for author in authors:
                author["is_corresponding"] = bool(author["is_corresponding"])

    # ---- funding statement and references ----

    def parse_funding_statement(self):
        texts = []
        for tag in self.soup.select(".article-fundPrjs, li.fundwrap"):
            if tag.find_parent(class_="author-box") or tag.find_parent(class_="article-fundPrjs"):
                continue
            text = _FUND_LABEL.sub("", _text(tag)).strip()
            if text and text not in texts:
                texts.append(text)
        if not texts:
            return None
        # several language versions: the English one, else the first (the rubric's abstract rule)
        english = [t for t in texts if not _CJK.search(t)]
        return english[0] if english else texts[0]

    def parse_references(self):
        """(references, references_complete) from the first reference table on the page."""
        wrap = next((w for w in self.soup.select("div.References-wrap") if w.select("tr.document-box")), None)
        if wrap is None:
            return None, False
        refs, numbers = [], []
        for row in wrap.select("tr.document-box"):
            cell = row.select_one("td.td2")
            if cell is None:
                continue
            shown = copy.copy(cell)  # never edit the page
            for link in shown.find_all("a"):
                if _REF_BUTTON.match(link.get_text()) or "crossref-img" in (link.get("class") or []):
                    link.decompose()
            raw = re.sub(r"\s+([,.;:])", r"\1", _text(shown))  # "<i>Title</i>, 2019": no space before the comma
            if not raw:
                continue
            num = row.select_one("td.td1")
            digits = re.sub(r"\D", "", num.get_text()) if num else ""
            if digits:
                numbers.append(int(digits))
            doi = None
            for link in cell.find_all("a", href=True):
                m = _DOI.search(link["href"].replace("%2F", "/"))
                if m and "doi.org/" in link["href"]:
                    doi = m.group(1).rstrip(".,;")
                    break
            refs.append({"position": len(refs) + 1, "raw": raw, "doi": doi})
        if not refs:
            return None, False
        stated = [int(n) for n in _STATED_COUNT.findall(_text(self.soup.body) if self.soup.body else "")]
        if numbers:
            complete = len(numbers) == len(refs) and numbers == list(range(1, len(refs) + 1))
            complete = complete and all(n == len(refs) for n in stated)
        else:
            complete = bool(stated) and all(n == len(refs) for n in stated)
        if _MORE.search(_text(wrap)[-200:]):
            complete = False
        return refs, complete

    def parse_abstract(self):
        # the generic parser's own abstract chain, so the abstract the page gets today is kept as it is
        generic = GenericPublisherParser(self.soup)
        return (generic.parse_abstract_meta_tags(include_seo_tags=False)
                or generic.parse_structured_abstract_section()
                or generic.parse_printed_seo_description())

    def parse(self):
        references, complete = self.parse_references()
        return {
            "authors": self.parse_authors(),
            "abstract": self.parse_abstract(),
            "funding_statement": self.parse_funding_statement(),
            "references": references,
            "references_complete": complete,
        }
