import re
import unicodedata

from bs4 import NavigableString, Tag

from parseland_lib.publisher.parsers.parser import PublisherParser

_PUBLISHER_TAG = 'citation_publisher'
_CORRESPOND = re.compile(r'correspond', re.I)
# The words after the note's label, to the first comma: "Corresponding author: Peter A. Tass, Institute ...",
# "Address for correspondence: Dr. Hiroki Kamada, ...", "Correspondence to: Ramana M. Pidaparti, Ph.D., ...",
# "Corresponding author. Xiang Ziquan, School ...". "Corresponding author. Tel.: ..." names no one.
_NOTE_NAME = re.compile(r'correspond\w*(?:\s+(?:authors?|to))?\s*[:.]?\s*([^,;]+)', re.I)
_ISBN = re.compile(r'\bISBN\b')


def _fold(text):
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()


def _clean(text):
    return re.sub(r'\s+', ' ', text).strip(' |\n\t')


class IOSPress(PublisherParser):
    """IOS Press article pages on content.iospress.com (the journals' site until their move to SAGE in 2025).

    The byline, affiliations, correspondence notes and abstract are rows of div.front-meta-data, each a
    p.metadata-entry labelled by its first span.generated ("Authors: ", "Affiliations: ", "Correspondence: ",
    "Note: ", "Abstract: "). Book chapters on ebooks.iospress.nl carry the same citation_publisher tag but no such
    block: the meta-tag parser reads those (oxjob #2330).
    """
    parser_name = "ios_press"
    # the byline's marks and the notes they point to are the page's own; other parsers read names only
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        # Every parser is asked on every DOI page (#2239: under 0.5 ms a page it does not claim): the citation_publisher
        # tag is looked for in the small <head> only, and the answer is kept for authors_found() and parse().
        if getattr(self, '_claimed', None) is None:
            head = self.soup.head
            meta = head.find('meta', attrs={'name': _PUBLISHER_TAG}) if head is not None else None
            self._claimed = meta is not None and 'ios press' in (meta.get('content') or '').lower()
        return self._claimed

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._entries().get('authors'))

    def _entries(self):
        """The front-matter rows by label, lower-cased without the colon: {"authors": [p], "note": [p, p], ...}."""
        if getattr(self, '_rows', None) is None:
            self._rows = {}
            front = self.soup.find('div', class_='front-meta-data')
            for row in front.find_all(class_='metadata-entry', recursive=False) if front else []:
                label = row.find('span', class_='generated')
                if label is not None:
                    self._rows.setdefault(_clean(label.get_text()).rstrip(':').strip().lower(), []).append(row)
        return self._rows

    def _row(self, label):
        rows = self._entries().get(label)
        return rows[0] if rows else None

    def _notes(self):
        """{span id: text} for every note the byline can point to (the "Correspondence" and "Note" rows)."""
        notes = {}
        for label in ('correspondence', 'note'):
            for row in self._entries().get(label, []):
                for span in row.find_all('span', recursive=False):
                    if 'generated' not in (span.get('class') or []):
                        notes.setdefault(span.get('id') or '', []).append(_clean(span.get_text(' ')))
        return {key: ' '.join(texts) for key, texts in notes.items()}

    def parse_affiliations(self):
        """[(keys, text)] in page order; keys are the anchor's id and the printed letter ("aff1" and "a")."""
        row = self._row('affiliations')
        if row is None:
            return []
        affs, keys, parts, in_label = [], set(), [], False
        anchored = row.find('a', id=True) is not None

        def flush():
            text = _clean(' '.join(parts))
            if text and not _CORRESPOND.search(text):
                affs.append((set(keys), text))

        for node in list(row.children)[1:]:  # after the row's label
            if isinstance(node, Tag) and node.name == 'a' and node.get('id') is not None and not node.get('href'):
                flush()
                keys, parts = {node['id']}, []
            elif isinstance(node, Tag) and 'generated' in (node.get('class') or []):
                in_label = node.get_text().strip() == '['
            elif isinstance(node, Tag) and (node.select_one('.__cf_email__') is not None
                                            or '__cf_email__' in (node.get('class') or [])):
                continue  # an e-mail address, never part of the affiliation
            elif in_label:
                keys.add(node.get_text().strip())
            elif not anchored and isinstance(node, NavigableString) and '|' in node:
                for i, piece in enumerate(str(node).split('|')):
                    if i:
                        flush()
                        keys, parts = set(), []
                    parts.append(piece)
            else:
                parts.append(node.get_text(' ') if isinstance(node, Tag) else str(node))
        flush()
        return affs

    def parse_authors(self):
        row = self._row('authors')
        affs = self.parse_affiliations()
        notes = self._notes()
        authors = []
        for link in row.select('a[href*=author]') if row is not None else []:
            sup = link.find_next_sibling()
            targets = []
            if sup is not None and sup.name == 'sup' and sup.find_previous_sibling() is link:
                targets = [a['href'][1:] for a in sup.find_all('a', href=True) if a['href'].startswith('#')]
            authors.append({'name': _clean(link.get_text()), 'targets': [t for t in targets if t]})
        # Affiliations pointed to from elsewhere (a guest editor's) are not the authors'
        elsewhere = {a['href'][1:] for label, rows in self._entries().items() if label not in ('authors', 'affiliations')
                     for row_ in rows for a in row_.find_all('a', href=True) if a['href'].startswith('#')}
        linked = any(t in keys for author in authors for t in author['targets'] for keys, _ in affs)
        everyone = [text for keys, text in affs if not keys & elsewhere]
        for author in authors:
            if linked:
                mine = [text for t in author['targets'] for keys, text in affs if t in keys]
                author['affiliations'] = list(dict.fromkeys(mine))
            else:
                author['affiliations'] = list(everyone)  # the page does not say who has which: everyone has all
            author['is_corresponding'] = any(_CORRESPOND.search(notes.get(t, '')) for t in author['targets'])
        if authors and not any(author['is_corresponding'] for author in authors):
            self._mark_named_correspondents(authors, notes)
        return [{key: author[key] for key in ('name', 'affiliations', 'is_corresponding')} for author in authors]

    @staticmethod
    def _mark_named_correspondents(authors, notes):
        """A correspondence note no byline mark points to names its author: match the surname (the byline prints
        "Surname, Given") in the words after the note's label; a shared surname needs the given name's initial."""
        for text in notes.values():
            if not (m := _NOTE_NAME.search(text)):
                continue
            named = _fold(m.group(1))
            hits = []
            for author in authors:
                surname, _, given = author['name'].partition(',')
                surname = _fold(surname.strip())
                if surname and re.search(r'(?<![a-z])' + re.escape(surname) + r'(?![a-z])', named):
                    hits.append((author, _fold(given.strip())[:1]))
            if len(hits) > 1:
                hits = [(a, g) for a, g in hits if g and re.search(r'(?<![a-z])' + re.escape(g), named)]
            if len(hits) == 1:
                hits[0][0]['is_corresponding'] = True

    def parse_abstract(self):
        row = self._row('abstract')
        if row is None:
            return self._full_text_abstract()
        # the text is cut into a shown part and a "below-fold" part, often mid-word: join them as printed
        text = _clean(''.join(span.get_text() for span in row.find_all('span', recursive=False)
                              if 'generated' not in (span.get('class') or [])))
        article_type = self._row('article type')
        if article_type is not None and 'book review' in article_type.get_text().lower() and _ISBN.search(text):
            return None  # a book review's "Abstract" row cites the book reviewed
        return text or None

    def _full_text_abstract(self):
        """The abstract the full text's front matter prints under its "Abstract" callout, for pages whose front-matter
        block has no Abstract row (10.3233/adr-230088): every section, "Background: ..." to "Conclusions: ...", one per
        line. The generic heading reader kept only the first section (#2239)."""
        front = self.soup.select_one('section.nlm-article div.front')
        title = front.find('h4', class_='callout-title', recursive=False) if front is not None else None
        if title is None or _clean(title.get_text(' ')).lower() != 'abstract':
            return None
        parts = []
        for node in title.find_next_siblings():
            if node.name == 'h4':  # the next callout ("Keywords")
                break
            if node.name == 'p':
                parts.append(_clean(node.get_text()))
            elif node.name == 'div' and 'section' in (node.get('class') or []):
                heading = node.find(class_='section-title')
                paras = [_clean(p.get_text()) for p in node.find_all('p')]
                text = '\n'.join(p for p in paras if p)
                parts.append(_clean(heading.get_text(' ')) + ' ' + text if heading is not None and text else text)
        return '\n'.join(p for p in parts if p) or None

    def parse(self):
        return {'authors': self.parse_authors(),
                'abstract': self.parse_abstract()}
