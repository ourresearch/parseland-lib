"""APA's supplemental-material pages (supp.apa.org; DOIs ending ".supp") (oxjob #2213).

The page has no meta tags: the byline is one <span class="author">, names joined by commas and a final "and", some
followed by an ORCID icon link. ~22K supplementary-materials works had no authors because no parser read it. The page
shows no abstract, affiliation, correspondence mark, acknowledgments, funding statement or reference list.
"""
import re

from parseland_lib.publisher.parsers.parser import PublisherParser

SUFFIXES = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv"}
# A degree or credential the byline lists after a name, as its own comma part ("Maayan Abargil, PhD, Orya Tishby,
# PhD"; ~110 of 22K supp pages, mostly Psychoanalytic Psychology and Families, Systems, & Health): one word of
# letters (dots and hyphens allowed), at most 8 letters, at least 2 capitals: PhD, MD, MSc, PsyD, DClinPsy, CCC-SLP,
# Ph.D., L.A.D.C. A one-word name keeps its place (Samian, Scout, Kashaf-A-Duja).
CREDENTIAL = re.compile(r"[A-Za-z][A-Za-z.\-]*")


def _is_credential(part):
    letters = re.sub(r"[.\-]", "", part)
    return (CREDENTIAL.fullmatch(part) is not None and 2 <= len(letters) <= 8
            and sum(c.isupper() for c in letters) >= 2)


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
            elif names and _is_credential(part):
                continue
            else:
                names.append(part)
        return {"authors": [{"name": n, "affiliations": [], "is_corresponding": None} for n in names],
                "abstract": None}
