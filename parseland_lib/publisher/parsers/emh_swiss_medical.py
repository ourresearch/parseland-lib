"""EMH Swiss Medical Publishers' journals on TYPO3 (saez.ch, bullmed.ch, smw.ch, primary-hospital-care.ch, sanp.ch,
cardiovascmed.ch, medicalforum.ch ...; DOI prefix 10.4414).

Two layouts (oxjob #2338, a uniform sample of 80 stored pages, 17 Nov 2026):
- the journals' article page: a byline `p.authors` in `#section-authors` whose names carry affiliation markers (bare
  <sup> letters, or <a class="xref aff"> links to the affiliation's id), `p.affiliation` entries, a "Correspondence" /
  "Korrespondenzadresse" section naming the corresponding author, and `p.ref-list` references. Read whole here.
- Swiss Medical Forum's (medicalforum.ch): its "Literatur" accordion is read here; authors and abstract stay the
  generic parser's.
Most other pages are PDF-only stubs (a surname byline, "Dieser Text ist nur als PDF verfügbar."): the generic parser
reads those, as before.
"""
import re
import unicodedata

from bs4 import NavigableString, Tag

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

_EMH_PUBLISHER = re.compile(r"^\s*EMH\b")  # citation_publisher / dc.publisher "EMH Media"
_SPLIT = re.compile(r"[,;]")
_EMAIL = re.compile(r"[a-z0-9._%+-]+@[\w.-]+\.[a-z]{2,}")  # lower-case start: "Wetter Eeva.wetter@suva.ch" keeps "E"
_DEGREE = re.compile(r"^(?:(?:Prof|PD|Dr|med|méd|dent|vet|phil|pharm|lic|dipl)(?:\.\s*|\s+))+")  # "Dr. med. Peter ..."
_DEGREE_ONLY = re.compile(r"^(?:MD|PhD|MSc|MPH|MBA|MME|FMH)$")  # ", MD" after a name is no author
_TYPED_NUMBER = re.compile(r"^\s*\[?(\d{1,3})[.)\]]?(?:\s+|$)")  # "1\tZentrale ...", "1. ", "[3] "
_FUNDING_HEADING = re.compile(r"fund|financ|finanz|förder|soutien|support", re.I)
_NOT_FUNDING_HEADING = re.compile(r"conflict|interest|interessen|intérêt", re.I)
_MF_REFERENCE_TITLE = re.compile(r"^(?:literatur|littérature|letteratura|references?|référence|referenze)", re.I)


def _plain(text):
    """Lower case without accents, for matching a name against a correspondence address or an e-mail."""
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))


def _body_text(tag, heading_tags=("h2", "h3", "h4")):
    """A section's text without its heading, paragraphs on their own lines."""
    paragraphs = [squash(p.get_text(" ")) for p in tag.find_all("p")]
    if not paragraphs:
        paragraphs = [squash(" ".join(t for t in tag.find_all(string=True)
                                      if not (t.parent and t.parent.name in heading_tags)))]
    return "\n".join(p for p in paragraphs if p) or None


def _reference(position, raw, links):
    # imported here: back_matter imports this package's utils, and the package imports every parser at load time
    from parseland_lib.back_matter import _clean_doi, _pick_doi, _printed_doi
    doi = _pick_doi(*(_clean_doi(a.get("href")) for a in links if "doi.org/10." in (a.get("href") or "")),
                    _printed_doi(raw))
    return {"position": position, "raw": raw, "doi": doi}


def _numbered(entries):
    """(references, whole): whole only when every entry carries a list number and they run 1..n."""
    numbers = [n for n, _, _ in entries]
    whole = bool(entries) and numbers == list(range(1, len(entries) + 1))
    return [_reference(i, raw, links) for i, (_, raw, links) in enumerate(entries, 1)], whole


