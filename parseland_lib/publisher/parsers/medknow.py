import re

from bs4 import BeautifulSoup, NavigableString, Tag

from parseland_lib.elements import Author, Affiliation
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

# Back-matter labels Medknow prints in bold (oxjob #2289): "<b><i>Acknowledgements</i></b>", "<b>Financial support and
# sponsorship</b>", and the header's "<b>Source of Support:</b> None, <b>Conflict of Interest:</b> None".
_ACK_LABEL = re.compile(r"^acknowledge?ments?\s*:?$", re.I)
_FUNDING_LABEL = re.compile(r"^(?:financial support(?: and sponsorship)?|sources? of (?:funding|support)|"
                            r"funding(?: information| sources?| statement)?)\s*:?$", re.I)
_BLOCKS = {"table", "div", "p", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "section"}
_BOLD = ("b", "strong")


def _label_key(text):
    text = squash(text)
    return "acknowledgments" if _ACK_LABEL.match(text) else (
        "funding_statement" if _FUNDING_LABEL.match(text) else None)


def _next_nonblank(node):
    """The next sibling that is a tag or holds text other than whitespace and &nbsp;."""
    node = node.next_sibling
    while node is not None and isinstance(node, NavigableString) and not squash(str(node)):
        node = node.next_sibling
    return node


def _heads_paragraph(bold):
    """A bold label on a line of its own ("<b>Acknowledgment</b><br>"), not one run into its text."""
    nxt = _next_nonblank(bold)
    return isinstance(nxt, Tag) and nxt.name == "br"


def _text_after(start):
    """The text after a label (or a section bar), one line per <br>-separated paragraph, up to the next block (the
    References bar) or the next bold label on a line of its own ("<b>Conflicts of interest</b><br>")."""
    lines, line = [], []
    for node in start.next_siblings:
        if isinstance(node, Tag):
            if node.name in _BLOCKS:
                break
            if node.name == "br":
                lines.append(squash("".join(line)))
                line = []
                continue
            if node.name in _BOLD and not squash("".join(line)) and _heads_paragraph(node):
                break
            line.append(node.get_text())
        elif isinstance(node, NavigableString):
            line.append(str(node))
    lines.append(squash("".join(line)))
    return "\n".join(text for text in lines if text) or None


def _run_in_text(bold):
    """The text a run-in label leads ("<b>Source of Support:</b> None, <b>Conflict of Interest:</b> ..."), up to the
    next bold label or line break, without the comma before it."""
    parts = []
    for node in bold.next_siblings:
        if isinstance(node, Tag) and (node.name in _BOLD or node.name == "br" or node.name in _BLOCKS):
            break
        parts.append(node.get_text() if isinstance(node, Tag) else str(node))
    return squash("".join(parts)).rstrip(",;").strip() or None


