from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import same_person


def _singles_out(marked, n_authors):
    """A star or asterisk counts only when it picks some authors out: stars on every author of a
    multi-author page mark no one (the page never explains them; gold v1.3 counts a star that singles
    an author out)."""
    return marked if n_authors == 1 or len(marked) < n_authors else []


def ekb_corresponding_marks(soup):
    """Byline names (in byline order) and the indexes of those the page marks as corresponding.

    Sinaweb author list (`li.padding-3`): an envelope `mailto` whose tooltip reads "Email to Corresponding
    Author" marks its author; with no envelope on the page, a Font Awesome asterisk in an author's `<sup>`
    does. Older template (`a.citation_author`): the same envelope, or `<sup>*</sup>`, inside the author's link.
    (oxjob #2216; #2149 EXPLORE § 1)
    """
    names, envelopes, stars = [], [], []
    for li in soup.select("li.padding-3"):
        link = li.select_one('a[href*="_au="]')
        if link is None:
            continue
        if li.select_one('sup a[href^="mailto:"]') is not None:
            envelopes.append(len(names))
        elif li.select_one("sup i.fa-asterisk") is not None:
            stars.append(len(names))
        names.append(link.get_text(" ", strip=True))
    if not names:
        for link in soup.select("a.citation_author"):
            sup = link.find("sup")
            if link.select_one('a[href^="mailto:"]') is not None:
                envelopes.append(len(names))
            elif sup is not None and "*" in sup.get_text():
                stars.append(len(names))
            names.append(link.get_text(" ", strip=True).replace("*", "").strip())
    return names, envelopes or _singles_out(stars, len(names))


class EgyptianKnowledgeBank(PublisherParser):
    parser_name = "egyptian_knowledge_bank"

    def is_publisher_specific_parser(self):
        for meta_citation_url in self.soup.find_all(
            "meta", {"name": "citation_abstract_html_url"}
        ):
            if "journals.ekb.eg" in meta_citation_url.get("content", ""):
                return True

        return False

    def authors_found(self):
        return self.soup.find("meta", {"name": "citation_author"})

    def parse(self):
        authors = self.parse_author_meta_tags()
        self.mark_corresponding(authors)
        return {'authors': authors,
                'abstract': self.parse_abstract_meta_tags()}

    def mark_corresponding(self, authors):
        """Set is_corresponding=True on the meta authors the byline marks; others keep None.

        The byline and the citation_author tags come from the same author list, in the same order, on
        every marked page sampled (116 of 116), so a mark maps by position when the counts agree and by
        name otherwise; a mark that matches no meta author is dropped."""
        names, marked = ekb_corresponding_marks(self.soup)
        for i in marked:
            if len(names) == len(authors):
                hits = [authors[i]]
            else:
                hits = [a for a in authors if same_person(a["name"], names[i])]
            if len(hits) == 1:
                hits[0]["is_corresponding"] = True

    test_cases = [
        {
            "doi": "10.21608/ejchem.2021.93025.4397",
            "result": [
                {
                    "name": "Ahmed Ahmed",
                    "affiliations": [
                        "Department of Chemistry, College of Science, Al-Nahrain University, Baghdad, Iraq."
                    ],
                    "is_corresponding": None,
                },
                {
                    "name": "Ismaeel Y. Majeed",
                    "affiliations": [
                        "Department of Chemistry, College of Education for Pure Science Ibn-Al-Haitham, University of\r\nBaghdad, Iraq"
                    ],
                    "is_corresponding": None,
                },
                {
                    "name": "Noora Asaad",
                    "affiliations": [
                        "Department of Chemistry, College of Science, Al-Nahrain University, Baghdad, Iraq."
                    ],
                    "is_corresponding": None,
                },
                {
                    "name": "Riyadh Mahmood Ahmed",
                    "affiliations": [
                        "Department of Chemistry, College of Education for Pure Science Ibn-Al-Haitham, University of\nBaghdad, Iraq."
                    ],
                    "is_corresponding": None,
                },
                {
                    "name": "Ghada M. Kamil",
                    "affiliations": [
                        "Department Of Applied sciences, Branch of Applied Chemistry, University Of Technology, Baghdad, Iraq."
                    ],
                    "is_corresponding": None,
                },
                {
                    "name": "Sarah Abdul Rahman",
                    "affiliations": [
                        "Department of Chemistry, College of Education for Pure Science Ibn-Al-Haitham, University of\nBaghdad, Iraq."
                    ],
                    "is_corresponding": None,
                },
            ],
        },
        {
            "doi": "10.21608/jlaw.2021.190634",
            "result": [
                {
                    "name": "حسين السيد حسين محمد",
                    "affiliations": [],
                    "is_corresponding": None,
                }
            ],
        },
        {
            "doi": "10.21608/jstc.2021.191414",
            "result": [
                {
                    "name": "محمد الهادي",
                    "affiliations": [
                        "أستاذ متفرغ الحاسب الآلى ونظم المعلومات\nقسم الحاسب الآلى ونظم المعلومات\nأکاديمية السادات للعلوم الادارية"
                    ],
                    "is_corresponding": None,
                }
            ],
        },
        {
            "doi": "10.21608/mnase.2021.70758.1148",
            "result": [
                {
                    "name": "محمود حسن الحوفي",
                    "affiliations": ["کلية التربية الرياضيه جامعه مدينه السادات"],
                    "is_corresponding": None,
                },
                {
                    "name": "محمد صلاح ابوسريع",
                    "affiliations": ["کلية التربية الرياضيه جامعه مدينه السادات"],
                    "is_corresponding": None,
                },
                {
                    "name": "Mohamed Zaki",
                    "affiliations": ["مدينة السادات - المنطقة الرابعة - کشک الکاشف"],
                    "is_corresponding": None,
                },
            ],
        },
    ]
