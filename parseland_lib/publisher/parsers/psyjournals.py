"""psyjournals.ru: the Portal of Russian Psychological Publications (MSUPE's own CMS, DOI prefix 10.17759) (oxjob #2210).

One template for every journal on the portal, English (/en/...) and Russian. The byline is a row of author links; the
article body is a series of <section aria-labelledby="..."> blocks: "abstract", "generalinfo" (funding and
acknowledgements as bold-labelled paragraphs), "references" (an <ol>) and "authorsinfo" (one prose paragraph per
author: degree, position, institutions, ORCID, e-mail). The page marks no corresponding author.
"""
import copy
import re

from bs4 import BeautifulSoup, NavigableString, Tag

from parseland_lib.publisher.parsers.parser import PublisherParser

SITE = re.compile(r"^https?://(www\.)?psyjournals\.ru/", re.I)
AUTHOR_ID = re.compile(r"/authors/(\d+)")
# the author paragraph ends with identifiers and contact details, never an affiliation
TAIL = re.compile(r"[,.;]?\s*\b(ORCID|e-?mail|Researcher\s?ID|Scopus|SPIN|AuthorID|Web of Science)\b", re.I)
# a segment that names an organisation (or a unit of one); segments without one are degrees, positions or places
ORG = re.compile(
    r"univers|institut|academ|college|school|facult|depart|laborat|\blab\b|cent(er|re)|hospital|clinics?\b|foundation|"
    r"association|society|ministry|council|agency|company|corporat|committee|bureau|museum|library|gymnasium|lyceum|"
    r"organi[sz]ation|office|union|independent researcher|\b(LLC|Ltd|Inc|JSC)\b|"
    r"университет|институт|академи|колледж|школ|факультет|кафедр|лаборатор|центр|департамент|отдел|больниц|клиник|"
    r"фонд|ассоциаци|обществ|министерств|управлени|комитет|служб|гимнази|лицей|учреждени|организаци|сектор|музей|"
    r"библиотек|детск|представительств|независим\w* исследовател|«", re.I)
ORG_ABBR = re.compile(r"\b(ФГ\w*|ГБУ\w*|ГБОУ\w*|ГАОУ\w*|АНО|ООО|АО|РАН|РАО|НИУ|ВШЭ|МГУ|СПбГУ|МГППУ)\b")
# Russian position words in front of the unit they belong to: "научный сотрудник лаборатории ..." -> "лаборатории ..."
RU_POSITION = re.compile(
    r"^((старш(ий|ая)|ведущ(ий|ая)|главн(ый|ая)|младш(ий|ая))\s+)?(научн(ый|ая)\s+сотрудни(к|ца)|преподаватель|"
    r"сотрудни(к|ца)|доцент|профессор|заведующ(ий|ая)|директор|аспирант(ка)?|студент(ка)?|магистрант(ка)?|"
    r"докторант(ка)?|руководитель|начальник|заместитель\s+директора|ассистент|научный\s+руководитель)\s+(?=\w)", re.I)
FUNDING = re.compile(r"^(funding|финансирование)[.:]?$", re.I)
ACK = re.compile(r"^(acknowledge?ments?|благодарности|благодарность)[.:]?$", re.I)
DOI = re.compile(r"(10\.\d{4,9}/[^\s\"<>]+)")
MORE = re.compile(r"show (all|more)|load (all|more)|see all|показать (все|ещ[её])|все ссылки", re.I)


def _text(tag):
    """Text of a tag with <br> as a space and whitespace collapsed (inline markup adds no spaces)."""
    parts = []
    for node in tag.descendants:
        if isinstance(node, NavigableString):
            parts.append(str(node))
        elif isinstance(node, Tag) and node.name == "br":
            parts.append(" ")
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def _split_top(text, sep):
    """Split on sep outside parentheses and «» quotes."""
    out, depth, cur = [], 0, []
    for ch in text:
        if ch in "(«":
            depth += 1
        elif ch in ")»" and depth:
            depth -= 1
        if ch == sep and depth == 0:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    out.append("".join(cur))
    return [s.strip() for s in out if s.strip()]


def _is_org(segment):
    return bool(ORG.search(segment) or ORG_ABBR.search(segment))


