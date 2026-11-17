"""Academic Journals (academicjournals.org, DOI prefix 10.5897, ~100 titles): each author's affiliations and the starred
corresponding author (oxjob #2338).

The site's abstract pages print the byline in one of two templates, both inside div.abstract_title:
- current: a div.user card per author, li.authorname and then one li with that author's affiliation;
- older (2007-2015 issues): one h5.black line of names with plain markers glued on ("Touati1, ... Mashaly1, 2*"), then
  span.black with one affiliation per line (numbered when the byline is) and an "Email:" line with one address.
The citation_author tags carry names only, so the generic parser read no affiliation on either template, and it read
the star only where no number is glued to the starred name (its byline-node test needs two names to match).

Corresponding: the author whose byline name carries "*". On the older template the "Email:" line is the star's legend,
as in the generic parser's star rule ("* E-mail: ..."), so a star counts only on pages that print it. The current
template prints the star with no note (1 of 20 such sample pages); the generic parser marked it there and still does.

Names come from the byline, not the citation_author tags: the tags drop accented letters on the current template
("J&essica", "Sp&inola-Filho") and on the older one they strip or break them ("Neziha", "TUNCcedil;") and split names
at "and" ("Luis Fern", "o Paredes-Fernandez"). An older byline with a one-word part that does not split into as many
names as the page has citation_author tags is left to the generic parser.
"""
import re

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser

_SITE_URL_TAGS = ["citation_abstract_html_url", "citation_pdf_url", "citation_public_url"]
_STARS = "*∗"
# a byline part: the name, then the markers glued to it ("Mashaly1", "Bellifa1*", "Bairu*"); a part that is all
# markers ("2*" in "Mashaly1, 2*") belongs to the name before it
_PART = re.compile(r"^(.*?)\s*([\d\s*∗]*)$")
_NUMBERED = re.compile(r"^(\d+)\s*(\S.*)$")


def _clean(text):
    return " ".join((text or "").replace("\xa0", " ").split())


class AcademicJournals(PublisherParser):
    parser_name = "academic_journals"
    # the byline's names beat the citation_author tags' (see above)
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        # Cheap marker first (#2239: every parser's claim runs on every page): the <head>'s citation_publisher tag,
        # exactly the site's name, then one of its URL tags on the site's domain. Cached: the dispatcher calls
        # authors_found() and then this on the same instance.
        claim = self.__dict__.get("_claim")
        if claim is None:
            claim = False
            head = self.soup.head
            tag = head.find("meta", attrs={"name": "citation_publisher"}) if head is not None else None
            if tag is not None and _clean(tag.get("content")) == "Academic Journals":
                claim = any("academicjournals.org" in (t.get("content") or "")
                            for t in head.find_all("meta", attrs={"name": _SITE_URL_TAGS}))
            self._claim = claim
        return claim

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._byline())

    def _byline(self):
        if "_authors" not in self.__dict__:
            self._authors = self._read_byline()
        return self._authors

    def _read_byline(self):
        title = self.soup.select_one("div.abstract_title")
        if title is None:
            return None
        if cards := title.select("div.user"):
            return self._current_byline(cards)
        if (names := title.select_one("h5.black")) is not None:
            return self._older_byline(names)
        return None

    @staticmethod
    def _current_byline(cards):
        authors = []
        for card in cards:
            name_tag = card.select_one("li.authorname") or card.find("h5")
            raw = _clean(name_tag.get_text(" ")) if name_tag is not None else ""
            name = raw.strip(" ," + _STARS)
            if not name:
                return None
            affiliations = []
            for item in card.select("ul > li"):
                classes = item.get("class") or []
                if "authorname" in classes or "search" in classes or item.find("a") is not None:
                    continue
                if text := _clean(item.get_text(" ")):
                    affiliations.append(text)
            authors.append({"name": name, "affiliations": affiliations,
                            "starred": any(s in raw for s in _STARS)})
        return authors

    def _older_byline(self, names_tag):
        parts = []  # [name, markers]
        for part in re.split(r",|\s+and\s+", _clean(names_tag.get_text(" "))):
            name, markers = _PART.match(part.strip()).groups()
            if name:
                parts.append([name, markers])
            elif markers.strip() and parts:
                parts[-1][1] += "," + markers
        # A one-word part is half of an inverted name ("Lima, Ana"): then the byline must split into as many names as
        # the page has citation_author tags. Not otherwise: the site's tags split names at "and" ("Luis Fern",
        # "o Paredes-Fernandez").
        if not parts:
            return None
        if any(len(name.split()) < 2 for name, _ in parts):
            tags = [m for m in self.soup.find_all("meta", attrs={"name": "citation_author"}) if _clean(m.get("content"))]
            if len(tags) != len(parts):
                return None

        lines, legend = [], False
        block = names_tag.find_next("span", class_="black")
        if block is not None and _clean(block.get_text()).lower() != "email":
            lines = [line for line in (_clean(t) for t in block.get_text("\n").split("\n")) if line]
            legend = block.find_next("span", class_="black", string=re.compile(r"^\s*e-?mail\s*$", re.I)) is not None
        numbers = [re.findall(r"\d+", markers) for _, markers in parts]
        if any(numbers):
            numbered, current = {}, None
            for line in lines:
                if m := _NUMBERED.match(line):
                    current = m.group(1)
                    numbered[current] = m.group(2)
                elif current is not None:  # an affiliation wrapped onto a second line
                    numbered[current] += " " + line
            affiliations = [[numbered[n] for n in nums if n in numbered] for nums in numbers]
        else:  # no markers: the listed affiliations are everyone's
            affiliations = [list(lines) for _ in parts]
        return [{"name": name, "affiliations": affs, "starred": legend and any(s in markers for s in _STARS)}
                for (name, markers), affs in zip(parts, affiliations)]

    def parse(self):
        authors = self._byline() or []
        starred = any(a["starred"] for a in authors)
        generic = GenericPublisherParser(self.soup)
        return {
            "authors": [{"name": a["name"], "affiliations": a["affiliations"],
                         "is_corresponding": a["starred"] if starred else None} for a in authors],
            # the abstract the generic parser reads on these pages, unchanged
            "abstract": (self.parse_abstract_meta_tags(include_seo_tags=False)
                         or generic.parse_structured_abstract_section()
                         or generic.parse_printed_seo_description()),
        }
