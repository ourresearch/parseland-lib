"""Universum scientific journals (7universum.com, ООО «МЦНО», Moscow) article pages (oxjob #2339).

The site runs its own CMS. One article page per DOI (https://7universum.com/ru/<journal>/archive/item/<n>):
- a byline `div.authors_article` with one link per author, short names ("Шамшидинов И.Т.");
- the body `div.article_content`: an "АННОТАЦИЯ" heading paragraph and the Russian abstract, an "ABSTRACT" heading and
  the English one (either order; older pages and 2026 pages use <p><strong>, newer ones <h2>), "Ключевые слова:" and
  "Keywords:", the text, then "Список литературы:" / "References:" followed by one <ol> (or, on 2026 pages, an <h2>
  and "1. ..." paragraphs), sometimes followed by the same list transliterated under "References";
- `div.author_information`: one `div.item` per author, in byline order, each with one `div.information` per language
  (`.name` full name, `.post` "degree, position, organisation, country, city").
No citation_* meta tags; the meta description holds the citation, which the generic parser took for the abstract.
Nothing on the page marks a corresponding author. The pages' canonical link names the site, and the claim reads only
the <head>'s own children, so pages of other sites cost almost nothing.
"""
import re
from urllib.parse import urlsplit

from parseland_lib.publisher.parsers.parser import PublisherParser

HOSTS = {"7universum.com", "www.7universum.com"}
WS = re.compile(r"\s+")
CYR = re.compile(r"[А-Яа-яЁё]")
# (heading key without spaces: "A BSTRACT" is a heading; inline label: "ABSTRACT: The article ...")
EN_ABSTRACT = ("abstract", re.compile(r"^\s*abstract\s*[.:]\s*(?=\S)", re.I), re.compile(r"[A-Za-z]"))
RU_ABSTRACT = ("аннотация", re.compile(r"^\s*аннотация\s*[.:]\s*(?=\S)", re.I), CYR)
ABSTRACT_END = re.compile(r"^\s*(аннотация|abstract|a\s?bstract|ключевые\s+слов\w*|keywords?|key\s+words|введение|"
                          r"introduction)\b", re.I)
LATIN = re.compile(r"[A-Za-z]")
REFS_HEADING = re.compile(r"^(список(использованной|использованных)?(литературы|источников)(иисточников)?|"
                          r"библиографическийсписок|литература|references|literature|bibliography)[:.]?$")
NUMBERED = re.compile(r"^(\d{1,3})\s*\.\s*(\S.*)$", re.S)
DOI = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>«»]+)")
SHOW_MORE = re.compile(r"(?i)show more|load more|показать (все|ещ[её])")
BLOCKS = ["p", "h1", "h2", "h3", "h4", "h5", "h6", "ol", "ul"]
HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

# A .post is "degree, position, organisation, country, city". Leading comma-separated parts with no organisation word
# are degrees and positions ("д-р техн. наук", "PhD", "доцент"); a position word may also open the organisation part
# ("докторант Академии ...", "Professor of Namangan ... institute"). Shortcut: word lists from the 52 sample pages;
# a part they miss stays in the string (the gate's fuzzy match still takes a short lead-in).
ORG_WORD = re.compile(
    r"(университет|институт|академи|колледж|лице[йя]|школ|центр|лаборатор|кафедр|факультет|отдел|больниц|клиник|"
    r"госпитал|министерств|комитет|филиал|управлени|предприяти|компани|корпораци|объединени|фонд|музе[йя]|"
    r"библиотек|\bООО\b|\bОАО\b|\bЗАО\b|\bАО\b|\bТОО\b|\bГУП\b|ФГБОУ|ФГАОУ|ФГБУ|ГБУЗ|\bРАН\b|\bНИИ\b|\bМЧС\b|"
    r"universit|institut|academ|college|school|cent(er|re)|laborator|department|faculty|hospital|clinic|ministry|"
    r"branch|company|committee|agency|foundation|museum|library|lyceum|\bLLC\b|\bLLP\b|\bJSC\b|\bLtd\b|\bInc\b)",
    re.I)
POSITION_LEAD = re.compile(
    r"^((базовый\s+)?докторант(ка)?|аспирант(ка)?|магистрант(ка)?|студент(ка)?|соискатель|ассистент(\s+преподаватель)?|"
    r"(старший\s+|ст\.\s*)?преп(одаватель|одователь|\.)|доцент|доц\.|профессор|проф\.|"
    r"(старший\s+|младший\s+|ведущий\s+|ст\.\s*|мл\.\s*|вед\.\s*)?(научный\s+сотрудник|науч\.\s*сотр\.)|[мс]\.\s*н\.\s*с\.|инженер|"
    r"зав\.|заведующ\w*|"
    r"(basic\s+)?doctoral\s+(student|candidate)|ph\.?\s*d\.?\s+(student|candidate)|postgraduate\s+student|"
    r"(senior\s+|junior\s+)?(lecturer|teacher|researcher)|(associate\s+|assistant\s+)?professor|assistant|applicant|"
    r"masters?(\s+student)?|student)"
    r"\.?(\s+(of|at|in)(\s+the)?)?\s+", re.I)


def _text(node):
    return WS.sub(" ", node.get_text(" ").replace("\xa0", " ")).strip()


def _key(text):
    return WS.sub("", text).lower()


def _mostly(text, script):
    """Most of the text's letters are in `script` (Cyrillic or Latin)."""
    own, other = len(script.findall(text)), len((LATIN if script is CYR else CYR).findall(text))
    return own >= other


