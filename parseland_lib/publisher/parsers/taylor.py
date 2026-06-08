import html
import json
import re

from bs4 import BeautifulSoup, NavigableString

from parseland_lib.elements import AuthorAffiliations
from parseland_lib.publisher.parsers.parser import PublisherParser


class Taylor(PublisherParser):
    parser_name = "taylor"

    def is_publisher_specific_parser(self):
        return (
            self.domain_in_meta_og_url("tandfonline.com")
            or self.domain_in_canonical_link("tandfonline.com")
            or self.domain_in_meta_og_url("taylorfrancis.com")
            or self.domain_in_canonical_link("taylorfrancis.com")
        )

    def authors_found(self):
        return (
            self.soup.find("div", class_="publicationContentAuthors")
            or self._taylorfrancis_jsonld_chapter()
        )

    def parse(self):
        results = []
        author_soup = self.soup.find("div", class_="publicationContentAuthors")
        if author_soup:
            authors = author_soup.findAll("div", class_="entryAuthor")
        else:
            authors = []
        bio_affiliations = self._author_bio_affiliations_by_name()
        for author in authors:
            name = author.a.text

            correspondence_header = author.find("span", class_="heading")
            if (
                correspondence_header
                and correspondence_header.text.lower() == "correspondence"
            ):
                is_corresponding = True
            else:
                is_corresponding = False

            affiliations = []
            affiliation = author.find("span", class_="overlay")
            if affiliation and affiliation.contents:
                first_content = affiliation.contents[0]
                # Only extract affiliation if it's a text node (not an ORCID link or other tag)
                if isinstance(first_content, NavigableString):
                    aff_text = str(first_content).strip()
                    # Skip if it looks like a URL or is empty
                    if (
                        aff_text
                        and not aff_text.startswith('http')
                        and "view further author information" not in aff_text.lower()
                    ):
                        affiliation_trimmed = re.sub('^[a-z0-9] ', '', aff_text)
                        affiliations.append(affiliation_trimmed)
            if not affiliations:
                bio_affiliation = bio_affiliations.get(self._name_key(name))
                if bio_affiliation:
                    affiliations.append(bio_affiliation)
            results.append(
                AuthorAffiliations(
                    name=name,
                    affiliations=affiliations,
                    is_corresponding=is_corresponding,
                )
            )
        if not results:
            results = self._parse_taylorfrancis_chapter_authors()
        abstract_tag = self.soup.find('div', class_='abstractInFull')
        if not abstract_tag:
            # Fallback: hlFld-Abstract container covers the older/legacy
            # Taylor & Francis layout where abstractInFull is absent.
            abstract_tag = self.soup.find(class_='hlFld-Abstract')
        if abstract_tag:
            abstract = abstract_tag.text
            # Strip duplicated leading "Abstract" / "ABSTRACT" / "RÉSUMÉ" labels
            # (hlFld-Abstract sometimes contains the heading twice).
            abstract = re.sub(r'^\s*(?:abstract|résumé|resumen|zusammenfassung)\s*',
                              '', abstract, flags=re.IGNORECASE)
            abstract = re.sub(r'^\s*(?:abstract|résumé|resumen|zusammenfassung)\s*',
                              '', abstract, flags=re.IGNORECASE)
            abstract = abstract.strip() or None
        else:
            abstract = self._parse_taylorfrancis_chapter_abstract()
        return {"authors": results, "abstract": abstract}

    def _taylorfrancis_jsonld_chapter(self):
        for script in self.soup.find_all("script", type="application/ld+json"):
            raw = script.string or script.get_text("", strip=False)
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except Exception:
                continue
            objects = payload if isinstance(payload, list) else [payload]
            for obj in objects:
                if not isinstance(obj, dict):
                    continue
                raw_type = obj.get("@type")
                types = raw_type if isinstance(raw_type, list) else [raw_type]
                if "Chapter" not in types:
                    continue
                url = str(obj.get("url") or "")
                publisher = obj.get("publisher") or {}
                publisher_name = ""
                if isinstance(publisher, dict):
                    publisher_name = str(publisher.get("name") or "")
                if "taylorfrancis.com" in url or "Taylor & Francis" in publisher_name:
                    return obj
        return None

    def _parse_taylorfrancis_chapter_authors(self):
        chapter = self._taylorfrancis_jsonld_chapter()
        if not chapter:
            return []
        raw_authors = chapter.get("author") or []
        if isinstance(raw_authors, dict):
            raw_authors = [raw_authors]
        results = []
        for author in raw_authors:
            if not isinstance(author, dict):
                continue
            for name in self._taylorfrancis_jsonld_author_names(author):
                results.append(
                    AuthorAffiliations(
                        name=name,
                        affiliations=[],
                        is_corresponding=False,
                    )
                )
        return results

    def _taylorfrancis_jsonld_author_names(self, author):
        """Return one or more names from TaylorFrancis Chapter JSON-LD.

        Some Taylor eBook chapter pages compress several contributors into one
        schema.org Person object, with comma-separated givenName and familyName
        lists. Splitting only when both sides have the same multi-part count
        keeps the fallback conservative for normal single-author metadata.
        """
        name = str(author.get("name") or "").strip()
        given = str(author.get("givenName") or "").strip()
        family = str(author.get("familyName") or "").strip()

        given_parts = self._split_taylorfrancis_name_parts(given)
        family_parts = self._split_taylorfrancis_name_parts(family)
        if len(given_parts) == len(family_parts) and len(given_parts) > 1:
            names = [
                " ".join(part for part in (g, f) if part).strip()
                for g, f in zip(given_parts, family_parts)
            ]
            return [n for n in names if n]

        if not name:
            name = " ".join(part for part in (given, family) if part)
        name = re.sub(r"\s+", " ", name).strip()
        return [name] if name else []

    def _split_taylorfrancis_name_parts(self, value):
        return [
            re.sub(r"\s+", " ", part).strip()
            for part in (value or "").split(",")
            if part.strip()
        ]

    def _author_bio_affiliations_by_name(self):
        affiliations = {}
        for block in self.soup.select("div.author-infos div.addAuthorInfo"):
            data = block.select_one(".AuthorInfoData") or block
            heading = data.find("h4")
            if not heading:
                continue
            name = heading.get_text(" ", strip=True)
            if not name:
                continue
            text = data.get_text(" ", strip=True)
            affiliation = self._extract_affiliation_from_bio(name, text)
            if affiliation:
                affiliations[self._name_key(name)] = affiliation
        return affiliations

    def _extract_affiliation_from_bio(self, name, text):
        text = re.sub(r"\s+", " ", text or "").strip(" •")
        text = re.sub(rf"^{re.escape(name)}\b\s*", "", text).strip(" ,•")
        text = re.sub(rf"^{re.escape(name)}\b\s*", "", text).strip(" ,•")
        if not text:
            return None

        with_match = re.search(r"\bare with the\s+(.+?)(?:\.|$)", text, re.I)
        if with_match:
            return self._clean_bio_affiliation(with_match.group(1))

        is_match = re.search(r"\bis\s+(.+?)(?:\.|$)", text, re.I)
        if not is_match:
            return None
        tail = is_match.group(1).strip(" ,")

        in_match = re.search(r"\bin the\s+(.+)$", tail, re.I)
        if in_match:
            return self._clean_bio_affiliation(in_match.group(1))

        at_match = re.search(r"\bat (?:the\s+)?(.+)$", tail, re.I)
        if at_match and self._looks_like_affiliation(at_match.group(1)):
            return self._clean_bio_affiliation(at_match.group(1))

        parts = [part.strip() for part in tail.split(",") if part.strip()]
        for i, part in enumerate(parts):
            if self._looks_like_affiliation(part):
                return self._clean_bio_affiliation(", ".join(parts[i:]))
        return None

    def _clean_bio_affiliation(self, value):
        value = re.sub(r"\s+", " ", value or "").strip(" .;,")
        value = re.sub(
            r"\s+and\s+(?:editor|author|co-?editor)\b.*$",
            "",
            value,
            flags=re.I,
        )
        value = re.sub(
            r"\bat\s+(?:the\s+)?(?=(?:University|College|School|Institute|"
            r"Center|Centre|Hospital|Clinic)\b)",
            ", ",
            value,
            count=1,
            flags=re.I,
        )
        value = re.sub(r"\s*,\s*", ", ", value)
        return value or None

    def _looks_like_affiliation(self, value):
        return bool(re.search(
            r"\b(?:University|College|School|Department|Institute|Laborator(?:y|ies)|"
            r"Center|Centre|Hospital|Clinic|Facility|Research|CSIRO|UMKC|UCLA)\b",
            value,
            re.I,
        ))

    def _name_key(self, value):
        return re.sub(r"\W+", "", value or "").lower()

    def _parse_taylorfrancis_chapter_abstract(self):
        product_abstract = self._parse_taylorfrancis_product_abstract()
        if product_abstract:
            return product_abstract
        chapter = self._taylorfrancis_jsonld_chapter()
        if not chapter:
            return None
        description = str(chapter.get("description") or "").strip()
        if not description:
            return None
        return self._clean_taylorfrancis_abstract(description)

    def _parse_taylorfrancis_product_abstract(self):
        for script in self.soup.find_all("script", type="application/json"):
            raw = script.string or script.get_text("", strip=False)
            if not raw or "&q;abstracts&q;" not in raw:
                continue
            normalized = self._decode_taylorfrancis_jsonish(raw)
            try:
                payload = json.loads(normalized)
            except Exception:
                payload = None
            value = self._find_product_abstract_value(payload) if payload else None
            if not value:
                match = re.search(
                    r'&q;abstracts&q;\s*:\s*\[.*?&q;value&q;\s*:\s*&q;(.*?)&q;',
                    raw,
                    flags=re.DOTALL,
                )
                if match:
                    value = self._decode_taylorfrancis_jsonish(match.group(1))
            if value:
                cleaned = self._clean_taylorfrancis_abstract(str(value))
                if cleaned:
                    return cleaned
        return None

    def _find_product_abstract_value(self, payload):
        if isinstance(payload, dict):
            abstracts = payload.get("abstracts")
            if isinstance(abstracts, list):
                for item in abstracts:
                    if isinstance(item, dict) and item.get("value"):
                        return item["value"]
            for value in payload.values():
                found = self._find_product_abstract_value(value)
                if found:
                    return found
        elif isinstance(payload, list):
            for item in payload:
                found = self._find_product_abstract_value(item)
                if found:
                    return found
        return None

    def _decode_taylorfrancis_jsonish(self, value):
        return html.unescape(
            value
            .replace("&q;", '"')
            .replace("&l;", "<")
            .replace("&g;", ">")
            .replace("&a;", "&")
        )

    def _clean_taylorfrancis_abstract(self, value):
        text = BeautifulSoup(value, "lxml").get_text(" ", strip=True)
        return text.strip() or None

    test_cases = [
        {
            "doi": "10.1080/23311932.2021.1910156",
            "result": [
                {
                    "name": "Joseph Alulu",
                    "affiliations": [
                        "Department of Agricultural Economics, Faculty of Agriculture, University of Nairobi, Nairobi, Kenya"
                    ],
                    "is_corresponding": True,
                },
                {
                    "name": "David Jakinda Otieno",
                    "affiliations": [
                        "Department of Agricultural Economics, Faculty of Agriculture, University of Nairobi, Nairobi, Kenya"
                    ],
                    "is_corresponding": False,
                },
                {
                    "name": "Willis Oluoch-Kosura",
                    "affiliations": [
                        "Department of Agricultural Economics, Faculty of Agriculture, University of Nairobi, Nairobi, Kenya"
                    ],
                    "is_corresponding": False,
                },
                {
                    "name": "Justus Ochieng",
                    "affiliations": ["World Vegetable Center, Arusha, Tanzania"],
                    "is_corresponding": False,
                },
                {
                    "name": "Manuel Tejada Moral",
                    "affiliations": ["University of Seville, Seville, SPAIN"],
                    "is_corresponding": False,
                },
            ],
        },
        {
            # ORCID link in overlay - should not extract URL as affiliation
            "doi": "10.1080/14746700.2023.2294530",
            "result": [
                {
                    "name": "Mois Navon",
                    "affiliations": [],
                    "is_corresponding": False,
                },
            ],
        },
    ]
