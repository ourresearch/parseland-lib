"""KoreaMed Synapse / XMLink journal sites (oxjob #2268): ~300K works on ~340 Korean society journals.

Two page layouts of the template, claimed by marks only XMLink's software prints, never by a site's domain:
  - the Synapse NLM viewer (``ViewNLM_m.css``; byline in ``div.abody span.capture-id``): older journal sites;
  - the JATS view page (``div.author_layer`` whose author links go to ``/articles/search_result.php?term=author``, or
    its reference list ``li.ref_layer[name="jats-ref-pub"]``).
The citation_* meta tags are right on both, so the generic parser's reading is kept and only what it misses is added:
the Synapse viewer's printed abstract, corresponding authors named after "Address reprint requests to" / "Address for
correspondence" / "Corresponding to", the JATS view's lettered affiliations when the meta tags leave them blank, and
the reference list and acknowledgments both layouts print.
"""
import copy
import re
from urllib.parse import unquote

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser

# The notes these pages put a corresponding author's name after. Generic already reads "Correspondence to" and
# "Corresponding author"; these are the wordings it misses.
_CORR_NOTE = re.compile(
    r"address\s+(?:for\s+)?(?:reprint\s+requests?|correspondence)(?:\s+to)?\s*:?|reprint\s+requests?\s+to\s*:?|"
    r"corresponding\s+(?:to|author)\s*:?|correspondence\s*(?:to\s*)?:", re.I)
_NOTE_MAX = 800  # a note, not a paragraph of body text that happens to say "corresponding to"
_REF_NUMBER = re.compile(r"^\s*(\d{1,4})\s*[.)]\s*")


def _doi(link):
    """The DOI a reference's doi.org link points to ("https://doi.org/10.4143%2Fcrt.2016.089"), or None."""
    m = re.search(r"(10\.\d{4,9}/\S+)", unquote(link.get("href") or "")) if link else None
    return m.group(1) if m else None


def _text(node):
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()


