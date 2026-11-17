"""DKS Center's own article pages (DOI prefix 10.32702; oxjob #2339).

The publisher's journals (Ефективна економіка, Економіка та держава, Агросвіт, Інвестиції: практика та досвід,
Державне управління: удосконалення та розвиток) kept their articles on their own sites until mid-2022
(www.economy.nayka.com.ua, www.economy.in.ua, www.agrosvit.info, www.investplan.com.ua, www.dy.nayka.com.ua, each
article at "?op=1&z=<id>"); since then they use Open Journal Systems at nayka.com.ua/index.php/, which this parser
leaves to the OJS readers (#2267).

The older pages' citation_author and description tags already give the generic reader the authors and the abstract,
so this parser passes its output on unchanged. What it adds is the reference list: each page prints it twice, under
"Література" ("Литература") in the article's language and under "References" in English and transliteration, as one
paragraph of entries typed "1." to "n." and separated by <br>. The English one is returned (the version the rubric
asks for where a page shows several languages); the other only when there is no English list. Affiliations (the
"Відомості про авторів" panel) are left to a later round: in the 76-page sample only 3 works that lack them (about 700
works in all) had such a page, under the swarm's floor of 1,000 works per field.
"""
import copy
import re
from urllib.parse import urlsplit

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

# The old sites (the pages of three of them carry no citation_doi tag) and their article address, "?op=1&z=<id>";
# the OJS pages, nayka.com.ua/index.php/<journal>/article/view/<id>, never have it.
_OTHER_HOSTS = {"economy.in.ua", "agrosvit.info", "investplan.com.ua"}
_OWN_ADDRESS = re.compile(r"\?op=1&z=\d")
_ENGLISH_HEADING = "References"
_OTHER_HEADINGS = ("Література", "Литература")
_TYPED_NUMBER = re.compile(r"^(\d{1,3})(?:[.)]\s*|\s+)(?=\S)")  # "1.\t", "7 " (a tab typed without the full stop)
_LINE_BREAK = " "


def _entries(paragraph):
    """The paragraph's lines, one per <br>, whitespace squashed, empty lines dropped."""
    paragraph = copy.copy(paragraph)  # never edit the page: the other readers still read this soup
    for br in paragraph.find_all("br"):
        br.replace_with(_LINE_BREAK)
    return [line for line in (squash(part) for part in paragraph.get_text().split(_LINE_BREAK)) if line]


class Nayka(PublisherParser):
    parser_name = "nayka"

    def is_publisher_specific_parser(self):
        if getattr(self, "_claimed", None) is None:
            self._claimed = self._claim()
        return self._claimed

    def _claim(self):
        # One tag in the small <head>: other publishers' pages cost one head scan, never a whole-page walk.
        head = self.soup.head
        tag = head.find("meta", attrs={"name": "citation_abstract_html_url"}) if head is not None else None
        address = (tag.get("content") or "").strip() if tag is not None else ""
        if not _OWN_ADDRESS.search(address):
            return False
        try:
            host = (urlsplit(address).hostname or "").removeprefix("www.")
        except ValueError:
            return False
        return host.endswith(".nayka.com.ua") or host in _OTHER_HOSTS

    def _generic(self):
        if getattr(self, "_generic_parser", None) is None:
            self._generic_parser = GenericPublisherParser(self.soup)
        return self._generic_parser

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._generic().authors_found())

    def parse(self):
        refs, whole = self._references()
        parsed = dict(self._generic().parse())
        if refs:
            parsed["references"] = refs
            parsed["references_complete"] = whole
        return parsed

    # ---- the reference list ----

    def _lists(self):
        """{heading: [entry lines]} for the article's reference lists: a "bold m_top10" heading paragraph followed by
        a "rezume" paragraph."""
        scope = self.soup.find("article") or self.soup
        lists = {}
        for heading in scope.find_all("p", class_="m_top10"):
            title = squash(heading.get_text())
            if title != _ENGLISH_HEADING and title not in _OTHER_HEADINGS:
                continue
            body = heading.find_next_sibling("p")
            if body is not None and "rezume" in (body.get("class") or []) and title not in lists:
                lists[title] = _entries(body)
        return lists

    def _references(self):
        """(references, references_complete), or (None, False) when the page prints no list."""
        from parseland_lib.back_matter import _printed_doi  # here, not at the top: back_matter imports this package

        lists = self._lists()
        lines = lists.get(_ENGLISH_HEADING) or next((lists[h] for h in _OTHER_HEADINGS if lists.get(h)), None)
        if not lines:
            return None, False
        numbers = [int(m.group(1)) if (m := _TYPED_NUMBER.match(line)) else None for line in lines]
        texts = [_TYPED_NUMBER.sub("", line, count=1) for line in lines]
        refs = [{"position": i, "raw": text, "doi": _printed_doi(text)} for i, text in enumerate(texts, 1)]
        # Whole only on positive evidence: every line carries its number and they run 1..n (a line without one is
        # half of an entry broken in two), and the other language's list, when there is one, has as many entries.
        whole = numbers == list(range(1, len(lines) + 1)) and all(
            len(other) == len(lines) for other in lists.values())
        return refs, whole
