"""Revista FT (revistaft.com.br), a WordPress journal site (oxjob #2339).

The post body (div.entry-content) prints the byline as its first right-aligned paragraph: names split by line breaks,
";" or ",", each followed by a footnote marker (<sup>1</sup>, a Word footnote link "[1]", a Unicode superscript "¹",
or "*"); an advisor is named "Orientador(a): Prof. Dr. ...". The footnotes are right-aligned paragraphs after the
post's last separator, one marker each (or "1,2,3,4" for several authors), often with a role, a degree and an e-mail
around the institution. The page has no citation_author tags, so Parseland read no authors before this parser.
Kept: the footnote text without e-mails, ORCID iDs, Lattes links and an "Instituição:" label, and only when it names
an organisation (a bare degree such as "Mestre." or a student number is not an affiliation). A footnote with no
marker, under a byline with no markers, goes to every author (the rubric's unlinked case). The one explicit
"Autor correspondente" note in the sample is left alone (under the swarm's 1,000-works floor), so nobody is marked.
"""
import copy
import re

from bs4 import Tag

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser

_HOST = re.compile(r"^https?://(www\.)?revistaft\.com\.br/", re.I)
_SUPERSCRIPTS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")
_MARK = re.compile(r"\x01([^\x02]*)\x02")
_SUP_MARK = re.compile(r"\s*([\d\s,*∗]*?[\d*∗][\d\s,*∗]*?)\s*([;.,]?)\s*")
_ROLE = re.compile(r"^\s*(?:(?:professora?|prof\.?ª?)\s+)?(?:co-?)?orientador(?:a|\s*\(a\))?\s*:?\s*"
                   r"|^\s*(?:alun[oa]|professora?|autora?|discente|docente)\s*:\s*", re.I)
_HONORIFIC = re.compile(r"^\s*(?:prof(?:a|ª)?\.?|dr(?:a|ª)?\.?|me\.|ma\.|msc\.?|esp\.|ph\.?\s?d\.?)(?:\s*\(a\)\.?)?\s+", re.I)
_ORG = re.compile(r"\b(?:universi\w*|faculdade\w*|facultad\w*|faculty|institut\w*|institui\w*|centro|cent(?:er|re)|"
                  r"funda[cç][aã]o|escola|school|hospita\w*|minist[eé]rio|secretaria|prefeitura|departamento|department|"
                  r"col[eé]gio|college|laborat[oó]rio|academia|liga|tribunal|promotoria|programa)\b", re.I)
_ACRONYM = re.compile(r"\b[A-Z][A-Za-z]*[A-Z]{2,}[A-Za-z]*\b|\b[A-Z]{3,}\b")
_NOT_ORG_ACRONYMS = {"ORCID", "DOI", "CPF", "RG", "RA", "URL", "HTTP", "HTTPS", "PHD", "MBA", "MSC"}
_REF_HEADING = re.compile(r"^(?:\d+\s*[.:–-]?\s*)?(?:REFER[ÊE]NCIAS?(?:\s+BIBLIOGR[ÁA]FICAS?)?|REFERENCES|BIBLIOGRAFIA)"
                          r"\s*[:.]?$", re.I)
_AFTER_REFS = re.compile(r"^(?:ANEXOS?|AP[ÊE]NDICES?)\b", re.I)
_UNI_NAME = re.compile(r"\bUni[a-zà-ÿ]{3,}")  # one-word institution names: Unicarioca, Unifacisa, Unicamp
_INVISIBLE = re.compile(r"[\u200b-\u200f\u2060\ufeff]")
_DOI = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+)")


def _flatten(tag):
    """The tag's text with footnote markers as \\x01key\\x02 and line breaks as newlines (on a copy: never edit the page)."""
    tag = copy.copy(tag)
    for br in tag.find_all("br"):
        br.replace_with("\n")
    for a in tag.find_all("a"):
        if m := re.fullmatch(r"\s*\[(\d{1,2})\]\s*", a.get_text()):
            a.replace_with(f"\x01{m.group(1)}\x02")
    for sup in tag.find_all("sup"):
        text = sup.get_text()
        m = _SUP_MARK.fullmatch(text)
        sup.replace_with(f"\x01{m.group(1)}\x02{m.group(2)}" if m else text)
    text = tag.get_text().replace("\xa0", " ")
    text = re.sub(r"\[(\d{1,2})\]", "\x01\\1\x02", text)
    return re.sub(r"[⁰¹²³⁴⁵⁶⁷⁸⁹]+(?:,[⁰¹²³⁴⁵⁶⁷⁸⁹]+)*", lambda m: f"\x01{m.group(0).translate(_SUPERSCRIPTS)}\x02", text)


