"""ABEPRO's proceedings pages (abepro.org.br publicacoes/artigo.asp and proceedings/artigo.asp: ENEGEP, ICIEOM,
IJCIEOM, CNEG; DOI prefix 10.14488), oxjob #2339.

One ASP template: div#resultado holds "<b>RESUMO:</b><BR> abstract <BR><BR><b>PALAVRAS-CHAVE:</b>" in its left column
and "<b>AUTORES:</b>" in its right one, each author a text line followed by <small><i>...</i></small>. Newer pages add
citation_author meta tags inside the body, older ones have none; the generic parser reads those names only, never the
abstract. This parser reads the abstract, and the byline's names so that pages with no meta tags carry it.

Affiliations are left alone: the slot is empty on 2018 pages and holds a bare number ("441") on 2025 pages, the two
years whose works lack affiliations; every other year's works already have theirs (sample of 80 pages, 17 Nov 2026).
The page shows no corresponding author, acknowledgments, funding statement or reference list. ABEPRO's journals
(Produção Online, BJOPM) run Open Journal Systems and are left to the OJS readers.

Pages stored from 2023 on lost every non-ASCII byte at fetch ("PRODUO" for "PRODUÇÃO"): the parser reads them as they
are; the fix is a re-fetch (#1790), not here.
"""
import re

from bs4 import Comment, NavigableString

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

# The <title> every event page prints: "Anais Enegep | Proceedings ICIEOM", "Proceedings IJCIEOM", "Anais CNEG".
_TITLE = re.compile(r"^\s*(?:Anais (?:Enegep|CNEG)|Proceedings IJ?CIEOM)\b", re.I)
_C1 = re.compile("[\u0080-\u009f]")
_BREAK = "\u2028"  # a <br>: the abstract's paragraphs split here, never at the markup's own line ends


# A UTF-8 letter read as Latin-1 whose second byte is a C1 control ("Ã\\x9a" for Ú): the pair goes back to UTF-8.
_UTF8_PAIR = re.compile("[\u00c2-\u00df][\u0080-\u009f]")


def _cp1252(match):
    """A C1 control character is a Windows-1252 byte read as Latin-1 (\\x92 for ’): give back the letter."""
    try:
        return match.group(0).encode("latin-1").decode("cp1252")
    except UnicodeDecodeError:
        return ""


def _clean(text):
    text = _UTF8_PAIR.sub(lambda m: m.group(0).encode("latin-1").decode("utf-8"), text)
    return squash(_C1.sub(_cp1252, text))


class Abepro(PublisherParser):
    parser_name = "abepro"
    prefer_publisher_authors_over_generic = True

    def __init__(self, soup):
        super().__init__(soup)
        self._frame = False  # False: not looked for yet; None: not this template

    def _resultado(self):
        # Every DOI page asks every parser (#2239's CPU rule): the first <title> is found near the top of any page,
        # so other sites' pages stop at one string test.
        if self._frame is False:
            self._frame = None
            title = self.soup.title
            if title is not None and _TITLE.match(title.get_text()):
                frame = self.soup.find("div", id="resultado")
                if frame is not None and self._label(frame, "AUTORES") is not None:
                    self._frame = frame
        return self._frame

    @staticmethod
    def _label(frame, word):
        for b in frame.find_all("b"):
            if squash(b.get_text()).rstrip(":").strip().upper() == word:
                return b
        return None

    def is_publisher_specific_parser(self):
        return self._resultado() is not None

    def authors_found(self):
        return bool(self.is_publisher_specific_parser() and self.parse_authors())

    def parse_authors(self):
        frame = self._resultado()
        if frame is None:
            return []
        authors = []
        for node in self._label(frame, "AUTORES").next_siblings:
            if isinstance(node, Comment):
                continue
            if isinstance(node, NavigableString):  # a name; the <small> slot after it is skipped (see above)
                name = _clean(str(node))
                if name:
                    authors.append({"name": name, "affiliations": [], "is_corresponding": False})
            elif node.name == "b":
                break
        return authors

    def parse_abstract(self):
        frame = self._resultado()
        label = frame is not None and (self._label(frame, "RESUMO") or self._label(frame, "ABSTRACT"))
        if not label:
            return None
        parts = []
        for node in label.next_siblings:
            if isinstance(node, Comment):
                continue
            name = getattr(node, "name", None)
            if name == "b" or name in ("div", "table"):
                break
            parts.append(_BREAK if name == "br" else (node.get_text() if name else str(node)))
        lines = [_clean(line) for line in "".join(parts).split(_BREAK)]
        text = "\n".join(line for line in lines if line)
        return text if len(text) >= 20 else None

    def parse(self):
        return {
            "authors": self.parse_authors(),
            "abstract": self.parse_abstract(),
            "acknowledgments": None,
            "funding_statement": None,
            "references": None,
            "references_complete": False,
        }
