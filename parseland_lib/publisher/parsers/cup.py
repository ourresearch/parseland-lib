import re

from parseland_lib.elements import AuthorAffiliations
from parseland_lib.publisher.parsers.parser import PublisherParser


class CUP(PublisherParser):
    parser_name = "cambridge university press"
    prefer_publisher_authors_over_generic = True
    _NON_AUTHOR_ROLE_PREFIXES = (
        "appendix by",
        "general editor",
        "introduction by",
        "preface by",
        "translated by",
    )

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
            or self.soup.select_one("h1.chapter-title")
            or self.soup.select_one("li.author")
            or self.soup.select_one(".contributors-details")
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

    @staticmethod
    def _clean_contributor_name(text):
        text = re.sub(r"\s*\[Opens in a new window\]\s*", "", text or "")
        text = re.sub(r"\s+", " ", text)
        return text.strip(" ,")

    def _contributor_names(self, tag):
        names = []
        for selector in ("span.author-name", "a.more-by-this-author", ".contributor-type__contributor"):
            for node in tag.select(selector):
                text = self._clean_contributor_name(node.get_text(" ", strip=True))
                text = re.sub(r"\s+and$", "", text).strip(" ,")
                if text and text not in names:
                    names.append(text)
            if names:
                break
        return names

    def _detail_affiliations_by_name(self):
        affiliations_by_name = {}
        for author in self.soup.select("div.row.author"):
            name_tag = author.find("dt")
            if name_tag:
                name = self._clean_contributor_name(name_tag.get_text(" ", strip=True))
            else:
                text = author.get_text(" ", strip=True)
                name = self._clean_contributor_name(text.split("Affiliation:", 1)[0])
            if not name:
                continue

            affiliations = []
            affiliation_soup = author.find("div", class_="d-sm-flex")
            if affiliation_soup:
                for organization in affiliation_soup.stripped_strings:
                    organization = re.sub('email:.*?$', '', organization)
                    organization = re.sub(r'[a-zA-Z0-9._%+-]+@.*?$', '', organization)
                    organization = organization.strip('., ()')
                    if organization:
                        affiliations.append(organization)
            if affiliations:
                affiliations_by_name[name] = affiliations
        return affiliations_by_name

    def _contributors_from_tag(self, tag, detail_affiliations):
        names = self._contributor_names(tag)
        row_affiliations = [
            self._clean_contributor_name(node.get_text(" ", strip=True))
            for node in tag.select(".affiliation")
        ]
        row_affiliations = [aff for aff in row_affiliations if aff]

        authors = []
        for index, name in enumerate(names):
            affiliations = list(detail_affiliations.get(name, []))
            if not affiliations and len(row_affiliations) == len(names):
                affiliations = [row_affiliations[index]]
            elif not affiliations and len(names) == 1 and row_affiliations:
                affiliations = row_affiliations
            authors.append(
                AuthorAffiliations(
                    name=name,
                    affiliations=affiliations,
                    is_corresponding=False,
                )
            )
        return authors

    def _chapter_contributor_authors(self):
        if not (
            self.soup.select_one("h1.chapter-title")
            or self.soup.select_one("li.author.chapter")
        ):
            return []

        by_authors = []
        unlabeled_authors = []
        editor_authors = []
        detail_affiliations = self._detail_affiliations_by_name()
        seen = {"by": {}, "unlabeled": {}, "editor": {}}

        def append_many(bucket, key, authors):
            for author in authors:
                if author.name in seen[key]:
                    existing = seen[key][author.name]
                    if not existing.affiliations and author.affiliations:
                        existing.affiliations = author.affiliations
                    continue
                bucket.append(author)
                seen[key][author.name] = author

        for tag in self.soup.select("div.row.contributor-type, li.author"):
            classes = set(tag.get("class") or [])
            label_tag = tag.select_one(".contributor-type__label")
            label = label_tag.get_text(" ", strip=True).lower() if label_tag else ""
            text = tag.get_text(" ", strip=True).lower()
            authors = self._contributors_from_tag(tag, detail_affiliations)
            if not authors:
                continue

            if label == "by" or ("chapter" in classes and text.startswith("by ")):
                append_many(by_authors, "by", authors)
            elif label.startswith("edited") or text.startswith("edited by"):
                append_many(editor_authors, "editor", authors)
            elif not label and not text.startswith(self._NON_AUTHOR_ROLE_PREFIXES):
                append_many(unlabeled_authors, "unlabeled", authors)

        return by_authors or unlabeled_authors or editor_authors

    def parse(self):
        result_authors = self._chapter_contributor_authors()
        if not result_authors:
            authors = self.soup.findAll("div", class_="author")
            for author in authors:
                name_tag = author.find("dt")
                if not name_tag:
                    continue
                name = name_tag.text
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
