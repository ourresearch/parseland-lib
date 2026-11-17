"""OA Text (oatext.com) article pages (oxjob #2339).

The site runs its own PHP template (Foundation 5) and writes no citation_* meta tags. Every page carries the site's
keywords tag ("OA Text, OAT, Open Access Text, OAtext, ..."), which is what the parser claims pages by. An article
page prints:
- the byline as one div.custom-tootip-head per author (p.author-title holds the name) whose data-dropdown names a
  pop-up div ("a1", "a2", ...) with the author's affiliations (one <p> each; two in one <p> are split by <br>) and an
  e-mail line (mostly one placeholder address shared by every page: never read);
- an "Author Info" tab (id "Author_Info", "JIC_Author_Info" on older pages) headed "Corresponding author", then one
  h4 per corresponding author, each followed by the correspondence address and an e-mail line;
- the body in the "Article" tab, h2 sections, with "References" over one <ol>.
The abstract, acknowledgments and funding statement are left to parse.py's shared readers (the "Abstract" heading
reader and back_matter.headed_back_matter), which read them right on this site already.
"""
import copy
import re
import unicodedata
from urllib.parse import unquote

from bs4 import Comment

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

_SITE_KEYWORDS = ("OAtext", "Open Access Text")
_EMAIL_LINE = re.compile(r"^\s*e-?mail\s*:", re.I)
# A pop-up line that is not an affiliation: a correspondence note repeating the address, the journal role of an editor
_NOT_AFFILIATION = re.compile(r"^\s*(?:correspondence\b|corresponding author\b|editor[- ]in[- ]chief\b)", re.I)
_CORRESPONDING_LABEL = re.compile(r"^\s*corresponding\s+author\s*:?\s*(.*)$", re.I)
_PHONE_TAIL = re.compile(r"[,;.]?\s*(?:Tel|Telephone|Phone|Ph|Fax|Mob(?:ile)?|Cell)\b\.?\s*(?:No\.?)?\s*[:.]?\s*\+?[\d(].*$",
                         re.I)
_LEADING_TITLE = re.compile(r"^(?:(?:Dr|Prof|Colonel)\.?\s+)+", re.I)  # "Colonel (Dr) Priya ..."
_TITLE_IN_BRACKETS = re.compile(r"\((?:Dr|Prof)\.?\)", re.I)
# Degrees and titles a correspondence heading adds to the byline's name ("T. Boutsikou, MD, PhD", "Vishal Mago, M.Ch")
_DEGREE = re.compile(r"\b(?:ph\.?\s?d|m\.\s?ch|mbbs|m\.?d|msc|dr|prof|colonel)(?!\w)\.?", re.I)
# A correspondence address is a second affiliation only when it names an organisation or a unit of one (the rubric's
# "employers, departments, institutes and their addresses"), not a bare street address
_ORGANISATION = re.compile(r"\b(?:universi\w*|univ|institut\w*|college|colegio|hospital\w*|clinic\w*|klinik\w*|academ\w*|"
                           r"cent(?:er|re|ro)|laborat\w*|ministr\w*|council|agency|company|corporation|inc|ltd|gmbh|"
                           r"foundation|school|faculty|department|division|service)\b", re.I)
_PLACE_STOPWORDS = frozenset("the of and for de di da do la le du des del et in at".split())
_ARTICLE_TAB = re.compile(r"(?:^|_)Article$")
_AUTHOR_INFO_TAB = re.compile(r"(?:^|_)Author_Info$")
_SECTION_HEADINGS = ["h2", "h3", "h4"]
_REFERENCES_HEADING = re.compile(r"^\s*references?\s*:?\s*$", re.I)
_SITE_FOOTER = re.compile(r"^\s*(?:©\s*)?\d{4} Copyright OAT\b", re.I)  # printed into some reference lists
_LINK_LABEL = re.compile(r"^\s*\[[^\]]{1,30}\]\s*$")  # "[Crossref]", "[PubMed]", "[Google Scholar]"
_MORE = re.compile(r"\b(?:show|load|view|see)\s+(?:more|all)\b", re.I)


def _fold(text):
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c)).casefold()


