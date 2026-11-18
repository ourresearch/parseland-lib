"""Charles University's medical-faculty journals on cuni.cz (oxjob #2339): Acta Medica (actamedica.lfhk.cuni.cz),
Folia Biologica (foliabiologica.lf1.cuni.cz) and Prague Medical Report (pmr.lf1.cuni.cz). One template: its pages carry
<meta name="citation_publisher" content="Charles University in Prague, Karolinum Press"> and print the byline in
<div id="authors" class="abstract-authors">.

The generic reader already gets the byline and affiliations from the meta tags (citation_author,
citation_author_institution); this parser keeps its result as it is and adds the one thing only the page says: the
corresponding author, the one name the byline links to an e-mail address (mailto). label-v1's labellers read that link
as the mark ("an envelope or mail icon tied to them"); a mailto on every name is not one.

Not read here (oxjob #2339 RESULT.json): the page's abstract block (every work it stands for already has an abstract)
and its reference list, which sits on a separate ".../references/" page.
"""
from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import same_person

_PUBLISHER = "charles university in prague, karolinum press"


def _head(soup):
    html = soup.find("html", recursive=False)
    return (html or soup).find("head", recursive=False)


class CuniMedicalJournals(PublisherParser):
    parser_name = "cuni_medical_journals"

    def is_publisher_specific_parser(self):
        # Every page is offered to this parser, so the cheap test goes first: one meta tag looked for in <head> only
        # (#2239's per-page CPU rule). Nothing walks the whole tree until it passes. The answer is kept: authors_found()
        # and the caller both ask.
        if not hasattr(self, "_claimed"):
            head = _head(self.soup)
            meta = head.find("meta", attrs={"name": "citation_publisher"}) if head is not None else None
            self._claimed = bool(meta and " ".join((meta.get("content") or "").split()).lower() == _PUBLISHER
                                 and self._byline() is not None)
        return self._claimed

    def _byline(self):
        return self.soup.find("div", id="authors", class_="abstract-authors")

    def _generic(self):
        if not hasattr(self, "_generic_result"):
            # the byline's mail links first: nothing the generic reader does to the soup can touch them
            self._mailto_names = [a.get_text(" ", strip=True) for a in self._byline().select('a[href^="mailto:"]')]
            self._generic_result = GenericPublisherParser(self.soup).parse()
        return self._generic_result

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._generic().get("authors"))

    def _mark_corresponding(self, authors):
        names = [n for n in self._mailto_names if n]
        if not names or len(names) >= len(authors) or any(a.get("is_corresponding") for a in authors):
            return authors  # no mark, a mail link on every name, or the generic reader already marked someone
        marked = []
        for name in names:
            matches = [a for a in authors if same_person(a.get("name"), name)]
            if len(matches) == 1:  # a name that matches no author, or more than one, is skipped
                marked.append(matches[0])
        if marked:
            for a in authors:
                a["is_corresponding"] = any(a is m for m in marked)
        return authors

    def parse(self):
        generic = self._generic()
        authors = self._mark_corresponding([dict(a) for a in generic.get("authors") or []])
        return {**generic, "authors": authors}
