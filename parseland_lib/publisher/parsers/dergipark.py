"""DergiPark article pages (oxjob #2268): TUBITAK ULAKBIM's journal platform, dergipark.org.tr and the journals it
hosts under their own domains. Every page carries <meta name="generator" content="uds"> and a details table
(table.record_properties) whose "Yazarlar" / "Authors" row lists each author in a <p id="author123...">.

The generic reader already gets the byline, affiliations (citation_author_institution) and abstract from the meta tags;
this parser keeps those as they are and adds what only the page's own markup says:
- the corresponding author, which the details table marks three ways over the years: "<small>(Sorumlu Yazar)</small>"
  after the name; a star icon (span.primary-author-icon) inside a name link titled "Sorumlu Yazar"; and on 2024+ pages
  every name link titled "Sorumlu Yazar" with the star on the real one only, so the star decides. English-interface
  pages print "Primary Author" in the same places; label-v1's labellers do not read that as a corresponding-author
  mark (oxjob #2268 RESULT.json says why that may be wrong), so it marks no one here.
- the funding statement ("Destekleyen Kurum" / "Supporting Institution", with its "Proje Numarası" / "Project Number")
  and acknowledgments ("Teşekkür" / "Thanks"), rows of the details table or, on newer pages, their own sections.
The reference list is left to parse.py's readers (citation_reference tags), which already read it.
"""
import copy
import re
import unicodedata

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

_AUTHOR_ID = re.compile(r"^author\d+$")
_CORRESPONDING_LABELS = {"sorumlu yazar", "corresponding author"}
_FUNDING_LABELS = {"destekleyen kurum", "supporting institution"}
_PROJECT_LABELS = {"proje numarası", "project number"}
_THANKS_LABELS = {"teşekkür", "thanks"}
# what a journal prints when there is nothing to say ("yok" = none)
_PLACEHOLDER = re.compile(r"^(?:yok(?:tur)?|none|no|n/?a|bulunmamaktadır|-+|\.+)\.?$", re.I)


def _key(name):
    """A name compared across the table and the meta tags ("Fatih PULAT>" = "Fatih PULAT", "ULVİ" = "Ulvi")."""
    text = unicodedata.normalize("NFKD", (name or "").casefold().replace("ı", "i"))
    return "".join(c for c in text if c.isalnum())


def _label(text):
    return squash(text or "").strip(" ():").casefold()


def _display_name(entry):
    """An author entry's name: its first text once the label, the "Bu kişi benim" claim link and the marks are out."""
    entry = copy.copy(entry)  # never edit the page
    for tag in entry.select("small, sup, .primary-author-icon, a[class*=claim-authorship]"):
        tag.decompose()
    return next(iter(entry.stripped_strings), "").rstrip(">").strip()


def corresponding_names(soup):
    """The names a DergiPark page marks as corresponding, for whichever parser wins the page (#2239, round 8b): record
    pages (OAI-PMH ids) go to the repository parser, which keeps no mark, and the 2025 template (no "uds" generator,
    each author in a div#authorNNN) to the meta-tag parser, which reads its '*' on some pages only, and on English
    pages also beside "Primary Author".
    - details table (uds): the marks DergiPark._is_marked reads; a name link's title alone is no mark there (the table
      titles every author with a DergiPark profile "Sorumlu Yazar").
    - 2025 template: the name link titled "Sorumlu Yazar" (only the corresponding author's is) with its '*'.
    Returns None when the page has no such list or marks no one; [] when it shows only English "Primary Author"
    labels, which mark no one (see the module docstring)."""
    names, primary = [], False
    entries = [p for p in soup.select("table.record_properties p[id]") if _AUTHOR_ID.match(p.get("id", ""))]
    if entries:
        for entry in entries:
            if DergiPark._is_marked(entry):
                names.append(_display_name(entry))
            star = entry.select_one(".primary-author-icon")
            link = star.find_parent("a") if star is not None else None
            primary = primary or any(_label(s.get_text()) == "primary author" for s in entry.find_all("small")) or (
                link is not None and _label(link.get("title")) == "primary author")
    else:
        for entry in soup.select("div[id^=author]"):
            link = entry.select_one('a[href*="/pub/@"]') if _AUTHOR_ID.match(entry.get("id", "")) else None
            if link is None or not any(s.get_text(strip=True) == "*" for s in link.find_all("sup")):
                continue
            if _label(link.get("title")) in _CORRESPONDING_LABELS:
                names.append(_display_name(entry))
            primary = primary or _label(link.get("title")) == "primary author"
    names = [n for n in names if n]
    return names or ([] if primary else None)


