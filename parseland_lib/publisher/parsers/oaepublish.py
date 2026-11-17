"""OAE Publishing Inc. journals (oaepublish.com and its older per-journal sites, DOI prefix 10.20517) (oxjob #2339).

Two templates, both with citation_* tags whose authors carry no affiliations and no corresponding mark (the generic
parser read the byline from those tags, and gave the first author the "Correspondence to: ..." text that the newer
pages put in their one citation_author_institution tag):
- the older per-journal sites (hrjournal.net, cdrjournal.com, ..., oaepublish.com/<journal>/article/view/, 2016-2022):
  a byline `#authorString` of one <em> per author ("Name<sup>1,3</sup>"), affiliations as `div.Affs_con > p`
  ("<sup>1</sup>Department ..."), and a `div.CorrsAdd` reading "Correspondence Address: Prof. Name, ...";
- the Nuxt site (oaepublish.com/articles/..., 2023 on): the byline folds away all but the first and last authors, so
  the whole byline is read from the page's embedded state (`author:[{base:"Name<sup>1,*</sup>",...}]`); affiliations
  in `div.author_box` (or `div.Aff_current > p` on 2023-2024 pages); `span#cirrsMail` reads "*Correspondence to:
  Prof. Name, Dr. Name, ...".
An author is corresponding when the byline marks them "*" (which the correspondence note explains) or the
correspondence note names them. Both templates print a DECLARATIONS block whose "Acknowledgments" and "Financial
support and sponsorship" parts are returned (a "None." part is no statement). The abstract is the generic parser's.
The claim reads only the <head>'s own meta tags: the publisher tag, or a 10.20517 DOI tag.
"""
import json
import re
import unicodedata

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser

PUBLISHER = "oae publishing inc"
DOI_PREFIX = "10.20517/"
WS = re.compile(r"\s+")
NUXT_AUTHORS = re.compile(r'author:\[\{base:"')
NUXT_BASE = re.compile(r'base:"((?:[^"\\]|\\.)*)"')
SUP = re.compile(r"<sup>(.*?)</sup>", re.S)
TAG = re.compile(r"<[^>]+>")
CORRESPONDENCE = re.compile(r"^\W*correspondence\b", re.I)
AFF_NUMBER = re.compile(r"^[0-9]{1,3}[a-z]?$|^[a-z]$", re.I)
ACK_LABEL = re.compile(r"^acknowledge?ments?$", re.I)
FUNDING_LABEL = re.compile(r"^(?:financial support(?: and sponsorship)?|funding(?: information| sources?)?|"
                           r"sources? of (?:funding|support))$", re.I)
MIN_STATEMENT = 20  # "None.", "Nil.", "Not applicable." are no statement (back_matter.py's headed reader: the same floor)


def _squash(text):
    return WS.sub(" ", (text or "").replace("\xa0", " ")).strip()


