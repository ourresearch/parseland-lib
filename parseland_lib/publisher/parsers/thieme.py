import re

from bs4 import BeautifulSoup, NavigableString

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
        affs = []
        for tag in aff_tags:
            text = tag.get_text(" ", strip=True)
            sup_tag = tag.find('sup')
            if sup_tag:
                aff_id = sup_tag.get_text(" ", strip=True)
                org = re.sub(rf"^{re.escape(aff_id)}\s*", "", text).strip()
            else:
                aff_id = None
                org = text
            if not org:
                continue
            affs.append(Affiliation(organization=org, aff_id=aff_id))
        return affs

    def parse_authors(self):
        authors_tag = self.soup.select_one('.authors')
        authors = []
        if not authors_tag:
            return self._parse_citation_authors()

        # Older Thieme pages render "Name A, Name B" as a single text node with
        # no affiliation anchors. Citation metadata gives the reliable split.
        if not authors_tag.select_one('a[href^="#"]'):
            citation_authors = self._parse_citation_authors()
            if citation_authors:
                return citation_authors

        for tag in authors_tag:
            if isinstance(tag, NavigableString):
                name = tag.text.strip(' ,\n\r')
                if not name:
                    continue
                aff_ids = []
                aff_tag = tag
                while aff_tag.next_sibling and aff_tag.next_sibling.name == 'a':
                    aff_tag = aff_tag.next_sibling
                    aff_ids.append(aff_tag.text.strip())
                authors.append(Author(name, aff_ids))
        return self._dedupe_authors(authors)

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

    @staticmethod
    def _normalize_name(value):
        return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip().lower()

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
        abstract = self.parse_abstract()
        return {
            'authors': authors,
            'abstract': abstract
        }
