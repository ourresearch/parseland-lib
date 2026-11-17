import re
from urllib.parse import unquote

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser

_SITE_MARKS = ("eurekaselect.com", "benthamscience.com")
_NAME_SEPARATORS = re.compile(r",|\band\b")
_LETTER = re.compile(r"[^\W\d_]")
_DOI_LINK = re.compile(r"doi\.org/(10\.[^\s?#]+)")
_REF_NUMBER = re.compile(r"^\[?(\d+)[\].]?$")
_MORE = re.compile(r"\b(?:show|load|view|see) (?:more|all)\b", re.I)


def _on_bentham_site(soup):
    """Bentham Science's own site (eurekaselect.com, formerly benthamscience.com) names itself in <head>: og:site_name,
    og:url and its stylesheets. Every DOI page asks this parser (#2239: under 0.5 ms a page it does not claim), so only
    <head>'s direct children are read, never the whole tree (oxjob #2289)."""
    html = soup.find("html", recursive=False)
    head = (html or soup).find("head", recursive=False)
    if head is None:
        return False
    for tag in head.find_all(("meta", "link"), recursive=False):
        if tag.name == "meta":
            value = tag.get("content") if tag.get("property") in ("og:site_name", "og:url") else None
        else:
            value = tag.get("href") if "stylesheet" in (tag.get("rel") or ()) else None
        if value and any(mark in value for mark in _SITE_MARKS):
            return True
    return False


def _name(text):
    name = " ".join(text.replace("*", " ").split()).strip(" ,;.")
    return name if _LETTER.search(name) else None


class BenthamScience(PublisherParser):
    parser_name = "bentham_science"
    # the byline names every author; an author without a pop-up has no affiliation, never a reason to prefer the
    # generic parser's meta tags (oxjob #2289)
    prefer_publisher_authors_over_generic = True

    def __init__(self, soup):
        super().__init__(soup)
        self._site = None
        self._byline_tag = False  # not looked for yet

    def is_publisher_specific_parser(self):
        if self._site is None:
            self._site = _on_bentham_site(self.soup)
        return self._site

    def authors_found(self):
        return self.is_publisher_specific_parser() and self._byline() is not None

    def _byline(self):
        """Article pages: <span class="l-h-3"><strong>Author(s):</strong> ...</span>. Chapter pages print the same
        byline in a <p> under #side-b (oxjob #2289: no parser read chapter bylines)."""
        if self._byline_tag is False:
            tag = self.soup.find(lambda t: t.name == 'span' and 'l-h-3' in t.get('class', '') and t.find(
                'strong') and 'author' in t.find('strong').text.lower())
            if tag is None and (side := self.soup.find(id="side-b")) is not None:
                tag = next((s.parent for s in side.find_all("strong") if s.parent.name == "p"
                            and s.get_text(strip=True).lower().startswith("author")), None)
            self._byline_tag = tag
        return self._byline_tag

    def _is_chapter(self):
        return self._byline() is not None and self._byline().name == "p"

    def parse_authors(self):
        """Every name in the byline, in order: a pop-up link (data-content lists the author's affiliations) or plain
        text between commas and "and" (an author without affiliations). Until oxjob #2289 only the links were read,
        so plain-text authors were dropped."""
        authors = []
        for node in self._byline().children:
            if isinstance(node, Comment):
                continue
            if isinstance(node, NavigableString):
                for piece in _NAME_SEPARATORS.split(str(node)):
                    if name := _name(piece):
                        authors.append({'name': name, 'affiliations': [], 'is_corresponding': False})
            elif isinstance(node, Tag) and node.name == 'a' and 'green-orcid' not in (node.get('class') or ()):
                name = _name(node.text)
                if not name:
                    continue
                affs_soup = BeautifulSoup(node.get('data-content') or '', 'lxml')
                authors.append({
                    'name': name,
                    # the site's pop-up for an author it has no affiliation for holds a ",0" placeholder; an entry
                    # with no letter is never an affiliation (oxjob #2289)
                    'affiliations': [aff for aff in (tag.text.strip() for tag in affs_soup.find_all('li'))
                                     if _LETTER.search(aff)],
                    # Article bylines star an author with no note saying what the star means; read as corresponding
                    # since this parser was written, and left so (oxjob #2289). Chapter bylines are new: a star the page
                    # never explains is not a corresponding mark (label-v1), so it is not read there.
                    'is_corresponding': '*' in node.text and not self._is_chapter(),
                })
        return authors

    def parse_abstract(self):
        if self._is_chapter():
            # the abstract the generic parser read on chapter pages before this parser claimed them
            return GenericPublisherParser(self.soup).parse().get('abstract')
        abs_tags = self.soup.select('#abstract p')
        return '\n'.join([tag.text.strip() for tag in abs_tags])

    def parse_references(self):
        """Newer article pages print the whole list in #reference-box: one div.line per entry, its number "[n]" in
        .list-count and its text in .list-contact, followed after a <br> by the site's [DOI] and [PMID] links."""
        box = self.soup.find(id="reference-box")
        if box is None:
            return [], False
        refs, numbers = [], []
        for line in box.select("div.line"):
            contact = line.find(class_="list-contact")
            if contact is None:
                continue
            parts = []
            for node in contact.children:
                if isinstance(node, Tag) and node.name == "br":
                    break
                parts.append(node.get_text(" ") if isinstance(node, Tag) else str(node))
            raw = " ".join("".join(parts).split()) or " ".join(contact.get_text(" ").split())
            if not raw:
                continue
            count = line.find(class_="list-count")
            number = _REF_NUMBER.match(count.get_text(strip=True)) if count else None
            numbers.append(int(number.group(1)) if number else None)
            link = contact.find("a", href=_DOI_LINK)
            refs.append({"position": len(refs) + 1, "raw": raw,
                         "doi": unquote(_DOI_LINK.search(link["href"]).group(1)) if link else None})
        complete = bool(refs) and numbers == list(range(1, len(refs) + 1)) and not _MORE.search(box.get_text(" "))
        return refs, complete

    def parse(self):
        out = {'authors': self.parse_authors(),
               'abstract': self.parse_abstract()}
        refs, complete = self.parse_references()
        if refs:
            out['references'] = refs
            out['references_complete'] = complete
        return out
