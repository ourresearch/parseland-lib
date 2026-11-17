"""Editorum article pages: naukaru.ru, editorum.ru and ~30 Russian university journal sites on the platform (oxjob #2289).

No publisher parser claimed the platform, so the generic parser read its citation_author tags: no corresponding author,
and no authors at all on the pages whose tags are missing. The page prints:

- a byline card per author, `<div class="author-list-item">` with the name in `<span class="name">` and an envelope
  `mailto:` link when the author's profile holds an e-mail. Editorial-board cards in the sidebar share the class but
  carry a role in <b> and no `span.name`;
- the reference list in the panel after `<div id="article-references">`, one numbered <p> per entry ("1. ...");
- a "Funding:" row in the "Author and publication information" panel, when the journal filled it in.

Corresponding author: the envelope marks the author it singles out, a lone author's or the one author of several with
an e-mail (label-v1: "an envelope or mail icon tied to them"; #2166's lone e-mail rule for OJS). The platform shows the
envelope for every author whose profile has an e-mail (one card holds a placeholder, fake@neicon.ru), so envelopes on
two or more authors single no one out.

Affiliations and abstract are left to the readers that decide them today: the works already carry them. In #2289's
80-page sample (17 Nov 2026) one page each shows an affiliation or an abstract its work lacks (about 900 works),
under the swarm's 1,000-works floor; the "Abstract (English):" block and the numbered affiliation list are there.
"""
import copy
import re

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

# the platform's own stylesheet bundle, linked in <head> on every page it serves
_ASSET = re.compile(r"/bundles/journals/css/")
_NUMBERED = re.compile(r"^(\d{1,3})\.\s*(?=\S)")
_PLACEHOLDER_MAIL = re.compile(r"^mailto:\s*fake@", re.I)


class Editorum(PublisherParser):
    parser_name = "editorum"

    def _is_editorum(self):
        # cheap on every page: <head>'s direct children only, never a whole-tree search
        root = self.soup.html
        head = root.find("head", recursive=False) if root is not None else None
        return head is not None and head.find("link", href=_ASSET, recursive=False) is not None

    def is_publisher_specific_parser(self):
        return self._is_editorum()

    def authors_found(self):
        return self._is_editorum() and bool(self._byline())

    def _byline(self):
        return [card for card in self.soup.select("div.author-list-item") if card.select_one("span.name")]

    def _authors(self):
        cards = self._byline()
        mailed = [any(not _PLACEHOLDER_MAIL.match(a["href"]) for a in card.select('a[href^="mailto:"]'))
                  for card in cards]
        marked = mailed.index(True) if sum(mailed) == 1 else None
        return [{"name": squash(card.select_one("span.name").get_text(" ")), "affiliations": [],
                 "is_corresponding": i == marked} for i, card in enumerate(cards)]

    def _reference_block(self):
        anchor = self.soup.find("div", id="article-references")
        panel = anchor.find_next_sibling("div") if anchor else None
        return panel.select_one(".panel-body .article-text") if panel else None

    def _references(self):
        """(entries, whole): whole when the entries are numbered 1..n and the block holds nothing else."""
        # imported here: back_matter imports this package's utils, which imports every parser
        from parseland_lib.back_matter import _entry_doi
        block = self._reference_block()
        if block is None:
            return [], False
        entries, numbers = [], []
        for p in block.find_all("p"):
            text = squash(p.get_text())
            if not text:
                continue
            m = _NUMBERED.match(text)
            numbers.append(int(m.group(1)) if m else None)
            text = text[m.end():] if m else text
            entries.append({"position": len(entries) + 1, "raw": text, "doi": _entry_doi(p, text)})
        rest = copy.copy(block)
        for p in rest.find_all("p"):
            p.decompose()
        whole = bool(entries) and numbers == list(range(1, len(entries) + 1)) and not squash(rest.get_text())
        return entries, whole

    def _funding(self):
        for row in self.soup.select("div.article-info-row"):
            key, value = row.select_one(".key"), row.select_one(".value")
            if key and value and squash(key.get_text()) == "Funding:":
                return squash(value.get_text(" ")) or None
        return None

    def parse(self):
        refs, whole = self._references()
        out = {"authors": self._authors(), "abstract": None}
        if refs:
            out["references"] = refs
            out["references_complete"] = whole
        if funding := self._funding():
            out["funding_statement"] = funding
        return out
