import re

from parseland_lib.elements import AuthorAffiliations
from parseland_lib.publisher.parsers.parser import PublisherParser


class ScieloPreprints(PublisherParser):
    parser_name = "SciELO preprints"

    def is_publisher_specific_parser(self):
        stylesheets = self.soup.find_all("link", {"rel": "stylesheet"})

        if any(
            "preprints.scielo.org/" in stylesheet.get("href")
            for stylesheet in stylesheets
        ):
            return True

        return False

    def authors_found(self):
        return self.soup.find("ul", {"class": "authors"})

    def parse(self):
        authors = []
        authors_list = self.soup.find("ul", {"class": "authors"})
        for author_li in authors_list.find_all("li"):
            name_span = author_li.find("span", {"class": "name"})
            if name_span and name_span.text and name_span.text.strip():
                affiliation_spans = name_span.find_next_siblings(
                    "span", {"class": "affiliation"}
                )
                affiliations = []
                for affiliation_span in affiliation_spans:
                    if affiliation_span.text and affiliation_span.text.strip():
                        affiliations.append(
                            re.sub(r"\s+", " ", affiliation_span.text.strip())
                        )

                authors.append(
                    AuthorAffiliations(
                        name=re.sub(r"\s+", " ", name_span.text.strip()),
                        affiliations=affiliations,
                    )
                )

        return {"authors": authors, "abstract": None}

    test_cases = [
        {
            "doi": "10.1590/scielopreprints.1549",
            "result": [
                {
                    "name": "Solange Maria dos Santos",
                    "affiliations": [
                        "Scientific Electronic Library Online",
                    ],
                    "is_corresponding": None,
                },
                {
                    "name": "Grischa Fraumann",
                    "affiliations": [
                        "TIB Leibniz Information Centre for Science and Technology, Hannover, Germany"
                    ],
                    "is_corresponding": None,
                },
                {
                    "name": "Simone Belli",
                    "affiliations": [
                        "Complutense University of Madrid",
                    ],
                    "is_corresponding": None,
                },
                {
                    "name": "Rogério Mugnaini",
                    "affiliations": ["University of São Paulo"],
                    "is_corresponding": None,
                },
            ],
        },
    ]
