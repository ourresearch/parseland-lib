"""Galenos Publishing House journal system (oxjob #2268).

About 50 Turkish medical journals (hasekidergisi.com, jcrpe.org, turkjps.org, eajem.com, tjtcvs.org ...) run Galenos's
Nuxt journal system. Every page loads its images from Galenos's CloudFront host and ends with a "Galenos Publishing
House" footer; that pair is the claim (one site's domain would miss the other 50). The article page prints:

- the byline: one <a role="link"> per author, the name in <span class="... ms-2 text-nowrap"> with the affiliation
  numbers in <sup>, and a mail icon (<span class="ms-1">) after the corresponding author;
- the numbered affiliations in the "Author Information" panel (the first panel after the byline's buttons);
- the abstract in <div id="abstract">, structured-abstract labels as <p class="font-semibold">;
- the back matter as <div class="py-2"> blocks: an <h3> heading ("Acknowledgments") or a <strong> label
  ("Financial Disclosure:", "Funding:");
- the reference list in <div id="references">, one <span class="refnum"> number per entry, the entry's DOI on its
  "CrossRef" link.

The page state (__NUXT_DATA__) flags the corresponding author too (isCorrespondingAuthor); an author with no e-mail
gets the highlight but no mail icon, and the flag is the page's statement for them (label-v1: embedded page state
counts). Issue listings and error shells (no "Author Information" panel) are not read.
"""
import html
import json
import re

from bs4 import Comment

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

CDN = "d2v96fxpocvxx.cloudfront.net"  # Galenos's asset host: every journal's logo, favicon and figures
FOOTER = re.compile(r"Galenos Publishing House")
NUMBER = re.compile(r"\d+")
ACK_LABEL = re.compile(r"^acknowledge?ments?$", re.I)
FUNDING_LABEL = re.compile(r"^(?:financial disclosures?|funding(?: information| sources?| statement)?|financial support"
                           r"|sources? of funding|grant support)$", re.I)
MORE = re.compile(r"\b(?:show|load|view|see) (?:more|all)\b", re.I)
MAX_AUTHORS = 100  # more name spans than this is a listing, not one article's byline


def _label_key(label):
    label = squash(label).rstrip(":. ")
    return "acknowledgments" if ACK_LABEL.match(label) else (
        "funding_statement" if FUNDING_LABEL.match(label) else None)


def _own_text(span):
    """The name in a byline span: its own text, without the <sup> numbers or Vue's empty comments."""
    return squash("".join(s for s in span.find_all(string=True, recursive=False) if not isinstance(s, Comment)))


