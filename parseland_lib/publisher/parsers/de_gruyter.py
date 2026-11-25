import re

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import EMAIL_RE, _fold_name, name_position

# "Corresponding author: ...", "Corresponding authors ...", "* Correspondence address: ...", "Korrespondenz: ..."
CORRESPONDING_NOTE = re.compile(
    r'^[\s*†]*(?:corresponding\s+authors?|(?:address\s+for\s+)?correspondence|korrespondenz\w*)\b', re.I)
EMAIL_PART = re.compile(rf'^\s*(?:e-?\s?mail\b|{EMAIL_RE.pattern}\s*$)', re.I)


def _email_owner(authors, email):
    """The one author an email's local part names (its surname, first initial + surname, surname + first initial,
    or 3+ initials: 'gatta', 'glauc', 'schneiderr', 'upv'), or None when none or several do."""
    tokens = set(re.split(r'[._+-]+', email.split('@', 1)[0].lower()))
    hits = []
    for author in authors:
        words = _fold_name(author['name']).split()
        if len(words) < 2:
            continue
        first, surnames = words[0][0], [w for w in words[1:] if len(w) >= 2]
        initials = ''.join(w[0] for w in words)
        if any(t in (s, first + s, s + first) for t in tokens for s in surnames) or (
                len(initials) >= 3 and initials in tokens):
            hits.append(author)
    return hits[0] if len(hits) == 1 else None


# A chapter page with no abstract has its citation line as og:description: "<chapter title> was published in <book> on
# page 53." A template, not an abstract (landing-pages charter § 6, 24 Oct 2026); ~67K works showed it (oxjob #2604).
CHAPTER_LINE = re.compile(r'^.{3,}? was published in .{2,400} on page [0-9ivxlcdm]+\.?$', re.I)


class DeGruyter(PublisherParser):
    parser_name = "de_gruyter"

    def is_publisher_specific_parser(self):
        return (
            self.domain_in_meta_og_url('degruyter.com')
            or self.domain_in_meta_og_url('degruyterbrill.com')
            or self.domain_in_canonical_link('degruyter.com')
            or self.domain_in_canonical_link('degruyterbrill.com')
        )

    def author_tags(self):
        # The degruyter.com template wraps each contributor in span.contributor. The degruyterbrill.com template
        # (2023 on) uses span.contributor-dgb inside li.contributors-<ROLE>; only AUTHOR rows are authors (a book
        # can list only its editors there). Without this the parser fell back to meta tags and lost every
        # affiliation and corresponding mark on current pages (oxjob #1808).
        return (self.soup.select('span.contributor')
                or self.soup.select('li.contributors-AUTHOR span.contributor-dgb'))

    def authors_found(self):
        return bool(self.author_tags() or self.parse_author_meta_tags())

    def parse_authors(self):
        author_tags = self.author_tags()
        authors = []
        for author_tag in author_tags:
            # span.displayName holds the name on both templates; the tag's whole text can also carry the
            # pop-up's biography ("Panu M. Jaakkola\n\nPanu M. Jaakkola MD, PhD currently works...", oxjob #2251).
            if display_name := author_tag.select_one('span.displayName'):
                name = display_name.get_text(' ', strip=True)
            else:
                name = author_tag.text.strip('\n ')
            if cont_popdown := author_tag.select_one('contributor-popdown'):
                is_corresponding = bool(cont_popdown.get('email', ''))
                affiliations = []
                for aff in cont_popdown.get('affiliations', '').split(';'):
                    aff = aff.strip()
                    if CORRESPONDING_NOTE.match(aff):
                        # IUPAC entries put "Corresponding author" in that author's own pop-up (oxjob #2251)
                        is_corresponding = True
                    elif aff and not EMAIL_PART.match(aff):
                        affiliations.append(aff)
            else:
                is_corresponding = '@' in author_tag.get('title', '')
                affiliations = [aff.strip() for aff in author_tag.get('title', '').split(';')
                                if '@' not in aff and aff.strip()]

            authors.append({
                'name': name,
                'is_corresponding': is_corresponding,
                'affiliations': affiliations
            })
        if not authors:
            authors = self.parse_author_meta_tags()
        authors = self.dedupe_authors(authors)
        if author_tags and 'contributor' in (author_tags[0].get('class') or []):  # the old template only
            self.mark_corresponding_from_notes(authors)
        return authors

    def mark_corresponding_from_notes(self, authors):
        """The degruyter.com template leaves every pop-up's email empty and names the corresponding author in a
        `div.correspondingAuthor` note instead. Fill-only: mark the author the note names, else the one its email
        names; address notes with no corresponding wording single no one out (oxjob #2251)."""
        if not authors or any(a.get('is_corresponding') for a in authors):
            return
        for note in self.soup.find_all('div', class_='correspondingAuthor'):
            text = note.get_text(' ', strip=True)
            if not CORRESPONDING_NOTE.match(text):
                continue
            named = [a for a in authors if name_position(a['name'], text) is not None]
            if len(named) == 1:
                named[0]['is_corresponding'] = True
                continue
            for email in EMAIL_RE.findall(text):
                if owner := _email_owner(authors, email):
                    owner['is_corresponding'] = True
        if any(a.get('is_corresponding') for a in authors):
            for a in authors:
                a['is_corresponding'] = bool(a.get('is_corresponding'))

    @staticmethod
    def dedupe_authors(authors):
        deduped = []
        seen = set()
        for author in authors:
            name = (author.get('name') or '').strip()
            if not name:
                continue
            key = re.sub(r'\s+', ' ', name).casefold()
            if key in seen:
                continue
            seen.add(key)
            author = dict(author)
            author['name'] = name
            deduped.append(author)
        return deduped

    def parse_abstract(self):
        paragraphs = self.soup.select('section[id*=_abs_] p')
        if paragraphs:
            text = self.clean_abstract_text(
                ' '.join([p.get_text(' ', strip=True) for p in paragraphs])
            )
            if text:
                return text

        if (text := self.parse_abstract_meta_tags()) and not (len(text) < 2500 and CHAPTER_LINE.match(text.strip())):
            return self.clean_abstract_text(text)

        if abstract_tag := self.soup.select_one('div.abstract'):
            text = self.clean_abstract_text(abstract_tag.get_text(' ', strip=True))
            if text:
                return text

        if text_container := self.soup.select_one('div#text-container'):
            raw_text = text_container.get_text(' ', strip=True)
            if re.match(
                    r'^(showing a limited preview of this publication:\s*)?'
                    r'(abstract|zusammenfassung)\b',
                    raw_text,
                    flags=re.I,
            ):
                text = self.clean_abstract_text(raw_text)
                if text and len(text) < 5000:
                    return text

        return None

    @staticmethod
    def clean_abstract_text(text):
        text = re.sub(r'\s+', ' ', text or '').strip()
        text = re.sub(
            r'^showing a limited preview of this publication:\s*',
            '',
            text,
            flags=re.I,
        )
        text = re.sub(
            r'^(abstract|zusammenfassung)\s*[:.]?\s*',
            '',
            text,
            flags=re.I,
        )
        return text or None

    def parse(self):
        return {'authors': self.parse_authors(),
                'abstract': self.parse_abstract()}