class DergiPark(PublisherParser):
    parser_name = "DergiPark"
    prefer_publisher_authors_over_generic = True

    def _entries(self):
        return [p for p in self.soup.select("table.record_properties p[id]") if _AUTHOR_ID.match(p.get("id", ""))]

    def is_publisher_specific_parser(self):
        # Every page is offered to this parser, so the cheap marker goes first: the generator tag is looked for in the
        # small <head> only, and a page without it is turned down before anything walks the whole tree (#2239's
        # per-page CPU rule). The answer is kept, since authors_found() and the caller both ask (oxjob #2268).
        if not hasattr(self, "_claimed"):
            head = self.soup.head
            generator = head.find("meta", attrs={"name": "generator"}) if head is not None else None
            self._claimed = bool(
                generator and squash(generator.get("content") or "").lower() == "uds" and self._entries())
        return self._claimed

    def _generic(self):
        if not hasattr(self, "_generic_result"):
            self._generic_result = GenericPublisherParser(self.soup).parse()
        return self._generic_result

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._generic().get("authors"))

    @staticmethod
    def _is_marked(entry):
        small = entry.find("small")
        if small is not None and _label(small.get_text()) in _CORRESPONDING_LABELS:
            return True
        star = entry.select_one(".primary-author-icon")
        link = star.find_parent("a") if star is not None else None
        return link is not None and _label(link.get("title")) in _CORRESPONDING_LABELS

    @staticmethod
    def _entry_name(entry):
        link = entry.find("a")
        return squash(link.get_text()).rstrip(">").strip() if link is not None else ""

    def _mark_corresponding(self, authors):
        entries = self._entries()
        marked = [i for i, entry in enumerate(entries) if self._is_marked(entry)]
        if not marked:
            return authors
        keys = [_key(a["name"]) for a in authors]
        chosen = set()
        for i in marked:
            name = _key(self._entry_name(entries[i]))
            if name and name in keys:
                chosen.add(keys.index(name))
            elif len(entries) == len(authors):  # same byline in the same order, the name written differently
                chosen.add(i)
        if not chosen:
            return authors
        return [dict(a, is_corresponding=(i in chosen)) for i, a in enumerate(authors)]

    def _labelled_texts(self):
        """{label: text} from the details table's rows and the newer pages' own sections; the first one wins."""
        found = {}
        for th in self.soup.select("table.record_properties th"):
            if (td := th.find_next_sibling("td")) is not None:
                found.setdefault(_label(th.get_text()), self._text(td))
        for section in self.soup.select("div.data-section"):
            if (heading := section.find("h3")) is not None:
                body = copy.copy(section)  # never edit the page
                body.find("h3").decompose()
                found.setdefault(_label(heading.get_text()), self._text(body))
        return found

    @staticmethod
    def _text(block):
        paragraphs = [squash(p.get_text()) for p in block.find_all("p")] or [squash(block.get_text())]
        text = "\n".join(p for p in paragraphs if p)
        return None if not text or _PLACEHOLDER.match(text) else text

    def _back_matter(self):
        texts = self._labelled_texts()
        pick = lambda labels: next((texts[k] for k in labels if texts.get(k)), None)  # noqa: E731
        funding = pick(_FUNDING_LABELS)
        if funding and (project := pick(_PROJECT_LABELS)):
            funding += "\n" + project
        return {"acknowledgments": pick(_THANKS_LABELS), "funding_statement": funding}

    def parse(self):
        generic = self._generic()
        authors = self._mark_corresponding([dict(a) for a in generic.get("authors") or []])
        return {"authors": authors, "abstract": generic.get("abstract"), **self._back_matter()}
