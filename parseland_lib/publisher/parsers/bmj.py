import json
import re

from parseland_lib.elements import Author, Affiliation, AuthorAffiliations
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import name_in_text


class BMJ(PublisherParser):
    parser_name = "bmj"

    def is_publisher_specific_parser(self):
        return self.domain_in_meta_og_url("bmj.com")

    def authors_found(self):
        standard_authors = self.soup.find("ol",
                                          class_="contributor-list") or self.soup.find(
            "meta", {"name": "citation_author"}
        )
        if standard_authors:
            return standard_authors
        if not self.is_publisher_specific_parser():
            return None
        return self.get_data_layer_author_names() or self.find_legacy_inline_author_paragraph()

    def parse(self):
        result_authors = None

        authors = self.get_authors()
        if authors:
            affiliations = self.get_affiliations()
            result_authors = self.merge_authors_affiliations(authors,
                                                             affiliations)
        else:
            result_authors = self.parse_author_meta_tags()
            if not result_authors and self.is_publisher_specific_parser():
                result_authors = (
                    self.get_data_layer_authors()
                    or self.get_legacy_inline_authors()
                )

        return {"authors": result_authors,
                "abstract": self.get_abstract()}

    def get_abstract(self):
        return (
            self.parse_abstract_meta_tags()
            or self.parse_short_citation_abstract()
        )

    def parse_short_citation_abstract(self):
        meta = self.soup.find(
            "meta",
            {"name": re.compile(r"^citation_abstract$", re.I)},
        )
        if not meta:
            return None
        description = meta.get("content", "").strip()
        text_only = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", description)).strip()
        if (
            len(text_only.split()) >= 8
            and not description.endswith(("...", "…"))
            and not description.startswith("http")
        ):
            return re.sub(r"^abstract[:.]?\s*", "", description, flags=re.I)
        return None

    def get_authors(self):
        authors = []
        corr_str = self.get_correspondence_str()
        corr_split = corr_str.split(',', 1)
        corr_name = corr_split[0]
        corr_aff = None
        if len(corr_split) == 2:
            corr_aff = corr_split[1].split(';')[0]
        author_soup = self.soup.find("ol", class_="contributor-list")
        if not author_soup:
            return None

        author_soup = author_soup.findAll("li")
        for author in author_soup:
            name_soup = author.find("span", class_="name")
            if not name_soup:
                continue
            name = name_soup.text.strip()
            email_soup = author.find("span", class_="contrib-email")
            email_text = email_soup.get_text(" ", strip=True) if email_soup else ""
            aff_ids_raw = author.select('.xref-aff')
            aff_ids = []
            for aff_id_raw in aff_ids_raw:
                aff_id = self.clean_aff_id(
                    aff_id_raw.text,
                    aff_id_raw.get("href"),
                )
                if aff_id:
                    aff_ids.append(aff_id)
            is_corresponding = False
            author = Author(name=name, aff_ids=aff_ids,
                            is_corresponding=is_corresponding)
            direct_corr_name_match = name_in_text(name, corr_name)
            correspondence_match = self.name_matches_correspondence(name, corr_name)
            email_match = self.name_matches_correspondence(name, email_text)
            if correspondence_match or email_match or len(author_soup) == 1:
                is_corresponding = True
                if corr_aff and direct_corr_name_match and not aff_ids:
                    author = AuthorAffiliations(name=name,
                                                affiliations=[corr_aff],
                                                is_corresponding=is_corresponding)
                else:
                    author.is_corresponding = is_corresponding

            authors.append(author)
        if authors:
            return authors
        if self.is_publisher_specific_parser():
            return self.get_data_layer_authors() or self.get_legacy_inline_authors()
        return []

    @staticmethod
    def clean_aff_id(text, href=None):
        source = href or text or ""
        href_match = re.search(r"#?aff[-_]?([A-Za-z0-9]+)", source)
        if href_match:
            return href_match.group(1)
        text_match = re.search(r"[A-Za-z0-9]+", text or "")
        return text_match.group(0) if text_match else None

    def get_data_layer_authors(self):
        return [
            Author(name=name, aff_ids=[], is_corresponding=None)
            for name in self.get_data_layer_author_names()
        ]

    def get_data_layer_author_names(self):
        content = self.get_data_layer_content()
        if not content:
            return []

        names_raw = content.get("hwAuthors") or content.get("hwContributors") or ""
        corpus_code = str(content.get("hwCorpusCode") or "").strip().lower()
        if not names_raw:
            return []

        names = []
        for name in re.split(r"\s*,\s*", names_raw):
            name = name.strip()
            if not name or name.lower() == corpus_code:
                continue
            if not re.search(r"[A-Za-z]", name):
                continue
            names.append(name)
        return names

    def get_data_layer_content(self):
        for script in self.soup.find_all("script"):
            text = script.string or script.get_text("\n")
            if "window.dataLayer.push" not in text:
                continue
            match = re.search(r"window\.dataLayer\.push\((\{.*?\})\);", text, re.S)
            if not match:
                continue
            try:
                data = json.loads(match.group(1))
            except Exception:
                continue
            content = data.get("content")
            if isinstance(content, dict):
                return content
        return {}

    def find_legacy_inline_author_paragraph(self):
        role_words = (
            "specialist registrar",
            "consultant",
            "clinical research fellow",
            "professor",
        )
        for para in self.soup.select(".article.extract-view p, article p"):
            text = re.sub(r"\s+", " ", para.get_text(" ", strip=True)).strip()
            lower = text.lower()
            if "department " not in lower:
                continue
            if not any(role in lower for role in role_words):
                continue
            if self.extract_legacy_inline_author_names(text):
                return para
        return None

    def get_legacy_inline_authors(self):
        para = self.find_legacy_inline_author_paragraph()
        if not para:
            return []
        text = re.sub(r"\s+", " ", para.get_text(" ", strip=True)).strip()
        aff_match = re.search(r",\s*(department\b.+)$", text, re.I)
        if not aff_match:
            return []
        affiliation = aff_match.group(1).strip()
        return [
            AuthorAffiliations(
                name=name,
                affiliations=[affiliation],
                is_corresponding=False,
            )
            for name in self.extract_legacy_inline_author_names(text)
        ]

    @staticmethod
    def extract_legacy_inline_author_names(text):
        role_pattern = (
            r"specialist registrar|consultant|clinical research fellow|professor"
        )
        names = []
        for match in re.finditer(
            rf"(?:^|,\s*)([A-Z][A-Za-z.'’ -]*(?:\s+[A-Z][A-Za-z.'’ -]*)+),\s*(?:{role_pattern})",
            text,
            re.I,
        ):
            name = re.sub(r"\s+", " ", match.group(1)).strip(" ,")
            if name:
                names.append(name)
        return names

    @staticmethod
    def name_matches_correspondence(name, text):
        if not text:
            return False
        if name_in_text(name, text):
            return True

        name_parts = [
            part.lower()
            for part in re.findall(r"[A-Za-z]+", name)
            if part.strip()
        ]
        if len(name_parts) < 2:
            return False

        normalized_text = re.sub(r"[^a-z0-9]+", " ", text.lower())
        compact_text = re.sub(r"[^a-z0-9]+", "", text.lower())
        first = name_parts[0]
        last = name_parts[-1]
        if first in normalized_text.split() and last in normalized_text.split():
            return True

        if f"{first}{last}" in compact_text:
            return True

        initials = "".join(part[0] for part in name_parts[:-1])
        return bool(initials and f"{initials}{last}" in compact_text)

    def get_affiliations(self):
        aff_soup = self.soup.find("ol", class_="affiliation-list")

        results = []
        if aff_soup:
            affiliations = aff_soup.findAll("li", class_="aff")
            for aff_raw in affiliations:
                # affiliation id
                aff_id_raw = aff_raw.find("sup")
                if aff_id_raw:
                    aff_id = self.clean_aff_id(aff_id_raw.text)
                    aff_id_raw.clear()
                else:
                    aff_id = None

                # affiliation
                aff = aff_raw.text.strip()
                if len(affiliations) == 1:
                    aff_id = None
                results.append(Affiliation(organization=aff, aff_id=aff_id))
        return results

    def get_correspondence_str(self):
        if corr_soup := self.soup.find("li", class_="corresp"):
            if corr_label := corr_soup.select_one('.corresp-label'):
                corr_label.decompose()
            return corr_soup.text.strip() if corr_soup else None
        return ''

    test_cases = [
        {
            "doi": "10.1136/bcr-2020-239618",
            "result": {
                "authors": [
                    {
                        "name": "Brian Alexander Hummel",
                        "affiliations": [
                            "Division of Infectious Diseases, Immunology and Allergy, Department of Pediatrics, University of Ottawa Faculty of Medicine, Ottawa, Ontario, Canada",
                        ],
                        "is_corresponding": True,
                    },
                    {
                        "name": "Julie Blackburn",
                        "affiliations": [
                            "Département de Microbiologie et Immunologie, University of Montreal Faculty of Medicine, Montreal, Quebec, Canada"
                        ],
                        "is_corresponding": False,
                    },
                    {
                        "name": "Anne Pham-Huy",
                        "affiliations": [
                            "Division of Infectious Diseases, Immunology and Allergy, Department of Pediatrics, University of Ottawa Faculty of Medicine, Ottawa, Ontario, Canada",
                        ],
                        "is_corresponding": False,
                    },
                    {
                        "name": "Katherine Muir",
                        "affiliations": [
                            "Division of Neurology, Department of Pediatrics, University of Ottawa Faculty of Medicine, Ottawa, Ontario, Canada"
                        ],
                        "is_corresponding": False,
                    },
                ],
                "abstract": "<p>Cerebral vasculitis is a serious complication of bacterial meningitis that can cause significant morbidity and mortality due to stroke. Currently, there are no treatment guidelines or safety and efficacy studies on the management of cerebral vasculitis in this context. Herein, we report a case of a previously well 11-year-old girl who presented with acute otitis media that progressed to mastoiditis and fulminant meningitis. Group A <i>Streptococcus</i> was found in blood and ear-fluid cultures (lumbar puncture was unsuccessful). Her decreased level of consciousness persisted despite appropriate antimicrobial treatment, and repeat MRI revealed extensive large vessel cerebral vasculitis. Based on expert opinion and a presumed inflammatory mechanism, her cerebral vasculitis was treated with 7\u2009days of pulse intravenous methylprednisolone followed by oral prednisone taper. She was also treated with intravenous heparin. Following these therapies, she improved clinically and radiographically with no adverse events. She continues to undergo rehabilitation with improvement.</p>",
            },
        },
        {
            "doi": "10.1136/bmjopen-2020-043554",
            "result": {
                "authors": [
                    {
                        "name": "Kelly Teo",
                        "affiliations": [
                            "Department of Gerontology, Simon Fraser University, Vancouver, British Columbia, Canada",
                        ],
                        "is_corresponding": True,
                    },
                    {
                        "name": "Ryan Churchill",
                        "affiliations": [
                            "Department of Gerontology, Simon Fraser University, Vancouver, British Columbia, Canada"
                        ],
                        "is_corresponding": False,
                    },
                    {
                        "name": "Indira Riadi",
                        "affiliations": [
                            "Department of Gerontology, Simon Fraser University, Vancouver, British Columbia, Canada",
                        ],
                        "is_corresponding": False,
                    },
                    {
                        "name": "Lucy Kervin",
                        "affiliations": [
                            "Department of Gerontology, Simon Fraser University, Vancouver, British Columbia, Canada"
                        ],
                        "is_corresponding": False,
                    },
                    {
                        "name": "Theodore Cosco",
                        "affiliations": [
                            "Department of Gerontology, Simon Fraser University, Vancouver, British Columbia, Canada",
                            "Oxford Institute of Population Ageing, University of Oxford, Oxford, Oxfordshire, UK",
                        ],
                        "is_corresponding": False,
                    },
                ],
                "abstract": "<h3>Introduction</h3>\n<p>Despite evidence that illustrates the unmet healthcare needs of older adults, there is limited research examining their help-seeking behaviour, of which direct intervention can improve patient outcomes. Research in this area conducted with a focus on ethnic minority older adults is also needed, as their help-seeking behaviours may be influenced by various cultural factors. This scoping review aims to explore the global literature on the factors associated with help-seeking behaviours of older adults and how cultural values and backgrounds may impact ethnic minority older adults\u2019 help-seeking behaviours in different ways.</p><h3>Methods and analysis</h3>\n<p>The scoping review process will be guided by the methodology framework of Arksey and O\u2019Malley and the Preferred Reporting Items for Systematic Reviews and Meta-analysis Protocols Extension for Scoping Reviews guidelines. The following electronic databases will be systematically searched from January 2005 onwards: MEDLINE/PubMed, Web of Science, PsycINFO, CINAHL and Scopus. Studies of various designs and methodologies consisting of older adults aged 65 years or older, who are exhibiting help-seeking behaviours for the purpose of remedying a physical or mental health challenge, will be considered for inclusion. Two reviewers will screen full texts and chart data. The results of this scoping review will be summarised quantitatively through numerical counts and qualitatively through a narrative synthesis.</p><h3>Ethics and dissemination</h3>\n<p>As this is a scoping review of published literature, ethics approval is not required. Results will be disseminated through publication in a peer-reviewed journal.</p><h3>Discussion</h3>\n<p>This scoping review will synthesise the current literature related to the help-seeking behaviours of older adults and ethnic minority older adults. It will identify current gaps in research and potential ways to move forward in developing or implementing strategies that support the various health needs of the diverse older adult population.</p><h3>Registration</h3>\n<p>This scoping review protocol has been registered with the Open Science Framework (https://osf.io/69kmx).</p>",
            },
        },
        {
            "doi": "10.1136/bcr-2021-243370",
            "result": {
                "authors": [
                    {
                        "name": "John Leso",
                        "affiliations": [
                            "Internal Medicine, Albany Medical College, Albany, New York, USA",
                        ],
                        "is_corresponding": True,
                    },
                    {
                        "name": "Majd Al-Ahmad",
                        "affiliations": [
                            "Internal Medicine, Albany Medical College, Albany, New York, USA"
                        ],
                        "is_corresponding": False,
                    },
                    {
                        "name": "Drinnon O Hand",
                        "affiliations": [
                            "Internal Medicine, Albany Medical College, Albany, New York, USA",
                        ],
                        "is_corresponding": False,
                    },
                ],
                "abstract": "<p>A 34-year-old man with a medical history of injection drug use presented with 2 weeks of weakness, nausea, vomiting and septic shock secondary to infective endocarditis of a native tricuspid valve. On admission, CT chest demonstrated multiple cavitary lesions as well as numerous small infarcts seen on MRI brain concerning for systemic septic emboli. Subsequent transthoracic echo with bubble study revealed a large patent foramen ovale (PFO). The patient later received surgical debulking of his tricuspid valve vegetation with AngioVac. Subsequently, PFO closure was performed with a NobleStitch device. The case presented here demonstrates the importance of having a high index of suspicion with right-sided endocarditis and the development of other systemic signs and symptoms. It also underscores the necessity of a multidisciplinary team of cardiologists, surgeons, infectious disease specialists and intensivists in the treatment of these complicated patients.</p>",
            },
        },
    ]
