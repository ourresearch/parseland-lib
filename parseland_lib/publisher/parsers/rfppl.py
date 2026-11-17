import re

from parseland_lib.publisher.parsers.parser import PublisherParser


# Red Flower Publication's article pages (rfppl.co.in, Indian medical and nursing journals; oxjob #2339). The old
# PHP site (view_abstract.php, every stored page before the 2025 redesign) carries no citation_* meta tags: its
# <title> is "Red Flower Publications" on every page, and the article sits in a layout table. The row after
# td.articleTitle is the byline: either td[height=40] (names) with the next row's td.inner-content (affiliations),
# or one td holding two <p style="margin: 6px;"> (names, then affiliations). Names carry plain-text markers glued to
# them ("Koirala1", "Nischal*", "Aditya V.a"); the affiliation line repeats each marker before that author's
# position and department ("1,2Assistant Professor, 3Professor, Dept. of ..., College, City"). A marker that leads
# only a job title ("1Professor and Head, 2Tutor 3Assistant Professor, Department of X, College ...") shares the
# address that follows it, so that author gets the address from the next segment that names a department or an
# institution. "Corresponding Author : <name>, <title>, <address>" in the abstract block names the corresponding
# author; it is matched to the byline by name. The abstract is left to the generic heading reader (it reads it).
# Not read: issue tables of contents (no td.articleTitle), and the 2025 redesign (rfppl.co.in/article/..., its own
# markup, 1 of 80 sampled pages).

_TITLE = "Red Flower Publications"
_SPACES = re.compile(r"\s+")
_HONORIFIC = re.compile(r"^(?:(?:Dr|Sr|Prof|Mr|Mrs|Ms|Smt|Shri)\.?\s+)+", re.I)
_NAME_MARK = re.compile(r"\s*(?:\d{1,2}(?:\s*,\s*\d{1,2})*|\*+(?:\s*,\s*\*+)*)\s*\.?$")
_DIGITS = re.compile(r"\d{1,2}")
_STARS = re.compile(r"\*+")
# A comma between names, never one inside a marker list ("Koirala1,2, Bidita ..."); also " and " / " & ".
_NAME_SPLIT = re.compile(r",(?!\s*\d)|\s+and\s+|\s+&\s+")
# Markers in the affiliation line, before a capital: glued ("1,2Assistant", "3-6Senior"), dotted ("2.Prof") or
# spaced ("1 Assistant"). Only numbers the byline uses count, so a postcode or "Sector 12" is never one.
_AFF_DIGIT = re.compile(r"(?<![^\s,;.)])(\d{1,2}(?:\s*[,\-\u2013]\s*\d{1,2})*)[.\s]?(?=[A-Z(])")
_RANGE = re.compile(r"(\d{1,2})\s*[-\u2013]\s*(\d{1,2})")
_AFF_STAR = re.compile(r"\*+(?:\s*,\s*\*+)*")
_AFF_LETTER = re.compile(r"(?<![^\s,;.)])([a-z])(?=[A-Z])")
# What names an organisation or its part: an affiliation, not just a job title ("Professor and Head").
_ORG = re.compile(r"depart|dept|college|univers|institut|hospital|school|cent(?:re|er)\b|faculty|division|clinic|"
                  r"laborator|\bacadem(?:y|ie|ia)\b|foundation|ministry|council|sansthan|vidyap|trust|aiims|pgimer|campus|"
                  r"company|ltd|pvt|govt|government|corporation|society|nursing home|board|organi[sz]ation|agency|"
                  r"medical sciences|health services|polyclinic|unit of", re.I)
_CORR_LABEL = re.compile(r"^\s*corresponding\s+author", re.I)
_NAME_TOKEN_DROP = {"dr", "sr", "prof", "mr", "mrs", "ms", "smt", "shri"}


def _clean(text):
    return _SPACES.sub(" ", (text or "").replace("\xa0", " ")).strip()


def _digit_keys(mark):
    """'1,2' -> {'1', '2'}; '3-6' -> {'3', '4', '5', '6'}."""
    keys = set(_DIGITS.findall(_RANGE.sub("", mark)))
    for lo, hi in _RANGE.findall(mark):
        if int(lo) < int(hi) <= int(lo) + 20:
            keys |= {str(i) for i in range(int(lo), int(hi) + 1)}
    return keys


def _strip_aff(text):
    text = _clean(text).strip(" ,;&")
    text = re.sub(r"\s+(?:and|&)$", "", text).strip(" ,;")
    return text


