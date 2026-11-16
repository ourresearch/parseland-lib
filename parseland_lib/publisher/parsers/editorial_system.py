"""Editorial System (Bentus, Poland): the journal-site template of ~70 sites (psychiatriapolska.pl, jeeng.net,
pjoes.com, populationmedicine.eu, ecoeet.com, aaem.pl, ... served from journalssystem.com) (oxjob #2268).

Until this parser only the generic one read these pages: citation_author tags (no affiliations) and the explicit
"Corresponding author" block. The page itself links every author to its affiliations:

- byline: div.magAbstractAuthors > div#author_<id> (older sites: an inline span#author_<id>) with
  onmouseover="highlightAffs('1,2', ...)" naming the author's affiliation numbers (the <sup> beside it also carries
  contribution letters "A-F" and equal-contribution "+");
- affiliations in #articleDetailsId div.affiliations, as a table (td.affIndex / td.affName > span#aff_<n>) or a list
  (div.list-row-small#aff_<n>, the number in its first cell, the text in its second);
- a "Corresponding author" block whose a.corrAuthorLink points to the author's page (".../Author-.../<id>");
- an envelope (mailto) beside an author in the byline: a mark when it singles out some authors or is the only
  author's, not when every one of several authors has one (label-v1 rubric; the gate's dev gold for a sole author);
- labelled sections below the abstract: "REFERENCES (n)" (div.ref#ref_<k>, refNo "k.", refText), "FUNDING",
  "ACKNOWLEDGEMENTS" (div.abstractContentReal).

termedia.pl's own portal (div.dAuthor, div.dAffiliations) is an older Bentus layout this parser does not claim.
"""
import copy
import re

from bs4 import Tag

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

_HIGHLIGHT = re.compile(r"highlightAffs\(\s*'([^']*)'")
_AFF_ID = re.compile(r"^aff_(\d+)$")
_AUTHOR_ID = re.compile(r"^author_(\d+)$")
_AUTHOR_PAGE_ID = re.compile(r"/(\d+)/?$")
_STATED_COUNT = re.compile(r"\((\d+)\)")
_CUT_LINK = re.compile(r"\S*(?:\.\.\.|…)")  # "https://doi.org/10.1038/sc.201...": a link the page prints cut short
_MAIL = 'a[href^="mailto:"]:not([href^="mailto:?"])'
_PARAGRAPH = "\u2029"  # a mark for <br> and block ends while a section's text is read
_MORE = re.compile(r"\b(?:show|load|view|see) (?:all|more)\b", re.I)
# section labels, in the languages the template's sites print them
_ACK_LABEL = re.compile(r"^(?:acknowledge?ments?|podzi[eę]kowania|благодарност[иь])$", re.I)
_FUNDING_LABEL = re.compile(r"^(?:funding|financial support|sources? of funding|finansowanie|źródła finansowania|"
                            r"финансирование)$", re.I)
# the template's own assets, linked from <head> on every site (favicon, jQuery and scripts.js from journalssystem.com,
# the site's stylesheets under /es-static/); scripts.js defines the byline's highlightAffs()
_ASSETS = ("journalssystem.com", "/es-static/")


def _has_template_assets(soup):
    """A link or script in <head> from the template's assets: the cheap first test of the claim. Every parser's claim
    runs on every page (#2239: under 0.5 ms a page it does not claim), so <head> is reached through direct children
    only and searched alone; nothing walks the whole tree until this passes."""
    html = soup.find("html", recursive=False)
    head = (html or soup).find("head", recursive=False)
    if head is None:
        return False
    return any(any(asset in (tag.get("href") or tag.get("src") or "") for asset in _ASSETS)
               for tag in head.find_all(("link", "script")))


def _numbers(text):
    return re.findall(r"\d+", text or "")