class MedKnow(PublisherParser):
    parser_name = "medknow"

    def _medknow_head(self):
        """Medknow's Dublin Core schema link (<link rel="SCHEMA.dc">) in the page's <head> (oxjob #2289).

        Every parser's authors_found() runs on every DOI page (#2239's per-page CPU rule), so this looks only at the
        small <head>, found without searching the document, before anything walks the whole tree. Every stored page
        the old checks read carries it (56 of 56 in #2289's sample and pool) and no other template's page does (0 of
        2,250, Yektaweb's DC.* meta tags included). Worked out once: authors_found() and the dispatcher both ask."""
        if not hasattr(self, "_head_mark"):
            html = self.soup.find("html", recursive=False)
            head = html.find("head", recursive=False) if html is not None else None
            self._head_mark = head is not None and head.find("link", rel="SCHEMA.dc") is not None
        return self._head_mark

    def is_publisher_specific_parser(self):
        script_url = "https://www.medknow.com/ss/ftr.js"
        return self._medknow_head() and script_url in str(self.soup)

    def authors_found(self):
        return self._medknow_head() and self.soup.find("font", class_="articleAuthor")

    def parse(self):
        authors = self.get_authors()
        if authors:
            affiliations = self.get_affiliations()
            authors_affiliations = self.merge_authors_affiliations(
                authors, affiliations
            )
        else:
            # try meta tags
            authors_affiliations = self.parse_author_meta_tags(
                corresponding_tag="font", corresponding_class="CorrsAdd"
            )

        abstract = self.parse_abstract_meta_tags()
        try:
            abstract = BeautifulSoup(abstract, "lxml").text
            abstract = re.sub(r"^abstract[:.]?\s*", "", abstract, flags=re.I)
        except Exception:
            pass

        return {"authors": authors_affiliations, "abstract": abstract, **self.back_matter()}

    def back_matter(self):
        """Acknowledgments and funding statement (#2215's contract), verbatim without their labels (oxjob #2289).

        The article body heads each with a bold label on a line of its own; older pages give "Acknowledgment" its own
        section bar (td.pageSub, like References). The header's run-in "Source of Support: ..." is the funding
        statement only on pages whose body prints no funding section. "Nil." is a statement (label-v2 gold keeps it).
        The reference list is left to the other readers (its works were under #2289's floor)."""
        found, run_in = {}, {}
        for bold in self.soup.find_all(_BOLD):
            key = _label_key(bold.get_text())
            if key is None:
                continue
            if _heads_paragraph(bold):
                if key not in found and (text := _text_after(bold)):
                    found[key] = text
            elif key not in run_in and (text := _run_in_text(bold)):
                run_in[key] = text
        if "acknowledgments" not in found:
            for anchor in self.soup.select("td.pageSub a[name]"):
                bar = anchor.find_parent("table")
                if _ACK_LABEL.match(anchor["name"]) and bar is not None and (text := _text_after(bar)):
                    found["acknowledgments"] = text
                    break
        return {"acknowledgments": found.get("acknowledgments") or run_in.get("acknowledgments"),
                "funding_statement": found.get("funding_statement") or run_in.get("funding_statement")}

    def get_authors(self):
        results = []
        author_soup = self.soup.find("font", class_="articleAuthor")
        if not author_soup:
            return None

        authors = author_soup.findAll("a")
        affiliations = author_soup.findAll("sup")
        corresponding_text = self.get_corresponding_text("font", "CorrsAdd")
        is_corresponding = None

        # method 1
        if not authors and not affiliations:
            authors = author_soup.text.split(",")
            if authors:
                for author in authors:
                    name = author.strip()
                    if corresponding_text and name.lower() in corresponding_text:
                        is_corresponding = True
                    elif corresponding_text and name.lower() not in corresponding_text:
                        is_corresponding = False
                    results.append(
                        Author(
                            name=name,
                            aff_ids=[],
                            is_corresponding=is_corresponding,
                        )
                    )
            return results

        # method 2
        for author, affiliation in zip(authors, affiliations):
            name = author.text.strip()
            if corresponding_text and name.lower() in corresponding_text:
                is_corresponding = True
            elif corresponding_text and name.lower() not in corresponding_text:
                is_corresponding = False
            aff_ids = self.format_ids(affiliation.text.strip())
            results.append(
                Author(name=name, aff_ids=aff_ids, is_corresponding=is_corresponding)
            )
        return results

    def get_affiliations(self):
        aff_soup = self.soup.find("font", class_="AuthorAff")

        results = []
        if aff_soup:
            affiliations = aff_soup.findAll("sup")
            # method 1
            if not affiliations:
                organization = aff_soup.text.strip()
                results.append(Affiliation(organization=organization, aff_id=None))

            # method 2
            for aff in affiliations:
                # affiliation id
                aff_id = aff.text
                if aff_id.isdigit():
                    aff_id = int(aff_id)

                # affiliation
                organization = aff.next_sibling.text.strip()
                results.append(Affiliation(organization=organization, aff_id=aff_id))
        return results

    def get_corresponding_text(self, html_tag, class_name):
        text = None
        corresponding_soup = self.soup.find(html_tag, class_=class_name)
        if corresponding_soup:
            text = corresponding_soup.text
            text = re.sub(' +', ' ', text).lower()
        return text

    test_cases = [
        {
            "doi": "10.4103/djo.djo_93_20",
            "result": {
                "authors": [
                    {
                        "name": "Saleh A Naguib",
                        "affiliations": [
                            "Ophthalmology Department, Imbaba Ophthalmology Hospital, Cairo, Egypt"
                        ],
                        "is_corresponding": False,
                    },
                    {
                        "name": "Omar A Barada",
                        "affiliations": [
                            "Ophthalmology Department, Faculty of Medicine, Cairo University, Cairo, Egypt"
                        ],
                        "is_corresponding": False,
                    },
                    {
                        "name": "Esraa El-Mayah",
                        "affiliations": [
                            "Ophthalmology Department, Faculty of Medicine, Cairo University, Cairo, Egypt"
                        ],
                        "is_corresponding": False,
                    },
                    {
                        "name": "Hany E Elmekawey",
                        "affiliations": [
                            "Ophthalmology Department, Faculty of Medicine, Cairo University, Cairo, Egypt"
                        ],
                        "is_corresponding": True,
                    },
                ],
                "abstract": "Purpose The purpose of this study was to detect single or multiple best-performing parameters of corneal tomography and dynamic corneal biomechanics with high sensitivity and specificity in the diagnosis of keratoconus, subclinical keratoconus (SCKC), and forme fruste keratoconus (FFKC).Design This was a prospective observational study.Patients and methods In this study, one eye of each of 40 participants was included. They were divided into four groups: keratoconus, SCKC, FFKC, and a normal control group, with 10 participants in each group. All participants underwent a full ophthalmologic examination, analysis of corneal tomography using Pentacam HR and analysis of corneal biomechanical response using the Corvis ST at the initial visit and after 3 months.Results For the diagnosis of keratoconus, the 100% sensitive and specific parameters were Belin/Ambrósio Enhanced Ectasia Display (BAD d), Ambrósio’s relational thickness maximum (ARTmax), and tomographic biomechanical index (TBI) with cutoff values of 1.905, 344, and 0.785, respectively. For detection of SCKC, the 100% sensitive parameters were maximum keratometry and thickness profile index with cutoff values of 44.7 and 0.945, respectively. After 3 months of follow-up, maximum keratometry, index of surface variance, deflection amplitude, and deflection area showed 100% sensitivity with specificities of 90, 80, 70, and 60%, respectively. The highest percentage of change over time was for the index of highest decentration by 200%, followed by TBI by 133%. For FFKC, the deformation amplitude and corneal velocity 1 showed sensitivity of 90 and 80%, respectively, and specificity of 83 and 90%, respectively. After follow-up BAD d, deformation amplitude, deformation amplitude ratio, and TBI showed 100% sensitivity and specificity.Conclusion This study illustrated the efficacy of Corvis parameters for the diagnosis of keratoconus, but with lower discriminative ability than corneal tomography. It could also be used as a supplementary tool for the diagnosis and follow-up of SCKC and FFKC patients.",
            },
        },
    ]