class Galenos(PublisherParser):
    parser_name = "galenos"
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        if getattr(self, "_claim", None) is None:
            head = self.soup.head or self.soup
            on_cdn = any(CDN in (t.get("content") or t.get("href") or "") for t in head.find_all(["meta", "link"]))
            self._claim = on_cdn and self.soup.find(string=FOOTER) is not None
        return self._claim

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
        if not self.is_publisher_specific_parser():
            return out
        button = self.soup.find(lambda t: t.name == "button" and squash(t.get_text()) == "Author Information")
        if button is None:
            return out  # an issue listing or an error shell: no article header
        out["authors"] = self._authors(button)
        article = self.soup.select_one("div.article")
        if article is not None:
            out["abstract"] = self._abstract(article)
            out.update(self._back_matter(article))
            out["references"], out["references_complete"] = self._references(article)
        return out

    # ---- byline ----

    def _authors(self, button):
        spans = [s for s in button.find_all_previous("span", class_="text-nowrap")
                 if "ms-2" in s.get("class", []) and s.find_parent("a", attrs={"role": "link"}) is not None]
        spans.reverse()
        if not spans or len(spans) > MAX_AUTHORS:
            return []
        flagged = self._flagged_names()
        affs = self._affiliations(button)
        authors = []
        for span in spans:
            name = _own_text(span)
            if not name:
                continue
            numbers = NUMBER.findall(" ".join(s.get_text() for s in span.find_all("sup")))
            authors.append({"name": name, "numbers": numbers,
                            "is_corresponding": self._mail_icon(span) or name.casefold() in flagged})
        numbered = any(a["numbers"] for a in authors)
        texts = [t for _, t in affs]
        by_number = dict(affs)
        for a in authors:
            if numbered:
                a["affiliations"] = [by_number[n] for n in a["numbers"] if by_number.get(n)]
                if not a["numbers"] and len(texts) == 1:
                    a["affiliations"] = list(texts)
            else:
                a["affiliations"] = list(texts)  # no numbers: the page lists them without saying who has which
            del a["numbers"]
        return authors

    @staticmethod
    def _mail_icon(span):
        icon = span.find_next_sibling("span")
        return bool(icon is not None and "ms-1" in icon.get("class", []) and (
            icon.find("svg") is not None or icon.find(class_=re.compile("mail")) is not None))

    def _flagged_names(self):
        """Names the page state flags isCorrespondingAuthor (devalue: every value is an index into the array)."""
        script = self.soup.find("script", id="__NUXT_DATA__")
        if script is None:
            return set()
        try:
            data = json.loads(script.string or "")
        except ValueError:
            return set()
        if not isinstance(data, list):
            return set()

        def at(i):
            return data[i] if isinstance(i, int) and 0 <= i < len(data) else None

        return {squash(at(x["full_name"])).casefold() for x in data
                if isinstance(x, dict) and "full_name" in x and at(x.get("isCorrespondingAuthor")) is True
                and isinstance(at(x["full_name"]), str)}

    @staticmethod
    def _affiliations(button):
        """[(number, text)] from the "Author Information" panel, the first panel after the byline's buttons."""
        panel = button.parent.find_next_sibling("div") if button.parent is not None else None
        if panel is None:
            return []
        affs = []
        for item in panel.select("div.mb-1"):
            label = item.select_one("span.font-semibold")
            number = NUMBER.search(label.get_text()) if label is not None else None
            parts = [s for s in item.find_all(string=True) if not isinstance(s, Comment)
                     and (label is None or s.parent is not label)]
            text = squash(html.unescape(" ".join(parts)))  # some journals double-escape "&" in this panel
            affs.append((number.group(0) if number else str(len(affs) + 1), text))
        return affs

    # ---- abstract ----

    @staticmethod
    def _abstract(article):
        section = article.find(id="abstract")
        if section is None:
            return None
        paragraphs, label = [], None
        for p in section.find_all("p"):
            text = squash(p.get_text())
            first = p.find(True)
            if not text or (first is not None and "font-semibold" in first.get("class", [])
                            and squash(first.get_text()).lower().startswith("keywords")):
                continue  # the older skin prints "Keywords:" as a paragraph
            if "font-semibold" in p.get("class", []):
                label = text
                continue
            if label:
                text = f"{label}{' ' if label.endswith(':') else ': '}{text}"
                label = None
            paragraphs.append(text)
        return "\n".join(paragraphs) or None

    # ---- back matter ----

    @staticmethod
    def _back_matter(article):
        found = {}
        for block in article.select("div.py-2"):
            heading = block.find("h3")
            if heading is not None and (key := _label_key(heading.get_text())) and key not in found:
                body = heading.find_next_sibling("div")
                lines = []
                for item in (body.find_all("div", recursive=False) if body is not None else []):
                    text = squash(item.get_text())
                    strong = item.find("strong")
                    if text and not (strong is not None and squash(strong.get_text()) == text):
                        lines.append(text)  # not a lone label ("Footnotes", "DISCLOSURES") closing the block
                if lines:
                    found[key] = "\n".join(lines)
            for item in block.find_all("div"):
                strong = item.find(True)
                if strong is None or strong.name != "strong" or not squash(item.get_text()).startswith(
                        squash(strong.get_text())):
                    continue  # a label opens the item: "<strong>Financial Disclosure:</strong> The authors ..."
                if not (key := _label_key(strong.get_text())) or key in found:
                    continue
                rest = [s for s in item.find_all(string=True) if not isinstance(s, Comment)
                        and not any(p is strong for p in s.parents)]
                if text := squash("".join(rest)):
                    found[key] = text
        return found

    # ---- references ----

    @staticmethod
    def _references(article):
        # imported here: back_matter imports the parsers package, which imports this module
        from parseland_lib.back_matter import _clean_doi, _pick_doi, _printed_doi
        section = article.find(id="references")
        if section is None:
            return None, False
        refs, numbers = [], []
        for num in section.select("span.refnum"):
            entry = num.find_next_sibling("div")
            if entry is None:
                continue
            text_div = entry.find("div", class_="break-words") or entry
            raw = squash(text_div.get_text())
            if not raw:
                continue
            link = entry.find("a", href=re.compile(r"doi\.org/10\."))
            doi = _pick_doi(_clean_doi(link["href"]) if link is not None else None, _printed_doi(raw))
            numbers.append(squash(num.get_text()))
            refs.append({"position": len(refs) + 1, "raw": raw, "doi": doi})
        if not refs:
            return None, False
        whole = (numbers == [str(i) for i in range(1, len(refs) + 1)]
                 and len(refs) == len(section.select("span.refnum"))
                 and not MORE.search(section.get_text(" ")))
        return refs, whole
