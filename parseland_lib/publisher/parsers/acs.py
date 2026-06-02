from parseland_lib.exceptions import UnusualTrafficError
from parseland_lib.elements import AuthorAffiliations
from parseland_lib.publisher.parsers.parser import PublisherParser


class ACS(PublisherParser):
    parser_name = "acs"

    def is_publisher_specific_parser(self):
        if "Request forbidden by administrative rules" in str(self.soup):
            raise UnusualTrafficError(f"Page blocked within parser {self.parser_name}")
        return self.domain_in_meta_og_url(".acs.org")

    def authors_found(self):
        return self.soup.find("ul", class_="loa")

    def parse(self):
        result_authors = []
        author_soup = self.soup.find("ul", class_="loa")
        authors = author_soup.findAll("li")
        # Alternate ACS template (older / some journals): affiliations are not
        # per-author loa-info-affiliations divs but a page-level list of
        # div.aff-info > span.aff-text (the main institutional affiliation,
        # usually shared by all authors; the dagger/double-dagger footnotes are
        # present-address / correspondence notes, captured separately). Use it as
        # a shared fallback for authors that have no per-author affiliations.
        shared_affs = [
            t.get_text(" ", strip=True)
            for t in self.soup.select("div.aff-info span.aff-text")
        ]
        shared_affs = [a for a in shared_affs if a]
        for author in authors:
            # Prefer loa-info-name (modern template); fall back to
            # hlFld-ContribAuthor (alternate template — gives a clean name
            # without the trailing author-xref-symbol superscript); finally the
            # raw li text.
            name = author.find("div", class_="loa-info-name")
            if not name:
                name = author.find("span", class_="hlFld-ContribAuthor")
            if name:
                name = name.text.strip()
            else:
                name = author.text

            # ul.loa interleaves separator <li> elements (", " and " and ")
            # between author names; without a name div they fall through to
            # author.text and were being emitted as junk authors, tanking author
            # precision. Skip any <li> whose text is just a separator.
            name = (name or "").replace("\xa0", " ").strip()
            if not name or name.strip(" ,&").lower() in ("", "and"):
                continue

            strong = author.find("strong")
            is_corresponding = bool(strong and strong.text.strip() == "*")
            if not is_corresponding:
                # Alternate template marks the corresponding author with a '*'
                # in an author-xref-symbol superscript rather than a
                # <strong>*</strong>; the <strong> check alone missed these
                # (recall 0.63). The '*' xref is corresponding-only on ACS.
                is_corresponding = any(
                    "*" in x.get_text() for x in author.select(".author-xref-symbol")
                )

            affiliations = []
            affiliation_soup = author.find("div", class_="loa-info-affiliations")
            if affiliation_soup:
                for organization in affiliation_soup.findAll("div"):
                    affiliations.append(organization.text.strip())
            if not affiliations:
                affiliations = list(shared_affs)

            result_authors.append(
                AuthorAffiliations(
                    name=name,
                    affiliations=affiliations,
                    is_corresponding=is_corresponding,
                )
            )
        return {"authors": result_authors, "abstract": self.parse_abstract_meta_tags()}

    test_cases = [
        {
            "doi": "10.1021/acs.jpcb.1c05793",
            "result": {
                "authors": [
                    {
                        "name": "Piotr Wróbel",
                        "affiliations": [
                            "Faculty of Chemistry, Jagiellonian University, Gronostajowa 2, 30-387 Kraków, Poland",
                        ],
                        "is_corresponding": False,
                    },
                    {
                        "name": "Piotr Kubisiak",
                        "affiliations": [
                            "Faculty of Chemistry, Jagiellonian University, Gronostajowa 2, 30-387 Kraków, Poland"
                        ],
                        "is_corresponding": False,
                    },
                    {
                        "name": "Andrzej Eilmes",
                        "affiliations": [
                            "Faculty of Chemistry, Jagiellonian University, Gronostajowa 2, 30-387 Kraków, Poland"
                        ],
                        "is_corresponding": True,
                    },
                ],
                "abstract": "Classical molecular dynamics simulations have been performed for a series of electrolytes based on sodium bis(fluorosulfonyl)imide or sodium bis(trifluoromethylsulfonyl)imide salts and monoglyme, tetraglyme, and poly(ethylene oxide) as solvents. Structural properties have been assessed through the analysis of coordination numbers and binding patterns. Residence times for Na–O interactions have been used to investigate the stability of solvation shells. Diffusion coefficients of ions and electrical conductivity of the electrolytes have been estimated from molecular dynamics trajectories. Contributions to the total conductivity have been analyzed in order to investigate the role of ion–ion correlations. It has been found that the anion–cation interactions are more probable in the systems with NaTFSI salts. Accordingly, the degree of correlations between ion motions is larger in NaTFSI-based electrolytes.",
            },
        }
    ]