def bio_affiliations(bio):
    """Affiliations from an author paragraph: drop the leading degrees and positions, cut at each position that
    stands between two institutions, keep the place names after the last institution."""
    bio = TAIL.split(bio, maxsplit=1)[0].strip(" ,.;")
    affs = []
    for part in _split_top(bio, ";"):
        segs = _split_top(part, ",")
        orgs = [i for i, s in enumerate(segs) if _is_org(s)]
        if not orgs:
            continue
        cur = []
        for i, seg in enumerate(segs):
            if i < orgs[0]:
                continue
            if i <= orgs[-1] and not _is_org(seg):  # a position between two institutions
                if cur:
                    affs.append(cur)
                cur = []
                continue
            cur.append(RU_POSITION.sub("", seg) if _is_org(seg) else seg)
        if cur:
            affs.append(cur)
    return [", ".join(a).strip(" ,.") for a in affs if a]


class PsyJournals(PublisherParser):
    parser_name = "psyjournals"

    def is_publisher_specific_parser(self):
        og = self.soup.find("meta", property="og:url")
        canonical = self.soup.find("link", {"rel": "canonical"})
        urls = [og and og.get("content"), canonical and canonical.get("href")]
        return any(u and SITE.match(u.strip()) for u in urls)

    def _byline(self):
        # the first div.authors above the "Information About the Authors" heading (older pages have no <article>)
        for div in self.soup.select("div.authors"):
            if not div.find_parent("section") and not div.find_previous("h2", id="authorsinfo"):
                return div.select("a.author")
        return []

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._byline())

    def _section(self, name):
        """The nodes after the section's <h2 id=name>, up to the next heading or section. Read by heading, not by
        <section>: some pages break the <section> tag (an unclosed "</div" before it)."""
        h2 = self.soup.find("h2", id=name)
        if not h2:
            return None
        nodes = []
        for sib in h2.next_siblings:
            if isinstance(sib, Tag) and (sib.name in ("h2", "section", "aside") or sib.find("h2")):
                break
            if isinstance(sib, Tag):
                nodes.append(sib)
        holder = BeautifulSoup("<div></div>", "lxml").div
        for node in nodes:
            holder.append(copy.copy(node))
        return holder

    def _bios(self):
        bios = {}
        section = self._section("authorsinfo")
        for a in section.select("a.author") if section else []:
            p = a.find_parent("p")
            m = AUTHOR_ID.search(a.get("href") or "")
            if not p or not m:
                continue
            name = _text(a)
            whole = _text(p)
            rest = whole.split(name, 1)[1] if name and name in whole else ""
            bios[m.group(1)] = rest.strip(" ,")
        return bios

    def parse_authors(self):
        bios = self._bios()
        authors = []
        for a in self._byline():
            name = _text(a)
            if not name:
                continue
            m = AUTHOR_ID.search(a.get("href") or "")
            bio = bios.get(m.group(1)) if m else None
            authors.append({"name": name, "affiliations": bio_affiliations(bio) if bio else [],
                            "is_corresponding": None})
        return authors

    def parse_abstract(self):
        section = self._section("abstract")
        if not section:
            return None
        text = " ".join(_text(c) for c in section.children if isinstance(c, Tag))
        text = re.sub(r"\s+", " ", text).strip()
        return text or None

    def _labelled(self, label_re):
        section = self._section("generalinfo")
        for p in section.find_all("p") if section else []:
            label = p.find(["strong", "b"])
            if label and label_re.match(_text(label)):
                text = _text(p)
                lab = _text(label)
                text = text[text.find(lab) + len(lab):].strip() if lab in text else text
                return text or None
        return None

    def parse_funding_statement(self):
        return self._labelled(FUNDING)

    def parse_acknowledgments(self):
        return self._labelled(ACK)

    def parse_references(self):
        section = self._section("references")
        if not section:
            return None, False
        items = [li for li in section.find_all("li") if not li.find("li")]
        refs = []
        for li in items:
            raw = _text(li)
            if not raw:
                continue
            doi = None
            for a in li.find_all("a", href=True):
                if "doi.org/" in a["href"] and (m := DOI.search(a["href"])):
                    doi = m.group(1).rstrip(".,;)")
                    break
            refs.append({"position": len(refs) + 1, "raw": raw, "doi": doi})
        if not refs:
            return None, False
        # the list is printed whole in one <ol>: entries run 1..n by construction; anything that hints at a preview,
        # a list that starts past 1, or reference text outside the list items makes it not complete
        starts_past_one = any((ol.get("start") or "1").strip() != "1" for ol in section.find_all("ol"))
        stray_text = any(_text(p) for p in section.find_all("p") if not p.find_parent("li"))
        complete = not (MORE.search(section.get_text(" ")) or starts_past_one or stray_text)
        return refs, complete

    def parse(self):
        refs, complete = self.parse_references()
        return {"authors": self.parse_authors(),
                "abstract": self.parse_abstract(),
                "acknowledgments": self.parse_acknowledgments(),
                "funding_statement": self.parse_funding_statement(),
                "references": refs,
                "references_complete": complete}
