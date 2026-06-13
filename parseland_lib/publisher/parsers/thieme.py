import copy
import re
import unicodedata

from bs4 import BeautifulSoup, NavigableString, Tag

from parseland_lib.elements import Author, AuthorAffiliations, Affiliation
from parseland_lib.publisher.parsers.parser import PublisherParser


class Thieme(PublisherParser):
    parser_name = "thieme"

    def is_publisher_specific_parser(self):
        has_thieme_description = False
        if desc_tag := self.soup.select_one('meta[name=description]'):
            has_thieme_description = desc_tag.get('content', '').startswith('Thieme')
        return (
            has_thieme_description
            or self.domain_in_meta_og_url('thieme-connect')
            or self.domain_in_canonical_link('thieme')
            or self.substr_in_citation_publisher('thieme')
        )

    def authors_found(self):
        return bool(
            self.soup.select_one('.authors')
            or self.soup.select_one('meta[name="citation_author"]')
            or (self.is_publisher_specific_parser() and self.soup.select_one('#abstract'))
        )

    def parse_affiliations(self):
        aff_tags = self.soup.select('.authorsAffiliationsList li')
        if not aff_tags:
            aff_tags = self.soup.select('.affiliation')
        affs = []
        seen = set()
        for tag in aff_tags:
            text = tag.get_text(" ", strip=True)
            sup_tag = tag.find('sup')
            if sup_tag:
                aff_id = sup_tag.get_text(" ", strip=True)
                org = re.sub(rf"^{re.escape(aff_id)}\s*", "", text).strip()
            else:
                match = re.match(r"^(\d+)\s+(.+)$", text)
                if match:
                    aff_id = match.group(1)
                    org = match.group(2).strip()
                else:
                    aff_id = None
                    org = text
            if not org:
                continue
            key = (aff_id, self._normalize_text(org))
            if key in seen:
                continue
            seen.add(key)
            affs.append(Affiliation(organization=org, aff_id=aff_id))
        return affs

    def parse_authors(self):
        authors_tag = self.soup.select_one('.authors')
        authors = []
        if not authors_tag:
            embedded_authors = self._parse_embedded_author_spans()
            if embedded_authors:
                return embedded_authors
            return self._parse_citation_authors()

        # Older Thieme pages render "Name A, Name B" as a single text node with
        # no affiliation anchors. Citation metadata gives the reliable split.
        if not self._has_visible_affiliation_refs(authors_tag):
            citation_authors = self._parse_citation_authors()
            if citation_authors:
                return citation_authors

        for tag in authors_tag:
            if isinstance(tag, NavigableString):
                name = tag.text.strip(' ,\n\r')
                if not name:
                    continue
                aff_ids = self._collect_following_aff_ids(tag)
                authors.append(Author(name, aff_ids))
        return self._dedupe_authors(authors)

    @classmethod
    def _has_visible_affiliation_refs(cls, tag):
        if tag.select_one('a[href^="#"]'):
            return True
        return any(cls._clean_aff_id(sup.get_text(" ", strip=True)) for sup in tag.find_all("sup"))

    @classmethod
    def _collect_following_aff_ids(cls, node):
        aff_ids = []
        current = node
        while current.next_sibling:
            current = current.next_sibling
            if isinstance(current, NavigableString):
                text = current.strip()
                if re.sub(r"[\s,;]+", "", text):
                    break
                continue
            if not isinstance(current, Tag):
                continue
            if current.name == "div":
                break
            if current.name in {"a", "sup"}:
                aff_id = cls._clean_aff_id(current.get_text(" ", strip=True))
                if aff_id:
                    aff_ids.append(aff_id)
        return aff_ids

    @staticmethod
    def _clean_aff_id(value):
        cleaned = re.sub(r"\D+", "", value or "")
        return cleaned or None

    @classmethod
    def _clean_embedded_affiliation(cls, value):
        text = cls._clean_text(value)
        return re.sub(r"^\d+\s+", "", text).strip()

    def _parse_embedded_author_spans(self):
        authors = []
        for tag in self.soup.select("span.author"):
            affiliations = [
                self._clean_embedded_affiliation(aff.get_text(" ", strip=True))
                for aff in tag.select(".affiliation")
            ]
            affiliations = [aff for aff in affiliations if aff]
            if not affiliations:
                continue

            name_tag = copy.copy(tag)
            for aff in name_tag.select(".affiliation"):
                aff.decompose()
            name = self._clean_text(name_tag.get_text(" ", strip=True)).strip(" ,")
            name = re.sub(r"\s+\d+(?:\s+\d+)*$", "", name).strip(" ,")
            if not name:
                continue
            authors.append(AuthorAffiliations(name=name, affiliations=affiliations))
        return self._dedupe_author_affiliations(authors)

    @classmethod
    def _dedupe_authors(cls, authors):
        seen = set()
        deduped = []
        for author in authors:
            key = (cls._normalize_name(author.name), tuple(author.aff_ids))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(author)
        return deduped

    @classmethod
    def _dedupe_author_affiliations(cls, authors):
        seen = set()
        deduped = []
        for author in authors:
            key = (
                cls._normalize_name(author.name),
                tuple(cls._normalize_text(aff) for aff in author.affiliations),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(author)
        return deduped

    @staticmethod
    def _normalize_name(value):
        return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip().lower()

    @staticmethod
    def _normalize_text(value):
        return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip().lower()

    @classmethod
    def _normalize_alpha(cls, value):
        value = cls._normalize_text(value)
        value = (
            value.replace("ä", "ae")
            .replace("ö", "oe")
            .replace("ü", "ue")
            .replace("ß", "ss")
        )
        value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
        return re.sub(r"[^a-z0-9]+", "", value)

    @classmethod
    def _name_matches_email(cls, name, email):
        local = (email or "").split("@", 1)[0]
        email_tokens = [cls._normalize_alpha(token) for token in re.split(r"[._+\-]+", local)]
        email_tokens = [token for token in email_tokens if token]
        if not email_tokens:
            return False

        name_tokens = [cls._normalize_alpha(token) for token in re.split(r"[\s\-]+", name)]
        name_tokens = [token for token in name_tokens if token]
        if not name_tokens:
            return False

        first_initial = name_tokens[0][:1]
        surname_tokens = [token for token in name_tokens[1:] if len(token) >= 3] or name_tokens[-1:]
        has_first_initial = any(token.startswith(first_initial) for token in email_tokens)
        has_surname = any(
            surname in token or token.endswith(surname)
            for surname in surname_tokens
            for token in email_tokens
        )
        has_initial_surname_prefix = any(
            token.startswith(first_initial + surname[:3])
            for surname in surname_tokens
            for token in email_tokens
            if len(surname) >= 4
        )
        return (has_first_initial and has_surname) or has_initial_surname_prefix

    def _mark_corresponding_from_email_meta(self, authors):
        emails = [
            tag.get("content", "").strip()
            for tag in self.soup.select('meta[name="citation_author_email"]')
            if tag.get("content", "").strip()
        ]
        if not emails:
            return authors

        matched = False
        for author in authors:
            if any(self._name_matches_email(author.name, email) for email in emails):
                author.is_corresponding = True
                matched = True

        if matched:
            for author in authors:
                if author.is_corresponding is None:
                    author.is_corresponding = False
        return authors

    def _parse_citation_authors(self):
        names = [
            tag.get("content", "").strip()
            for tag in self.soup.select('meta[name="citation_author"]')
            if tag.get("content", "").strip()
        ]
        if not names:
            return []

        affiliations = [
            tag.get("content", "").strip()
            for tag in self.soup.select('meta[name="citation_author_institution"]')
            if tag.get("content", "").strip()
        ]
        shared_affiliations = [aff.organization for aff in self.parse_affiliations() if aff.organization]
        results = []
        for idx, name in enumerate(names):
            author_affiliations = []
            if idx < len(affiliations):
                author_affiliations.append(affiliations[idx])
            elif len(shared_affiliations) == 1:
                author_affiliations.extend(shared_affiliations)
            results.append(AuthorAffiliations(name=name, affiliations=author_affiliations))
        return results

    def parse_abstract(self):
        if citation_abstract := self.soup.select_one('meta[name="citation_abstract"]'):
            text = self._clean_abstract_text(citation_abstract.get("content", ""))
            if len(text) > 50:
                return text

        if abstract := self.soup.select_one('#abstract'):
            text = abstract.get_text(" ", strip=True)
            text = self._clean_abstract_text(text)
            if len(text) > 50:
                return text
        return self.parse_abstract_meta_tags()

    @staticmethod
    def _clean_text(value):
        if "<" in value and ">" in value:
            value = BeautifulSoup(value, "html.parser").get_text(" ", strip=True)
        return re.sub(r"\s+", " ", value).strip()

    @classmethod
    def _clean_abstract_text(cls, value):
        text = cls._clean_text(value)
        opens_window = r"(?:\s+\(opens in new window\))?"
        text = re.sub(
            rf"^(?:PDF Download\s+)?(?:Buy Article{opens_window}\s+)?(?:Permissions and Reprints{opens_window}\s+)+",
            "",
            text,
            flags=re.I,
        )
        text = re.sub(r"^(?:PDF Download\s+)", "", text, flags=re.I)
        text = re.sub(r"^(Abstract|Summary|Zusammenfassung)[:.\s]+", "", text, flags=re.I)
        text = re.split(
            r"\s+(?:Abstract|Summary|Key words|Keywords|Schlüsselwörter)[:\s]+",
            text,
            maxsplit=1,
        )[0]
        return text.strip()

    def parse(self):
        affs = self.parse_affiliations()
        authors = self.parse_authors()
        if authors and isinstance(authors[0], Author):
            authors = self.merge_authors_affiliations(authors, affs)
        authors = self._mark_corresponding_from_email_meta(authors)
        abstract = self.parse_abstract()
        return {
            'authors': authors,
            'abstract': abstract
        }