def _name_tokens(name):
    name = _DEGREE.sub(" ", re.sub(r"\([^)]*\)", " ", name))
    return [t for t in re.split(r"[^\w']+", _fold(name).replace("-", " ")) if t.strip("'")]


def _same_author(a, b):
    """The correspondence heading's name and a byline name are one person: the same tokens, the same letters ("Suhair
    Shahwan" / "SuhairShahwan"), or a shared family name and the same first initial ("Ander DS" / "Douglas S Ander").
    Kept close to gate/fields.py name_match, which scores us."""
    ta, tb = _name_tokens(a), _name_tokens(b)
    if not ta or not tb:
        return False
    if set(ta) == set(tb) or "".join(ta) == "".join(tb):
        return True
    shared = {t for t in ta if len(t) > 1} & {t for t in tb if len(t) > 1}
    if not shared:
        return False
    rest_a, rest_b = [t for t in ta if t not in shared], [t for t in tb if t not in shared]
    if not rest_a or not rest_b:
        return len(shared) >= 2 or (not rest_a and not rest_b)
    return rest_a[0][0] == rest_b[0][0]


def _place_words(text):
    return {w for w in re.split(r"[^\w]+", _fold(text)) if len(w) > 1 and w not in _PLACE_STOPWORDS}


def _same_place(a, b):
    """Two affiliation strings name one place: most words of the shorter are in the longer ("University of Calgary,
    Alberta, Canada" in "Department of Biology, The University of Calgary, Calgary, Alberta, Canada T2N 1N4")."""
    wa, wb = _place_words(a), _place_words(b)
    return not wa or not wb or len(wa & wb) >= 0.75 * min(len(wa), len(wb))


def _popup_lines(popup):
    """An author's affiliation strings from the byline pop-up: one per <p>, split at <br>, without the e-mail line."""
    lines = []
    for p in popup.find_all("p"):
        parts, current = [], []
        for node in p.children:
            if isinstance(node, Comment):
                continue
            if getattr(node, "name", None) == "br":
                parts.append("".join(current))
                current = []
            else:
                current.append(node.get_text() if hasattr(node, "get_text") else str(node))
        parts.append("".join(current))
        for part in parts:
            text = squash(part)
            if text and not _EMAIL_LINE.match(text) and not _NOT_AFFILIATION.match(text):
                lines.append(text)
    return lines


