"""EAI's European Union Digital Library (eudl.eu) paper pages (oxjob #2338).

One template serves EAI's proceedings papers and journal articles. <section id="authors"> prints the byline (each
name followed by <sup>1</sup> or <sup>1,2</sup>, and <sup>,*</sup> for a contact author), the numbered affiliation list
("1: Tianjin University of Technology") and "*Contact email: ...", which explains the star. The meta tags hold names
only, often without the middle name ("Sukma Yunianti" for "Sukma Shinta Yunianti"), and the Description tag is the
abstract cut at 300 characters; <section class="full-abstract"> prints it whole. So the generic reader found no
affiliations, a cut abstract, and a corresponding author only where an e-mail address spelled the name.
"""
import re

from bs4 import NavigableString, Tag

from parseland_lib.publisher.parsers.parser import PublisherParser

_AFF = re.compile(r"^\s*(\d+)\s*:\s*(.+?)\s*$", re.S)


def _spaced(text):
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def _clean(text):
    return _spaced(text).strip(" ,;")


def _head_title(soup):
    """The <title> in <head>, reached through direct children only: every parser's authors_found() runs on every DOI
    page, so the claim must cost next to nothing on pages that are not this site's (#2239: under 0.5 ms a page)."""
    root = soup.find("html", recursive=False) or soup
    head = root.find("head", recursive=False)
    title = head.find("title", recursive=False) if head else None
    return title.get_text() if title else ""


class EUDL(PublisherParser):
    parser_name = "eudl"
    # the byline gives full names; the citation_author tags drop middle names
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        # "<title> - EUDL" on every paper page (76 of 76 read); the site's listings carry no byline section
        return _head_title(self.soup).rstrip().endswith("- EUDL")

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self.soup.select_one("section#authors span.author-list"))

    def _affiliations(self, block):
        affs = {}
        for li in block.select("ul.affiliation-list > li"):
            if m := _AFF.match(li.get_text()):
                affs[m.group(1)] = _clean(m.group(2))
        return affs

    def parse_authors(self):
        block = self.soup.select_one("section#authors")
        byline = block.select_one("span.author-list") if block else None
        if not byline:
            return []
        affs = self._affiliations(block)
        contact = block.select_one("section.corresponding-email")
        # the star is a contact mark only where the page explains it ("*Contact email: ...")
        star_explained = bool(contact and contact.get_text().strip().startswith("*"))

        authors = []
        for child in byline.children:
            if isinstance(child, Tag) and child.name == "sup":
                if not authors:
                    continue
                mark = child.get_text()
                if "*" in mark and star_explained:
                    authors[-1]["is_corresponding"] = True
                for num in re.findall(r"\d+", mark):
                    if (aff := affs.get(num)) and aff not in authors[-1]["affiliations"]:
                        authors[-1]["affiliations"].append(aff)
                continue
            text = child if isinstance(child, NavigableString) else child.get_text()
            # names come between the marks, separated by commas
            for part in str(text).split(","):
                if name := _clean(part):
                    authors.append({"name": name, "affiliations": [],
                                    "is_corresponding": False if star_explained else None})
        return authors

    def parse_abstract(self):
        block = self.soup.select_one("section.full-abstract > div")
        if not block:
            return None
        parts = [_spaced(p.get_text()) for p in block.find_all("p")] or [_spaced(block.get_text())]
        return " ".join(p for p in parts if p) or None

    def parse(self):
        return {"authors": self.parse_authors(), "abstract": self.parse_abstract()}
