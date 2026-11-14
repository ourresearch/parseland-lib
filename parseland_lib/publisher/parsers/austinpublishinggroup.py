"""austinpublishinggroup.com (Austin Publishing Group) full-text article pages (oxjob #2210).

One hand-built PHP template on every journal of the site: the byline is one <p class="subline"> (names split by ";",
"," or "and"; affiliation numbers in <sup> or as Unicode superscripts; "*" for a corresponding author), then one
<p class="affl"> per affiliation, a "*Corresponding author:" note (also <p class="affl">, id "ref"), the abstract under
an <h2> "Abstract" or "Summary", optional acknowledgments and funding sections (an <h2> or a bold label), and the
references as one <ol id="ref">. The citation_author meta tags carry names only, and there is no abstract meta tag.
"""
import copy
import re

from bs4 import Comment, NavigableString

from parseland_lib.publisher.parsers.parser import PublisherParser

DOMAIN = "austinpublishinggroup.com"
SUPERSCRIPTS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")
SUP_RUN = re.compile(r"[⁰¹²³⁴⁵⁶⁷⁸⁹]+(?:\s*[,،]\s*[⁰¹²³⁴⁵⁶⁷⁸⁹]+)*")
MARK = re.compile(r"\x01([^\x02]*)\x02")
SEPARATORS = re.compile(r"\s*[;,]\s*|\s+and\s+|\s+&\s+")
CORRESPONDING = re.compile(r"corresponding\s+author", re.I)
ABSTRACT_HEAD = re.compile(r"(abstract|summary)\W*", re.I)
STOP_ABSTRACT = re.compile(r"(key\s*words?|abbreviations)\b", re.I)
ACK_HEAD = re.compile(r"acknowledge?ments?\b", re.I)
FUNDING_HEAD = re.compile(r"(funding(\s+(sources?|information|statement))?|sources?\s+of\s+funding|financial\s+support)\W*",
                          re.I)
DOI = re.compile(r"10\.\d{4,9}/[^\s\"<>]+")
HEADINGS = ("h1", "h2", "h3")
DEGREES = {"md", "phd", "msc", "bsc", "ms", "ma", "mph", "mba", "dds", "dmd", "rn", "bsn", "msn", "mbbs", "frcs", "frcp",
           "facs", "faha", "mch", "dm", "dnb", "pharmd", "dvm", "pt", "dpt", "mpt", "bpt", "bds", "mds"}


def _text(tag):
    return re.sub(r"\s+", " ", tag.get_text()).strip()


def _fold(s):
    return re.sub(r"\s+", " ", s).strip().casefold()


