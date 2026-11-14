import re

from bs4 import BeautifulSoup

from parseland_lib.elements import Author, Affiliation
from parseland_lib.publisher.parsers.parser import PublisherParser

_STATEMENT_LABEL = re.compile(r"^\s*correspondence\s*:?\s*", re.I)
_EMAIL_IN_PARENS = re.compile(r"\(\s*[^()\s]+@[^()\s]+\s*\)")


def is_copernicus_page(soup):
    """A copernicus.org journal page: its <link rel="preconnect"> points at copernicus.org (the parser's claim)."""
    return any("copernicus.org" in (link.get("href") or "")
               for link in soup.find_all("link", rel="preconnect"))


def _statement_names(text):
    """Names in a correspondence statement: "Correspondence: Liji M. David (liji.david@usu.edu), Mary Barth
    (barthm@ucar.edu), and A. R. Ravishankara (...)". Each name is the text before an e-mail in parentheses."""
    text = _STATEMENT_LABEL.sub("", re.sub(r"\s+", " ", text or ""))
    parts = _EMAIL_IN_PARENS.split(text)[:-1] if _EMAIL_IN_PARENS.search(text) else re.split(r",|\band\b", text)
    names = []
    for part in parts:
        name = re.sub(r"^[\s,;]*(and\s+)?", "", part).strip(" ,;.")
        if name and "@" not in name and len(name.split()) <= 8:
            names.append(name)
    return names


def copernicus_corresponding_names(soup):
    """Names of the authors a Copernicus (copernicus.org) journal page marks as corresponding (oxjob #2218).

    The current template opens a pop-up per byline author (``div.authors-with-affiliations`` -> ``div.modal``); the
    corresponding author's pop-up header reads "CORRESPONDING AUTHOR" above the e-mail. The older template (byline in
    ``span.authors-full``) states it under the affiliations: ``p.correspondence-statement`` "Correspondence: Name
    (e-mail), ...". An ORCID logo is not a mark: the parser used to mark every ORCID holder corresponding.
    """
    if not is_copernicus_page(soup):
        return []
    names = []

    def add(name):
        name = re.sub(r"\s+", " ", name or "").strip(" ,;*")
        if name and name not in names:
            names.append(name)

    box = soup.find("div", class_="authors-with-affiliations")
    if box is not None:
        for span in box.select("span[data-target]"):
            # the byline links each pop-up by id ("#author831047") or, on newer pages, by class (".author916884")
            target = span.get("data-target") or ""
            modal = soup.find(id=target[1:]) if target.startswith("#") else \
                soup.find("div", class_=target[1:]) if target.startswith(".") and len(target) > 1 else None
            header = modal.find(class_="modal-header") if modal is not None else None
            if header is None:
                continue
            if not any(div.get_text(" ", strip=True).upper() == "CORRESPONDING AUTHOR"
                       for div in header.find_all("div")):
                continue
            title = header.find(class_="modal-title")
            add(title.get_text(" ", strip=True) if title else None)
    if not names:
        for statement in soup.select("p.correspondence-statement"):
            for name in _statement_names(statement.get_text(" ", strip=True)):
                add(name)
    return names


