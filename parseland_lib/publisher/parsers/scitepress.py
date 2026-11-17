"""SciTePress Digital Library (www.scitepress.org) paper pages (oxjob #2338).

The site is an ASP.NET WebForms app whose spans are named for their field (ContentPlaceHolder1_LinkPaperPage_
LinkPaperContent_...). Its citation_author tags carry names only (sometimes one twice), so the generic reader found
no affiliations, and the abstract is printed as a visible span cut at about 1,000 characters plus a hidden "(More)"
span with the rest, so the generic reader kept nothing on long abstracts. This reads the byline and joins the spans.
"""
import re

from parseland_lib.publisher.parsers.parser import PublisherParser

_ID = "ContentPlaceHolder1_LinkPaperPage_LinkPaperContent_"
_BYLINE_SPAN = re.compile("^" + _ID + r"(?:Authors|Affiliations)Repeater_")
_AUTHOR = re.compile(r"AuthorsRepeater_LabelAuthor_(\d+)$")
_AUTHOR_NUMBER = re.compile(r"AuthorsRepeater_NumbersRepeater_(\d+)_Number_\d+$")
_AFF = re.compile(r"AffiliationsRepeater_LabelAffiliation_(\d+)$")
_AFF_NUMBER = re.compile(r"AffiliationsRepeater_NumbersRepeater_(\d+)_Number_\d+$")


def _clean(text):
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip(" ,;")


def _head_title(soup):
    """The <title> in <head>, reached through direct children only: every parser's authors_found() runs on every DOI
    page, so the claim must cost next to nothing on pages that are not this site's (#2239: under 0.5 ms a page)."""
    root = soup.find("html", recursive=False) or soup
    head = root.find("head", recursive=False)
    title = head.find("title", recursive=False) if head else None
    return title.get_text(strip=True) if title else ""


class SciTePress(PublisherParser):
    parser_name = "scitepress"
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        # "SciTePress - Publication Details"; the site's proceedings, home and error pages have no byline spans.
        return _head_title(self.soup).lower().startswith("scitepress")

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(
            self.soup.find("span", id=_ID + "AuthorsRepeater_LabelAuthor_0"))

    def parse_authors(self):
        names, author_nums, affs, aff_nums = {}, {}, {}, {}
        for span in self.soup.find_all("span", id=_BYLINE_SPAN):
            sid = span["id"]
            if m := _AUTHOR.search(sid):
                names[int(m.group(1))] = _clean(span.get_text(" "))
            elif m := _AUTHOR_NUMBER.search(sid):
                author_nums.setdefault(int(m.group(1)), []).append(span.get_text(strip=True))
            elif m := _AFF.search(sid):
                affs[int(m.group(1))] = _clean(span.get_text(" "))
            elif m := _AFF_NUMBER.search(sid):
                aff_nums.setdefault(int(m.group(1)), []).append(span.get_text(strip=True))

        whole_list = list(dict.fromkeys(affs[i] for i in sorted(affs) if affs[i]))
        by_number = {}
        for i in sorted(affs):
            for n in aff_nums.get(i, []) if affs[i] else []:
                by_number.setdefault(n, affs[i])
        # Superscript numbers tie affiliations to authors. Without them (one affiliation, printed with empty
        # superscripts, or a list with none) the page leaves the linking open: every author gets the whole list
        # (label-v1 "unlinked").
        linked = len(whole_list) > 1 and by_number and any(author_nums.values())

        authors = []
        for i in sorted(names):
            if not names[i]:
                continue
            if linked:
                own = list(dict.fromkeys(by_number[n] for n in author_nums.get(i, []) if n in by_number))
            else:
                own = list(whole_list)
            authors.append({"name": names[i], "affiliations": own, "is_corresponding": None})
        return authors

    def parse_abstract(self):
        shown = self.soup.find("span", id=_ID + "LabelAbstract")
        if not shown:
            return None
        rest = self.soup.find("span", id=_ID + "MoreAbstract")
        # The cut falls anywhere, often mid-word: the two spans join with nothing between them.
        text = re.sub(r"\s+", " ", shown.get_text() + (rest.get_text() if rest else "")).strip()
        return text or None

    def parse(self):
        return {"authors": self.parse_authors(), "abstract": self.parse_abstract()}
