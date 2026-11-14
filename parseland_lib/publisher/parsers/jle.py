"""John Libbey Eurotext (www.jle.com) article pages (oxjob #2210, Parseland swarm pilot).

The site's article page opens on its "Résumé" tab, ``section.tab_content div.texte``:

- the byline: one ``div.auteur`` per author (older pages: one ``div.auteur`` holding every name), each name an
  ``<a href="...dans=auteur...">`` followed by ``<sup>N</sup>`` links to ``#xref_note_affN`` and a ``*`` link to
  ``#xref_note_cor1``;
- ``div.affiliation`` blocks: numbered ones (``a.xref_aff name="xref_note_affN"``), unnumbered ones (one line for the
  whole byline on older pages, or numbered only by order), and notes in the same class (the starred correspondence
  or reprints note ``a.xref_cor``, "Liens d'intérêt", a bare e-mail);
- ``ul.resume`` (keywords, DOI, pages, year), then the abstract paragraphs, ``h4`` labels for structured ones.

For a work with no abstract the tab shows the first ~500 characters of the body ending in "[...]": that preview is
not an abstract (both labellers, 13 Nov 2026). Acknowledgments, funding and references sit on other tabs, so this
parser returns none of them. The 2026 redesign (``/revues/<journal>/doc/...``, Bootstrap markup) has no ``div.texte``
and is left to the generic parser (2 of 57 stored article pages).
"""
import re
from urllib.parse import urlparse

from bs4 import NavigableString, Tag

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import name_position, _fold_name

_HOSTS = ("jle.com", "www.jle.com")
_EMAIL = re.compile(r"<?\s*[\w.+-]+@[\w-]+(?:\.[\w-]+)+\s*>?")
# notes that share the affiliation class: correspondence / reprints lines and "Label :" lines
_NOTE_START = re.compile(r"^\W*(?:correspondan(?:ce|t)|correspondence|corresponding|auteur correspondant|"
                         r"tir[ée]s? [àa] part|reprints?|e-?mail|courriel)\b", re.I)
_COR_WORDS = re.compile(r"correspond|tir[ée]s? [àa] part|reprint", re.I)
_PREVIEW_END = re.compile(r"\[\s*(?:\.\.\.|…)\s*\]\s*$")
_MIN_ABSTRACT = 50


def _squash(text):
    return re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()


def _surname_in(name, text):
    """The author's surname alone, as a word of the note ("Tirés à part : L. Rochette": name_position reads a
    three-letter given name such as "Luc" as initials and misses it)."""
    tokens = _fold_name(name).split()
    surname = tokens[-1] if len(tokens) > 1 else ""
    return len(surname) >= 3 and re.search(rf"\b{re.escape(surname)}\b", _fold_name(text)) is not None


def _one(authors, test):
    """The index of the one author that passes test, else None."""
    hits = [i for i, a in enumerate(authors) if test(a["name"])]
    return hits[0] if len(hits) == 1 else None


def _email_owner(authors, local):
    """The one author whose surname (else first given name) an e-mail's local part carries, or None."""
    def tokens(name):
        t = _fold_name(name).split()
        return t if len(t) >= 2 else []
    by_surname = [i for i, a in enumerate(authors) if (t := tokens(a["name"])) and len(t[-1]) >= 3 and t[-1] in local]
    if by_surname:
        return by_surname[0] if len(by_surname) == 1 else None
    return _one(authors, lambda n: bool(t := tokens(n)) and len(t[0]) >= 4 and t[0] in local)