class KoreaMedXMLink(PublisherParser):
    parser_name = "koreamed_xmlink"

    def _synapse_viewer(self):
        return bool(self.soup.select_one('link[href*="ViewNLM_m"]')) and bool(
            self.soup.select_one("div.abody span.capture-id"))

    def _jats_view(self):
        return bool(self.soup.select_one(
            'div.author_layer a[href*="search_result.php?term=author&"], ul.reference li.ref_layer[name="jats-ref-pub"]'))

    def is_publisher_specific_parser(self):
        return self._synapse_viewer() or self._jats_view()

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(GenericPublisherParser(self.soup).parse().get("authors"))

    def parse(self):
        out = copy.deepcopy(GenericPublisherParser(self.soup).parse())
        authors = out.get("authors") or []
        if self._jats_view() and authors and not any(a.get("affiliations") for a in authors):
            self._jats_affiliations(authors)
        if authors and not any(a.get("is_corresponding") for a in authors):
            self._mark_corresponding(authors)
        if self._synapse_viewer() and not out.get("abstract"):
            out["abstract"] = self.synapse_abstract()
        refs = self.references()
        if refs:
            out["references"] = [{"position": r["position"], "raw": r["raw"], "doi": r["doi"]} for r in refs]
            out["references_complete"] = self._whole(refs)
        if ack := self.acknowledgments():
            out["acknowledgments"] = ack
        return out

    # ---- abstract (Synapse viewer)
    def synapse_abstract(self):
        """The table row under the viewer's "Abstract" heading: labelled parts ("Purpose" ...) or plain paragraphs."""
        for head in self.soup.select("div.tl-main-part"):
            if _text(head).lower() != "abstract":
                continue
            row = head.find_parent("tr")
            cell = row.find_next_sibling("tr") if row else None
            cell = cell.find("td") if cell else None
            if not cell:
                return None
            cell = copy.copy(cell)  # labels are cut out below; the page's own soup stays whole for later readers
            parts = []
            for child in cell.find_all(["div", "p"], recursive=False):
                label = child.find("span", class_="tl-default") if child.name == "div" else None
                if label:
                    label_text = _text(label)
                    label.extract()
                    body = _text(child)
                    parts.append(f"{label_text}: {body}" if body else label_text)
                elif text := _text(child):
                    parts.append(text)
            text = "\n".join(parts) or _text(cell)
            return text or None
        return None

    # ---- affiliations (JATS view)
    def _english_byline(self):
        for layer in self.soup.select("div.author_layer"):
            links = layer.select('a[href*="search_result.php?term=author&"]')
            if links:
                return layer, links
        return None, []

    def _jats_affiliations(self, authors):
        layer, links = self._english_byline()
        if not layer or len(links) != len(authors):
            return
        aff_layer = layer.find_next_sibling("div")
        if not aff_layer or "aff_layer" not in (aff_layer.get("class") or []):
            return
        affs = {}
        unlabelled = []
        for entry in copy.copy(aff_layer).select("p.metadata-entry"):
            sup = entry.find("sup")
            label = _text(sup) if sup else ""
            if sup:
                sup.extract()
            text = _text(entry)
            if not text:
                continue
            if label:
                affs[label] = text
            else:
                unlabelled.append(text)
        for author, link in zip(authors, links):
            labels = []
            for sib in link.find_next_siblings():
                if sib.name != "sup":
                    break
                labels += [x.strip() for x in _text(sib).split(",") if x.strip()]
            found = [affs[x] for x in labels if x in affs]
            if not found and not affs and len(unlabelled) == 1:
                found = unlabelled  # one affiliation printed for the whole byline
            author["affiliations"] = found

    # ---- corresponding author
    def _mark_corresponding(self, authors):
        names = set()
        if self._synapse_viewer():
            # the viewer puts an envelope icon after the corresponding author's name and explains it in a note
            spans = [s for s in self.soup.select("div.abody span.capture-id") if s.select_one('img[src*="icon_corresp"]')]
            if any(_CORR_NOTE.search(_text(s)) or "correspondence to" in _text(s).lower() for s in spans):
                for span in spans:
                    text = _text(span)
                    if len(text) < 120 and not _CORR_NOTE.search(text):
                        names |= self._matching(text, authors)
        if not names:
            for string in self.soup.find_all(string=_CORR_NOTE):
                note = _text(string.parent)
                if len(note) > _NOTE_MAX:
                    continue
                m = _CORR_NOTE.search(note)
                if m:
                    found = self._matching(note[m.end():m.end() + 80], authors)
                    if len(found) == 1:
                        names |= found
        if not names:
            return
        for author in authors:
            author["is_corresponding"] = author.get("name") in names

    @staticmethod
    def _matching(text, authors):
        return {a["name"] for a in authors if a.get("name") and GenericPublisherParser._text_has_person(text, a["name"])}

    # ---- back matter
    def references(self):
        refs = []
        items = self.soup.select("div.bm div.ref-item")  # Synapse viewer
        if items:
            for item in items:
                data = item.find("div", class_="ref-data")
                if not data:
                    continue
                doi_link = data.select_one('a[href*="doi.org/"]')
                data = copy.copy(data)  # the PubMed / Crossref icon links sit in an inner div
                for inner in data.find_all("div"):
                    inner.decompose()
                label = item.find("div", class_="ref-label")
                refs.append({"position": len(refs) + 1, "label": _text(label) if label else "", "raw": _text(data),
                             "doi": _doi(doi_link)})
            return refs
        for ul in self.soup.select("ul.reference"):  # JATS view; the page repeats an empty copy in a hidden tab
            for li in ul.select("li.ref_layer"):
                span = li.find("span")
                text = _text(span) if span else ""
                m = _REF_NUMBER.match(text)
                doi_link = li.select_one('a[href*="doi.org/"]')
                refs.append({"position": len(refs) + 1, "label": m.group(1) if m else "",
                             "raw": text[m.end():] if m else text, "doi": _doi(doi_link)})
            if refs:
                return refs
        return refs

    @staticmethod
    def _whole(refs):
        """True only when every entry is numbered and the numbers run 1..n with no gap."""
        numbers = []
        for ref in refs:
            m = re.match(r"\s*(\d{1,4})", ref.get("label") or "")
            if not m or not ref.get("raw"):
                return False
            numbers.append(int(m.group(1)))
        return numbers == list(range(1, len(refs) + 1))

    def acknowledgments(self):
        for head in self.soup.select("div.tl-main-part"):  # Synapse viewer: heading table, then paragraphs
            if re.match(r"acknowledg", _text(head), re.I):
                table = head.find_parent("table")
                texts = []
                for sib in table.find_next_siblings() if table else []:
                    if sib.name != "p":
                        break
                    texts.append(_text(sib))
                return " ".join(t for t in texts if t) or None
        for head in self.soup.select("h4.link-target"):  # JATS view: heading, then one block
            if re.match(r"acknowledg", _text(head), re.I):
                body = head.find_next_sibling()
                if body and body.name == "div":
                    return _text(body) or None
        return None
