"""CNKI (China National Knowledge Infrastructure) kcms8 article detail pages (oxjob #2289).

Many Chinese journals' DOIs (10.13474, 10.16538, 10.13386 ... "j.cnki" in the DOI) resolve to CNKI's own detail page
(kns.cnki.net/kcms8/detail), which carries no citation meta tags, so the generic parser read nothing:

    <div class="wx-tit"><h1>TITLE</h1>
      <h3 class="author" id="authorpart"><span><a onclick="TurnPageToKnetV('au',...)">NAME<sup>1,2</sup></a>
          <input class="authorcode" type="hidden" ...></span> ...</h3>
      <h3><a class="author">1. AFFILIATION</a> ... &nbsp;&nbsp;3. AFFILIATION&nbsp;&nbsp; ...</h3>   (numbered)
      <h3><span><a class="author">AFFILIATION</a></span><span> AFFILIATION </span></h3>         (unlinked)
    </div>
    <span id="ChDivSummary" class="abstract-text">ABSTRACT</span>
    <div class="row"><span class="rowtit">基金资助：</span><p class="funds"><a>FUND（NUMBER）；</a> ...</p></div>

Numbered affiliations follow the byline's superscripts; unnumbered ones carry no link to any author, so every author
gets each of them (the labelling rubric's "unlinked"). An affiliation CNKI has no institution page for is bare text
between the links. When an article has no abstract the page shows the body's opening lines marked "＜正＞" instead:
not an abstract. The page shows no corresponding author, no acknowledgments, and loads its reference list into an
iframe, so none of those are read. Bylines are in the article's language (Chinese characters on most pages).
"""
import re

from bs4 import Comment, NavigableString, Tag

from parseland_lib.publisher.parsers.parser import PublisherParser

_NUMBERED = re.compile(r"^(\d{1,2})\s*[.\uff0e\u3001]\s*(\S.*)$", re.S)  # "1. Department ..." / "2．学院"
_MARK_SPLIT = re.compile(r"[,\uff0c\u3001\s]+")
_RANGE = re.compile(r"^(\d{1,2})[-\u2013](\d{1,2})$")
_GAP = re.compile(r"\u00a0{2,}")  # bare-text affiliations are set off by &nbsp;&nbsp;
_NAME_TRIM = " \t\r\n\u00a0;,\uff1b\uff0c"
_FUND_TRIM = " \t\r\n\u00a0;\uff1b~\uff5e"
_BODY_EXCERPT = re.compile(r"^\s*(?:\uff1c|<|&lt;)\u6b63(?:\uff1e|>|&gt;)")  # "＜正＞": the body's opening lines


def _cnki_head(soup):
    """The claim's cheap first test: does <head> link CNKI's kcms detail assets (piccache.cnki.net/.../kcms8/detail/)?
    Every parser's claim runs on every DOI page (#2239: under 0.5 ms a page it does not claim), so <head> is reached
    through direct children only and only its link and script tags are read."""
    html = soup.find("html", recursive=False)
    head = (html or soup).find("head", recursive=False)
    if head is None:
        return False
    for tag in head.find_all(("link", "script")):
        url = tag.get("href") or tag.get("src") or ""
        if "cnki.net/" in url and "/kcms" in url:
            return True
    return False


def _clean(text):
    return " ".join(text.split())


class Cnki(PublisherParser):
    parser_name = "cnki"
    # the byline is the page's only author list (no meta tags)
    prefer_publisher_authors_over_generic = True

    def _byline(self):
        """h3#authorpart, found once per page and only after the head test passed."""
        if not hasattr(self, "_byline_found"):
            self._byline_found = None
            if _cnki_head(self.soup):
                block = self.soup.find("h3", id="authorpart")
                if block is not None and block.find("span", recursive=False) is not None:
                    self._byline_found = block
        return self._byline_found

    def is_publisher_specific_parser(self):
        return self._byline() is not None

    def authors_found(self):
        return self.is_publisher_specific_parser()

    # ---- authors and affiliations ----

    @staticmethod
    def _marks(sup):
        out = []
        for part in _MARK_SPLIT.split(sup.get_text(" ", strip=True)):
            if m := _RANGE.match(part):
                out.extend(str(i) for i in range(int(m.group(1)), int(m.group(2)) + 1))
            elif part.isdecimal():
                out.append(str(int(part)))
        return out

    def _names(self, block):
        """[(name, [label])] in byline order."""
        out = []
        for span in block.find_all("span", recursive=False):
            node = span.find("a") or span
            name = "".join(s for s in node.find_all(string=True) if s.find_parent("sup") is None)
            name = _clean(name).strip(_NAME_TRIM)
            if name:
                sup = node.find("sup") or span.find("sup")
                out.append((name, self._marks(sup) if sup is not None else []))
        return out

    @staticmethod
    def _affiliation_items(h3):
        items = []
        for child in h3.children:
            if isinstance(child, Comment):
                continue
            if isinstance(child, NavigableString):
                items.extend(_GAP.split(str(child)))
            elif isinstance(child, Tag) and child.name not in ("script", "style", "input"):
                items.append(child.get_text(" ", strip=True))
        return [t for t in (_clean(i).strip(" ;\uff1b") for i in items) if t]

    def _authors(self):
        block = self._byline()
        names = self._names(block)
        sib = block.find_next_sibling()
        items = self._affiliation_items(sib) if sib is not None and sib.name == "h3" else []
        numbered = [_NUMBERED.match(i) for i in items]
        authors = [{"name": n, "affiliations": [], "is_corresponding": False} for n, _ in names]
        if items and all(numbered) and any(marks for _, marks in names):
            by_label = {}
            for m in numbered:
                by_label.setdefault(str(int(m.group(1))), _clean(m.group(2)))
            for author, (_, marks) in zip(authors, names):
                author["affiliations"] = list(dict.fromkeys(by_label[k] for k in marks if k in by_label))
        elif items and not any(marks for _, marks in names):
            # nothing links an affiliation to an author: every author gets every one ("unlinked")
            affs = list(dict.fromkeys(_clean(m.group(2)) if m else i for i, m in zip(items, numbered)))
            for author in authors:
                author["affiliations"] = list(affs)
        return authors

    # ---- abstract and funding ----

    def _abstract(self):
        span = self.soup.find("span", id="ChDivSummary")
        if span is None:
            return None
        text = _clean(span.get_text(""))
        if not text or _BODY_EXCERPT.match(text):
            return None
        return text

    def _funding(self):
        p = self.soup.find("p", class_="funds")
        if p is None:
            return None
        text = _clean(p.get_text("")).rstrip(_FUND_TRIM)
        return text or None

    def parse(self):
        return {
            "authors": self._authors(),
            "abstract": self._abstract(),
            "acknowledgments": None,
            "funding_statement": self._funding(),
            "references": None,
            "references_complete": False,
        }
