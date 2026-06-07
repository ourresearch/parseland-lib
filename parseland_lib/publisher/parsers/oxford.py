import json
import re

from parseland_lib.exceptions import UnusualTrafficError
from parseland_lib.elements import AuthorAffiliations
from parseland_lib.publisher.parsers.parser import PublisherParser


class Oxford(PublisherParser):
    parser_name = "oxford university press"
    oxford_domains = (
        "academic.oup.com",
        "oxfordscholarlyeditions.com",
        "oxforddnb.com",
        "oxfordmusiconline.com",
        "oxfordaasc.com",
        "universitypressscholarship.com",
        "oxfordbusinesstrove.com",
        "oxfordlawtrove.com",
        "oxfordre.com",
    )
    _AFFILIATION_SIGNAL = re.compile(
        r"\b("
        r"University|Department|School|College|Hospital|Institute|Centre|Center|"
        r"Laborator(?:y|ies)|Agency|Registry|Society|Royal|Infirmary|Foundation|"
        r"Clinic|Faculty|Ministry|Museum|Service|Bureau|Office|Climate Interactive"
        r")\b",
        re.I,
    )
    _TITLE_AFFILIATION_PREFIX = re.compile(
        r"^(?:"
        r"(?:associate|assistant|full|distinguished)\s+professor|"
        r"professor|senior lecturer(?:\s+in\s+[\w\s]+)?|lecturer(?:\s+in\s+[\w\s]+)?|"
        r"dean|co-founder and co-director|founding executive director|director|"
        r"phd|md|mph|drph"
        r")\s*,\s*",
        re.I,
    )

    def is_publisher_specific_parser(self):
        if self.soup.find(
                "div", class_="explanation-message"
        ) and "help us confirm that you are not a robot and we will take you to your content" in str(
            self.soup
        ):
            raise UnusualTrafficError(
                f"content blocked within {self.parser_name} parser"
            )
        # The HTML may have og:url=dx.doi.org (the DOI router) even when the
        # actual page is on academic.oup.com — common for cached HTML where
        # the publisher's page sets og:url to the DOI for citation portability.
        # Accept either signal across Oxford's journal and product domains.
        return any(
            self.domain_in_meta_og_url(domain)
            or self.domain_in_canonical_link(domain)
            for domain in self.oxford_domains
        )

    def authors_found(self):
        return (
            self.soup.find("div", class_="at-ArticleAuthors")
            or bool(self._extract_schema_author_meta())
            or bool(self._extract_product_author_bios())
            or bool(self._extract_author_affiliations_from_citation_title())
        )

    def parse(self):
        results = []
        if author_soup := self.soup.find("div", class_="at-ArticleAuthors"):
            authors = author_soup.findAll("div", class_="info-card-author")
            source_by_author = []

            for author in authors:
                name_tag = author.find("div", class_="info-card-name")
                if not name_tag:
                    continue
                name = self._clean_author_name(name_tag.get_text(" ", strip=True))

                is_corresponding = (
                    True
                    if author.find("div", class_="info-author-correspondence")
                    else False
                )

                affiliations, sources = self._extract_article_card_affiliations(
                    author
                )
                source_by_author.append(sources)

                results.append(
                    AuthorAffiliations(
                        name=name,
                        affiliations=affiliations,
                        is_corresponding=is_corresponding,
                    )
                )
            self._apply_single_structured_affiliation_to_empty_authors(
                results, source_by_author
            )
        if not results:
            results = self._extract_schema_author_meta()
        if results and not any(author.affiliations for author in results):
            results = self._merge_better_affiliation_fallbacks(results)
        if not results:
            results = (
                self._extract_product_author_bios()
                or self._extract_author_affiliations_from_citation_title()
            )
        abstract = self._extract_abstract()
        return {"authors": results,
                "abstract": abstract,}

    def _extract_schema_author_meta(self):
        """Read OUP product-page author metadata when article byline DOM is absent."""
        results = []
        seen = set()
        current = None
        author_keys = {
            "author",
            "article:author",
            "citation_author",
            "dc.creator",
            "http://schema.org/author",
            "https://schema.org/author",
        }
        for meta in self.soup.find_all("meta"):
            key = (
                meta.get("name")
                or meta.get("property")
                or meta.get("itemprop")
                or ""
            ).strip().lower()
            if key in {"citation_author_institution",
                       "bepress_citation_author_institution"}:
                affiliation = self._clean_affiliation_text(meta.get("content") or "")
                if current and affiliation:
                    current.affiliations.append(affiliation)
                continue
            if key not in author_keys:
                continue
            name = (meta.get("content") or "").strip()
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())
            current = AuthorAffiliations(
                name=self._clean_author_name(name),
                affiliations=[],
                is_corresponding=None,
            )
            results.append(current)
        return results

    def _merge_better_affiliation_fallbacks(self, results):
        """Prefer visible OUP byline fallbacks when metadata only has names."""
        fallbacks = (
            self._extract_product_author_bios()
            or self._extract_author_affiliations_from_citation_title()
        )
        if not fallbacks:
            return results

        fallback_by_name = {
            self._name_key(author.name): author
            for author in fallbacks
            if author.affiliations
        }
        merged = []
        changed = False
        for author in results:
            fallback = fallback_by_name.get(self._name_key(author.name))
            if fallback:
                changed = True
                merged.append(
                    AuthorAffiliations(
                        name=author.name,
                        affiliations=fallback.affiliations,
                        is_corresponding=author.is_corresponding,
                    )
                )
            else:
                merged.append(author)
        return merged if changed else fallbacks

    def _extract_article_card_affiliations(self, author_card):
        affiliations = []
        sources = []
        for selector in (
            "div.info-card-affilitation",
            "div.info-card-affiliation",
        ):
            affiliation_section = author_card.select_one(selector)
            if not affiliation_section:
                continue
            for aff in affiliation_section.select("div.aff"):
                affiliation = self._clean_affiliation_text(
                    aff.get_text(" ", strip=True),
                    require_signal=False,
                )
                if affiliation:
                    affiliations.append(affiliation)
                    sources.append("structured")

        if not affiliations:
            affiliation = self._extract_free_text_card_affiliation(author_card)
            if affiliation:
                affiliations.append(affiliation)
                sources.append("free_text")

        return self._dedupe(affiliations), sources

    def _extract_free_text_card_affiliation(self, author_card):
        card_text = author_card.get_text(" ", strip=True)
        if not card_text:
            return None
        name_tag = author_card.find("div", class_="info-card-name")
        if name_tag:
            name = name_tag.get_text(" ", strip=True)
            card_text = card_text.replace(name, " ", 1)
            clean_name = self._clean_author_name(name)
            if clean_name != name:
                card_text = card_text.replace(clean_name, " ", 1)
        card_text = re.sub(
            r"Search for other works by this author on:.*$",
            "",
            card_text,
            flags=re.I,
        )
        card_text = re.sub(r"\b(?:Oxford Academic|PubMed|Google Scholar)\b", " ", card_text)
        card_text = re.sub(
            r"^\*+\s*(?:to whom correspondence should be addressed\.)?\s*",
            "",
            card_text,
            flags=re.I,
        ).strip()
        if card_text.lower().startswith("correspondence:"):
            return None
        return self._clean_affiliation_text(card_text)

    @classmethod
    def _clean_author_name(cls, name):
        name = re.sub(r"\s+", " ", name or "").strip()
        name = re.sub(r"\s*\*+\s*$", "", name).strip()
        return name

    @classmethod
    def _clean_affiliation_text(cls, text, strip_titles=False, require_signal=True):
        text = re.sub(r"\s+", " ", text or "").strip()
        if not text:
            return None
        text = re.sub(r"^[\d\*\s]+", "", text).strip()
        text = re.sub(
            r"^(?:to whom correspondence should be addressed\.)\s*",
            "",
            text,
            flags=re.I,
        ).strip()
        text = re.sub(r"\b(?:Tel|Fax|Phone|Email|E-mail)\s*:.*$", "", text, flags=re.I)
        text = re.sub(r"[\w.+-]+@[\w.-]+\.\w+", "", text)
        text = re.sub(r"\s*;\s*$", "", text).strip(" .;")
        if strip_titles:
            previous = None
            while previous != text:
                previous = text
                text = cls._TITLE_AFFILIATION_PREFIX.sub("", text).strip()
        text = re.sub(r"\s+([,;:])", r"\1", text)
        text = re.sub(r"\s+", " ", text).strip(" .;")
        if not text or len(text) < 6:
            return None
        if require_signal and not cls._AFFILIATION_SIGNAL.search(text):
            return None
        return text

    @staticmethod
    def _dedupe(values):
        out = []
        seen = set()
        for value in values:
            key = re.sub(r"\s+", " ", value).strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(value)
        return out

    @staticmethod
    def _name_key(name):
        return re.sub(r"[^a-z0-9]+", "", (name or "").lower())

    def _apply_single_structured_affiliation_to_empty_authors(
            self, results, source_by_author):
        if len(results) < 2:
            return
        structured_affiliations = []
        structured_owner_count = 0
        for author, sources in zip(results, source_by_author):
            if author.affiliations and "structured" in sources:
                structured_owner_count += 1
                structured_affiliations.extend(author.affiliations)
        unique = self._dedupe(structured_affiliations)
        if len(unique) != 1 or structured_owner_count != 1:
            return
        shared = unique[0]
        for author in results:
            if not author.affiliations:
                author.affiliations.append(shared)

    def _extract_product_author_bios(self):
        results = []
        for author in self.soup.select('li[data-role="author"]'):
            name_tag = author.select_one(".popoverButton")
            bio_tag = author.select_one(".popoverAuthorBio")
            if not name_tag or not bio_tag:
                continue
            name = self._clean_author_name(name_tag.get_text(" ", strip=True))
            affiliation = self._clean_affiliation_text(
                bio_tag.get_text(" ", strip=True)
            )
            if not name:
                continue
            results.append(
                AuthorAffiliations(
                    name=name,
                    affiliations=[affiliation] if affiliation else [],
                    is_corresponding=None,
                )
            )
        return results

    def _extract_author_affiliations_from_citation_title(self):
        title = self._meta_content("citation_title")
        if not title or ":" not in title:
            return []
        _, suffix = title.split(":", 1)
        suffix = re.sub(r"\s+", " ", suffix).strip()
        if not suffix:
            return []

        degree_re = re.compile(r",\s*(?:PhD|MD|MPH|DrPH)\s*,\s*", re.I)
        degree_matches = list(degree_re.finditer(suffix))
        if degree_matches:
            return self._extract_degree_marked_title_authors(
                suffix, degree_matches
            )

        pattern = re.compile(
            r"(?P<name>[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){1,4}),\s*"
            r"(?:(?:PhD|MD|MPH|DrPH)\s*,\s*)?"
            r"(?P<aff>.*?)(?=\s+[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){1,4},\s*"
            r"(?:(?:PhD|MD|MPH|DrPH)\s*,)|$)"
        )
        results = []
        for match in pattern.finditer(suffix):
            name = self._clean_author_name(match.group("name"))
            affiliation = self._clean_affiliation_text(
                match.group("aff"), strip_titles=True
            )
            if not name or not affiliation:
                continue
            results.append(
                AuthorAffiliations(
                    name=name,
                    affiliations=[affiliation],
                    is_corresponding=None,
                )
            )
        return results

    def _extract_degree_marked_title_authors(self, suffix, degree_matches):
        author_spans = []
        previous_degree_end = 0
        for index, match in enumerate(degree_matches):
            if index == 0:
                name_start = 0
            else:
                between = suffix[previous_degree_end:match.start()]
                trailing_name_start = self._trailing_person_name_start(between)
                if trailing_name_start is None:
                    return []
                name_start = previous_degree_end + trailing_name_start
            name = self._clean_author_name(suffix[name_start:match.start()])
            if not name:
                return []
            author_spans.append({
                "name_start": name_start,
                "name": name,
                "degree_end": match.end(),
            })
            previous_degree_end = match.end()

        results = []
        for index, author in enumerate(author_spans):
            aff_start = author["degree_end"]
            aff_end = (
                author_spans[index + 1]["name_start"]
                if index + 1 < len(author_spans)
                else len(suffix)
            )
            affiliation = self._clean_affiliation_text(
                suffix[aff_start:aff_end],
                strip_titles=True,
            )
            if not affiliation:
                continue
            results.append(
                AuthorAffiliations(
                    name=author["name"],
                    affiliations=[affiliation],
                    is_corresponding=None,
                )
            )
        return results

    @staticmethod
    def _trailing_person_name_start(segment):
        tokens = list(re.finditer(r"\S+", segment))
        if len(tokens) < 2:
            return None
        start_index = len(tokens) - 2
        if start_index > 0 and re.match(
                r"^[A-Z]\.?$", tokens[start_index - 1].group(0).strip(",.")):
            start_index -= 1
        return tokens[start_index].start()

    def _meta_content(self, name, attr="name"):
        meta = self.soup.find("meta", attrs={attr: name})
        if meta and meta.get("content"):
            return meta.get("content").strip()
        if attr == "name":
            meta = self.soup.find("meta", attrs={"property": name})
            if meta and meta.get("content"):
                return meta.get("content").strip()
        return None

    def _extract_abstract(self):
        """Extract abstract with fallbacks for OUP markup variants.

        Order of preference:
          1. ``section.abstract p`` — standard OUP journal article template.
          2. ``.chapter-para`` — conference/supplement abstracts and some
             book-chapter templates that omit the ``section.abstract`` wrapper
             but expose the abstract body via the ``chapter-para`` class.
          3. ``meta[name=citation_abstract]`` content — used by a handful of
             OUP titles, full-length abstract.
          4. ``meta[property=og:description]`` / ``meta[name=description]``
             content with the leading "Abstract" prefix stripped — truncated
             at ~160 chars but better than no abstract at all.
        """
        primary = '\n'.join(
            tag.text for tag in self.soup.select('section.abstract p')
            if tag.text and tag.text.strip()
        ).strip()
        if primary:
            return primary

        chapter_paras = '\n'.join(
            tag.text for tag in self.soup.select('.chapter-para')
            if tag.text and tag.text.strip()
        ).strip()
        if chapter_paras and not self._is_low_quality_abstract_fallback(chapter_paras):
            return chapter_paras

        citation_meta = self.soup.select_one('meta[name="citation_abstract"]')
        if citation_meta and (citation_meta.get('content') or '').strip():
            return citation_meta.get('content').strip()

        for selector in ('meta[property="og:description"]',
                         'meta[name="description"]'):
            meta = self.soup.select_one(selector)
            if not meta:
                continue
            content = (meta.get('content') or '').strip()
            if not content:
                continue
            # Strip leading "Abstract" / "Abstract." prefix that OUP injects.
            content = re.sub(r'^abstract[\.\s:]*', '', content, flags=re.I).strip()
            if content and not self._is_low_quality_abstract_fallback(content):
                return content
        return ''

    @staticmethod
    def _is_low_quality_abstract_fallback(content):
        """Reject fallback-only snippets that are page chrome or citations."""
        normalized = re.sub(r'\s+', ' ', content).strip().lower()
        if not normalized:
            return True
        if normalized.startswith("this content is only available as a pdf"):
            return True
        if normalized.startswith("section editor:"):
            return True
        if "published on by oxford university press" in normalized:
            return True
        if "https://doi.org/" in normalized and re.search(
                r'\bvolume\b.+\bissue\b.+\bpages\b', normalized):
            return True
        return False


    test_cases = [
        {
            "doi": "10.1093/bib/bbab286",
            "result": [
                {
                    "name": "Chun-Chun Wang",
                    "affiliations": [
                        "School of Information and Control Engineering, China University of Mining and Technology"
                    ],
                    "is_corresponding": False,
                },
                {
                    "name": "Chen-Di Han",
                    "affiliations": [
                        "School of Information and Control Engineering, China University of Mining and Technology"
                    ],
                    "is_corresponding": False,
                },
                {
                    "name": "Qi Zhao",
                    "affiliations": [
                        "School of Computer Science and Software Engineering, University of Science and Technology Liaoning"
                    ],
                    "is_corresponding": True,
                },
                {
                    "name": "Xing Chen",
                    "affiliations": [
                        "China University of Mining and Technology"],
                    "is_corresponding": True,
                },
            ],
        },
        {
            "doi": "10.1093/jamia/ocab164",
            "result": [
                {
                    "name": "Chi Yuan",
                    "affiliations": [
                        "Department of Biomedical Informatics, Columbia University, New York, New York, USA"
                    ],
                    "is_corresponding": False,
                },
                {
                    "name": "Patrick B Ryan",
                    "affiliations": [
                        "Department of Biomedical Informatics, Columbia University, New York, New York, USA",
                        "Observational Health Data Sciences and Informatics, New York, New York, USA",
                        "Epidemiology Analytics, Janssen Research and Development, Titusville, New Jersey, USA",
                    ],
                    "is_corresponding": False,
                },
                {
                    "name": "Casey N Ta",
                    "affiliations": [
                        "Department of Biomedical Informatics, Columbia University, New York, New York, USA"
                    ],
                    "is_corresponding": False,
                },
                {
                    "name": "Jae Hyun Kim",
                    "affiliations": [
                        "Department of Biomedical Informatics, Columbia University, New York, New York, USA"
                    ],
                    "is_corresponding": False,
                },
                {
                    "name": "Ziran Li",
                    "affiliations": [
                        "Department of Biomedical Informatics, Columbia University, New York, New York, USA"
                    ],
                    "is_corresponding": False,
                },
                {
                    "name": "Chunhua Weng",
                    "affiliations": [
                        "Department of Biomedical Informatics, Columbia University, New York, New York, USA"
                    ],
                    "is_corresponding": True,
                },
            ],
        },
        {
            "doi": "10.1093/arclin/acab062.129",
            "result": [
                {
                    "name": "Julianne Wilson",
                    "affiliations": [],
                    "is_corresponding": None,
                },
                {
                    "name": "Amanda R Rabinowitz",
                    "affiliations": [],
                    "is_corresponding": None,
                },
                {
                    "name": "Tessa Hart",
                    "affiliations": [],
                    "is_corresponding": None,
                },
            ],
        },
    ]
