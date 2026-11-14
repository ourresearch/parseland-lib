from parseland_lib.elements import AuthorAffiliations
from parseland_lib.publisher.parsers.parser import PublisherParser


class Emerald(PublisherParser):
    parser_name = "emerald"

    def is_publisher_specific_parser(self):
        return self.domain_in_canonical_link("emerald.com")

    def authors_found(self):
        return self.soup.find("span", class_="m:contributor-display")

    def parse(self):
        results = []
        author_soup = self.soup.find("span", class_="m:contributor-display")
        authors = author_soup.findAll("div", {"contrib-type": "author"})
        if not authors:
            return results
        # The Emerald Insight template marks the corresponding author with JATS corresp="yes" on the author's div
        # (2015+ articles); pages that mark no one leave every flag None (oxjob #2212).
        any_marked = any(a.get("corresp") == "yes" for a in authors)
        for author in authors:
            name = author.a.text.strip()

            affiliations = []
            affiliation_soup = author.find(
                "span", class_="intent_contributor_affiliate"
            )
            if affiliation_soup:
                for organization in affiliation_soup.text.split(", and"):
                    organization = (
                        organization.strip().replace(", and", "").replace("\n", "")
                    )
                    if organization.startswith("("):
                        organization = organization[1:]
                    if organization.endswith(")"):
                        organization = organization[:-1]
                    affiliations.append(organization)

            is_corresponding = (author.get("corresp") == "yes") if any_marked else None
            results.append(AuthorAffiliations(name=name, affiliations=affiliations, is_corresponding=is_corresponding))
        return results

    test_cases = [
        {
            "doi": "10.1108/SEF-09-2020-0364",
            "result": [
                {
                    "name": "Zakaria Lacheheb",
                    "affiliations": [
                        "School of Business and Economics, Universiti Putra Malaysia, Serdang, Malaysia",
                        "Kulliyyah of Economics and Management Sciences, International Islamic University Malaysia, Gombak, Malaysia",
                    ],
                    "is_corresponding": True,  # the page marks this author corresp="yes" (oxjob #2212)
                },
                {
                    "name": "Normaz Wana Ismail",
                    "affiliations": [
                        "School of Business and Economics, Universiti Putra Malaysia, Serdang, Malaysia"
                    ],
                    "is_corresponding": False,
                },
                {
                    "name": "N.A.M. Naseem",
                    "affiliations": [
                        "School of Business and Economics, Universiti Putra Malaysia, Serdang, Malaysia"
                    ],
                    "is_corresponding": False,
                },
                {
                    "name": "Ly Slesman",
                    "affiliations": [
                        "Centre for Advanced Research (CARe), Universiti Brunei Darussalam, Bandar Seri Begawan, Brunei Darussalam"
                    ],
                    "is_corresponding": False,
                },
            ],
        },
    ]

