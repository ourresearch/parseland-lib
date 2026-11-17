"""SciRP: Scientific Research Publishing's article pages (scirp.org, about 165K works) (oxjob #2289).

One ASP.NET template on every page: the byline in div#JournalInfor_div_paper as one
<a href="articles?searchcode=...&searchfield=authors"> link per author, each followed by a <sup> of affiliation numbers
and marks ("1,2*#"); the affiliations in span#JournalInfor_div_affs, numbered by a <sup> when there are several; the
full text in div#htmlContent, its section headings <p class="E-Title1"> ("Acknowledgements", "NOTES", whose notes
explain the byline's marks: "*Joint first author." "#Corresponding author."). The generic parser read only the
citation_author tags: no affiliations, and on recent pages a name with an accent split in two at a broken entity
("Lucas S&amp;#225" / "vio ..."). The byline's names are right.
"""
import json
import re

from bs4 import Tag

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser

PUBLISHER = "Scientific Research Publishing"
_AUTHOR_LINK = re.compile(r"searchfield=authors")
_ACKNOWLEDGMENTS = re.compile(r"^\s*acknowledge?ments?\b", re.I)
# a note that explains a byline mark as the corresponding author's: "#Corresponding author." "* Corresponding author"
_CORRESPONDING_NOTE = re.compile(r"^\s*([*#†‡§¶]+)\s*(?:corresponding\s+author|correspondence)\b", re.I)


def _clean(text):
    return " ".join((text or "").split())


class SciRP(PublisherParser):
    parser_name = "scirp"
    # the byline's names beat the citation_author tags, which split an accented name at a broken entity
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        # Paid on every DOI page (#2239): the one head tag first, the article template's block only on SciRP's pages.
        if getattr(self, "_claim", None) is None:
            head = self.soup.head
            tag = head.find("meta", attrs={"name": "citation_publisher"}) if head is not None else None
            self._claim = bool(tag is not None and _clean(tag.get("content")) == PUBLISHER
                               and self.soup.find(id="JournalInfor_div_paper") is not None)
        return self._claim

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._authors())

    def parse(self):
        result = {"authors": self._authors(), "abstract": self._abstract()}
        if ack := self._acknowledgments():
            result["acknowledgments"] = ack
        return result

    # ---- byline ----

    def _authors(self):
        if getattr(self, "_cache", None) is None:
            self._cache = self._read_byline()
        return self._cache

    def _read_byline(self):
        paper = self.soup.find(id="JournalInfor_div_paper")
        first = paper.find("a", href=_AUTHOR_LINK) if paper is not None else None
        if first is None:
            return []
        entries = []  # [name, the <sup> text after it]
        for node in first.parent.children:
            if not isinstance(node, Tag):
                continue
            if node.name == "a" and _AUTHOR_LINK.search(node.get("href") or ""):
                if name := _clean(node.get_text()):
                    entries.append([name, ""])
            elif node.name == "sup" and entries:
                entries[-1][1] += node.get_text()
            elif node.get("id") == "JournalInfor_div_affs":
                break
        numbered, plain = self._affiliation_list(paper)
        authors = [{"name": name, "affiliations": list(dict.fromkeys(
                        numbered[n] for n in re.findall(r"\d+", sup) if n in numbered)), "is_corresponding": None}
                   for name, sup in entries]
        self._link_unnumbered(authors, numbered, plain)
        self._mark_corresponding(authors, [set(re.sub(r"[\d,\s]", "", sup)) for _, sup in entries])
        return authors

    @staticmethod
    def _affiliation_list(paper):
        """({number: affiliation}, [affiliations printed without a number]) from span#JournalInfor_div_affs."""
        numbered, plain = {}, []
        span = paper.find(id="JournalInfor_div_affs")
        number = None
        for node in span.children if span is not None else []:
            if not isinstance(node, Tag):
                continue
            if node.name == "sup":
                number = _clean(node.get_text()) or None
            elif node.name == "a" and (text := _clean(node.get_text())):
                if number:
                    numbered.setdefault(number, text)
                else:
                    plain.append(text)
                number = None
        return numbered, plain

    def _link_unnumbered(self, authors, numbered, plain):
        """Affiliations no number links: one affiliation is every author's, a lone author's are all theirs; several of
        each are linked only by the page's JSON-LD (its author list, in byline order), never guessed."""
        if not authors:
            return
        if len(authors) == 1 and not authors[0]["affiliations"]:
            authors[0]["affiliations"] = list(dict.fromkeys(list(numbered.values()) + plain))
            return
        if numbered or not plain:
            return
        if len(plain) == 1:
            for a in authors:
                a["affiliations"] = list(plain)
            return
        linked = self._json_ld_affiliations()
        if len(linked) == len(authors) and all(_clean(n) == a["name"] for (n, _), a in zip(linked, authors)):
            for (_, affs), a in zip(linked, authors):
                a["affiliations"] = [x for x in affs if x in plain]

    def _json_ld_affiliations(self):
        for script in self.soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
            except ValueError:
                continue
            people = data.get("author") if isinstance(data, dict) else None
            if isinstance(people, list) and people:
                return [(p.get("name") or "", [_clean(o.get("name")) for o in p.get("affiliation") or []
                                               if isinstance(o, dict)])
                        for p in people if isinstance(p, dict)]
        return []

    def _mark_corresponding(self, authors, author_marks):
        """Only a mark the page explains as the corresponding author's (a note in the full text's NOTES); a bare star
        the page never explains is no mark (rubric label-v1), and SciRP also uses the star for joint first authors."""
        box = self.soup.find(id="htmlContent")
        marks = set()
        for p in box.find_all("p") if box is not None else []:
            text = _clean(p.get_text())
            if len(text) <= 200 and (m := _CORRESPONDING_NOTE.match(text)):
                marks.update(m.group(1))
        if not any(m & marks for m in author_marks):
            return
        for a, m in zip(authors, author_marks):
            a["is_corresponding"] = bool(m & marks)

    # ---- abstract and back matter ----

    def _abstract(self):
        # the generic parser's own readers, in its order: SciRP's citation_abstract tag holds the whole abstract
        return (self.parse_abstract_meta_tags(include_seo_tags=False)
                or GenericPublisherParser(self.soup).parse_structured_abstract_section()
                or self.parse_printed_seo_description())

    def _acknowledgments(self):
        """The text under the full text's "Acknowledgements" heading, paragraphs joined by a newline, up to the next
        heading. A funding sentence inside it stays there (#2215 contract): SciRP prints no funding heading of its own
        on the pages sampled."""
        box = self.soup.find(id="htmlContent")
        for title in box.find_all("p", class_="E-Title1") if box is not None else []:
            if not _ACKNOWLEDGMENTS.match(title.get_text()):
                continue
            parts = []
            for node in title.find_next_siblings():
                if node.name == "p" and "E-Title1" in (node.get("class") or []):
                    break
                if text := _clean(node.get_text()):
                    parts.append(text)
            return "\n".join(parts) or None
        return None
