import re

from bs4 import NavigableString, Tag

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
import html

from parseland_lib.publisher.parsers.utils import strip_prefix, cleanup_raw_name, same_person

_MAILTO = re.compile(r"^mailto:", re.I)


def _og_url_in_head(soup):
    """The page's og:url, read from <head> only. Every parser's authors_found() runs on every DOI page (#2239: under
    0.5 ms a page it does not claim), so <head> is reached through direct children and searched alone; the whole-page
    select below runs only on publish.csiro.au pages (the select alone cost 1.0 ms a page, #2338)."""
    head = (soup.find("html", recursive=False) or soup).find("head", recursive=False)
    tag = head.find("meta", attrs={"property": "og:url"}) if head else None
    return (tag.get("content") or "") if tag else ""


class CSIRO(PublisherParser):
    parser_name = "csiro_publishing"

    def is_publisher_specific_parser(self):
        return self.domain_in_meta_og_url('publish.csiro.au')

    def authors_found(self):
        if 'publish.csiro.au' not in _og_url_in_head(self.soup):
            return False
        return bool(self.soup.select('.editors')) or bool(self.old_byline_links())

    def old_byline_links(self):
        """Names the old byline links to an e-mail address. Articles from before about 2004 print
        <div class="Editors"> (capital E): plain names, the one the site has an address for wrapped in a mailto link,
        which citation_author_email repeats (oxjob #2338)."""
        byline = self.soup.find("div", class_="Editors")
        if not byline:
            return []
        return [name for a in byline.find_all("a", href=_MAILTO) if (name := a.get_text(" ", strip=True))]

    def parse_old_byline(self):
        """The old byline's mailto link marks that author as corresponding (the gold marks the one author whose
        e-mail the byline shows; a link on every author is no mark). Authors and abstract stay the generic reader's,
        which won these pages before: their citation_author tags list the byline in order."""
        parsed = GenericPublisherParser(self.soup).parse()
        authors = [dict(a) for a in parsed.get("authors") or []]
        linked = self.old_byline_links()
        if any(a.get("is_corresponding") for a in authors) or (len(authors) > 1 and len(linked) >= len(authors)):
            return parsed
        for name in linked:
            matches = [a for a in authors if same_person(a["name"], name)]
            if len(matches) == 1:
                matches[0]["is_corresponding"] = True
        if not any(a.get("is_corresponding") for a in authors):
            return parsed
        for a in authors:
            if a.get("is_corresponding") is None:
                a["is_corresponding"] = False
        return {**parsed, "authors": authors}

    def parse_affs(self):
        affs = {}
        aff_tags = self.soup.select('#full-description p')
        for aff_tag in aff_tags:
            sup = aff_tag.find('sup')
            num = sup.text.strip()
            sup.decompose()
            aff_text = aff_tag.text.strip()
            affs[num] = aff_text
        return affs

    def parse_authors(self):
        authors_tag = self.soup.select_one('.editors')
        authors = []
        affs = self.parse_affs()
        for tag in authors_tag.children:
            if isinstance(tag, NavigableString):
                if name := cleanup_raw_name(tag.text):
                    author = {'name': name,
                              'affiliations': [],
                              'is_corresponding': None}
                    authors.append(author)
            elif isinstance(tag, Tag) and tag.name == 'sup':
                num = tag.text.strip()
                aff = affs[num]
                if 'corresponding' in aff.lower():
                    authors[-1]['is_corresponding'] = True
                else:
                    authors[-1]['affiliations'].append(affs[num])
        return authors

    def mark_corresponding(self, authors):
        authors_tag = self.soup.select_one('.editors')
        current_name = None
        for child in authors_tag.children:
            if isinstance(child, NavigableString):
                if name := html.unescape(
                        re.sub('^and', '', child.text.strip()).strip(' .,')):
                    current_name = name
            elif isinstance(child,
                            Tag) and child.name == 'sup' and child.text.strip() == '*':
                for author in authors:
                    if author['name'] == current_name:
                        author['is_corresponding'] = True
        return authors

    def parse(self):
        if not self.soup.select_one('.editors'):
            return self.parse_old_byline()
        authors = self.parse_author_meta_tags()
        authors = self.mark_corresponding(authors)
        if not any([author['is_corresponding'] for author in authors]):
            authors = self.parse_authors()

        return {'authors': authors,
                'abstract': self.parse_abstract_meta_tags()}
