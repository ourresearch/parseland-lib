"""Acta Ecologica Sinica (生态学报, www.ecologica.cn) article pages (oxjob #2339).

The site runs Beijing Qinyun's (勤云) journal system. Its abstract page ships the byline empty
(<ul id="CnAuthorList"></ul>) and fills it in the browser from a JSON string in an inline script:

    var strAuthorsJson="{\\"authors\\":[{\\"cn_name\\":\\"...\\",\\"en_name\\":\\"...\\",\\"cn_institution\\":...}]}";

The stored page itself prints, under labels: 作者单位 (p#DisplayCnInstitutionValue: every author's institutions
joined by commas, no linking; empty on most pages from 2016 on), 基金项目 (p#CnFundProjectValue), Fund Project
(p#EnFundProjectValue: often a shortened version without grant numbers) and both abstracts. The reference list is
loaded later by Ajax, so a stored page holds none.

What it reads, as both blind labellers read the build pages (label-v1):
- authors: the JSON's cn_name in order (the Chinese byline, as in the page's citation line); en_name when cn_name is
  empty. The meta tags list the Chinese names and then the English ones (the generic parser read both as one byline)
  or join them in one tag.
- affiliations: the printed 作者单位 list, split at commas and semicolons (an English institution keeps its own
  commas), deduplicated, given to every author: the page does not say who has which. The JSON's per-author
  cn_institution is not read: the labels count only the printed list (#2339 RESULT.json, labels_you_think_are_wrong).
- corresponding: none. Every author's is_contact_author is empty (the site's script then draws the contact icon on
  every author), and one author carrying an e-mail is not a mark the page explains.
- abstract: None, so parse_page's own readers decide as before (every work in the sample already has an abstract).
- funding_statement: 基金项目, else Fund Project.
Not read: the site's old view_abstract.aspx pages (no strAuthorsJson; about 1 page in 80).
"""
import json
import re

from parseland_lib.publisher.parsers.parser import PublisherParser

JOURNAL = "生态学报"
_AUTHORS_JSON = re.compile(r'var\s+strAuthorsJson\s*=\s*"((?:[^"\\]|\\.)*)"')
_SEPARATOR = re.compile(r"([,，;；])")
_CJK = re.compile(r"[㐀-鿿]")
_WS = re.compile(r"\s+")


def _journal_tag(soup):
    """The claim's cheap first test: the citation_journal_title tag in <head> names the journal. Every parser's claim
    runs on every page (#2239: under 0.5 ms a page it does not claim), so <head> is reached through direct children
    only and its meta tags alone are searched."""
    html = soup.find("html", recursive=False)
    head = (html or soup).find("head", recursive=False)
    if head is None:
        return False
    for tag in head.find_all("meta"):
        if (tag.get("name") or "").lower() == "citation_journal_title":
            return (tag.get("content") or "").strip() == JOURNAL
    return False


def _text(tag):
    return _WS.sub(" ", tag.get_text(" ", strip=True)).strip() if tag is not None else ""


def _split_institutions(text):
    """The printed list's entries in order, without repeats. A comma between two entries with no Chinese characters
    is inside one English institution ("Department of X, University of Florida"), so those pieces stay together."""
    parts = _SEPARATOR.split(text)
    entries, prev_sep = [], None
    for i in range(0, len(parts), 2):
        piece = parts[i]
        if (entries and prev_sep in (",", "，") and piece.strip() and not _CJK.search(piece)
                and not _CJK.search(entries[-1])):
            entries[-1] += prev_sep + piece
        else:
            entries.append(piece)
        prev_sep = parts[i + 1] if i + 1 < len(parts) else None
    out, seen = [], set()
    for entry in entries:
        entry = _WS.sub(" ", entry).strip()
        if entry and entry not in seen:
            seen.add(entry)
            out.append(entry)
    return out


class Ecologica(PublisherParser):
    parser_name = "ecologica"
    # the script's byline beats the meta tags (Chinese and English names in one list, or several names in one tag)
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        if not hasattr(self, "_claim"):  # authors_found asks too: the head test runs once per page
            self._claim = _journal_tag(self.soup)
        return self._claim

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._json_authors())

    def _json_authors(self):
        """The script's author records, or [] when the page has none or they can't be read."""
        if not hasattr(self, "_records"):
            self._records = []
            for script in self.soup.find_all("script", src=False):
                m = _AUTHORS_JSON.search(script.string or "")
                if not m:
                    continue
                try:  # a JS string literal holding JSON; \' is a JS escape JSON lacks
                    data = json.loads(json.loads('"' + m.group(1).replace("\\'", "'") + '"'))
                    records = data.get("authors") if isinstance(data, dict) else None
                except (ValueError, TypeError):
                    records = None
                self._records = [r for r in records or [] if isinstance(r, dict)]
                break
        return self._records

    def parse(self):
        printed = _text(self.soup.find("p", id="DisplayCnInstitutionValue"))
        affiliations = _split_institutions(printed) if printed else []
        authors = []
        for record in self._json_authors():
            name = _WS.sub(" ", str(record.get("cn_name") or record.get("en_name") or "")).strip()
            if name:
                authors.append({"name": name, "affiliations": list(affiliations), "is_corresponding": False})
        funding = _text(self.soup.find("p", id="CnFundProjectValue")) or _text(self.soup.find("p", id="EnFundProjectValue"))
        return {"authors": authors, "abstract": None, "acknowledgments": None, "funding_statement": funding or None,
                "references": None, "references_complete": False}