class Copernicus(PublisherParser):
    parser_name = "copernicus"
    chars_to_ignore = ["*", "†", "‡", "§"]

    def is_publisher_specific_parser(self):
        link = self.soup.find("link", {"rel": "preconnect"})
        if link and "copernicus.org" in link.get("href"):
            return True

    def authors_found(self):
        return self.soup.find("span", class_="authors-full")

    def parse(self):
        authors = self.get_authors()
        affiliations = self.get_affiliations()
        authors_affiliations = self.merge_authors_affiliations(authors,
                                                               affiliations)

        abstract = self.parse_abstract_meta_tags()
        try:
            abstract = BeautifulSoup(abstract, "lxml").text
            abstract = re.sub(r"^abstract[:.]?\s*", "", abstract, flags=re.I)
        except Exception:
            pass

        return {"authors": authors_affiliations, "abstract": abstract}

    def get_authors(self):
        authors = []
        author_soup = self.soup.find("span", class_="authors-full")
        author_soup = author_soup.findAll("nobr")
        for author in author_soup:
            if author.sup:
                aff_ids = self.format_ids(author.sup.text, self.chars_to_ignore)
                author.sup.clear()
            else:
                aff_ids = []
            name = author.text
            # clean name
            if name.endswith(","):
                name = name[:-1].strip()
            if name.startswith("and"):
                name = name[3:].strip()
            # an ORCID logo is not a corresponding mark (#2218): parse_page applies the page's own marks
            # (copernicus_corresponding_names) to whichever parser wins the page
            authors.append(Author(name=name, aff_ids=aff_ids))
        return authors

    def get_affiliations(self):
        aff_soup = self.soup.find("ul", class_="affiliation-list")

        results = []
        if aff_soup:
            affiliations = aff_soup.findAll("li")
            for aff_raw in affiliations:
                # affiliation id
                aff_id_raw = aff_raw.find("sup")
                if aff_id_raw:
                    aff_id = aff_id_raw.text
                    aff_id_raw.clear()
                else:
                    aff_id = None

                # affiliation
                aff = aff_raw.text
                if aff_id and aff_id.isdigit():
                    aff_id = int(aff_id)
                results.append(Affiliation(organization=aff, aff_id=aff_id))
        return results

    test_cases = [
        {
            "doi": "10.5194/hess-2021-324-rc2",
            "result": {
                "authors": [
                    {
                        "name": "Jared D. Smith",
                        "affiliations": [
                            "Department of Engineering Systems and Environment, University of Virginia, Charlottesville, VA, USA",
                        ],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Laurence Lin",
                        "affiliations": [
                            "Department of Environmental Sciences, University of Virginia, Charlottesville, VA, USA"
                        ],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Julianne D. Quinn",
                        "affiliations": [
                            "Department of Engineering Systems and Environment, University of Virginia, Charlottesville, VA, USA",
                        ],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Lawrence E. Band",
                        "affiliations": [
                            "Department of Engineering Systems and Environment, University of Virginia, Charlottesville, VA, USA",
                            "Department of Environmental Sciences, University of Virginia, Charlottesville, VA, USA",
                        ],
                        "is_corresponding": None,
                    },
                ],
                "abstract": "Spatially distributed hydrologic models are commonly employed to optimize the locations of engineering control measures across a watershed. Yet, parameter screening exercises that aim to reduce the dimensionality of the calibration search space are typically completed only for gauged locations, like the watershed outlet, and use screening metrics that are relevant to calibration instead of explicitly describing decision objectives. Identifying parameters that control physical processes in ungauged locations that affect decision objectives should lead to a better understanding of control measure effectiveness. This paper provides guidance on evaluating model parameter uncertainty at the spatial scales and flow magnitudes of interest for such decision-making problems. We use global sensitivity analysis to screen parameters for model calibration, and to subsequently evaluate the appropriateness of using parameter multipliers to further reduce dimensionality. We evaluate six sensitivity metrics that align with four decision objectives; two metrics consider model residual error that would be considered in spatial optimizations of engineering designs. We compare the resulting parameter selection for the basin outlet and each hillslope. We also compare basin outlet results to those obtained by four calibration-relevant metrics. These methods were applied to a RHESSys ecohydrological model of an exurban forested watershed near Baltimore, MD, USA. Results show that 1) the set of parameters selected by calibration-relevant metrics does not include parameters that control decision-relevant high and low streamflows, 2) evaluating sensitivity metrics at only the basin outlet does not capture many parameters that control streamflows in hillslopes, and 3) for some parameter multipliers, calibration of just one of the parameters being adjusted may be the preferred approach for reducing dimensionality. Thus, we recommend that parameter screening exercises use decision-relevant metrics that are evaluated at the spatial scales appropriate to decision making. While including more parameters in calibration will exacerbate equifinality, the resulting parametric uncertainty should be important to consider in discovering control measures that are robust to it.",
            },
        },
        {
            "doi": "10.5194/egusphere-egu21-5804",
            "result": {
                "authors": [
                    {
                        "name": "Shahbaz Chaudhry",
                        "affiliations": [
                            "University of Warwick, Physics, United Kingdom of Great Britain – England, Scotland, Wales (shahbaz.chaudhry@warwick.ac.uk)",
                        ],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Sandra Chapman",
                        "affiliations": [
                            "University of Warwick, Physics, United Kingdom of Great Britain – England, Scotland, Wales (shahbaz.chaudhry@warwick.ac.uk)"
                        ],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Jesper Gjerloev",
                        "affiliations": [
                            "University of Warwick, Physics, United Kingdom of Great Britain – England, Scotland, Wales (shahbaz.chaudhry@warwick.ac.uk)",
                        ],
                        "is_corresponding": None,
                    },
                ],
                "abstract": None,
            },
        },
        {
            "doi": "10.5194/gmd-2021-281",
            "result": {
                "authors": [
                    {
                        "name": "Christopher Horvat",
                        "affiliations": [
                            "Institute at Brown for Environment and Society, Brown University, Providence, RI, USA"
                        ],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Lettie A. Roach",
                        "affiliations": [
                            "Department of Atmospheric Sciences, University of Washington, Seattle, WA, USA"
                        ],
                        "is_corresponding": None,
                    },
                ],
                "abstract": "Ocean surface waves play an important role in maintaining the marginal ice zone, a heterogenous region occupied by sea ice floes with variable horizontal sizes. The location, width, and evolution of the marginal ice zone is determined by the mutual interaction of ocean waves and floes, as waves propagate into the ice, bend it, and fracture it. In previous work, we developed a one-dimensional “superparameterized” scheme to simulate the interaction between the stochastic ocean surface wave field and sea ice. As this method is computationally expensive and not bitwise reproducible, here we use a pair of neural networks to accelerate this parameterization, delivering an adaptable, computationally-inexpensive, reproducible approach for simulating stochastic wave-ice interactions. Implemented in the sea ice model CICE, this accelerated code reproduces global statistics resulting from the full wave fracture code without increasing computational overheads. The combined model, Wave-Induced Floe Fracture (WIFF v1.0) is publicly available and may be incorporated into climate models that seek to represent the effect of waves fracturing sea ice.",
            },
        },
    ]