class RedFlower(PublisherParser):
    parser_name = "red_flower_publication"
    prefer_publisher_authors_over_generic = True

    def _byline(self):
        """(names text, affiliations text) of the article's byline rows, or None when the page is not one."""
        if hasattr(self, "_byline_cache"):
            return self._byline_cache
        self._byline_cache = None
        # cheap first: the old site's fixed <title> (the soup's first <title>, in <head>)
        title = self.soup.title
        if title is None or _clean(title.get_text()) != _TITLE:
            return None
        head = self.soup.find("td", class_="articleTitle")
        if head is None:
            return None
        row = head.find_parent("tr")
        nxt = row.find_next_sibling("tr") if row is not None else None
        td = nxt.find("td") if nxt is not None else None
        if td is None:
            return None
        heading = head.find("span", class_="Heading1")
        title_text = _clean((heading or head).get_text(" "))
        if td.get("height") == "40":
            names = _clean(td.get_text(" "))
            aff_row = nxt.find_next_sibling("tr")
            aff_td = aff_row.find("td", class_="inner-content") if aff_row is not None else None
            affs = _clean(aff_td.get_text(" ")) if aff_td is not None else ""
        else:
            paras = [p for p in td.find_all("p") if _clean(p.get_text(" "))]
            if not paras:
                return None
            names = _clean(paras[0].get_text(" "))
            whole = _clean(td.get_text(" "))
            affs = whole[len(names):].strip() if whole.startswith(names) else ""
        # no byline: the row repeats the title (a page with no authors), or the affiliation row repeats the names
        if not names or names == title_text or len(names) > 600:
            return None
        if affs == names:
            affs = ""
        self._byline_cache = (names, affs)
        return self._byline_cache

    def is_publisher_specific_parser(self):
        return self._byline() is not None

    def authors_found(self):
        return self._byline() is not None

    # ---- byline -------------------------------------------------------------------------------------------------

    @staticmethod
    def _split_names(text):
        """[(name, markers)]; markers are '1'.. for digits, '*'.. for stars (one key per star count)."""
        out = []
        for raw in _NAME_SPLIT.split(text):
            raw = _clean(raw).strip(" ,;")
            if not raw:
                continue
            keys = set()
            m = _NAME_MARK.search(raw)
            if m and m.group(0).strip(" ."):
                mark = m.group(0)
                keys = set(_DIGITS.findall(mark)) | {s for s in _STARS.findall(mark)}
                raw = raw[:m.start()]
            name = _HONORIFIC.sub("", _clean(raw).strip(" ,;*")).strip()
            if name:
                out.append([name, keys])
        return out

    @staticmethod
    def _letter_marks(authors, affs):
        """Letter markers ("Aditya V.a, H. Prabhu M.b" with "aPost Graduate bAssociate Professor"): each name ends in
        the next letter, a, b, c ...; strip it and use it as the key. Only when every name does and the affiliation
        line opens with "a" + a capital."""
        if not 2 <= len(authors) <= 26 or not re.match(r"[a-z][A-Z]", affs) or any(keys for _, keys in authors):
            return False
        letters = "abcdefghijklmnopqrstuvwxyz"
        if not all(name.endswith(letters[i]) and len(name) > 2 for i, (name, _) in enumerate(authors)):
            return False
        for i, author in enumerate(authors):
            author[0] = author[0][:-1].strip()
            author[1] = {letters[i]}
        return True

    @staticmethod
    def _segments(affs, kind, keys):
        """[(keys, text)] in the line's order; the text before the first marker gets the key '' ."""
        if kind == "digit":
            marks = [(m.start(), m.end(), k) for m in _AFF_DIGIT.finditer(affs)
                     if (k := _digit_keys(m.group(1))) and k <= keys]
        elif kind == "star":
            marks = [(m.start(), m.end(), set(_STARS.findall(m.group(0)))) for m in _AFF_STAR.finditer(affs)]
        elif kind == "letter":
            marks = [(m.start(), m.end(), {m.group(1)}) for m in _AFF_LETTER.finditer(affs) if m.group(1) in keys]
        else:
            marks = []
        segments = []
        if not marks:
            return [(set(), affs)]
        if marks[0][0] > 0:
            segments.append((set(), affs[:marks[0][0]]))
        for i, (start, end, k) in enumerate(marks):
            stop = marks[i + 1][0] if i + 1 < len(marks) else len(affs)
            segments.append((k, affs[end:stop]))
        return segments

    @staticmethod
    def _address_tail(text):
        """The segment from its first part that names a department or an institution ("Assistant Professor,
        Department of X, College" -> "Department of X, College")."""
        parts = text.split(",")
        for i, part in enumerate(parts):
            if _ORG.search(part):
                return _strip_aff(",".join(parts[i:]))
        return None

    def _affiliations(self, authors, affs):
        """Fill each author's affiliations from the affiliation line."""
        if not affs:
            return
        all_keys = set().union(*(keys for _, keys in authors)) if authors else set()
        if self._letter_marks(authors, affs):
            kind, all_keys = "letter", set().union(*(keys for _, keys in authors))
        elif any(k.isdigit() for k in all_keys):
            kind = "digit"
        elif any(k.startswith("*") for k in all_keys):
            kind = "star"
        else:
            kind = None
        segments = [(k, _strip_aff(t)) for k, t in self._segments(affs, kind, all_keys)]
        segments = [(k, t) for k, t in segments if t]
        if not segments:
            return
        marked = [s for s in segments if s[0]]
        if not marked:
            # no markers in the line: one author takes it; several split it positionally when it lists one
            # affiliation each (" , " between them), else share it
            text = segments[0][1]
            if len(authors) == 1:
                authors[0].append([text] if _ORG.search(text) else [])
                return
            parts = [_strip_aff(p) for p in re.split(r"\s+,\s+", affs)]
            if len(parts) == len(authors) and all(parts):
                for i, author in enumerate(authors):
                    tail = next((p for p in parts[i:] if _ORG.search(p)), None)
                    own = parts[i] if _ORG.search(parts[i]) else (self._address_tail(tail) if tail else None)
                    author.append([own] if own else [])
                return
            for author in authors:
                author.append([text] if _ORG.search(text) else [])
            return
        # text before the first marker belongs to the first key the line never prints ("Assistant Professor ...
        # 2Professor ... 3Professor ..." for "Koirala1, Khandelwal2, Zaman3")
        if not segments[0][0]:
            printed = set().union(*(k for k, _ in marked))
            missing = [k for _, keys in authors for k in sorted(keys) if k not in printed]
            if missing:
                segments[0] = ({missing[0]}, segments[0][1])
            else:
                segments = segments[1:]
        by_key = {}
        for i, (keys, text) in enumerate(segments):
            if _ORG.search(text):
                value = text
            else:  # a job title only: the address that follows it
                nxt = next((t for _, t in segments[i + 1:] if _ORG.search(t)), None)
                value = self._address_tail(nxt) if nxt else None
            if value:
                for k in keys:
                    by_key.setdefault(k, [])
                    if value not in by_key[k]:
                        by_key[k].append(value)
        for author in authors:
            values = []
            for k in sorted(author[1], key=lambda x: (len(x), x)):
                for v in by_key.get(k, []):
                    if v not in values:
                        values.append(v)
            author.append(values)

    # ---- corresponding author -----------------------------------------------------------------------------------

    def _corresponding_text(self):
        for strong in self.soup.find_all("strong"):
            if not _CORR_LABEL.match(strong.get_text(" ")):
                continue
            bits = []
            for sib in strong.next_siblings:
                if getattr(sib, "name", None) in ("br", "strong", "p", "div"):
                    break
                bits.append(sib.get_text(" ") if hasattr(sib, "get_text") else str(sib))
            text = _clean(" ".join(bits)).lstrip(":").strip()
            if text:
                return text
        return None

    @staticmethod
    def _tokens(name):
        name = re.sub(r"[^\w\s]", " ", _clean(name).lower())
        return [t for t in name.split() if t not in _NAME_TOKEN_DROP and not t.isdigit()]

    @classmethod
    def _match_tier(cls, corr, name):
        a, b = cls._tokens(corr), cls._tokens(name)
        if not a or not b:
            return 0
        if set(a) == set(b) or "".join(a) == "".join(b):
            return 3
        long_a, long_b = {t for t in a if len(t) > 1}, {t for t in b if len(t) > 1}
        shared = long_a & long_b
        if not shared:
            return 0
        if long_b <= long_a:  # "Anita Pawar Assistant Professor" holds "Anita Pawar"
            return 2
        rest_a = {t[0] for t in a if t not in shared}
        rest_b = {t[0] for t in b if t not in shared}
        if rest_a and rest_b and (rest_a <= rest_b or rest_b <= rest_a):
            return 2
        return 1 if any(len(t) > 2 for t in shared) else 0

    def _mark_corresponding(self, authors):
        text = self._corresponding_text()
        if not text:
            return
        name = _NAME_MARK.sub("", text.split(",")[0]).strip(" *.")
        name = _HONORIFIC.sub("", name)
        tiers = [self._match_tier(name, a["name"]) for a in authors]
        best = max(tiers, default=0)
        if best and tiers.count(best) == 1:
            authors[tiers.index(best)]["is_corresponding"] = True

    # ---- parse ----------------------------------------------------------------------------------------------------

    def parse(self):
        byline = self._byline()
        if byline is None:
            return self.no_authors_output()
        names, affs = byline
        authors = self._split_names(names)
        self._affiliations(authors, affs)
        out = [{"name": a[0], "affiliations": a[2] if len(a) > 2 else [], "is_corresponding": False} for a in authors]
        self._mark_corresponding(out)
        return {"authors": out, "abstract": None}
