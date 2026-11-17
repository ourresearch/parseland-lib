import copy
import re
import unicodedata
from urllib.parse import unquote

from bs4 import BeautifulSoup, NavigableString, Tag

from parseland_lib.elements import Author, AuthorAffiliations, Affiliation
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

_DOI_LINK = re.compile(r"doi\.org/10\.")
_LEADING_NUMBER = re.compile(r"^(\d+)(?:\s+|$)")  # "1 Buckwold V E, ..." (an older list prints its number as text)
_MORE = re.compile(r"\b(?:show|load|view|see) (?:more|all)\b", re.I)


def _has_thieme_mark(soup):
    """The claim (oxjob #2289), from the four marks it always used: the platform's description ("Thieme E-Books &
    E-Journals", on every stored Thieme Connect page), an og:url on thieme-connect, a canonical link on a thieme host,
    a citation_publisher naming Thieme. Every parser's claim runs on every DOI page (#2239: under 0.5 ms a page it does
    not claim), so only <head>'s direct children are read; a page with no <head> has its <meta> and <link> tags
    scanned by name, never a CSS select over the whole tree."""
    html = soup.find("html", recursive=False)
    head = (html or soup).find("head", recursive=False)
    tags = head.find_all(("meta", "link"), recursive=False) if head is not None else soup.find_all(("meta", "link"))
    for tag in tags:
        if tag.name == "link":
            if "canonical" in (tag.get("rel") or []) and "thieme" in (tag.get("href") or ""):
                return True
            continue
        name, content = tag.get("name") or tag.get("property"), tag.get("content") or ""
        if (name == "description" and content.startswith("Thieme")) or (
                name == "og:url" and "thieme-connect" in content) or (
                name == "citation_publisher" and "thieme" in content.lower()):
            return True
    return False


def _has_byline_mark(soup):
    """An element of class "authors" or a citation_author meta tag anywhere in the page (the old CSS selects
    '.authors' and 'meta[name="citation_author"]'), in one walk that ends at the first one."""
    for tag in soup.descendants:
        attrs = getattr(tag, "attrs", None)
        if attrs and ("authors" in (attrs.get("class") or ()) or (
                tag.name == "meta" and attrs.get("name") == "citation_author")):
            return True
    return False


class Thieme(PublisherParser):
    parser_name = "thieme"

    def __init__(self, soup):
        super().__init__(soup)
        self._claimed = None

    def is_publisher_specific_parser(self):
        if self._claimed is None:
            self._claimed = _has_thieme_mark(self.soup)
        return self._claimed

    def authors_found(self):
        # True on any page with an .authors element or a citation_author tag, as it always was: on pages of other
        # platforms this parser is a fallback that some of them depend on (Actavia's <dt class="authors"> byline and
        # <dd class="affiliation"> list are read here). Every DOI page asks this (#2239: under 0.5 ms a page it does
        # not claim), so the two tests are one walk that stops at the first match, not two CSS selects (#2289:
        # 0.3 ms a page on 300 other templates' pages, was 2.2 ms).
        return bool(
            _has_byline_mark(self.soup)
            or (self.is_publisher_specific_parser() and self.soup.find(id='abstract'))
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
        # only on Thieme Connect's own pages: on other platforms' pages this parser is a fallback (authors_found)
        references, references_complete = self.parse_references() if self.is_publisher_specific_parser() \
            else (None, False)
        return {
            'authors': authors,
            'abstract': abstract,
            'references': references,
            'references_complete': references_complete,
        }

    def parse_references(self):
        """(references, references_complete) from the list the abstract page prints under its References tab
        (<section id="references"><ul class="literaturliste">, oxjob #2289). Each item is one entry, numbered in a
        <strong> (newer pages) or as its first text (older ones); an item holding the <h3> is the list's heading, an
        empty item is the placeholder of a page with no list. Whole only when every entry is numbered and the numbers
        run 1..n, there is one list, no placeholder and nothing saying there are more."""
        # imported here: back_matter imports the parsers package, which imports this module
        from parseland_lib.back_matter import _clean_doi, _pick_doi, _printed_doi

        section = self.soup.find("section", id="references")
        lists = section.find_all("ul", class_="literaturliste") if section is not None else []
        refs, numbers, placeholder = [], [], False
        for item in (li for ul in lists for li in ul.find_all("li", recursive=False)):
            if item.find("h3") is not None:
                continue
            item = copy.copy(item)  # the other parsers still read this soup
            links = item.find("div", class_="referenceLinks")  # the Crossref / PubMed / Google Scholar buttons
            doi_link = links.find("a", href=_DOI_LINK) if links is not None else None
            linked_doi = _clean_doi(unquote(doi_link["href"])) if doi_link is not None else None
            for block in item.find_all("div", class_="referenceLinks"):
                block.decompose()
            number = None
            first = next((c for c in item.children if not (isinstance(c, NavigableString) and not c.strip())
                          and not (isinstance(c, Tag) and c.name == "a" and not c.get_text(strip=True))), None)
            if isinstance(first, Tag) and first.name == "strong" and first.get_text(strip=True).isdecimal():
                number = int(first.get_text(strip=True))
                first.decompose()
            raw = squash(item.get_text())
            if number is None and (found := _LEADING_NUMBER.match(raw)):
                number, raw = int(found.group(1)), raw[found.end():]
            if not raw:
                placeholder = True
                continue
            doi = _pick_doi(linked_doi, _printed_doi(raw))
            numbers.append(number)
            refs.append({"position": len(refs) + 1, "raw": raw, "doi": doi})
        if not refs:
            return None, False
        whole = (len(lists) == 1 and not placeholder and numbers == list(range(1, len(refs) + 1))
                 and not _MORE.search(section.get_text(" ")))
        return refs, whole
