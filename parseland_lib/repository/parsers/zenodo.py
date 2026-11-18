import json
import re

from parseland_lib.repository.parsers.parser import RepositoryParser


# A creator placeholder, not a person: "&Na;," (an "N/A" mangled on import, on Zenodo's bulk-imported 1880s records),
# "n/a", "Demselben," ("by the same", the German journals' running credit) (#2239 round 8b)
_PLACEHOLDER = re.compile(r"\W*(?:&\w+;|n/?a|demselben|derselbe)?\W*", re.I)


# A role label where the affiliation goes: "(Autor/in)" ("(author)", on records imported from German library
# catalogues), "(Hrsg.)". A role is never an employer or institute (#2239 round 8c).
_ROLE_LABEL = re.compile(
    r"\(?\s*(?:autor|author|verfasser|herausgeber|hrsg|editor|bearbeiter|übersetzer|translator|contributor|creator)"
    r"(?:/?in(?:nen)?|en|s)?\.?\s*\)?", re.I)


def _as_list(value):
    return value if isinstance(value, list) else [value] if value else []


def _names(value):
    """Affiliation names from a JSON-LD value: a string, an Organization, or a list of either (InvenioRDM writes
    [{"@type": "Organization", "name": ...}])."""
    names = [item.get("name") if isinstance(item, dict) else item for item in _as_list(value)]
    return [n.strip() for n in names if isinstance(n, str) and n.strip() and not _ROLE_LABEL.fullmatch(n.strip())]


def zenodo_affiliations(soup):
    """(creator name, affiliations) per JSON-LD creator of a Zenodo record page that has any (#2239 round 8b)."""
    parser = Zenodo(soup)
    if not parser.is_correct_parser():
        return []
    try:
        authors = parser.parse()["authors"]
    except ValueError:  # a malformed JSON-LD block
        return []
    return [(a["name"], a["affiliations"]) for a in authors if a["affiliations"]]


class Zenodo(RepositoryParser):
    parser_name = "Zenodo"

    def is_correct_parser(self):
        # the host, not the path: Zenodo's move from /record/ to /records/ (InvenioRDM, Oct 2023) silently stopped this
        # parser from matching (#2239 round 5); authors come only from the record's JSON-LD creators
        return self.domain_in_meta_og_url("zenodo.org/")

    def authors_found(self):
        return self.soup.find("script", {"type": "application/ld+json"})

    def parse(self):
        authors = []

        for ld_json in self.soup.find_all("script", {"type": "application/ld+json"}):
            article_metadata = json.loads(ld_json.text)
            for creator in _as_list(article_metadata.get("creator")):
                if isinstance(creator, dict) and creator.get("@type") == "Person" and creator.get("name") and (
                        not _PLACEHOLDER.fullmatch(creator["name"])):
                    authors.append(
                        {
                            "name": creator["name"],
                            "affiliations": _names(creator.get("affiliation")),
                            "is_corresponding": None,
                        }
                    )

        return {"authors": authors}

    test_cases = [
        {
            "page-id": "PPUy5baHbVk44dssWdcx",  # https://zenodo.org/record/5580983
            "result": {
                "authors": [
                    {
                        "name": "Gattu Vijaya Kumar",
                        "affiliations": [
                            "Department of Computer Science and  Engineering, Sreenidhi Institute of Science and Technology, Yamnampet,  Ghatkesar, Hyderabad, Telangana, India."
                        ],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Prasanta Kumar Sahoo",
                        "affiliations": [
                            "Department of Computer Science and  Engineering, Sreenidhi Institute of Science and Technology, Yamnampet,  Ghatkesar, Hyderabad, Telangana, India."
                        ],
                        "is_corresponding": None,
                    },
                    {
                        "name": "K.Eswaran",
                        "affiliations": [
                            "Department of Computer Science and  Engineering, Sreenidhi Institute of Science and Technology, Yamnampet,  Ghatkesar, Hyderabad, Telangana, India."
                        ],
                        "is_corresponding": None,
                    },
                ]
            },
        },
    ]
