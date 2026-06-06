import re

from parseland_lib.elements import AuthorAffiliations
from parseland_lib.publisher.parsers.parser import PublisherParser


class CUP(PublisherParser):
    parser_name = "cambridge university press"

    def is_publisher_specific_parser(self):
        return (
            self.domain_in_meta_og_url("cambridge.org")
            or self.domain_in_canonical_link("cambridge.org")
        )

    def authors_found(self):
        if self.soup.find("div", class_="author"):
            return True
        if not self.is_publisher_specific_parser():
            return False
        return bool(
            self.soup.select_one('meta[name="citation_author"]')
            or self.soup.select_one('meta[name="citation_abstract"]')
            or self.soup.select_one("div.abstract")
            or self.soup.select_one('div[class*="abstract"]')
            or self.soup.select_one('section[class*="abstract"]')
        )

    def _visible_abstract(self):
        for selector in (
            "div.abstract",
            'div[class*="abstract"]',
            'section[class*="abstract"]',
        ):
            for tag in self.soup.select(selector):
                text = tag.get_text(" ", strip=True)
                text = re.sub(r"^(abstract\s*)+", "", text, flags=re.I).strip()
                if len(text) >= 20:
                    return text
        return None

    def parse(self):
        result_authors = []
        authors = self.soup.findAll("div", class_="author")
        for author in authors:
            name = author.find("dt").text
            if "*" in name:
                is_corresponding = True
            else:
                is_corresponding = False
            name = name.strip().replace("*", "")

            affiliations = []
            affiliation_soup = author.find("div", class_="d-sm-flex")
            if affiliation_soup:
                for organization in affiliation_soup.stripped_strings:
                    organization = re.sub('email:.*?$', '', organization)
                    organization = re.sub(r'[a-zA-Z0-9._%+-]+@.*?$', '', organization)
                    affiliations.append(organization.strip('., ()'))

            result_authors.append(
                AuthorAffiliations(
                    name=name,
                    affiliations=affiliations,
                    is_corresponding=is_corresponding,
                )
            )
        # Older CUP journal pages and Cambridge eBook (cbo*) chapters use a
        # different template with no div.author — authors live in
        # citation_author meta tags (affiliations in citation_author_institution).
        # Fall back to meta-tag parsing so these ~40% of pages aren't dropped.
        if not result_authors:
            result_authors = self.parse_author_meta_tags()

        # Journal pages carry the abstract in meta tags. Cambridge eBook (cbo*)
        # chapter pages do not — their meta og:description is just the book
        # title ("Frank Sinatra - June 2007"), while the real chapter abstract
        # lives in div.abstract. Fall back to it when the meta abstract is
        # missing or too short to be a real abstract.
        abstract = self.parse_abstract_meta_tags()
        visible_abstract = self._visible_abstract()
        if visible_abstract and (
            not abstract
            or len(abstract) < 200
            or "an abstract is not available for this content" in visible_abstract.lower()
        ):
            abstract = visible_abstract

        return {"authors": result_authors, "abstract": abstract}

    test_cases = [
        {
            "doi": "10.1017/S1355770X21000218",
            "result": {
                "authors": [
                    {
                        "name": "Julien Wolfersberger",
                        "affiliations": [
                            "Université Paris-Saclay, INRAE, AgroParisTech, Economie Publique, Thiverval-Grignon, France",
                            "Climate Economics Chair, Palais Brongniart, Paris, France",
                        ],
                        "is_corresponding": True,
                    },
                    {
                        "name": "Gregory S. Amacher",
                        "affiliations": [
                            "Virginia Polytechnic Institute and State University, Blacksburg, VA, USA"
                        ],
                        "is_corresponding": False,
                    },
                    {
                        "name": "Philippe Delacote",
                        "affiliations": [
                            "Climate Economics Chair, Palais Brongniart, Paris, France",
                            "BETA, Université Lorraine, INRAE, AgroParisTech, Nancy, France",
                        ],
                        "is_corresponding": False,
                    },
                    {
                        "name": "Arnaud Dragicevic",
                        "affiliations": ["IRSTEA, Clermont-Ferrand, Aubiere, France"],
                        "is_corresponding": False,
                    },
                ],
                "abstract": "We develop a model of optimal land allocation in a developing economy that features three possible land uses: agriculture, primary and secondary forests. The distinction between those forest types reflects their different contributions in terms of public goods. In our model, reforestation is costly because it undermines land title security. Using the forest transition concept, we study long-term land-use change and explain important features of cumulative deforestation across countries. Our results shed light on the speed at which net deforestation ends, on the effect of tenure costs in this process, and on composition in steady state. We also present a policy analysis that emphasizes the critical role of institutional reforms addressing the costs of both deforestation and tenure in order to promote a transition. We find that focusing only on net forest losses can be misleading since late transitions may yield, upon given conditions, a higher level of environmental benefits.",
            },
        },
    ]