class OAText(PublisherParser):
    parser_name = "oa_text"
    # the pop-up byline is the page's own; the generic parser reads body sentences as names on this site
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        """The site's keywords tag. Only the <head>'s own children are read: production asks every parser this on
        every DOI page (oxjob #2239's cost rule), so no search of the whole tree."""
        claimed = getattr(self, "_claimed", None)
        if claimed is None:
            claimed = self._claimed = self._site_keywords()
        return claimed

    def _site_keywords(self):
        root = next((c for c in self.soup.contents if getattr(c, "name", None) == "html"), None)
        head = next((c for c in root.contents if getattr(c, "name", None) == "head"), None) if root else None
        for tag in head.contents if head is not None else ():
            if getattr(tag, "name", None) == "meta" and (tag.get("name") or "").lower() == "keywords":
                content = tag.get("content") or ""
                return all(word in content for word in _SITE_KEYWORDS)
        return False

    def authors_found(self):
        return self.is_publisher_specific_parser() and self.soup.select_one(
            "div.custom-tootip-head[data-dropdown]") is not None

    def _authors(self):
        popups = {div.get("id"): div for div in self.soup.select("div[data-dropdown-content][id]")}
        authors = []
        for head in self.soup.select("div.custom-tootip-head[data-dropdown]"):
            tag = head.select_one("p.author-title") or head
            name = _LEADING_TITLE.sub("", squash(_TITLE_IN_BRACKETS.sub(" ", tag.get_text(" "))))
            if not name:
                continue
            popup = popups.get(head["data-dropdown"])
            authors.append({"name": name, "affiliations": _popup_lines(popup) if popup is not None else [],
                            "is_corresponding": False})
        return authors

    def _corresponding_entries(self):
        """(name, correspondence address) for each author the Author Info tab lists under "Corresponding author"."""
        info = self.soup.find(id=_AUTHOR_INFO_TAB)
        if info is None:
            return []
        entries, labelled = [], False
        for h4 in info.find_all("h4"):
            # an h4's own spans (older pages leave the label's h4 open around the name's h4)
            spans = h4.find_all("span", recursive=False)
            texts = [squash(s.get_text(" ")) for s in spans] or [squash("".join(h4.find_all(string=True, recursive=False)))]
            name_parts = []
            for text in texts:
                if m := _CORRESPONDING_LABEL.match(text):
                    labelled = True
                    text = m.group(1)
                if text:
                    name_parts.append(text)
            name = " ".join(name_parts).strip(" ,")
            if labelled and name:
                entries.append((name, self._address_after(h4, info)))
        return entries

    @staticmethod
    def _address_after(h4, info):
        for node in h4.find_all_next(["p", "h4", "hr"], limit=4):
            if node.name != "p" or info not in node.parents:
                return None
            text = squash(node.get_text(" "))
            if text and not _EMAIL_LINE.match(text):
                return _PHONE_TAIL.sub("", text).strip(" ,;") or None
        return None

    def _references(self):
        """(references, references_complete): the <ol> under the Article tab's one "References" heading. Whole when
        it is that heading's only list, starts at 1, and no other text sits in it or beside it (the site's copyright
        line printed into some lists is not reference text)."""
        # imported here: back_matter imports this package, which imports every parser module
        from parseland_lib.back_matter import _clean_doi, _pick_doi, _printed_doi

        article = self.soup.find(id=_ARTICLE_TAB)
        if article is None:
            return None, False
        headings = [h for h in article.find_all(_SECTION_HEADINGS) if _REFERENCES_HEADING.match(h.get_text(" "))]
        if not headings:
            return None, False
        heading = headings[-1]
        found = heading.find_next(["ol", "ul"])
        if found is None or article not in found.parents or found.find_previous(_SECTION_HEADINGS) is not heading:
            return None, False
        refs, skipped = [], False
        for item in found.find_all("li", recursive=False):
            link = item.find("a", href=re.compile(r"doi\.org/10\."))
            item = copy.copy(item)
            for a in item.find_all("a"):
                if _LINK_LABEL.match(a.get_text()):
                    a.decompose()
            raw = squash(item.get_text())
            if not raw:
                skipped = True
                continue
            doi = _pick_doi(_clean_doi(unquote(link["href"])) if link is not None else None, _printed_doi(raw))
            refs.append({"position": len(refs) + 1, "raw": raw, "doi": doi})
        if not refs:
            return None, False
        stray = [squash(s) for s in found.find_all(string=True, recursive=False) if not isinstance(s, Comment)]
        beside = []
        if found.parent is heading.parent:
            for node in list(heading.next_siblings):
                if node is found:
                    continue
                if getattr(node, "name", None) in _SECTION_HEADINGS:
                    break
                if not isinstance(node, Comment):
                    beside.append(squash(node.get_text(" ") if hasattr(node, "get_text") else str(node)))
        else:
            beside.append("list not beside its heading")
        whole = (found.name == "ol" and not skipped and len(headings) == 1 and (found.get("start") or "1").strip() == "1"
                 and not any(t and not _SITE_FOOTER.match(t) for t in stray + beside)
                 and not _MORE.search(found.get_text(" ")))
        return refs, whole

    def parse(self):
        authors = self._authors()
        for name, address in self._corresponding_entries():
            hits = [a for a in authors if _same_author(name, a["name"])]
            if len(hits) > 1:  # two byline names fit: only the one with the same tokens decides
                hits = [a for a in hits if set(_name_tokens(a["name"])) == set(_name_tokens(name))]
            if len(hits) != 1:
                continue
            author = hits[0]
            author["is_corresponding"] = True
            if address and _ORGANISATION.search(address) and not any(
                    _same_place(address, aff) for aff in author["affiliations"]):
                author["affiliations"].append(address)
        references, complete = self._references()
        return {"authors": authors, "abstract": None, "acknowledgments": None, "funding_statement": None,
                "references": references, "references_complete": complete}