def _block_lines(block):
    """A section body's text, one line per paragraph (<p>, <div> or <br>), whitespace inside a line squashed: a line
    break in the page source is only a space ("...Program of\\nXinjiang Uygur...")."""
    block = copy.copy(block)  # the other parsers still read this soup
    for br in block.find_all("br"):
        br.replace_with(_PARAGRAPH)
    for p in block.find_all(["p", "div"]):
        p.append(_PARAGRAPH)
    lines = [squash(line) for line in block.get_text().split(_PARAGRAPH)]
    return "\n".join(line for line in lines if line) or None


def _is_author(tag):
    return isinstance(tag, Tag) and bool(_AUTHOR_ID.match(tag.get("id") or "")) and \
        bool(_HIGHLIGHT.search(tag.get("onmouseover") or ""))


def _has_mail(author):
    """An envelope (mailto) in the author's block or after it, before the next author."""
    if author.select_one(_MAIL):
        return True
    for sib in author.next_siblings:
        if not isinstance(sib, Tag):
            continue
        if _is_author(sib) or any(_is_author(t) for t in sib.select('[id^="author_"]')):
            return False
        if (sib.name == "a" and sib.has_attr("href") and sib["href"].startswith("mailto:")
                and not sib["href"].startswith("mailto:?")) or sib.select_one(_MAIL):
            return True
    return False