class JLE(PublisherParser):
    parser_name = "jle"

    def _texte(self):
        return self.soup.select_one("section.tab_content div.texte")

    def is_publisher_specific_parser(self):
        for name in ("citation_fulltext_html_url", "citation_pdf_url", "citation_abstract_html_url"):
            tag = self.soup.select_one(f'meta[name="{name}"]')
            if tag is not None and urlparse((tag.get("content") or "").strip()).netloc.lower() in _HOSTS:
                return True
        return False

    def authors_found(self):
        texte = self._texte()
        return bool(texte and texte.select('div.auteur a[href*="dans=auteur"]'))

    # ---- byline -------------------------------------------------------------------------------------------------

    def _byline(self, texte):
        """[(name, [aff refs], cor ref or None)] in byline order."""
        out = []
        for div in texte.select("div.auteur"):
            for a in div.find_all("a"):
                href = a.get("href") or ""
                if "dans=auteur" in href:
                    name = _squash(a.get_text())
                    if name:
                        out.append([name, [], None])
                elif out and "#xref_note_" in href:
                    ref = href.split("#", 1)[1]
                    if ref.startswith("xref_note_cor"):
                        out[-1][2] = ref
                    else:
                        out[-1][1].append(ref)
        return out

    # ---- affiliation blocks -------------------------------------------------------------------------------------

    @staticmethod
    def _aff_text(div):
        """The block's text without its number, lines split by <br/> joined with ", ", e-mails dropped."""
        parts, cur = [], []
        for node in div.descendants:
            if isinstance(node, Tag):
                if node.name == "br":
                    parts.append("".join(cur))
                    cur = []
            elif type(node) is NavigableString and node.find_parent("a", class_="xref_aff") is None:
                cur.append(str(node))
        parts.append("".join(cur))
        text = ""
        for part in (_squash(p) for p in parts):
            if part:
                sep = "" if not text or text.endswith("-") else " " if text.endswith((",", ";")) else ", "
                text = f"{text}{sep}{part}"
        return _squash(_EMAIL.sub(" ", text)).strip(" ,;")

    def _blocks(self, texte):
        """(numbered {ref: text}, unnumbered [text], notes [div])."""
        numbered, unnumbered, notes = {}, [], []
        for div in texte.select("div.affiliation"):
            if div.select_one("a.xref_cor"):
                notes.append(div)
                continue
            first = div.find(True)
            lead = _squash(first.get_text()) if first is not None else ""
            plain = _squash(div.get_text())
            if (first is not None and first.name == "b" and lead.endswith(":") and plain.startswith(lead)) \
                    or _NOTE_START.match(plain):
                notes.append(div)
                continue
            text = self._aff_text(div)
            if not re.search(r"[^\W\d_]{2}", text):  # a bare e-mail or nothing left
                continue
            anchor = div.select_one("a.xref_aff[name]")
            if anchor is not None:
                numbered[anchor["name"]] = text
            else:
                unnumbered.append(text)
        return numbered, unnumbered, notes

    # ---- corresponding ------------------------------------------------------------------------------------------

    @staticmethod
    def _note_text(div):
        return _squash(div.get_text(" ")).lstrip("* ").strip()

    def _mark_from_notes(self, authors, byline, notes):
        cor_notes = {}
        for div in notes:
            anchor = div.select_one("a.xref_cor[name]")
            text = self._note_text(div)
            if anchor is not None and text:
                cor_notes[anchor["name"]] = text
            elif anchor is None and _COR_WORDS.search(text):
                cor_notes.setdefault(None, text)
        # 1. a byline '*' that links to an explained note
        linked = [i for i, (_, _, ref) in enumerate(byline) if ref and cor_notes.get(ref)]
        if linked:
            for i in linked:
                authors[i]["is_corresponding"] = True
            return
        for text in cor_notes.values():
            # 2. the note names one author ("Correspondance : P. Wils")
            bare = _EMAIL.sub(" ", text)
            named = [i for i, a in enumerate(authors) if name_position(a["name"], bare) is not None]
            if not named:
                named = [i for i, a in enumerate(authors) if _surname_in(a["name"], bare)]
            if len(named) == 1:
                authors[named[0]]["is_corresponding"] = True
                return
            # 3. the note's e-mail carries one author's surname
            emails = [m.group(0) for m in _EMAIL.finditer(text)]
            if emails:
                local = _fold_name(emails[0].strip("<> ").split("@")[0]).replace(" ", "")
                if (owner := _email_owner(authors, local)) is not None:
                    authors[owner]["is_corresponding"] = True
                    return
            # 4. a correspondence note on a one-author page
            if len(authors) == 1 and (_COR_WORDS.search(text) or emails):
                authors[0]["is_corresponding"] = True
                return

    def parse_authors(self):
        texte = self._texte()
        byline = self._byline(texte)
        numbered, unnumbered, notes = self._blocks(texte)
        any_refs = any(refs for _, refs, _ in byline)
        authors = []
        for name, refs, _ in byline:
            affs = []
            for ref in refs:
                text = numbered.get(ref)
                if text is None and not numbered and (m := re.fullmatch(r"xref_note_aff(\d+)", ref)):
                    n = int(m.group(1))  # numbered by order only
                    text = unnumbered[n - 1] if 0 < n <= len(unnumbered) else None
                if text and text not in affs:
                    affs.append(text)
            if not any_refs:  # unlinked: every author gets the whole list
                affs = list(unnumbered) or list(numbered.values())
            authors.append({"name": name, "affiliations": affs, "is_corresponding": False})
        self._mark_from_notes(authors, byline, notes)
        return authors

    # ---- abstract -----------------------------------------------------------------------------------------------

    def parse_abstract(self):
        texte = self._texte()
        resume = texte.select_one("ul.resume")
        if resume is None:
            return None
        paras, label = [], None
        for node in resume.find_next_siblings():
            if node.name in ("h4", "h5"):
                label = _squash(node.get_text())
                continue
            if node.name in ("ul", "ol"):  # a list inside the abstract ("nous rappelons : - ...; - ...")
                for item in node.find_all("li"):
                    text = _squash("".join(t for t in item.find_all(string=True)
                                           if t.find_parent("span", class_="label") is None))
                    if text:
                        paras.append(text)
                continue
            if node.name != "p":
                continue
            if node.select_one('img[alt="Licence"], a.tool_PDF') or node.select_one('a[href*="creativecommons.org"]'):
                continue
            text = _squash(node.get_text())
            if not text:
                continue
            paras.append(f"{label.rstrip(' :')}: {text}" if label else text)
            label = None
        abstract = "\n".join(paras)
        if len(abstract) < _MIN_ABSTRACT or _PREVIEW_END.search(abstract):
            return None
        return abstract

    def parse(self):
        return {"authors": self.parse_authors(), "abstract": self.parse_abstract()}
