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

    @staticmethod
    def _detail_name_key(name):
        name = re.split(r"\s*\(contact author\)", name or "", flags=re.I)[0]
        name = re.sub(r"\s+", " ", name).strip().lower()
        return name or None

    @staticmethod
    def _is_no_affiliation_placeholder(affiliation):
        return "affiliation not provided to ssrn" in (affiliation or "").lower()

    @staticmethod
    def _dedupe_affiliations(affiliations):
        deduped = []
        seen = set()
        for affiliation in affiliations:
            key = re.sub(r"\s+", " ", affiliation or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(affiliation)
        return deduped

    @staticmethod
    def _clean_detail_org(text):
        text = re.sub(r"\(\s*email\s*\)", " ", text or "", flags=re.I)
        return re.sub(r"\s+", " ", text).strip(" ,")

    @staticmethod
    def _is_detail_noise(text):
        text = (text or "").strip()
        if not text:
            return True
        lower = text.lower()
        if lower == "email" or lower == "no address available":
            return True
        if "(phone)" in lower or "(fax)" in lower:
            return True
        return False

    def _detail_affiliations_by_author(self):
        by_author = {}
        current_key = None
        for author in self.soup.find_all("div", class_="author"):
            heading = author.find("h3")
            if heading:
                heading_text = re.split(
                    r"\s*\(contact author\)",
                    heading.get_text(" ", strip=True),
                    flags=re.I,
                )[0]
                current_key = self._detail_name_key(heading_text)
            if not current_key:
                continue

            block = author.find("div", class_="block-quote") or author
            org_tag = block.find("h4")
            org = self._clean_detail_org(org_tag.get_text(" ", strip=True) if org_tag else "")
            if self._is_no_affiliation_placeholder(org):
                continue

            address = []
            address_tag = block.find("p")
            if address_tag:
                for part in address_tag.stripped_strings:
                    part = re.sub(r"\s+", " ", part).strip(" ,")
                    if not self._is_detail_noise(part):
                        address.append(part)

            parts = [p for p in [org, *address] if p]
            if parts:
                by_author.setdefault(current_key, []).append(", ".join(parts))
        return {
            key: self._dedupe_affiliations(affiliations)
            for key, affiliations in by_author.items()
        }

    def parse(self):
        results = []
        authors = self.soup.find("div", class_="authors")
        name_soup = authors.findAll("h2")
        affiliation_soup = authors.findAll("p")
        contact_author_keys = self._contact_author_keys()
        detail_affiliations_by_author = self._detail_affiliations_by_author()

        for name, affiliation in zip(name_soup, affiliation_soup):
            name = name.text.strip()
            name_key = self._name_key(name)
            is_corresponding = name_key in contact_author_keys
            affiliations = []
            affiliation = affiliation.text.strip()
            if not self._is_no_affiliation_placeholder(affiliation):
                aff_split = affiliation.split(";")
                for aff in aff_split:
                    affiliations.append(aff.strip())
            detail_key = self._detail_name_key(name)
            affiliations = (
                detail_affiliations_by_author.get(detail_key)
                or self._dedupe_affiliations(affiliations)
            )
            results.append(
                AuthorAffiliations(
                    name=name,
                    affiliations=affiliations,
                    is_corresponding=is_corresponding,
                )
            )
        abstract_parts = [
            tag.text.strip()
            for tag in self.soup.select("div.abstract-text p")
            if tag.text.strip()
        ]
        abstract = " ".join(abstract_parts) if abstract_parts else None
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