class EMHSwissMedical(PublisherParser):
    parser_name = "emh_swiss_medical"
    prefer_publisher_authors_over_generic = True

    def __init__(self, soup):
        super().__init__(soup)
        self._claimed = None
        self._parsed = None

    # ---- claim

    def is_publisher_specific_parser(self):
        # Every DOI page asks every parser (#2239: under 0.5 ms a page it does not claim), so the claim reads only the
        # <meta> tags that are direct children of <head>, once per page.
        if self._claimed is None:
            html = self.soup.find("html", recursive=False)
            head = (html or self.soup).find("head", recursive=False)
            self._claimed = head is not None and any(self._emh_meta(m) for m in head.find_all("meta", recursive=False))
        return self._claimed

    @staticmethod
    def _emh_meta(meta):
        name, content = meta.get("name"), meta.get("content") or ""
        if name in ("citation_publisher", "dc.publisher"):
            return bool(_EMH_PUBLISHER.match(content))
        return (meta.get("property") == "og:url" or name == "og:url") and "bullmed.ch" in content  # the old claim

    def authors_found(self):
        if not self.is_publisher_specific_parser():
            return False
        return self._byline() is not None or bool(self._mf_reference_boxes())

    # ---- the journals' article page

    def _byline(self):
        section = self.soup.find("section", id="section-authors")
        return section.find("p", class_="authors") if section else None

    def _affiliations(self):
        """({marker: text}, {element id: [texts]}, [texts without a marker])"""
        by_marker, by_id, unmarked = {}, {}, []
        section = self.soup.find("section", id="section-affiliation")
        for p in section.find_all("p", class_="affiliation") if section else []:
            marker, parts, texts = None, [], []

            def close():
                if text := squash(" ".join(parts)).strip(" ;,"):
                    texts.append(text)
                    if marker:
                        by_marker[marker] = text
                    else:
                        unmarked.append(text)

            for child in p.children:
                if isinstance(child, Tag) and child.name == "sup":
                    close()
                    marker, parts = squash(child.get_text()), []
                else:
                    parts.append(child.get_text(" ") if isinstance(child, Tag) else str(child))
            close()
            if p.get("id"):
                by_id[p["id"]] = texts
        return by_marker, by_id, unmarked

    def _meta_names(self):
        names = []
        for meta in self.soup.find_all("meta", attrs={"name": "citation_author"}):
            if any(c.isalpha() for c in meta.get("content") or ""):
                names.append(meta["content"])
        return names

    def parse_authors(self):
        byline = self._byline()
        if byline is None:
            return []
        entries, current = [], {"text": "", "markers": []}  # markers: (letter, the linked affiliation's id or None)
        for child in byline.children:
            if isinstance(child, NavigableString):
                pieces = _SPLIT.split(str(child))
                for i, piece in enumerate(pieces):
                    if i:
                        entries.append(current)
                        current = {"text": "", "markers": []}
                    current["text"] += piece
            elif child.name == "sup":
                current["markers"] += [(m, None) for m in re.split(r"[,\s]+", child.get_text()) if m]
            elif child.name == "a" and "xref" in (child.get("class") or []):
                # "xref aff", or a bare "xref" whose link goes nowhere (smw.ch 2022: href="#da39a3..." on every
                # marker, so the letter decides); "xref fn" is a footnote ("*": equal contribution)
                if "fn" not in child.get("class"):
                    current["markers"].append((squash(child.get_text()), (child.get("href") or "").lstrip("#")))
            else:
                current["text"] += child.get_text()
        entries.append(current)

        by_marker, by_id, unmarked = self._affiliations()
        surnames = {_plain(w) for n in self._meta_names() for w in re.split(r"[\s,]+", n) if len(w) > 1}
        authors, with_email = [], []
        for entry in entries:
            name = squash(_DEGREE.sub("", squash(_EMAIL.sub("", entry["text"]))))
            if not any(c.isalpha() for c in name) or (authors and _DEGREE_ONLY.match(name)):
                continue
            # a letter writer's town: "Dr. med. Peter Ryser-Düblin, Seftigen" (citation_author "Ryser-Düblin, Peter")
            if authors and surnames and " " not in name and _plain(name) not in surnames:
                continue
            affs = []
            for marker, ref_id in entry["markers"]:
                for text in (by_id.get(ref_id) if ref_id else None) or ([by_marker[marker]] if marker in by_marker else []):
                    if text not in affs:
                        affs.append(text)
            authors.append({"name": name, "affiliations": affs, "is_corresponding": False})
            if _EMAIL.search(entry["text"]):
                with_email.append(authors[-1])
        if unmarked and not by_marker and not any(a["affiliations"] for a in authors):
            for author in authors:  # affiliations with no markers: every author gets the whole list (rubric "unlinked")
                author["affiliations"] = list(unmarked)
        self._mark_corresponding(authors)
        if len(with_email) == 1 and len(authors) > 1 and not any(a["is_corresponding"] for a in authors):
            with_email[0]["is_corresponding"] = True  # the one author whose e-mail the byline shows (gold v1.3, #2166)
        return authors

    def _mark_corresponding(self, authors):
        section = self.soup.find("section", id="section-correspondence")
        if section is None or not authors:
            return
        text = _plain(squash(" ".join(p.get_text(" ") for p in section.find_all("p")) or section.get_text(" ")))
        named = [a for a in authors if _plain(a["name"]) in text]
        if not named and (mail := re.search(r"([\w.-]+)\s*(?:\[at\]|@)", text)):  # only an e-mail: "jean.martin[at]saez.ch"
            local = set(re.split(r"[._-]", mail.group(1)))
            named = [a for a in authors if (words := [w for w in re.split(r"[\s-]+", _plain(a["name"])) if len(w) > 2])
                     and words[-1] in local]
        if len(named) == 1:
            named[0]["is_corresponding"] = True

    def _section_body(self, section_id):
        section = self.soup.find("section", id=section_id)
        return (section, _body_text(section)) if section else (None, None)

    def parse_funding(self):
        for section in self.soup.find_all("section", id=re.compile(r"^section-(?:funding|disclosures|financial)")):
            heading = section.find(["h2", "h3", "h4"])
            title = squash(heading.get_text()) if heading else ""
            if _FUNDING_HEADING.search(title) and not _NOT_FUNDING_HEADING.search(title):
                return _body_text(section)
        return None

    def parse_references(self):
        section = self.soup.find("section", id="section-references")
        entries = []
        for p in section.find_all("p", class_="ref-list") if section else []:
            num, body = p.find(class_="ref-list-num"), p.find(class_="ref-list-text") or p
            links = body.find_all("a", href=True)
            parts = [t for t in body.find_all(string=True)
                     if not (t.parent.name == "a" and "pubid" in (t.parent.get("class") or []))
                     and not (num and num in t.parents)]
            raw = squash("".join(parts))
            label = squash(num.get_text()) if num else None
            if label is None and (m := _TYPED_NUMBER.match(raw)):
                label, raw = m.group(1), raw[m.end():].strip()
            number = int(m.group(1)) if label and (m := re.match(r"^\[?(\d{1,3})[.)\]]?$", label)) else None
            if raw:
                entries.append((number, raw, links))
        return _numbered(entries)

    # ---- Swiss Medical Forum's layout

    def _mf_reference_boxes(self):
        for title in self.soup.find_all("a", class_="emh-content-accordion__title"):
            if _MF_REFERENCE_TITLE.match(squash(title.get_text())):
                return title.parent.find_all("div", class_="emh-content-accordion__textbox")
        return []

    def parse_mf_references(self):
        entries = []
        for box in self._mf_reference_boxes():
            for item in box.find_all(class_="article-detail-recommendations__item-title") or [box]:
                raw = squash(item.get_text(" "))
                number = None
                if m := _TYPED_NUMBER.match(raw):
                    number, raw = int(m.group(1)), raw[m.end():].strip()
                if raw:
                    entries.append((number, raw, item.find_all("a", href=True)))
        return _numbered(entries)

    # ----

    def parse(self):
        if self._parsed is None:
            if self._byline() is not None:
                references, whole = self.parse_references()
                _, acknowledgments = self._section_body("section-acknowledgements")
                self._parsed = {"authors": self.parse_authors(), "abstract": self.parse_abstract_meta_tags(),
                                "acknowledgments": acknowledgments, "funding_statement": self.parse_funding(),
                                "references": references or None, "references_complete": whole}
            else:
                parsed = dict(GenericPublisherParser(self.soup).parse())
                references, whole = self.parse_mf_references()
                parsed.update(references=references or None, references_complete=whole)
                self._parsed = parsed
        return self._parsed
