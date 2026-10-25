import html
import re

from parseland_lib.elements import Author, Affiliation
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import NuxtPayload


def _plain(rich):
    """Payload and byline strings are rich text: drop inline tags (<i>, <sup>) and entities, collapse spaces."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", rich or ""))).strip()


class MDPI(PublisherParser):
    parser_name = "mdpi"
    chars_to_ignore = ["*", "†", "‡", "§"]
    NEW_AUTHOR = {"data-testid": "article-author"}  # find(attrs=...) is cheaper than a CSS select on every page

    def is_publisher_specific_parser(self):
        return self.domain_in_meta_og_url("mdpi.com")

    def _old_template(self):
        if not hasattr(self, "_old"):
            self._old = self.soup.find("div", class_="art-authors")
        return self._old

    def authors_found(self):
        return self._old_template() or self.soup.find(attrs=self.NEW_AUTHOR)

    def parse(self):
        if self._old_template():
            authors = self.get_authors()
            affiliations = self.get_affiliations()
        else:
            authors, affiliations = self.get_new_template()
        authors_affiliations = self.merge_authors_affiliations(authors, affiliations)
        return {
            "authors": authors_affiliations,
            "abstract": self.parse_abstract_meta_tags(),
        }

    def get_new_template(self):
        """MDPI's 2025-26 front end (Nuxt; ``data-testid="article-author"``), oxjob #1805.

        Each author's superscript holds affiliation numbers and ``*`` for the corresponding author ("2,*"). The full
        lists sit in the page's Nuxt payload (the HTML shows only the first four affiliations behind "Show more"), so
        the payload comes first and the visible byline is the fallback.
        """
        raw_authors, raw_affs = self._nuxt_authors_affiliations()
        if not raw_authors:
            raw_authors, raw_affs = self._html_authors_affiliations()
        authors = []
        for name, sup in raw_authors:
            name = _plain(name)
            if not name:
                continue
            sup = sup or ""
            authors.append(Author(name=name, aff_ids=self.format_ids(sup.replace(" ", ""), self.chars_to_ignore),
                                  is_corresponding="*" in sup))
        if len(authors) == 1 and not authors[0].is_corresponding:
            authors[0].is_corresponding = True  # the old template's rule: a sole author is the corresponding one
        affiliations = []
        for ident, org in raw_affs:
            ident, org = ("" if ident is None else str(ident)).strip(), _plain(org)
            if not org or ident in self.chars_to_ignore:
                continue  # '*' / '†' entries are correspondence and equal-contribution notes
            if not ident:
                affiliations.append(Affiliation(organization=org, aff_id=None))
            elif ident.isdigit():
                affiliations.append(Affiliation(organization=org, aff_id=int(ident)))
        return authors, affiliations

    def _nuxt_authors_affiliations(self):
        payload = NuxtPayload.from_soup(self.soup)
        if payload is None:
            return [], []
        root = payload.node(0)
        data = payload.node(root.get("data")) if isinstance(root, dict) else None
        if not isinstance(data, dict):
            return [], []
        for key, idx in data.items():
            article = payload.node(idx)
            if not (key.startswith("article-") and isinstance(article, dict)
                    and "authors" in article and "affiliations" in article):
                continue
            return ([(payload.node(a.get("name")), payload.node(a.get("superscript")))
                     for a in payload.dicts(article["authors"])],
                    [(payload.node(f.get("identifier")), payload.node(f.get("name")))
                     for f in payload.dicts(article["affiliations"])])
        return [], []

    def _html_authors_affiliations(self):
        authors = []
        for tag in self.soup.find_all(attrs=self.NEW_AUTHOR):
            name = tag.select_one('[itemprop="name"]')
            sup = tag.find("sup")
            authors.append((name.get_text(" ", strip=True) if name else None,
                            sup.get_text("", strip=True) if sup else ""))
        affs = []
        for tag in self.soup.select('[data-testid="article-affiliation"]'):
            sup = tag.find("sup")
            org = tag.select_one(".m-rich-text")
            affs.append((sup.get_text("", strip=True) if sup else "", org.get_text(" ", strip=True) if org else None))
        return authors, affs

    def get_authors(self):
        authors = []
        author_soup = self.soup.find("div", class_="art-authors")
        author_soup = author_soup.findAll("span", class_="inlineblock")
        for author in author_soup:
            if author.div:
                name = author.div.text
            else:
                name = author.a.text
            if "*" in author.sup.text:
                is_corresponding = True
            else:
                is_corresponding = False
            aff_ids = self.format_ids(author.sup.text, self.chars_to_ignore)
            authors.append(
                Author(name=name, aff_ids=aff_ids, is_corresponding=is_corresponding)
            )
        if len(authors) == 1 and authors[0].is_corresponding is False:
            authors[0].is_corresponding = True
        return authors

    def get_affiliations(self):
        aff_soup = self.soup.find("div", class_="art-affiliations")

        results = []
        if aff_soup:
            affiliations = aff_soup.findAll("div", class_="affiliation")
            for aff_raw in affiliations:
                aff_id_raw = aff_raw.find("sup")
                if aff_id_raw:
                    aff_id = aff_id_raw.text
                else:
                    aff_id = None
                aff = aff_raw.find("div", class_="affiliation-name").text
                if aff_id is None:
                    results.append(Affiliation(organization=aff, aff_id=aff_id))
                elif aff_id not in self.chars_to_ignore and aff_id.isnumeric():
                    aff_id = int(aff_id) if aff_id else None
                    results.append(Affiliation(organization=aff, aff_id=aff_id))
        return results

    test_cases = [
        {
            "doi": "10.3390/act10080193",
            "result": {
                "authors": [
                    {
                        "name": "Wenfei Li",
                        "affiliations": [
                            "Shenzhen Institutes of Advanced Technology, Chinese Academy of Sciences, Shenzhen 518055, China",
                            "SIAT Branch, Shenzhen Institute of Artificial Intelligence and Robotics for Society, Shenzhen 518055, China",
                            "Guangdong-Hong Kong-Macao Joint Laboratory of Human-Machine Intelligence-Synergy Systems, Shenzhen 518055, China",
                        ],
                        "is_corresponding": False,
                    },
                    {
                        "name": "Huiyun Li",
                        "affiliations": [
                            "Shenzhen Institutes of Advanced Technology, Chinese Academy of Sciences, Shenzhen 518055, China",
                            "SIAT Branch, Shenzhen Institute of Artificial Intelligence and Robotics for Society, Shenzhen 518055, China",
                            "Guangdong-Hong Kong-Macao Joint Laboratory of Human-Machine Intelligence-Synergy Systems, Shenzhen 518055, China",
                        ],
                        "is_corresponding": True,
                    },
                    {
                        "name": "Chao Huang",
                        "affiliations": [
                            "Department of Industrial and Systems Engineering, The Hong Kong Polytechnic University, Hong Kong 999077, China"
                        ],
                        "is_corresponding": False,
                    },
                    {
                        "name": "Kun Xu",
                        "affiliations": [
                            "Shenzhen Institutes of Advanced Technology, Chinese Academy of Sciences, Shenzhen 518055, China"
                        ],
                        "is_corresponding": False,
                    },
                    {
                        "name": "Tianfu Sun",
                        "affiliations": [
                            "Shenzhen Institutes of Advanced Technology, Chinese Academy of Sciences, Shenzhen 518055, China"
                        ],
                        "is_corresponding": False,
                    },
                    {
                        "name": "Haiping Du",
                        "affiliations": [
                            "School of Electrical, Computer and Telecommunications Engineering, University of Wollongong, Wollongong 2522, Australia"
                        ],
                        "is_corresponding": False,
                    },
                ],
                "abstract": "The coordinated control of a blended braking system is always a difficult task. In particular, blended braking control becomes more challenging when the braking actuator has an input time-delay and some states of the braking system cannot be measured. In order to improve the tracking performance, a coordinated control system was designed based on the input time-delay and state observation for a blended braking system comprising a motor braking system and friction braking system. The coordinated control consists of three parts: Sliding mode control, a multi-input single-output observer, and time-delay estimation-based Smith Predictor control. The sliding mode control is used to calculate the total command braking torque according to the desired braking performance and vehicle states. The multi-input single-output observer is used to simultaneously estimate the input time-delay and output braking torque of the friction braking system. With time-delay estimation-based Smith Predictor control, the friction braking system is able to effectively track the command braking torque of the friction braking system. The tracking of command braking torque is realized through the coordinated control of the motor braking system and friction braking system. In order to validate the effectiveness of the proposed approach, numerical simulations on a quarter-vehicle braking model were performed.",
            },
        }
    ]
