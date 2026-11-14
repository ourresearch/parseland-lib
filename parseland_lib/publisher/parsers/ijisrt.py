"""IJISRT (International Journal of Innovative Science and Research Technology, ijisrt.com) article pages (oxjob #2210).

The site runs its own PHP template with no citation_* meta tags. On an article page the Authors tab
(div#authors) holds "Authors : A; B; C", the DOI link (prefix 10.38124/ijisrt) and, after a "References :"
paragraph, the reference list as one <ol> (a few pages continue it in a second <ol> whose first item carries
value="n"). The Abstract tab (div#profile) holds the abstract on every page, including the older layout that has
no "Abstract :" paragraph in the Authors tab. Pages show no affiliations, corresponding-author marks,
acknowledgments or funding statements.
"""
import re
from urllib.parse import unquote

from bs4 import NavigableString

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import cleanup_raw_name

DOI_LINK = re.compile(r"doi\.org/10\.38124/ijisrt", re.I)
HONORIFIC = re.compile(r"^(?:dr|prof|shri|smt)(?:\.\s*|\s+)", re.I)
DOI_IN_TEXT = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>\[\]©&]+)")
LEADING_NUMBER = re.compile(r"^\s*\[?\d{1,3}[\].)]\s+")
SHOW_MORE = re.compile(r"\b(show|load|view|see) (more|all)\b", re.I)


def _text(tag, sep=""):
    return re.sub(r"\s+", " ", tag.get_text(sep)).strip()


class IJISRT(PublisherParser):
    parser_name = "ijisrt"
    # the pages show no affiliations; another parser's affiliation guesses must not win over this byline
    prefer_publisher_authors_over_generic = True

    def _pane(self):
        return self.soup.find("div", id="authors")

    def is_publisher_specific_parser(self):
        pane = self._pane()
        return bool(pane and pane.find("a", href=DOI_LINK))

    def authors_found(self):
        return self.is_publisher_specific_parser() and self._labelled("Authors") is not None

    def _labelled(self, label):
        """The bold label `label` ("Authors : ...") that opens a paragraph in the Authors tab."""
        for strong in self._pane().find_all("strong"):
            if strong.get_text(strip=True).rstrip(" :") == label and strong.parent.name == "p":
                return strong
        return None

    def parse_authors(self):
        strong = self._labelled("Authors")
        text = _text(strong.parent, " ")
        text = text.split(":", 1)[1] if ":" in text else text
        authors = []
        for raw in text.split(";"):
            name = cleanup_raw_name(HONORIFIC.sub("", raw.strip()))
            if name:
                authors.append({"name": name, "affiliations": [], "is_corresponding": False})
        return authors

    def parse_abstract(self):
        pane = self.soup.find("div", id="profile")
        abstract = _text(pane, " ") if pane else ""
        return abstract or None

    def parse_references(self):
        """(references, complete). Complete only when the items number 1..n with no gap and no reference text sits
        outside the lists' items (no "show more" either)."""
        strong = self._labelled("References")
        if strong is None:
            return [], False
        pane, head = self._pane(), strong.parent
        lists = [ol for ol in head.find_all_next("ol") if pane in ol.parents and not ol.find_parent("li")]
        refs, numbers_ok, expected = [], True, 1
        for ol in lists:
            start = ol.get("start", "")
            number = int(start) if start.isdecimal() else 1
            for li in ol.find_all("li", recursive=False):
                if li.get("value", "").isdecimal():
                    number = int(li["value"])
                numbers_ok = numbers_ok and number == expected
                raw = LEADING_NUMBER.sub("", _text(li))
                if raw:
                    refs.append({"position": len(refs) + 1, "raw": raw, "doi": self._doi(li, raw)})
                number += 1
                expected += 1
        after = [s for s in head.find_all_next(string=True)
                 if type(s) is NavigableString and s.parent is not strong and pane in s.parents]
        stray = any(s.strip() and not any(p.name == "ol" for p in s.parents) for s in after)
        more = SHOW_MORE.search(" ".join(after))
        complete = bool(refs) and numbers_ok and not stray and not more
        return refs, complete

    @staticmethod
    def _doi(li, raw):
        for text in [unquote(a["href"]) for a in li.find_all("a", href=True)] + [raw]:
            if m := DOI_IN_TEXT.search(text):
                doi = m.group(1).rstrip(".,;:-")
                while doi.endswith(")") and doi.count(")") > doi.count("("):
                    doi = doi[:-1].rstrip(".,;:-")
                return doi
        return None

    def parse(self):
        references, complete = self.parse_references()
        return {"authors": self.parse_authors(),
                "abstract": self.parse_abstract(),
                "acknowledgments": None,
                "funding_statement": None,
                "references": references,
                "references_complete": complete}