def _key(text):
    """Letters and digits only, accents dropped, lower case: 'Cózar-Castellano' -> 'cozar castellano'."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return " ".join(re.findall(r"[a-z0-9]+", text))


def _marks(sup_text):
    return [m.strip() for m in (sup_text or "").split(",") if m.strip()]


class OAEPublish(PublisherParser):
    parser_name = "oae_publishing"
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        if "_claimed" not in self.__dict__:
            self._claimed = False
            html = self.soup.find("html", recursive=False)
            head = html.find("head", recursive=False) if html is not None else None
            if head is not None:
                for meta in head.find_all("meta", recursive=False):
                    name = (meta.get("name") or "").lower()
                    content = meta.get("content") or ""
                    if (name == "citation_publisher" and _key(content) == PUBLISHER) or (
                            name in ("citation_doi", "dc.identifier") and DOI_PREFIX in content):
                        self._claimed = True
                        break
        return self._claimed

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._read()["authors"])

    def parse(self):
        return self._read()

    # ---- reading
    def _read(self):
        if "_result" not in self.__dict__:
            authors = self._byline()
            self._link_affiliations(authors)
            self._mark_corresponding(authors)
            generic = GenericPublisherParser(self.soup)
            result = {
                "authors": [{"name": a["name"], "affiliations": a["affiliations"],
                             "is_corresponding": a["is_corresponding"]} for a in authors],
                "abstract": (generic.parse_abstract_meta_tags(include_seo_tags=False)
                             or generic.parse_structured_abstract_section()
                             or generic.parse_printed_seo_description()),
            }
            result.update(self._declarations())
            self._result = result
        return self._result

    def _byline(self):
        """[{name, marks}] in byline order: the Nuxt state's author list, else the older sites' <em> byline."""
        authors = []
        for script in self.soup.find_all("script"):
            text = script.string or ""
            if not (match := NUXT_AUTHORS.search(text)):
                continue
            end = text.find("}]", match.start())
            for raw in NUXT_BASE.findall(text[match.start():end + 2]):
                try:
                    base = json.loads('"' + raw + '"')
                except ValueError:
                    continue
                sups = SUP.findall(base)
                name = _squash(TAG.sub(" ", SUP.sub(" ", base)))
                if name:
                    authors.append({"name": name, "marks": [m for s in sups for m in _marks(TAG.sub("", s))]})
            break
        if authors:
            return authors
        byline = self.soup.select_one("#authorString")
        if byline is None:
            return []
        for em in byline.find_all("em", recursive=False):
            marks = [m for sup in em.find_all("sup") for m in _marks(sup.get_text())]
            name = _squash("".join(s for s in em.find_all(string=True, recursive=False)))
            if name:
                authors.append({"name": name.strip(" ,"), "marks": marks})
        return authors

    def _affiliation_list(self):
        """[(number or None, text)] from the first affiliation block the page has."""
        block = (self.soup.select_one("div.author_box") or self.soup.select_one("div.Affs_con")
                 or self.soup.select_one("div.Aff_current"))
        if block is None:
            return []
        out = []
        for el in block.find_all(["p", "div"]):
            if el.find(["p", "div"]) is not None or el.find_parent(class_="CorrsPlus") is not None:
                continue  # a wrapper, or the correspondence note inside author_box
            sup = el.find("sup")
            number = None
            first = next((c for c in el.children if not (isinstance(c, str) and not c.strip())), None)
            if sup is not None and first is sup:
                number = _squash(sup.get_text())
                if not AFF_NUMBER.match(number):
                    continue  # "<sup>#</sup>Authors contributed equally.": a note, not an affiliation
            text = _squash("".join(s for s in el.find_all(string=True) if s.parent is not sup))
            if text and not CORRESPONDENCE.match(text):
                out.append((number, text))
        return out

    def _link_affiliations(self, authors):
        affs = self._affiliation_list()
        numbered = {n: t for n, t in affs if n}
        unnumbered = [t for n, t in affs if not n]
        for a in authors:
            a["affiliations"] = [numbered[m] for m in a["marks"] if m in numbered]
        if unnumbered and not numbered and not any(a["affiliations"] for a in authors):
            for a in authors:  # no numbers anywhere: every author gets the whole list
                a["affiliations"] = list(unnumbered)

    def _correspondence_text(self):
        for el in self.soup.select("#cirrsMail, div.CorrsAdd"):
            text = _squash(el.get_text(" "))
            if CORRESPONDENCE.match(text):
                return text
        return ""

    def _mark_corresponding(self, authors):
        note = _key(self._correspondence_text())
        padded = f" {note} "
        for a in authors:
            starred = "*" in a["marks"] and bool(note)
            tokens = _key(a["name"]).split()
            forms = {" ".join(tokens), " ".join(reversed(tokens))}
            if len(tokens) > 2:  # "Frances E. Carr" is "Dr. Frances Carr" in the note
                forms.add(f"{tokens[0]} {tokens[-1]}")
            named = bool(tokens) and any(f" {form} " in padded for form in forms)
            a["is_corresponding"] = starred or named
        if not any(a["is_corresponding"] for a in authors):
            for a in authors:
                a["is_corresponding"] = None

    def _declarations(self):
        block = self.soup.select_one("div.article-declarations")
        if block is None:
            return {}
        parts, key = {}, None
        for child in block.children:
            if getattr(child, "name", None) is None:
                continue
            if child.name in ("h3", "h4", "span", "strong", "b"):
                label = _squash(child.get_text()).rstrip(":.")
                key = "acknowledgments" if ACK_LABEL.match(label) else (
                    "funding_statement" if FUNDING_LABEL.match(label) else None)
            elif child.name == "h2":
                key = None
            elif key and child.name in ("p", "div"):
                if text := _squash(child.get_text()):
                    parts.setdefault(key, []).append(text)
        return {k: text for k, v in parts.items() if len(text := "\n".join(v)) >= MIN_STATEMENT}
