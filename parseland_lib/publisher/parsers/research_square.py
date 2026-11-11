import json
import re

from parseland_lib.elements import AuthorAffiliations
from parseland_lib.publisher.parsers.parser import PublisherParser

_NEXT_DATA_RE = re.compile(rb'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def research_square_corresponding_names(lp_content):
    """Names Research Square flags as corresponding authors in the page's embedded Next.js data (oxjob #2153).

    Research Square's byline shows "A, B, and 4 more" until clicked; the expanded list and its "Corresponding author"
    label are drawn from `__NEXT_DATA__` -> props.pageProps.initialData.authors[], where each author carries
    `correspondingAuthor`. The old server-rendered `div.authors-expanded` block (ResearchSquare.parse) is on ~5% of
    stored pages (0 of 200 sampled pages whose work had no corresponding author), so the meta-tag parser wins and no
    one was marked. A list that flags every one of >= 2 authors
    is no mark. Returns [] unless the data is a 10.21203 Research Square article.
    """
    if isinstance(lp_content, str):
        lp_content = lp_content.encode("utf-8", "replace")
    m = _NEXT_DATA_RE.search(lp_content)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
        article = data["props"]["pageProps"]["initialData"]
        authors = article["authors"]
    except (ValueError, KeyError, TypeError):
        return []
    if not isinstance(authors, list) or not str(article.get("doi") or "").lower().startswith("10.21203/"):
        return []
    names = [(a.get("name") or "").strip() for a in authors
             if isinstance(a, dict) and a.get("correspondingAuthor") is True]
    names = [n for n in names if n]
    if len(authors) >= 2 and len(names) == len(authors):
        return []
    return names


class ResearchSquare(PublisherParser):
    parser_name = "research square"

    def is_publisher_specific_parser(self):
        return self.domain_in_meta_og_url("researchsquare.com")

    def authors_found(self):
        return bool(self.soup.select('div.authors-expanded div.author'))

    def parse(self):
        results = []
        authors = []
        if author_section := self.soup.find("div", class_="authors-expanded"):
            authors = author_section.findAll("div", class_="author")
        for author in authors:
            name = author.find("h5").text.strip()

            is_corresponding = (
                True if "corresponding author" in author.text.lower() else False
            )

            affiliations = []
            affiliations_soup = author.findAll("h6")
            for aff in affiliations_soup:
                if "corresponding" in aff.text.lower():
                    break
                affiliations.append(aff.text)

            results.append(
                AuthorAffiliations(
                    name=name,
                    affiliations=affiliations,
                    is_corresponding=is_corresponding,
                )
            )
        return results

    test_cases = [
        {
            "doi": "10.21203/rs.3.rs-725749/v1",
            "result": [
                {
                    "name": "Bo WenBo",
                    "affiliations": [
                        "College of Electrical and Mechanical Engineering"
                    ],
                    "is_corresponding": True,
                },
                {
                    "name": "Chao-Qing Dai",
                    "affiliations": [
                        "College of Optical,Mechanical and Electrical Engineering,Zhejiang A&F University"
                    ],
                    "is_corresponding": False,
                },
                {
                    "name": "Yue-Yue Wang",
                    "affiliations": [
                        "College of Optical,Mechanical and Engineering,Zhejiang A&F University,Lin'an 311300,China"
                    ],
                    "is_corresponding": False,
                },
                {
                    "name": "Peng-Fei Li",
                    "affiliations": [
                        "Department of Physics, Taiyuan Normal University"
                    ],
                    "is_corresponding": False,
                },
            ],
        },
    ]
