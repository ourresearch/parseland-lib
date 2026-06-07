import re

from bs4 import BeautifulSoup

from parseland_lib.publisher.parsers.parser import PublisherParser


class GenericPublisherParser(PublisherParser):
    parser_name = "generic_publisher_parser"

    def __init__(self, soup):
        super().__init__(soup)
        self._parse_result = None

    def is_publisher_specific_parser(self):
        return False

    def authors_found(self):
        parsed = self.parse()
        return parsed.get('authors') or parsed.get('abstract')

    def parse(self):
        if not self._parse_result:
            authors = self.parse_author_meta_tags()
            authors = self.mark_preprints_starred_corresponding(authors)
            self._parse_result = {
                "authors": authors,
                "abstract": (
                    self.parse_abstract_meta_tags()
                    or self.parse_structured_abstract_section()
                ),
            }

        return self._parse_result

    @staticmethod
    def _person_key(name):
        return re.sub(r"[^a-z0-9]+", "", (name or "").lower())

    def mark_preprints_starred_corresponding(self, authors):
        """Use Preprints.org's visible byline star when citation metadata omits CA.

        Preprints.org exposes authors in citation meta tags but keeps the
        corresponding marker only in ``div.manuscript-authors`` as a ``*`` sup.
        Keep this domain-specific so generic citation metadata pages elsewhere
        do not inherit star semantics from unrelated footnote markers.
        """
        if not authors or not self.domain_in_meta_og_url("preprints.org"):
            return authors
        byline = self.soup.select_one("div.manuscript-authors")
        if not byline:
            return authors

        starred_keys = set()
        for sup in byline.find_all("sup"):
            if "*" not in sup.get_text(" ", strip=True):
                continue
            name_text = ""
            for sibling in sup.previous_siblings:
                if hasattr(sibling, "get_text"):
                    text = sibling.get_text(" ", strip=True)
                else:
                    text = str(sibling).strip()
                if text:
                    name_text = re.split(r",|;", text)[-1].strip()
                    break
            key = self._person_key(name_text)
            if key:
                starred_keys.add(key)

        if not starred_keys:
            return authors
        for author in authors:
            key = self._person_key(author.get("name"))
            if key in starred_keys:
                author["is_corresponding"] = True
            elif author.get("is_corresponding") is None:
                author["is_corresponding"] = False
        return authors

    def parse_structured_abstract_section(self):
        """Recover generic Atypon/TechRxiv-style visible abstract sections.

        Some generic pages expose only truncated dc.Description metadata but
        have a full semantic abstract in ``section#abstract``. Keep this narrow
        to avoid treating article navigation as an abstract.
        """
        section = (
            self.soup.select_one('section#abstract[role="doc-abstract"]')
            or self.soup.select_one('section#abstract[property="abstract"]')
            or self.soup.select_one('section[property="abstract"][typeof="Text"]')
        )
        if not section:
            return None

        section_soup = BeautifulSoup(str(section), "lxml")
        for heading in section_soup.find_all(re.compile(r"^h[1-6]$")):
            if heading.get_text(" ", strip=True).lower() == "abstract":
                heading.decompose()

        text = re.sub(r"\s+", " ", section_soup.get_text(" ", strip=True)).strip()
        if len(text) <= 200:
            return None
        return text

    test_cases = [
        {
            "doi": "10.1158/1538-7445.sabcs18-4608",
            "result": {
                "authors": [
                    {
                        "name": "Shanshan Deng",
                        "affiliations": [
                            "University of Tennessee Health Science Center, Memphis, TN."
                        ],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Hao Chen",
                        "affiliations": [
                            "University of Tennessee Health Science Center, Memphis, TN."
                        ],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Raisa Krutilina",
                        "affiliations": [
                            "University of Tennessee Health Science Center, Memphis, TN."
                        ],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Najah G. Albadari",
                        "affiliations": [
                            "University of Tennessee Health Science Center, Memphis, TN."
                        ],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Tiffany N. Seagroves",
                        "affiliations": [
                            "University of Tennessee Health Science Center, Memphis, TN."
                        ],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Duane D. Miller",
                        "affiliations": [
                            "University of Tennessee Health Science Center, Memphis, TN."
                        ],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Wei Li",
                        "affiliations": [
                            "University of Tennessee Health Science Center, Memphis, TN."
                        ],
                        "is_corresponding": None,
                    },
                ],
                "abstract": "<p>Triple-negative breast cancer (TNBC) cases account for about 15% of all breast cancers in the United States and have poorer overall prognosis relative to other molecular subtypes, partially due to the rapid development of drug resistance to chemotherapies and the increased risk of visceral metastasis. One of the standard treatment regimens for TNBC is the use of a taxane-based chemotherapy, such as paclitaxel, which stabilizes microtubules. However, drug resistance and neurotoxicities often limit the clinical efficacy of taxanes. Therefore, there are continuous needs to develop more effective therapies that could overcome resistance to taxanes. In this study, a novel series of structurally related pyridine analogs based on our previously reported lead compound ABI-274, was designed and synthesized to identify a molecule with improved antiproliferative potency. Most of these pyridine compounds exhibited potent cytotoxicity when tested in a panel of melanoma and breast cancer cell lines, with IC<sub>50</sub> values in the low nanomolar range. Among them, CH-II-77 is the most potent compound with an IC<sub>50</sub> value of 1\u22123 nM against these cancer cell lines, including paclitaxel-resistant sublines. The high-resolution X-ray crystal structure of CH-II-77 in complex with tubulin protein confirmed its direct binding to the colchicine-binding site. It strongly induced apoptosis and produced G2/M phase cell cycle arrest in TNBC cells in a dose-dependent manner <i>in vitro</i>. <i>In vivo</i>, CH-II-77 inhibited tumor growth in A375 melanoma xenografts and MDA-MB-231 TNBC xenografts in a dose-dependent manner. CH-II-77 was able to induce tumor necrosis and apoptosis <i>in vivo</i>. Collectively, these studies strongly suggest that CH-II-77 is a potent inhibitor of the growth of TNBC <i>in vitro</i> and <i>in vivo</i>. Thus, CH-II-77 and optimization of this analog are promising new generation of tubulin inhibitors for the treatment of TNBC and other types of cancers where tubulin inhibitors are currently being used clinically.</p><p><b>Citation Format:</b> Shanshan Deng, Hao Chen, Raisa Krutilina, Najah G. Albadari, Tiffany N. Seagroves, Duane D. Miller, Wei Li. Colchicine binding site agents as potent tubulin inhibitors suppressing triple negative breast cancer [abstract]. In: Proceedings of the American Association for Cancer Research Annual Meeting 2019; 2019 Mar 29-Apr 3; Atlanta, GA. Philadelphia (PA): AACR; Cancer Res 2019;79(13 Suppl):Abstract nr 4608.</p>",
            },
        },
    ]