class EditorialSystem(PublisherParser):
    parser_name = "editorial_system"
    prefer_publisher_authors_over_generic = True  # the byline links affiliations; the meta tags carry none

    def _byline(self):
        """The byline's author blocks: div#author_<id> (or span) carrying the template's highlightAffs() hover."""
        box = self.soup.select_one("div.magAbstractAuthors")
        if box is None:
            return []
        return [tag for tag in box.select('div[id^="author_"], span[id^="author_"]') if _is_author(tag)]

    def is_publisher_specific_parser(self):
        if (claim := getattr(self, "_claim", None)) is None:  # computed once: authors_found() asks too
            claim = self._claim = _has_template_assets(self.soup) and bool(self._byline()) \
                and self.soup.select_one("div#articleDetailsId") is not None
        return claim

    def authors_found(self):
        return self.is_publisher_specific_parser()

    def _affiliations(self):
        """{number: text} from the details block's table or list layout."""
        block = self.soup.select_one("div#articleDetailsId div.affiliations")
        if block is None:
            return {}
        affs = {}
        for row in block.select("tr"):
            name, index = row.select_one("td.affName"), row.select_one("td.affIndex")
            if name is None:
                continue
            span = name.select_one('[id^="aff_"]')
            m = _AFF_ID.match(span.get("id", "")) if span else None
            number = m.group(1) if m else next(iter(_numbers(index.get_text() if index else "")), None)
            if number and (text := squash(name.get_text(" "))):
                affs[number] = text
        for row in block.select('div.list-row-small[id^="aff_"]'):
            m = _AFF_ID.match(row.get("id", ""))
            cells = row.find_all("div", recursive=False)
            if m and len(cells) >= 2 and (text := squash(cells[1].get_text(" "))):
                affs[m.group(1)] = text
        return affs

    def _corresponding_ids(self):
        """Author ids the "Corresponding author" block links to."""
        ids = set()
        for link in self.soup.select("a.corrAuthorLink"):
            if m := _AUTHOR_PAGE_ID.search(link.get("href") or ""):
                ids.add(m.group(1))
        return ids

    def parse_authors(self):
        affs = self._affiliations()
        corr_ids = self._corresponding_ids()
        authors, mails = [], []
        for tag in self._byline():
            aid = _AUTHOR_ID.match(tag["id"]).group(1)
            name_tag = copy.copy(tag.find("a") or tag)
            for sup in name_tag.find_all("sup"):  # "Yongzheng Bao<sup>+</sup>": an equal-contribution mark
                sup.decompose()
            name = squash(name_tag.get_text(" "))
            if not name:
                continue
            numbers = _numbers(_HIGHLIGHT.search(tag["onmouseover"]).group(1))
            authors.append({"name": name,
                            "affiliations": [affs[n] for n in numbers if n in affs],
                            "is_corresponding": aid in corr_ids if corr_ids else None,
                            "_id": aid})
            mails.append(_has_mail(tag))
        if authors and affs and not any(a["affiliations"] for a in authors):
            # affiliations listed without numbers on anyone: every author gets the whole list (rubric: "unlinked")
            for a in authors:
                a["affiliations"] = list(affs.values())
        if corr_ids and not any(a["is_corresponding"] for a in authors):
            # the block names someone the byline ids don't: match by name instead
            names = {squash(link.get_text(" ")).casefold() for link in self.soup.select("a.corrAuthorLink")}
            for a in authors:
                a["is_corresponding"] = a["name"].casefold() in names
        # an envelope that singles out some authors marks them; one for every author of several marks no one (rubric),
        # but the only author's envelope does (the gate's adjudicated dev gold, ecoeet.com)
        if not corr_ids and any(mails) and (not all(mails) or len(authors) == 1):
            for a, mail in zip(authors, mails):
                a["is_corresponding"] = mail
        for a in authors:
            a.pop("_id")
        return authors

    def _section(self, label_re):
        for label in self.soup.select("div.abstractLabel"):
            if label_re.match(squash(label.get_text(" ")).rstrip(":")):
                body = label.find_next_sibling("div")
                if body is not None and "abstractLabel" not in (body.get("class") or []):
                    return _block_lines(body)
        return None

    def parse_references(self):
        """(references, references_complete) from the list under the "#references" anchor's heading."""
        # imported here: back_matter and parse import this package, so a module-level import is circular
        from parseland_lib.back_matter import _entry_doi, _numbering_whole
        from parseland_lib.parse import _entries_look_whole
        anchor = self.soup.select_one("a#references")
        heading = anchor.find_next_sibling("div", class_="abstractLabel") if anchor else None
        body = heading.find_next_sibling("div", class_="abstractContent") if heading else None
        if body is None:
            return [], False
        refs, labels = [], []
        for entry in body.select('div.ref[id^="ref_"]'):
            text_tag = entry.select_one("div.refText")
            if text_tag is None:
                continue
            text_tag = copy.copy(text_tag)
            for links in text_tag.select("div.refLinks"):
                links.decompose()
            raw = squash(text_tag.get_text(" "))
            if not raw:
                continue
            labels.append(squash(entry.select_one("div.refNo").get_text()) if entry.select_one("div.refNo") else "")
            refs.append({"position": len(refs) + 1, "raw": raw, "doi": _entry_doi(entry, _CUT_LINK.sub(" ", raw))})
        stated = _STATED_COUNT.search(heading.get_text(" "))
        # parse_page's own whole-list check too, so this answer is the one the response carries (it turns down lists
        # with an entry that starts with a link: "https://www.gov.pl/web/edukacj... , dostęp: 21.05.2021")
        complete = bool(refs) and all(labels) and _numbering_whole(labels) and stated is not None \
            and int(stated.group(1)) == len(refs) and not _MORE.search(body.get_text(" ")) \
            and _entries_look_whole([ref["raw"] for ref in refs])
        return refs, complete

    def parse(self):
        # the abstract exactly as the generic parser reads these pages (the description tag the page prints)
        generic = GenericPublisherParser(self.soup)
        abstract = (generic.parse_abstract_meta_tags(include_seo_tags=False)
                    or generic.parse_structured_abstract_section()
                    or generic.parse_printed_seo_description())
        references, complete = self.parse_references()
        return {
            "authors": self.parse_authors(),
            "abstract": abstract,
            "acknowledgments": self._section(_ACK_LABEL),
            "funding_statement": self._section(_FUNDING_LABEL),
            "references": references,
            "references_complete": complete,
        }
