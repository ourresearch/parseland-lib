import re
import unicodedata

from bs4 import NavigableString

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import is_h_tag, squash

# The contact block's first line names the corresponding author, after a lead-in and a title ("Correspondence to:
# Dr. Didier G. Ebo", "Dott. Filippo Salvati, via ...") and before an address, credentials or e-mail after a comma
_CONTACT_LEAD = re.compile(r"^(?:(?:address\s+for\s+)?correspondence(?:\s+to)?\s*:?\s*)", re.I)
_TITLE = re.compile(r"^(?:(?:prof|dr|dott|dres|med|mr|mrs|ms|mme|pd|priv\.-doz)\.?\s+)+", re.I)


def _plain(text):
    """Casefolded, accents dropped, whitespace squashed: "Müller-Stich" and "Muller-Stich" match."""
    text = unicodedata.normalize("NFKD", squash(text)).casefold()
    return "".join(c for c in text if not unicodedata.combining(c))


class Karger(PublisherParser):
    """Karger's own pages (www.karger.com/Article/FullText|Abstract/<id>) and its Silverchair-era pages (karger.com).

    Own pages: the byline is ``span.autoren`` ("Family I." names split by ``<span class="color">·</span>``, each with
    an optional ``<sup>`` of affiliation labels, a ``<br />`` after the last), ``div#cAffi`` the affiliations
    (labelled by ``<sup>``, or one unlabelled block for every author) and ``div#cAuthors`` the corresponding
    author's name and address. The last name of a byline without labels used to be lost, and with a sole author the
    page's affiliation (oxjob #2330: ~50K works lacked an affiliation the page prints); ``div#cAuthors`` was not read
    (~44K works with no corresponding author).

    Silverchair-era pages (``.al-author-name``) are read as before, and are mostly left to the generic reader:
    ``parse_authors_2`` fails on most of them. This parser also runs on other Silverchair publishers' pages (its
    ``authors_found`` is true there), so that path stays exactly as it was.
    """
    parser_name = "karger"

    def is_publisher_specific_parser(self):
        return self.domain_in_meta_og_url('karger.com')

    def authors_found(self):
        # Asked on every DOI page (#2239: under 0.5 ms a page it does not claim). Same answer as the CSS selects
        # 'span.autoren' or '.al-author-name' anywhere in the page, in one plain walk of the tree that reads each
        # tag's class list (~0.2 ms a page against ~1.4 ms for the two selects; oxjob #2330).
        for tag in self.soup.descendants:
            attrs = getattr(tag, "attrs", None)
            if not attrs or not (classes := attrs.get("class")):
                continue
            if isinstance(classes, str):
                classes = classes.split()
            if "al-author-name" in classes or ("autoren" in classes and tag.name == "span"):
                return True
        return False

    def parse_authors_2(self):
        author_tags = self.soup.select('.al-author-name')
        authors = []
        for author_tag in author_tags:
            name = author_tag.find('a').text
            author = {'name': name, 'affiliations': [], 'is_corresponding': bool(author_tag.select_one('.info-card-footnote'))}
            aff_tags = author_tag.select('.info-card-affilitation .aff')
            for aff_tag in aff_tags:
                label = aff_tag.find('span')
                label.decompose()
                author['affiliations'].append(aff_tag.text)
            authors.append(author)
        return authors

    def parse_affiliations(self):
        affs = {}
        if affs_tag := self.soup.select_one('div#cAffi'):
            current_sup = None
            for child in affs_tag.children:
                if child.name == 'br':
                    continue
                elif child.name == 'sup':
                    current_sup = child.text.strip()
                else:
                    affs[current_sup] = squash(child.text)  # one line: blocks may break lines mid-name
        return affs

    def parse_authors(self):
        authors_tag = self.soup.select_one('span.autoren')
        affiliations = self.parse_affiliations()
        current_author = None
        authors = []
        labels = {}  # id(author) -> the byline labels after the name (affiliations, and a co-corresponding note)
        for child in authors_tag.children:
            if isinstance(child, NavigableString):
                if len(child.text.strip()) >= 2:
                    current_author = {'name': child.text.strip(), 'affiliations': [],
                                      'is_corresponding': None}
                else:
                    continue
            elif child.name == 'sup':
                affs = child.text.split(',')
                for aff in affs:
                    if affiliations and aff in affiliations:
                        current_author['affiliations'].append(affiliations.get(aff))
                if current_author is not None:
                    labels[id(current_author)] = {a.strip() for a in affs}
                authors.append(current_author)
                current_author = None
            elif child.name == 'span':
                authors.append(current_author)
                current_author = None
            elif current_author is None and len(child.text.strip()) >= 2:
                current_author = {'name': child.text.strip(), 'affiliations': [], 'is_corresponding': None}
        # the last name has no label or separator after it, only a <br />: it is an author too (a sole author always)
        authors.append(current_author)
        authors = [author for author in authors if author]
        if len(affiliations) == 1:
            for author in authors:
                author['affiliations'] = affiliations.values()
        self._mark_corresponding(authors, labels)
        return authors

    @staticmethod
    def _family_and_initial(name):
        """("cherrad", "t") for "Cherrad T.", ("van gasse", "a") for "Van Gasse A.L."; None for a name without
        initials."""
        tokens = name.split()
        if len(tokens) < 2 or not ("." in tokens[-1] or tokens[-1].isupper()):
            return None
        return _plain(" ".join(tokens[:-1])), _plain(tokens[-1])[:1]

    def _mark_corresponding(self, authors, labels):
        """Mark the authors ``div#cAuthors`` names: its first line's name, matched to a byline "Family I." by family
        name and first initial, and any author whose byline label is footnoted there as co-corresponding. Nobody is
        marked unless exactly one byline name matches the contact."""
        contact = self.soup.select_one('div#cAuthors')
        if contact is None or not authors:
            return
        lines = [squash(p.get_text(" ")) for p in contact.find_all('p')] or [squash(contact.get_text(" "))]
        first = _TITLE.sub("", _CONTACT_LEAD.sub("", lines[0] if lines else "")).split(",")[0]
        name = _plain(first)
        matched = []
        for author in authors:
            parts = self._family_and_initial(author['name'])
            if parts and name.startswith(parts[1]) and (name == parts[0] or name.endswith(" " + parts[0])):
                matched.append(author)
        if len(matched) != 1:
            return
        marked = {id(matched[0])}
        for sup in contact.find_all('sup'):
            note = sup.next_sibling
            if isinstance(note, NavigableString) and "corresponding" in note.lower():
                marked |= {id(a) for a in authors if sup.get_text(strip=True) in labels.get(id(a), ())}
        for author in authors:
            author['is_corresponding'] = id(author) in marked

    def parse_abstract(self):
        if abs_heading := self.soup.find(lambda tag: is_h_tag(tag) and 'abstract' in tag.text.lower()):
            return abs_heading.find_next_sibling('p').text

    def parse(self):
        authors = self.parse_authors_2() if bool(self.soup.select('.al-author-name')) else self.parse_authors()
        return {'authors': authors, 'abstract': self.parse_abstract()}