class AustinPublishingGroup(PublisherParser):
    parser_name = "austin_publishing_group"

    def is_publisher_specific_parser(self):
        if self.domain_in_canonical_link(DOMAIN) or self.domain_in_meta_og_url(DOMAIN):
            return True
        # one 2016 page has no canonical link; its citation URLs still name the site
        return any(DOMAIN in (m.get("content") or "") for m in self.soup.select(
            'meta[name="citation_pdf_url"], meta[name="citation_fulltext_html_url"]'))

    def authors_found(self):
        return bool(self.soup.select_one("p.subline")) and self.is_publisher_specific_parser()

    # --- byline and affiliations -------------------------------------------------------------------------------

    @staticmethod
    def _marked_text(tag):
        """The tag's text with each <sup> and each run of Unicode superscripts wrapped as \\x01mark\\x02."""
        tag = copy.copy(tag)
        for sup in tag.find_all("sup"):
            sup.replace_with(f"\x01{sup.get_text()}\x02")
        text = re.sub(r"\s+", " ", tag.get_text())
        return SUP_RUN.sub(lambda m: f"\x01{m.group(0).translate(SUPERSCRIPTS)}\x02", text)

    def _byline(self):
        """[(name, [affiliation keys], starred)] from the subline."""
        sub = self.soup.select_one("p.subline")
        text = self._marked_text(sub)
        marks = []
        text = MARK.sub(lambda m: marks.append(m.group(1)) or f"\x03{len(marks) - 1}\x03", text)
        out = []
        for chunk in SEPARATORS.split(text):
            keys, starred = [], "*" in re.sub(r"\x03\d+\x03", "", chunk)
            for i in re.findall(r"\x03(\d+)\x03", chunk):
                mark = marks[int(i)]
                starred = starred or "*" in mark
                keys += re.findall(r"\d+", mark)
            name = re.sub(r"\x03\d+\x03", " ", chunk)
            name = re.sub(r"\s+", " ", re.sub(r"[*#†‡§]", "", name)).strip(" .,;")
            if name and out and all(w in DEGREES for w in re.split(r"[\s.]+", name.casefold()) if w):
                # "Xin Su, MD*": a degree after a comma belongs to the name before it, with its marks
                prev = out[-1]
                out[-1] = (prev[0], prev[1] + keys, prev[2] or starred)
            elif name:
                out.append((name, keys, starred))
        return out

    def _header_paragraphs(self):
        """(affiliation paragraphs, corresponding-note paragraphs) from the p.affl run under the byline."""
        affs, notes = [], []
        for p in self.soup.select("p.affl"):
            text = _text(p)
            if re.match(r"received\b", text, re.I):
                break
            if p.get("id") == "ref" or CORRESPONDING.search(text) or notes:
                notes.append(p)
            elif text:
                affs.append(p)
        return affs, notes

    def _affiliations(self, paras):
        """({number: text}, [unnumbered text]); footnotes such as "#Contributed equally" are dropped."""
        numbered, plain = {}, []
        for p in paras:
            text = self._marked_text(p).strip()
            m = re.match(r"\x01([^\x02]*)\x02\s*", text)
            if m:
                rest = re.sub(r"\s+", " ", MARK.sub(lambda x: x.group(1), text[m.end():])).strip()
                key = re.sub(r"\D", "", m.group(1))
                if key and rest:
                    numbered[key] = rest
                continue  # a "#", "*" or "†" footnote is not an affiliation
            plain.append(re.sub(r"\s+", " ", MARK.sub(lambda x: x.group(1), text)).strip())
        if not numbered and len(plain) > 1:
            # "1Degree in ...", "2Doctor of ...": plain leading numbers that run 1..n
            lead = [re.match(r"(\d{1,2})(?=\D)", t) for t in plain]
            if all(lead) and [int(m.group(1)) for m in lead] == list(range(1, len(plain) + 1)):
                numbered = {m.group(1): t[m.end():].strip() for m, t in zip(lead, plain)}
                plain = []
        return numbered, plain

    @staticmethod
    def _note_names(notes):
        """The opening words of each corresponding-author note, folded."""
        out = []
        for p in notes:
            text = _text(p)
            text = re.sub(r"^.*?corresponding\s+author\s*s?\s*[:：]?", "", text, flags=re.I).strip(" *:")
            text = re.sub(r"^(dr|prof|d-r)\.?\s+", "", text, flags=re.I)
            out.append(_fold(text))
        return out

    @staticmethod
    def _named_in_note(name, note):
        folded = _fold(name)
        if note.startswith(folded):
            return True
        head = re.split(r"[\s,]+", note)[:4]
        words = [w for w in re.split(r"\s+", name) if len(w) > 2 and not (w.isupper() and len(w) <= 3)]
        return any(_fold(w) in head for w in words)

    def _authors(self):
        byline = self._byline()
        affs, notes = self._header_paragraphs()
        numbered, plain = self._affiliations(affs)
        has_note = any(CORRESPONDING.search(_text(p)) for p in notes)
        authors = []
        for name, keys, starred in byline:
            if numbered and keys:
                aff = [numbered[k] for k in dict.fromkeys(keys) if k in numbered]
            elif numbered and not plain and len(numbered) == 1:
                aff = list(numbered.values())
            else:
                aff = list(plain)
            authors.append({"name": name, "affiliations": aff, "is_corresponding": bool(starred and has_note)})
        if has_note and authors and not any(a["is_corresponding"] for a in authors):
            for note in self._note_names(notes):
                hits = [a for a in authors if self._named_in_note(a["name"], note)]
                if len(hits) == 1:
                    hits[0]["is_corresponding"] = True
        return authors

    # --- sections ------------------------------------------------------------------------------------------------

    def _section(self, pattern):
        """Paragraph texts under the first heading whose whole text matches pattern, up to the next heading."""
        for h in self.soup.find_all(["h2", "h3"]):
            if not pattern.fullmatch(_text(h)):
                continue
            paras = []
            for sib in h.find_next_siblings():
                if sib.name in HEADINGS:
                    break
                if sib.name == "p" and (t := _text(sib)):
                    paras.append(t)
            return paras
        return []

    def _abstract(self):
        paras = []
        for t in self._section(ABSTRACT_HEAD):
            if STOP_ABSTRACT.match(t):
                break
            paras.append(t)
        return "\n".join(paras) or None

    def _labelled(self, label):
        """The text of a paragraph that opens with a bold label ("Funding:", "Acknowledgements:")."""
        art = self.soup.select_one("div.article") or self.soup
        for b in art.find_all(["strong", "b"]):
            if b.parent.name != "p" or not re.fullmatch(label.pattern + r"\s*[:.]?", _text(b), re.I):
                continue
            first = next((c for c in b.parent.contents if not (isinstance(c, NavigableString) and not c.strip())), None)
            if first is not b:
                continue
            rest = _text(b.parent)[len(_text(b)):].strip(" :")
            if rest:
                return rest
        return None

    def parse_acknowledgments(self):
        paras = self._section(re.compile(ACK_HEAD.pattern + r".*", re.I))
        return "\n".join(paras) if paras else self._labelled(re.compile(r"acknowledge?ments?", re.I))

    def parse_funding_statement(self):
        paras = self._section(FUNDING_HEAD)
        return "\n".join(paras) if paras else self._labelled(FUNDING_HEAD)

    def parse_references(self):
        """(references, complete): one plain <ol id="ref">, so the page numbers its items 1..n itself."""
        ol = self.soup.select_one("ol#ref")
        if ol is None:
            return None, False
        items = ol.find_all("li", recursive=False)
        refs = []
        for li in items:
            raw = _text(li)
            if not raw:
                continue
            doi = None
            for a in li.find_all("a", href=True):
                if "doi.org/" in a["href"] and (d := DOI.search(a["href"])):
                    doi = d.group(0).rstrip(".,;")
                    break
            refs.append({"position": len(refs) + 1, "raw": raw, "doi": doi})
        if not refs:
            return None, False
        stray = [t for t in ol.find_all(string=True, recursive=False) if t.strip() and not isinstance(t, Comment)]
        around = " ".join([_text(ol)] + [_text(s) for s in ol.find_next_siblings()[:3]])
        more = re.search(r"show more|load more|view all|see all|more references", around, re.I)
        start = ol.get("start")
        complete = (len(refs) == len(items) and not stray and not more and (start is None or start.strip() == "1")
                    and len(self.soup.select("ol#ref")) == 1)
        return refs, complete

    def parse(self):
        authors = self._authors() or self.parse_author_meta_tags()
        refs, complete = self.parse_references()
        return {"authors": authors,
                "abstract": self._abstract(),
                "acknowledgments": self.parse_acknowledgments(),
                "funding_statement": self.parse_funding_statement(),
                "references": refs,
                "references_complete": complete}