def _start(ol):
    try:
        return int(str(ol.get("start") or 1).strip())
    except ValueError:
        return 2  # an unreadable start is no evidence of a whole list


def _affiliation(post):
    parts = [p.strip() for p in post.split(",")]
    first = next((i for i, p in enumerate(parts) if ORG_WORD.search(p)), None)
    if first is None:
        return post.strip(" ,;.")
    parts = parts[first:]
    lead = POSITION_LEAD.match(parts[0])
    if lead and ORG_WORD.search(parts[0][lead.end():]):
        parts[0] = parts[0][lead.end():]
    return ", ".join(p for p in parts if p).strip(" ,;")


class Universum7(PublisherParser):
    parser_name = "7universum"
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        if "_claimed" not in self.__dict__:
            self._claimed = self._item = False
            html = self.soup.find("html", recursive=False)
            head = html.find("head", recursive=False) if html is not None else None
            if head is not None:
                for link in head.find_all("link", recursive=False):
                    if "canonical" in (link.get("rel") or []):
                        try:
                            url = urlsplit((link.get("href") or "").strip())
                        except ValueError:
                            break
                        self._claimed = url.netloc.lower() in HOSTS
                        self._item = "/archive/item/" in url.path  # an article, not an issue's contents page
                        break
        return self._claimed

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._read()["authors"])

    def parse(self):
        return self._read()

    # ---- reading ----

    def _read(self):
        if "_cache" not in self.__dict__:
            out = {"authors": [], "abstract": None, "acknowledgments": None, "funding_statement": None,
                   "references": None, "references_complete": False}
            if self.is_publisher_specific_parser() and self._item:
                out["authors"] = self._authors()
                body = self.soup.select_one("div.article_content")
                if body is not None:
                    blocks = [b for b in body.find_all(BLOCKS) if b.name in ("ol", "ul") or _text(b)]
                    out["abstract"] = self._abstract(blocks)
                    out["references"], out["references_complete"] = self._references(blocks)
            self._cache = out
        return self._cache

    def _authors(self):
        byline = [_text(a) for a in self.soup.select("div.authors_article a")]
        items = self.soup.select("div.author_information div.item")
        authors = []
        if items and (not byline or len(items) == len(byline)):
            for i, item in enumerate(items):
                infos = item.select("div.information")
                if not infos:
                    return []
                info = infos[0]
                if byline:  # the language version in the byline's script
                    cyr = bool(CYR.search(byline[i]))
                    info = next((x for x in infos if x.select_one(".name") is not None
                                 and bool(CYR.search(_text(x.select_one(".name")))) == cyr), infos[0])
                name_tag, post_tag = info.select_one(".name"), info.select_one(".post")
                name = _text(name_tag) if name_tag is not None else ""
                if not name and byline:
                    name = byline[i]
                if not name:
                    return []
                aff = _affiliation(_text(post_tag)) if post_tag is not None else ""
                authors.append({"name": name, "affiliations": [aff] if aff else [], "is_corresponding": False})
        else:
            authors = [{"name": n, "affiliations": [], "is_corresponding": False} for n in byline if n]
        return authors

    @staticmethod
    def _section(blocks, label):
        """The paragraphs after the heading block `label` names (or after its inline label), up to the keywords, the
        next heading, or a paragraph in the other language (pages without a keywords line run into the text)."""
        key, inline, script = label
        for i, b in enumerate(blocks):
            if b.name in ("ol", "ul"):
                continue
            t = _text(b)
            m = None if _key(t).rstrip(".:") == key else inline.match(t)
            if m is None and _key(t).rstrip(".:") != key:
                continue
            paras = [t[m.end():]] if m else []
            for nxt in blocks[i + 1:]:
                if nxt.name in ("ol", "ul") or any(p is b for p in nxt.parents):
                    continue
                nt = _text(nxt)
                if nxt.name in HEADINGS or ABSTRACT_END.match(nt) or not _mostly(nt, script):
                    break
                paras.append(nt)
            if paras:
                return "\n".join(paras)
        return None

    def _abstract(self, blocks):
        # the English version when the page shows one (label-v1), else the Russian
        return self._section(blocks, EN_ABSTRACT) or self._section(blocks, RU_ABSTRACT)

    @staticmethod
    def _references(blocks):
        start = next((i for i, b in enumerate(blocks)
                      if b.name not in ("ol", "ul") and REFS_HEADING.match(_key(_text(b)))), None)
        if start is None or start + 1 >= len(blocks):
            return None, False
        rest = blocks[start + 1:]
        first = rest[0]
        if first.name == "ol":
            items = [_text(li) for li in first.find_all("li", recursive=False)]
            items = [t for t in items if t]
            after = [b for b in rest[1:] if not any(p is first for p in b.parents)]
            whole = (bool(items) and _start(first) <= 1 and not SHOW_MORE.search(_text(first))
                     and (not after or bool(REFS_HEADING.match(_key(_text(after[0]))))))
        else:
            items, nums, after = [], [], []
            for j, b in enumerate(rest):
                m = NUMBERED.match(_text(b)) if b.name == "p" else None
                if not m:
                    after = rest[j:]
                    break
                nums.append(int(m.group(1)))
                items.append(m.group(2).strip())
            whole = (bool(items) and nums == list(range(1, len(nums) + 1))
                     and (not after or bool(REFS_HEADING.match(_key(_text(after[0]))))))
        if not items:
            return None, False
        refs = []
        for pos, raw in enumerate(items, 1):
            d = DOI.search(raw)
            refs.append({"position": pos, "raw": raw, "doi": d.group(1).rstrip(".,;:)]") if d else None})
        return refs, whole

