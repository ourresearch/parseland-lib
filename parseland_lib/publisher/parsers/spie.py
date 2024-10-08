from parseland_lib.elements import Author, Affiliation
from parseland_lib.publisher.parsers.parser import PublisherParser


class SPIE(PublisherParser):
    parser_name = "spie"

    def is_publisher_specific_parser(self):
        link = self.soup.find("a", class_="logo")
        return link and "spie.org" in link.get("href")

    def authors_found(self):
        return self.soup.find(id="affiliations")

    def parse(self):
        authors = self.get_authors()
        affiliations = self.get_affiliations()
        authors_affiliations = self.merge_authors_affiliations(authors, affiliations)
        return {
            "authors": authors_affiliations,
            "abstract": self.parse_abstract_meta_tags(),
        }

    def get_authors(self):
        authors = []
        author_soup = self.soup.find(id="affiliations")
        # find and remove orcid link
        links = author_soup.findAll("a")
        for link in links:
            if "orcid.org" in link.get("href"):
                link.decompose()

        author_soup = author_soup.b.findAll("sup")
        for author in author_soup:
            name = str(author.previous_sibling).strip(' ,')
            aff_ids_raw = author.text
            aff_ids = []
            for aff_id_raw in aff_ids_raw:
                aff_id = aff_id_raw.strip()
                if aff_id:
                    aff_ids.append(aff_id)
            authors.append(Author(name=name, aff_ids=aff_ids, is_corresponding='*' in aff_ids_raw))
        return authors

    def get_affiliations(self):
        aff_soup = self.soup.find(id="affiliations")

        results = []
        if aff_soup:
            affiliations = aff_soup.find("br").find_next_siblings("sup")
            for affiliation in affiliations:
                # affiliation id
                aff_id = affiliation.text
                affiliation.clear()

                # affiliation
                aff = affiliation.next_element.strip()
                results.append(Affiliation(organization=aff, aff_id=aff_id))
        return results

    test_cases = [
        {
            "doi": "10.1117/12.2602977",
            "result": {
                "authors": [
                    {
                        "name": "Le Li",
                        "affiliations": [
                            "Naval Univ. of Engineering (China)",
                        ],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Zhi-hao Ye",
                        "affiliations": ["Naval Univ. of Engineering (China)"],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Yi-hui Xia",
                        "affiliations": [
                            "Naval Univ. of Engineering (China)",
                        ],
                        "is_corresponding": None,
                    },
                ],
                "abstract": "In order to suppress the torque ripple of five-phase induction motor after phase fault, based on the idea of order reduction and decoupling, space transformation matrices under different faults are constructed, and new rotation transformation matrices are established. The mathematical model and simulation system of five-phase induction motor under three different phase-missing faults are established. and the effective action time carrier type pwm are adopted at the same time, so that the motor can continue to run smoothly and without disturbance in the event of a fault.",
            },
        },
    ]
