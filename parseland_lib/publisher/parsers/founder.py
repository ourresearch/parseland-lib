"""Founder journal cloud (rc-pub) article pages: the funding statement (oxjob #2268).

Founder's Nuxt journal sites (cjig.cn, ygxb.ac.cn, *.lightpublishing.cn, *.publish.founderss.cn, wsp-publishing.com
and more) server-render an article page whose author box is empty: authors and abstract are only in citation_* tags,
which the generic parser reads, and this parser returns that same parse unchanged. What no parser read is the funding
the page states: a "基金信息" (fund information) row in the article's info block, and the article record's
`fund` / `enFund` value in the preloaded page state (window.__NUXT__), which holds it on sites that render no row.

The pages also carry HighWire's HW.* meta tags (so does SciEngine, another platform). The claim never uses them: a page
is Founder's when it links the platform's article download path and preloads the platform's article state.
"""
import json
import re

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

_JS_STRING = r'"((?:[^"\\]|\\.)*)"'
_JS_VALUE = r'(?:' + _JS_STRING + r'|[\w$]+)'
# the article record in the page state: ...,authorCompany:<value>,fund:<value>,enFund:<value>. A value that is a bare
# name points into the state's argument list (often null): read only literal strings. The state's fundList is the
# site's list of funders, never this article's.
_RECORD_FUND = re.compile(r'[,{]authorCompany:(?:"(?:[^"\\]|\\.)*"|[\w$]+),fund:' + _JS_VALUE + r',enFund:' + _JS_VALUE)
_FUND_LABEL = re.compile(r"^(?:基金信息|基金项目|基金|Funds?|Funding)\s*[:：]?$", re.I)


def _js_string(value):
    if not value:
        return None
    try:
        text = json.loads(f'"{value}"')
    except ValueError:
        return None
    return squash(text) or None


def _preloads_nuxt_state(soup):
    """Cheap test (no tree walk) that a page may preload a Nuxt state: Nuxt 2's server render marks <html
    data-n-head-ssr> (every Founder page seen) and writes the window.__NUXT__ script straight into <body>."""
    html = soup.html
    if html is not None and html.has_attr("data-n-head-ssr"):
        return True
    body = soup.body
    return body is not None and any(child.name == "script" and (child.string or "").lstrip().startswith("window.__NUXT__")
                                    for child in body.children)


class Founder(PublisherParser):
    parser_name = "founder_journal_cloud"

    def _state(self):
        """The page's preloaded Nuxt state, or None when this is not a Founder article page."""
        if not hasattr(self, "_nuxt"):
            self._nuxt = None
            # Every parser's claim runs on every page, so a cheap marker comes first and other pages are rejected
            # before anything walks the tree.
            if not _preloads_nuxt_state(self.soup):
                return None
            if self.soup.select_one('a[href*="/rc-pub/front/front-article/"]'):
                for script in self.soup.find_all("script"):
                    text = script.string or ""
                    if text.lstrip().startswith("window.__NUXT__") and "thesisData:" in text:
                        self._nuxt = text
                        break
        return self._nuxt

    def is_publisher_specific_parser(self):
        return self._state() is not None

    def authors_found(self):
        return self._state() is not None

    def parse(self):
        parsed = dict(GenericPublisherParser(self.soup).parse())
        parsed.update(acknowledgments=None, funding_statement=self.funding_statement(), references=None,
                      references_complete=False)
        return parsed

    def funding_statement(self):
        for row in self.soup.select("li.authors-company"):
            label, text = row.select_one("div.fl"), row.select_one(".authors-company__text")
            if label and text and _FUND_LABEL.match(squash(label.get_text(" ", strip=True))):
                if value := squash(text.get_text(" ", strip=True)):
                    return value
        state = self._state()
        found = _RECORD_FUND.search(state) if state else None
        if not found:
            return None
        chinese, english = _js_string(found.group(1)), _js_string(found.group(2))
        if (self.soup.html.get("lang") or "").lower().startswith("en") if self.soup.html else False:
            return english or chinese
        return chinese or english
