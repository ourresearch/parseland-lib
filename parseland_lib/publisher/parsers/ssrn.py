import re

from parseland_lib.elements import AuthorAffiliations
from parseland_lib.publisher.parsers.parser import PublisherParser


class SSRN(PublisherParser):
    parser_name = "ssrn"

    def is_publisher_specific_parser(self):
        return self.domain_in_canonical_link("papers.ssrn.com")

    def authors_found(self):
        return self.soup.find("div", class_="authors")

    @staticmethod
    def _name_key(name):
        cleaned = re.sub(r"\([^)]*\)", " ", name or "")
        tokens = re.findall(r"[A-Za-z]+", cleaned.lower())
        if not tokens:
            return None
        return (tokens[-1], tokens[0][:1])

    def _contact_author_keys(self):
        keys = set()
        for author in self.soup.find_all("div", class_="author"):
            text = author.get_text(" ", strip=True)
            if "(contact author)" not in text.lower():
                continue
            contact_name = re.split(r"\s*\(contact author\)", text, flags=re.I)[0]
            key = self._name_key(contact_name)
            if key:
                keys.add(key)
        return keys

    def parse(self):
        results = []
        authors = self.soup.find("div", class_="authors")
        name_soup = authors.findAll("h2")
        affiliation_soup = authors.findAll("p")
        contact_author_keys = self._contact_author_keys()

        for name, affiliation in zip(name_soup, affiliation_soup):
            name = name.text.strip()
            is_corresponding = self._name_key(name) in contact_author_keys
            affiliations = []
            affiliation = affiliation.text.strip()
            if affiliation != "affiliation not provided to SSRN":
                aff_split = affiliation.split(";")
                for aff in aff_split:
                    affiliations.append(aff.strip())
            results.append(
                AuthorAffiliations(
                    name=name,
                    affiliations=affiliations,
                    is_corresponding=is_corresponding,
                )
            )
        abstract_tag = self.soup.select_one("div.abstract-text p")
        abstract = abstract_tag.text if abstract_tag else None
        return {"authors": results, "abstract": abstract}

    test_cases = [
        {
            "doi": "10.2139/ssrn.1500730",
            "result": [
                {
                    "name": "Susann Rohwedder",
                    "affiliations": [
                        "RAND Corporation",
                    ],
                    "is_corresponding": True,
                },
                {
                    "name": "Robert J. Willis",
                    "affiliations": [
                        "University of Michigan at Ann Arbor - Department of Economics",
                        "National Bureau of Economic Research (NBER)",
                    ],
                    "is_corresponding": False,
                },
            ],
        },
        {
            "doi": "10.2139/ssrn.3782675",
            "result": [
                {
                    "name": "Madison Condon",
                    "affiliations": [
                        "Boston University - School of Law",
                        "New York University School of Law",
                    ],
                    "is_corresponding": True,
                },
            ],
        },
    ]