def _keys(marker_text):
    return [k.replace("∗", "*") for k in re.findall(r"\d+|[*∗]", marker_text)]


def _clean_name(raw):
    name = " ".join(_INVISIBLE.sub("", raw).split()).strip(" .,;:")
    stars = re.search(r"[*∗]+$", name)
    name = name[:stars.start()].strip(" .,;:") if stars else name
    for _ in range(4):
        before = name
        name = _HONORIFIC.sub("", _ROLE.sub("", name)).strip(" .,;:")
        if name == before:
            break
    if (m := re.fullmatch(r"([A-ZÀ-Ý][A-ZÀ-Ý' -]+),\s*(.+)", name)) and "," not in m.group(2):
        name = f"{m.group(2)} {m.group(1).strip()}"  # "OLIVEIRA, L. da S." -> "L. da S. OLIVEIRA"
    words = name.split()
    if not 2 <= len(words) <= 12 or len(name) > 100 or re.search(r"[\d@:()]", name):
        return None
    return name, bool(stars)


def _byline_entries(text):
    """[(name, [marker keys])] in byline order."""
    plain = _MARK.sub("", text)
    sep = r"[;\n]" if ";" in plain else r"[;\n,]"
    entries, name, keys = [], "", []
    for piece in re.split(r"(\x01[^\x02]*\x02)", text):
        if piece.startswith("\x01"):
            keys += _keys(piece[1:-1])
            continue
        parts = re.split(sep, piece)
        name += parts[0]
        for part in parts[1:]:
            entries.append((name, keys))
            name, keys = part, []
    entries.append((name, keys))
    out = []
    for raw, keys in entries:
        if cleaned := _clean_name(raw):
            name, starred = cleaned
            out.append((name, keys + (["*"] if starred else [])))
    return out


