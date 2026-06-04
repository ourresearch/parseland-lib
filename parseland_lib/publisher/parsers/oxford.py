import json
import re

from parseland_lib.exceptions import UnusualTrafficError
from parseland_lib.elements import AuthorAffiliations
from parseland_lib.publisher.parsers.parser import PublisherParser


class Oxford(PublisherParser):
    parser_name = "oxford university press"

    def is_publisher_specific_parser(self):
        if self.soup.find(
                "div", class_="explanation-message"
        ) and "help us confirm that you are not a robot and we will take you to your content" in str(
            self.soup
        ):
            raise UnusualTrafficError(
                f"content blocked within {self.parser_name} parser"
            )
        # The HTML may have og:url=dx.doi.org (the DOI router) even when the
        # actual page is on academic.oup.com — common for cached HTML where
        # the publisher's page sets og:url to the DOI for citation portability.
        # Accept either signal: og:url OR canonical link.
        return (
            self.domain_in_meta_og_url("academic.oup.com")
            or self.domain_in_canonical_link("academic.oup.com")
        )

    def authors_found(self):
        return self.soup.find("div", class_="at-ArticleAuthors")

    def parse(self):
        results = []
        if author_soup := self.soup.find("div", class_="at-ArticleAuthors"):
            authors = author_soup.findAll("div", class_="info-card-author")

            for author in authors:
                name = author.find("div", class_="info-card-name").text.strip()

                is_corresponding = (
                    True
                    if author.find("div", class_="info-author-correspondence")
                    else False
                )

                affiliations = []
                affiliation_section = author.find("div",
                                                  class_="info-card-affilitation")
                if affiliation_section:
                    affiliations_soup = affiliation_section.findAll("div",
                                                                    class_="aff")
                    for aff in affiliations_soup:
                        aff_cleaned = re.sub('^\d+', '', aff.text)
                        affiliations.append(aff_cleaned)

                results.append(
                    AuthorAffiliations(
                        name=name,
                        affiliations=affiliations,
                        is_corresponding=is_corresponding,
                    )
                )
        abstract = self._extract_abstract()
        return {"authors": results,
                "abstract": abstract,}

    def _extract_abstract(self):
        """Extract abstract with fallbacks for OUP markup variants.

        Order of preference:
          1. ``section.abstract p`` — standard OUP journal article template.
          2. ``.chapter-para`` — conference/supplement abstracts and some
             book-chapter templates that omit the ``section.abstract`` wrapper
             but expose the abstract body via the ``chapter-para`` class.
          3. ``meta[name=citation_abstract]`` content — used by a handful of
             OUP titles, full-length abstract.
          4. ``meta[property=og:description]`` / ``meta[name=description]``
             content with the leading "Abstract" prefix stripped — truncated
             at ~160 chars but better than no abstract at all.
        """
        primary = '\n'.join(
            tag.text for tag in self.soup.select('section.abstract p')
            if tag.text and tag.text.strip()
        ).strip()
        if primary:
            return primary

        chapter_paras = '\n'.join(
            tag.text for tag in self.soup.select('.chapter-para')
            if tag.text and tag.text.strip()
        ).strip()
        if chapter_paras:
            return chapter_paras

        citation_meta = self.soup.select_one('meta[name="citation_abstract"]')
        if citation_meta and (citation_meta.get('content') or '').strip():
            return citation_meta.get('content').strip()

        for selector in ('meta[property="og:description"]',
                         'meta[name="description"]'):
            meta = self.soup.select_one(selector)
            if not meta:
                continue
            content = (meta.get('content') or '').strip()
            if not content:
                continue
            # Strip leading "Abstract" / "Abstract." prefix that OUP injects.
            content = re.sub(r'^abstract[\.\s:]*', '', content, flags=re.I).strip()
            if content:
                return content
        return ''


    test_cases = [
        {
            "doi": "10.1093/bib/bbab286",
            "result": [
                {
                    "name": "Chun-Chun Wang",
                    "affiliations": [
                        "School of Information and Control Engineering, China University of Mining and Technology"
                    ],
                    "is_corresponding": False,
                },
                {
                    "name": "Chen-Di Han",
                    "affiliations": [
                        "School of Information and Control Engineering, China University of Mining and Technology"
                    ],
                    "is_corresponding": False,
                },
                {
                    "name": "Qi Zhao",
                    "affiliations": [
                        "School of Computer Science and Software Engineering, University of Science and Technology Liaoning"
                    ],
                    "is_corresponding": True,
                },
                {
                    "name": "Xing Chen",
                    "affiliations": [
                        "China University of Mining and Technology"],
                    "is_corresponding": True,
                },
            ],
        },
        {
            "doi": "10.1093/jamia/ocab164",
            "result": [
                {
                    "name": "Chi Yuan",
                    "affiliations": [
                        "Department of Biomedical Informatics, Columbia University, New York, New York, USA"
                    ],
                    "is_corresponding": False,
                },
                {
                    "name": "Patrick B Ryan",
                    "affiliations": [
                        "Department of Biomedical Informatics, Columbia University, New York, New York, USA",
                        "Observational Health Data Sciences and Informatics, New York, New York, USA",
                        "Epidemiology Analytics, Janssen Research and Development, Titusville, New Jersey, USA",
                    ],
                    "is_corresponding": False,
                },
                {
                    "name": "Casey N Ta",
                    "affiliations": [
                        "Department of Biomedical Informatics, Columbia University, New York, New York, USA"
                    ],
                    "is_corresponding": False,
                },
                {
                    "name": "Jae Hyun Kim",
                    "affiliations": [
                        "Department of Biomedical Informatics, Columbia University, New York, New York, USA"
                    ],
                    "is_corresponding": False,
                },
                {
                    "name": "Ziran Li",
                    "affiliations": [
                        "Department of Biomedical Informatics, Columbia University, New York, New York, USA"
                    ],
                    "is_corresponding": False,
                },
                {
                    "name": "Chunhua Weng",
                    "affiliations": [
                        "Department of Biomedical Informatics, Columbia University, New York, New York, USA"
                    ],
                    "is_corresponding": True,
                },
            ],
        },
        {
            "doi": "10.1093/arclin/acab062.129",
            "result": [
                {
                    "name": "Julianne Wilson",
                    "affiliations": [],
                    "is_corresponding": None,
                },
                {
                    "name": "Amanda R Rabinowitz",
                    "affiliations": [],
                    "is_corresponding": None,
                },
                {
                    "name": "Tessa Hart",
                    "affiliations": [],
                    "is_corresponding": None,
                },
            ],
        },
    ]
