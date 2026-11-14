"""APA's supplemental-material pages (supp.apa.org; DOIs ending ".supp") (oxjob #2213).

The page has no meta tags: the byline is one <span class="author">, names joined by commas and a final "and", some
followed by an ORCID icon link. ~22K supplementary-materials works had no authors because no parser read it. The page
shows no abstract, affiliation, correspondence mark, acknowledgments, funding statement or reference list.
"""
import re

from parseland_lib.publisher.parsers.parser import PublisherParser

SUFFIXES = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv"}


class APASupplementalMaterial(PublisherParser):
    parser_name = "apa_supplemental_material"

    def is_publisher_specific_parser(self):
        # APA's header logo plus the note every supp.apa.org page carries ("This content was submitted by the author
        # as supplemental material for an article published in APA's PsycARTICLES" / "APA PsycArticles")
        if not self.soup.find("img", alt="APA's header logo"):
            return False
        return any("submitted by the author as supplemental" in " ".join(d.get_text().split())
                   for d in self.soup.find_all(class_="disclaimer"))

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._byline())

    def _byline(self):
        # ORCID links hold only an icon <img>, so they add no text
        span = self.soup.find("span", class_="author")
        return " ".join(span.get_text().split()) if span else ""

    def parse(self):
        names = []
        for part in re.split(r"\s*,\s*", re.sub(r"(?:,\s*|\s+)and(?:\s+|$)", ", ", self._byline())):
            if not part:
                continue
            if names and part.lower() in SUFFIXES:
                names[-1] += " " + part
            else:
                names.append(part)
        return {"authors": [{"name": n, "affiliations": [], "is_corresponding": None} for n in names],
                "abstract": None}
