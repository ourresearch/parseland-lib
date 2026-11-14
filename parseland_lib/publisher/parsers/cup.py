import copy
import re
from urllib.parse import unquote

from parseland_lib.elements import AuthorAffiliations
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import same_opening_text, squash, states_what_the_work_does


class CUP(PublisherParser):
    parser_name = "cambridge university press"
    prefer_publisher_authors_over_generic = True
    _NON_AUTHOR_ROLE_PREFIXES = (
        "appendix by",
        "general editor",
        "introduction by",
        "preface by",
        "translated by",
    )

    def is_publisher_specific_parser(self):
        # cached: parse() asks again for the new fields and the caller asks after parse(); on a long page without
        # og:url each ask walks the whole tree (oxjob #2222)
        if getattr(self, "_claimed", None) is None:
            self._claimed = bool(
                self.domain_in_meta_og_url("cambridge.org")
                or self.domain_in_canonical_link("cambridge.org")
            )
        return self._claimed

    def authors_found(self):
        if self.soup.find("div", class_="author"):
            return True
        if not self.is_publisher_specific_parser():
            return False
        return bool(
            self.soup.select_one('meta[name="citation_author"]')
            or self.soup.select_one('meta[name="citation_abstract"]')
            or self.soup.select_one("h1.chapter-title")
            or self.soup.select_one("li.author")
            or self.soup.select_one(".contributors-details")
            or self.soup.select_one("div.abstract")
            or self.soup.select_one('div[class*="abstract"]')
            or self.soup.select_one('section[class*="abstract"]')
        )

    # No-abstract pages put an access notice inside div.abstract ("An abstract is
    # not available for this content so a preview has been provided..." / the
    # "A summary is not available..." variant). That notice must never become the
    # abstract.
    _NO_ABSTRACT_NOTICE = re.compile(
        r"(an abstract|a summary) is not available for this content", re.I
    )

    # When a chapter or article has no abstract, Cambridge Core shows its opening instead and marks it on the page:
    # a chapter's "Summary" holds div.abstract with data-abstract-type="extract", an article's section is headed
    # "Extract" (oxjob #2162). An opening is body text, not an abstract (landing-pages charter § 6, 24 Oct 2026; gold
    # v1.3 labels these pages "no abstract"). data-abstract-type="normal" under "Summary" or "Abstract" is kept.
    def _section_heading(self, tag):
        for parent in list(tag.parents)[:3]:
            heading = parent.find(["h2", "h3"], recursive=False)
            if heading:
                return heading.get_text(" ", strip=True)
        return ""

    def _is_marked_extract(self, tag):
        if states_what_the_work_does(tag.get_text(" ", strip=True)):
            return False
        if (tag.get("data-abstract-type") or "").strip().lower() == "extract":
            return True
        return self._section_heading(tag).strip().lower() == "extract"

    def _marked_extracts(self):
        return [tag for tag in self.soup.select("div.abstract") if self._is_marked_extract(tag)]

    def marked_openings(self):
        """The texts this page marks as the work's opening (its extract), for parse_page's guard."""
        return [tag.get_text(" ", strip=True) for tag in self._marked_extracts()]

    def _visible_abstract(self):
        extracts = self._marked_extracts()
        for selector in (
            "div.abstract",
            'div[class*="abstract"]',
            'section[class*="abstract"]',
        ):
            for tag in self.soup.select(selector):
                if any(tag is m or m in tag.parents or tag in m.parents for m in extracts):
                    continue
                text = tag.get_text(" ", strip=True)
                text = re.sub(r"^((abstract|summary)\s*)+", "", text, flags=re.I).strip()
                if self._NO_ABSTRACT_NOTICE.search(text):
                    continue
                if len(text) >= 20:
                    return text
        return None

    @staticmethod
    def _clean_contributor_name(text):
        text = re.sub(r"\s*\[Opens in a new window\]\s*", "", text or "")
        text = re.sub(r"\s+", " ", text)
        return text.strip(" ,")

    @staticmethod
    def _surname_from_name(name):
        tokens = re.findall(r"[A-Za-z][A-Za-z'-]+", name or "")
        return tokens[-1].lower() if tokens else ""

    def _footnote_marks_first_meta_author_corresponding(self, first_author_name):
        text = self.soup.get_text(" ", strip=True)
        match = re.search(r"Footnotes?\s*\*\s*(.{0,700})", text, flags=re.I)
        if not match:
            return False

        snippet = match.group(1)
        email = re.search(
            r"(?:e-?mail|email)\s*:\s*([A-Z0-9._%+-]+)@[A-Z0-9.-]+\.[A-Z]{2,}",
            snippet,
            flags=re.I,
        )
        if not email:
            return False

        surname = self._surname_from_name(first_author_name)
        return bool(surname and surname in email.group(1).lower())

    def _contributor_names(self, tag):
        names = []
        for selector in ("span.author-name", "a.more-by-this-author", ".contributor-type__contributor"):
            for node in tag.select(selector):
                text = self._clean_contributor_name(node.get_text(" ", strip=True))
                text = re.sub(r"\s+and$", "", text).strip(" ,")
                if text and text not in names:
                    names.append(text)
            if names:
                break
        return names

    def _detail_affiliations_by_name(self):
        affiliations_by_name = {}
        for author in self.soup.select("div.row.author"):
            name_tag = author.find("dt")
            if name_tag:
                name = self._clean_contributor_name(name_tag.get_text(" ", strip=True))
            else:
                text = author.get_text(" ", strip=True)
                name = self._clean_contributor_name(text.split("Affiliation:", 1)[0])
            if not name:
                continue

            affiliations = []
            affiliation_soup = author.find("div", class_="d-sm-flex")
            if affiliation_soup:
                for organization in affiliation_soup.stripped_strings:
                    organization = re.sub('email:.*?$', '', organization)
                    organization = re.sub(r'[a-zA-Z0-9._%+-]+@.*?$', '', organization)
                    organization = organization.strip('., ()')
                    if organization:
                        affiliations.append(organization)
            if affiliations:
                affiliations_by_name[name] = affiliations
        return affiliations_by_name

    def _contributors_from_tag(self, tag, detail_affiliations):
        names = self._contributor_names(tag)
        row_affiliations = [
            self._clean_contributor_name(node.get_text(" ", strip=True))
            for node in tag.select(".affiliation")
        ]
        row_affiliations = [aff for aff in row_affiliations if aff]

        authors = []
        for index, name in enumerate(names):
            affiliations = list(detail_affiliations.get(name, []))
            if not affiliations and len(row_affiliations) == len(names):
                affiliations = [row_affiliations[index]]
            elif not affiliations and len(names) == 1 and row_affiliations:
                affiliations = row_affiliations
            authors.append(
                AuthorAffiliations(
                    name=name,
                    affiliations=affiliations,
                    is_corresponding=False,
                )
            )
        return authors

    def _chapter_contributor_authors(self):
        if not (
            self.soup.select_one("h1.chapter-title")
            or self.soup.select_one("li.author.chapter")
        ):
            return []

        by_authors = []
        unlabeled_authors = []
        editor_authors = []
        detail_affiliations = self._detail_affiliations_by_name()
        seen = {"by": {}, "unlabeled": {}, "editor": {}}

        def append_many(bucket, key, authors):
            for author in authors:
                if author.name in seen[key]:
                    existing = seen[key][author.name]
                    if not existing.affiliations and author.affiliations:
                        existing.affiliations = author.affiliations
                    continue
                bucket.append(author)
                seen[key][author.name] = author

        for tag in self.soup.select("div.row.contributor-type, li.author"):
            classes = set(tag.get("class") or [])
            label_tag = tag.select_one(".contributor-type__label")
            label = label_tag.get_text(" ", strip=True).lower() if label_tag else ""
            text = tag.get_text(" ", strip=True).lower()
            authors = self._contributors_from_tag(tag, detail_affiliations)
            if not authors:
                continue

            if label == "by" or ("chapter" in classes and text.startswith("by ")):
                append_many(by_authors, "by", authors)
            elif label.startswith("edited") or text.startswith("edited by"):
                append_many(editor_authors, "editor", authors)
            elif not label and not text.startswith(self._NON_AUTHOR_ROLE_PREFIXES):
                append_many(unlabeled_authors, "unlabeled", authors)

        return by_authors or unlabeled_authors or editor_authors

    # Acknowledgments, funding statement and reference list (oxjob #2222; output contract: oxjob #2215 README).
    # Cambridge Core renders JATS back matter: div.ack ("Acknowledgements"), a funding section headed "Funding",
    # "Financial support" or "Funding statement" (div.funding-statement, div.notes or div.sec), and #references-list
    # with one .circle-list__item per entry. That list also holds footnotes on many humanities journals (item ids
    # fn1, en1; old pages "page 381 note 1"): notes are not references, so they are never returned.
    _ACK_HEADING = re.compile(r"^acknowledge?ments?(\s+(and|&)\s+funding)?$", re.I)  # combined section: acknowledgments
    _FUNDING_HEADING = re.compile(
        r"^(funding(\s+(statement|information|sources?))?|financial\s+support|sources?\s+of\s+funding)$", re.I)
    _NOTE_ID = re.compile(r"^(fn|en)\d", re.I)
    _PAGE_NOTE = re.compile(r"^page\s+\S+\s+note\b", re.I)
    _ENTRY_NUMBER = re.compile(r"^[\[(]?(\d+)[\])]?\.?$")
    _DOI_IN_LINK = re.compile(r"doi\.org/(10\.\d{4,9}/[^\s?#]+)", re.I)
    _MORE_MARKER = re.compile(r"\b(show|load|view)\s+(all|more)\b|\bfirst\s+\d+\s+references\b", re.I)

    @staticmethod
    def _heading_text(section):
        heading = section.find(["h2", "h3", "h4"], recursive=False)
        return squash(heading.get_text()).rstrip(":").strip() if heading else ""

    @staticmethod
    def _section_body(section):
        """The section's text without its heading: its paragraphs joined by a newline."""
        paragraphs = [squash(p.get_text()) for p in section.find_all("p")]
        if not paragraphs:
            section = copy.copy(section)  # never edit the page the other parsers read
            for heading in section.find_all(["h2", "h3", "h4"]):
                heading.decompose()
            paragraphs = [squash(section.get_text())]
        return "\n".join(p for p in paragraphs if p) or None

    def _back_matter(self):
        """(acknowledgments, funding_statement) as the page prints them, each None when it prints none."""
        acknowledgments, funding = [], []
        for section in self.soup.find_all("div", class_=["ack", "funding-statement", "notes", "sec"]):
            heading = self._heading_text(section)
            in_ack = "ack" in (section.get("class") or [])
            if self._FUNDING_HEADING.match(heading):
                bucket = funding
            elif self._ACK_HEADING.match(heading) or (in_ack and not heading):
                bucket = acknowledgments
            else:
                continue
            text = self._section_body(section)
            if text and text not in bucket:
                bucket.append(text)
        return "\n".join(acknowledgments) or None, "\n".join(funding) or None

    def _references(self):
        """(references, references_complete). Complete only when the entries are numbered 1..n with no gap, no
        footnote sits among them and nothing in the list's container says there are more."""
        container = self.soup.select_one("#references-list")
        if container is None:
            return None, False
        refs, numbers, skipped = [], [], False
        for item in container.select(".circle-list__item"):
            number_tag = item.select_one(".circle-list__item__number")
            number = number_tag.get_text(strip=True) if number_tag else ""
            if self._NOTE_ID.match(item.get("id") or "") or self._PAGE_NOTE.match(number):
                skipped = True
                continue
            content = item.select_one(".circle-list__item__grouped__content")
            if content is None:
                skipped = True
                continue
            content = copy.copy(content)
            doi = None
            for link in content.select("a.ref-link"):  # "CrossRef", "Google Scholar", "PubMed" buttons
                match = self._DOI_IN_LINK.search(unquote(link.get("href") or ""))
                if match and doi is None:
                    doi = match.group(1).rstrip(".,;")
                link.decompose()
            label = content.find("span", class_="label", recursive=False)
            if label:
                label.decompose()
            raw = squash(content.get_text())
            if not raw:
                skipped = True
                continue
            refs.append({"position": len(refs) + 1, "raw": raw, "doi": doi})
            numbered = self._ENTRY_NUMBER.match(number)
            numbers.append(int(numbered.group(1)) if numbered else None)
        if not refs:
            return None, False
        if skipped or numbers != list(range(1, len(refs) + 1)):
            return refs, False
        # a "show more" marker outside the entries (a reference's own title may say "view all")
        markers = container.find_all(string=self._MORE_MARKER)
        return refs, all(marker.find_parent(class_="circle-list__item") for marker in markers)

    def _new_fields(self):
        if not self.is_publisher_specific_parser():
            return {}
        acknowledgments, funding_statement = self._back_matter()
        references, references_complete = self._references()
        return {
            "acknowledgments": acknowledgments,
            "funding_statement": funding_statement,
            "references": references,
            "references_complete": references_complete,
        }

    def parse(self):
        result_authors = self._chapter_contributor_authors()
        if not result_authors:
            authors = self.soup.findAll("div", class_="author")
            for author in authors:
                name_tag = author.find("dt")
                if not name_tag:
                    continue
                name = name_tag.text
                if "*" in name:
                    is_corresponding = True
                else:
                    is_corresponding = False
                name = name.strip().replace("*", "")

                affiliations = []
                affiliation_soup = author.find("div", class_="d-sm-flex")
                if affiliation_soup:
                    for organization in affiliation_soup.stripped_strings:
                        organization = re.sub('email:.*?$', '', organization)
                        organization = re.sub(r'[a-zA-Z0-9._%+-]+@.*?$', '', organization)
                        affiliations.append(organization.strip('., ()'))

                result_authors.append(
                    AuthorAffiliations(
                        name=name,
                        affiliations=affiliations,
                        is_corresponding=is_corresponding,
                    )
                )
        # Older CUP journal pages and Cambridge eBook (cbo*) chapters use a
        # different template with no div.author — authors live in
        # citation_author meta tags (affiliations in citation_author_institution).
        # Fall back to meta-tag parsing so these ~40% of pages aren't dropped.
        if not result_authors:
            result_authors = self.parse_author_meta_tags()
            if result_authors:
                first_author = result_authors[0]
                first_name = first_author.get("name") if isinstance(first_author, dict) else first_author.name
                if self._footnote_marks_first_meta_author_corresponding(first_name):
                    if isinstance(first_author, dict):
                        first_author["is_corresponding"] = True
                    else:
                        first_author.is_corresponding = True

        # Journal pages carry the abstract in meta tags. Cambridge eBook (cbo*)
        # chapter pages do not — their meta og:description is just the book
        # title ("Frank Sinatra - June 2007"), while the real chapter abstract
        # lives in div.abstract. Fall back to it when the meta abstract is
        # missing or too short to be a real abstract.
        abstract = self.parse_abstract_meta_tags()
        if abstract and self._NO_ABSTRACT_NOTICE.search(abstract):
            abstract = None
        # The meta abstract (citation_abstract) repeats the opening on pages that mark it as an extract (#2162).
        if abstract and any(same_opening_text(abstract, opening) for opening in self.marked_openings()):
            abstract = None
        visible_abstract = self._visible_abstract()
        if visible_abstract and (not abstract or len(abstract) < 200):
            abstract = visible_abstract

        return {"authors": result_authors, "abstract": abstract, **self._new_fields()}

    test_cases = [
        {
            "doi": "10.1017/S1355770X21000218",
            "result": {
                "authors": [
                    {
                        "name": "Julien Wolfersberger",
                        "affiliations": [
                            "Université Paris-Saclay, INRAE, AgroParisTech, Economie Publique, Thiverval-Grignon, France",
                            "Climate Economics Chair, Palais Brongniart, Paris, France",
                        ],
                        "is_corresponding": True,
                    },
                    {
                        "name": "Gregory S. Amacher",
                        "affiliations": [
                            "Virginia Polytechnic Institute and State University, Blacksburg, VA, USA"
                        ],
                        "is_corresponding": False,
                    },
                    {
                        "name": "Philippe Delacote",
                        "affiliations": [
                            "Climate Economics Chair, Palais Brongniart, Paris, France",
                            "BETA, Université Lorraine, INRAE, AgroParisTech, Nancy, France",
                        ],
                        "is_corresponding": False,
                    },
                    {
                        "name": "Arnaud Dragicevic",
                        "affiliations": ["IRSTEA, Clermont-Ferrand, Aubiere, France"],
                        "is_corresponding": False,
                    },
                ],
                "abstract": "We develop a model of optimal land allocation in a developing economy that features three possible land uses: agriculture, primary and secondary forests. The distinction between those forest types reflects their different contributions in terms of public goods. In our model, reforestation is costly because it undermines land title security. Using the forest transition concept, we study long-term land-use change and explain important features of cumulative deforestation across countries. Our results shed light on the speed at which net deforestation ends, on the effect of tenure costs in this process, and on composition in steady state. We also present a policy analysis that emphasizes the critical role of institutional reforms addressing the costs of both deforestation and tenure in order to promote a transition. We find that focusing only on net forest losses can be misleading since late transitions may yield, upon given conditions, a higher level of environmental benefits.",
            },
        },
    ]


def cambridge_marked_openings(soup):
    """Openings a Cambridge Core page marks as its extract (oxjob #2162); [] elsewhere."""
    return CUP(soup).marked_openings()

