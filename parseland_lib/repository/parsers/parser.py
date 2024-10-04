import copy
import re
from abc import ABC, abstractmethod
from pydoc import resolve
from urllib.parse import urlparse

from parseland_lib.elements import AuthorAffiliations
from parseland_lib.legacy_parse_utils.fulltext import \
    parse_repo_fulltext_locations
from parseland_lib.legacy_parse_utils.pdf import DuckLink, find_pdf_link, \
    trust_publisher_license, find_normalized_license, find_version, \
    get_link_target, discard_pdf_url, find_doc_download_link, \
    try_pdf_link_as_doc, find_bhl_view_link, trust_repo_license
from parseland_lib.legacy_parse_utils.version_and_license import \
    page_potential_license_text


class RepositoryParser(ABC):
    def __init__(self, soup):
        self.soup = soup

    @property
    @abstractmethod
    def parser_name(self):
        pass

    @abstractmethod
    def is_correct_parser(self):
        pass

    @abstractmethod
    def authors_found(self):
        pass

    @staticmethod
    def no_authors_output():
        return []

    @abstractmethod
    def parse(self):
        pass

    def domain_in_canonical_link(self, domain):
        canonical_link = self.soup.find("link", {"rel": "canonical"})
        if (
            canonical_link
            and canonical_link.get("href")
            and domain in canonical_link.get("href")
        ):
            return True

    def domain_in_meta_og_url(self, domain):
        meta_og_url = self.soup.find("meta", property="og:url")
        if (
            meta_og_url
            and meta_og_url.get("content")
            and domain in meta_og_url.get("content")
        ):
            return True

    def parse_meta_tags(self):
        results = []
        metas = self.soup.findAll("meta")

        result = None
        for meta in metas:
            if meta.get("name") == "citation_author":
                if result:
                    # reset for next author
                    results.append(result)
                name = meta["content"].strip()
                result = {
                    "name": name,
                    "affiliations": [],
                    "is_corresponding": None,
                }
            if result and meta.get("name") == "citation_author_institution":
                result["affiliations"].append(meta["content"].strip())

        # append name from last loop
        if result:
            results.append(result)

        return results

    @staticmethod
    def format_name(name):
        return " ".join(reversed(name.split(", ")))

    @staticmethod
    def merge_authors_affiliations(authors, affiliations):
        results = []
        for author in authors:
            author_affiliations = []

            # scenario 1 affiliations with ids
            for aff_id in author.aff_ids:
                for aff in affiliations:
                    if aff_id == aff.aff_id:
                        author_affiliations.append(str(aff.organization))

            # scenario 2 affiliations with no ids (applied to all authors)
            for aff in affiliations:
                if len(author.aff_ids) == 0 and aff.aff_id is None:
                    author_affiliations.append(str(aff.organization))

            results.append(
                AuthorAffiliations(name=author.name, affiliations=author_affiliations)
            )
        return results

    def parse_fulltext_locations(self, resolved_url):
        return parse_repo_fulltext_locations(self.soup, resolved_url)

    test_cases = []