def _clean_note(text):
    lines = [" ".join(line.split()) for line in text.split("\n")]
    labelled = [line for line in lines if re.match(r"^institui[çc][ãa]o\s*:", line, re.I)]
    text = re.sub(r"^institui[çc][ãa]o\s*:\s*", "", labelled[0], flags=re.I) if labelled else " ".join(lines)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\bORCID\b\s*(?:n[º°o]\.?)?\s*:?\s*(?:\d{4}-\d{4}-\d{4}-\d{3}[\dX])?\.?", " ", text, flags=re.I)
    text = re.sub(r"\b\d{4}-\d{4}-\d{4}-\d{3}[\dX]\b\.?", " ", text)
    text = re.sub(r"\b(?:link\s+)?(?:do\s+)?(?:curr[ií]culo\s+)?lattes\s*:?", " ", text, flags=re.I)
    text = re.sub(r"\be-?mail(?:\s+para\s+contato)?\s*:?", " ", text, flags=re.I)
    text = re.sub(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+[.,;]?", " ", text)
    text = re.sub(r"(?:\s*[–/|,;:-]\s*){2,}", " – ", " ".join(text.split()))
    text = re.sub(r"\s+([.,;])", r"\1", text)
    return text.strip(" –/|,;:-")


def _names_org(text):
    if _ORG.search(text) or _UNI_NAME.search(text):
        return True
    return any(m.group(0).upper() not in _NOT_ORG_ACRONYMS for m in _ACRONYM.finditer(text))


def _is_heading(tag):
    """A paragraph that is all bold (a section heading: "ANEXO A ...", "Dados Gerais"), or an appendix's title."""
    if tag.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
        return True
    text = " ".join(tag.get_text(" ", strip=True).split())
    if not text:
        return False
    if _AFTER_REFS.match(text):
        return True
    bold = " ".join(" ".join(b.get_text(" ", strip=True).split()) for b in tag.find_all(["strong", "b"]))
    return len(bold) >= 0.9 * len(text)


class RevistaFT(PublisherParser):
    parser_name = "revistaft"
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        if getattr(self, "_claimed", None) is None:
            self._claimed = self._claim()
        return self._claimed

    def _claim(self):
        """Both <head> marks: the journal-title tag "Revista ft" and a canonical link on revistaft.com.br. Only the
        <head> is searched, so other sites' pages cost a <head> scan, never a whole-tree walk."""
        head = self.soup.head
        if head is None:
            return False
        title = head.find("meta", attrs={"name": "citation_journal_title"})
        if title is None or (title.get("content") or "").strip().lower() != "revista ft":
            return False
        canonical = head.find("link", rel="canonical")
        return canonical is not None and bool(_HOST.match(canonical.get("href") or ""))

    def _body(self):
        if not hasattr(self, "_entry"):
            self._entry = self.soup.select_one("article div.entry-content") or self.soup.select_one("div.entry-content")
        return self._entry

    def _byline(self):
        body = self._body()
        return body.find("p", class_="has-text-align-right", recursive=False) if body is not None else None

    def authors_found(self):
        if not self.is_publisher_specific_parser():
            return False
        byline = self._byline()
        return byline is not None and bool(_byline_entries(_flatten(byline)))

    def _notes(self, byline):
        """{marker key: [note text]} and the unmarked notes, from the paragraphs after the body's last separator."""
        children = [c for c in self._body().children if isinstance(c, Tag)]
        last_hr = max((i for i, c in enumerate(children) if c.name == "hr"), default=-1)
        if last_hr < 0 or last_hr <= children.index(byline) + 1:
            return {}, []
        keyed, unmarked = {}, []
        for p in children[last_hr + 1:]:
            if p.name != "p":
                continue
            current = None
            for line in _flatten(p).split("\n"):
                line = line.strip()
                if not line:
                    continue
                m = re.match(r"^(?:\x01([^\x02]*)\x02|([*∗]))\s*", line)
                if m:
                    current = {"keys": _keys(m.group(1) or m.group(2)), "lines": [line[m.end():]]}
                    for key in current["keys"]:
                        keyed.setdefault(key, []).append(current)
                elif current is not None:
                    current["lines"].append(line)
                else:
                    current = {"keys": [], "lines": [line]}
                    unmarked.append(current)
        texts = lambda notes: [t for n in notes if (t := _clean_note("\n".join(n["lines"]))) and _names_org(t)]  # noqa: E731
        return {k: texts(v) for k, v in keyed.items()}, texts(unmarked)

    def _authors(self):
        byline = self._byline()
        entries = _byline_entries(_flatten(byline))
        keyed, unmarked = self._notes(byline)
        any_marker = any(keys for _, keys in entries)
        authors = []
        for name, keys in entries:
            affs = []
            for key in keys:
                for text in keyed.get(key, []):
                    if text not in affs:
                        affs.append(text)
            if not any_marker:
                affs = list(unmarked)
            authors.append({"name": name, "affiliations": affs, "is_corresponding": False})
        return authors

    def _references(self):
        body = self._body()
        children = [c for c in body.children if isinstance(c, Tag)] if body is not None else []
        start = next((i for i, c in enumerate(children) if c.name in ("p", "h2", "h3", "h4", "h5", "h6")
                      and _REF_HEADING.match(" ".join(c.get_text(" ", strip=True).split()))), None)
        if start is None:
            return [], False
        raws, lists = [], 0
        for c in children[start + 1:]:
            if c.name == "hr" or _is_heading(c):
                break
            if c.name in ("ol", "ul"):
                lists += 1
                items = [" ".join(li.get_text(" ", strip=True).split()) for li in c.find_all("li", recursive=False)]
                raws += [t for t in items if t]
                whole_ol = c.name == "ol" and int(c.get("start") or 1) <= 1
            elif c.name == "p":
                text = " ".join(c.get_text(" ", strip=True).split())
                if text:
                    raws.append(text)
        only_one_ol = lists == 1 and len(raws) == len([1 for c in children[start + 1:] if c.name == "ol"
                                                       for li in c.find_all("li", recursive=False)
                                                       if li.get_text(strip=True)])
        numbered = [re.match(r"^\[?(\d{1,3})(?:[.)\]]\s*|\s)", r) for r in raws]
        runs = all(numbered) and [int(m.group(1)) for m in numbered] == list(range(1, len(raws) + 1))
        complete = bool(raws) and ((only_one_ol and whole_ol) or runs)
        refs = []
        for i, raw in enumerate(raws, 1):
            doi = _DOI.search(raw)
            refs.append({"position": i, "raw": raw, "doi": doi.group(1).rstrip(".,;)") if doi else None})
        return refs, complete

    def parse(self):
        refs, complete = self._references()
        return {"authors": self._authors(),
                "abstract": GenericPublisherParser(self.soup).parse().get("abstract"),
                "acknowledgments": None,
                "funding_statement": None,
                "references": refs,
                "references_complete": complete}
