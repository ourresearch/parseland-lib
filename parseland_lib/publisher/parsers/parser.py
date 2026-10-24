import copy
import re
from abc import ABC, abstractmethod

from parseland_lib.elements import AuthorAffiliations, Author
from parseland_lib.legacy_parse_utils.fulltext import \
    parse_publisher_fulltext_location
from parseland_lib.legacy_parse_utils.strings import cleanup_soup
from parseland_lib.not_abstract import is_not_abstract
from parseland_lib.publisher.parsers.utils import remove_parents, strip_seq, \
    strip_prefix, \
    is_h_tag


class Parser(ABC):

    @abstractmethod
    def parse(self):
        pass

    @staticmethod
    @abstractmethod
    def no_authors_output():
        pass


def frontmatter_abstract(soup):
    """The abstract in Atypon's ``<div id="abstracts" data-extent="frontmatter">`` block, or None.

    Atypon sites (Elsevier society sites, RSNA, Neurology, CABI ...) put the full abstract there: either sections
    (``#abstract`` / ``#author-abstract`` beside editor summaries, highlights and graphical abstracts) or, for
    meeting abstracts and research letters, bare paragraphs with no heading. Their meta tags cut it to the first
    200 characters or first section (oxjob #1794 for Elsevier, #1800 for the rest).
    """
    block = soup.select_one('#abstracts[data-extent="frontmatter"]')
    if block is None:
        return None
    sections = block.find_all("section")
    if sections:
        chosen = next((s for s in sections if s.get("id") in ("author-abstract", "abstract")), None)
        if chosen is None:
            return None
        text = chosen.get_text(" ", strip=True)
        heading = chosen.find(re.compile("^h[1-6]$"))
        heading_text = heading.get_text(" ", strip=True) if heading is not None else ""
        if heading_text and text.startswith(heading_text):
            text = text[len(heading_text):]
    else:
        text = block.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def silverchair_abstract(soup):
    """The abstract in a Silverchair article page's ``section.abstract`` (AIP, OUP, Karger, Emerald ...), or None.

    Silverchair meta descriptions stop at ~160 characters, under the parsers' 200-character floor, so a page no
    publisher parser claims (the new pubs.aip.org) came out with no abstract (oxjob #1800). Paragraph text is
    joined as Oxford's parser does it (tag.text keeps CO<sub>2</sub> as CO2).
    """
    section = soup.select_one("div.widget-ArticleFulltext section.abstract")
    if section is None:
        return None
    paras = [p.text.strip() for p in section.find_all("p") if p.text and p.text.strip()]
    text = "\n".join(paras) if paras else " ".join(section.text.split())
    text = re.sub(r"^abstract[:.]?\s*", "", text.strip(), flags=re.I)
    return text or None


class PublisherParser(Parser, ABC):
    def __init__(self, soup):
        self.soup = soup

    @property
    @abstractmethod
    def parser_name(self):
        pass

    @abstractmethod
    def is_publisher_specific_parser(self):
        pass

    @abstractmethod
    def authors_found(self):
        pass

    @staticmethod
    def no_authors_output():
        return {"authors": [], "abstract": None, "published_date": None,
                "genre": None}

    def domain_in_canonical_link(self, domain):
        canonical_link = self.soup.find("link", {"rel": "canonical"})
        return (
                canonical_link
                and canonical_link.get("href")
                and domain in canonical_link.get("href")
        )


    def domain_in_meta_og_url(self, domain):
        meta_og_url = self.soup.find("meta",
                                     property="og:url") or self.soup.select_one(
            'meta[name="og:url"]')
        return (meta_og_url
                and meta_og_url.get("content")
                and domain in meta_og_url.get("content")
                )

    def substr_in_citation_journal_title(self, substr):
        if tag := self.soup.select_one('meta[name="citation_journal_title"]'):
            content = tag.get('content')
            return substr.lower() in content.lower()
        return False

    def substr_in_citation_publisher(self, substr):
        if tag := self.soup.select_one('meta[name="citation_publisher"]'):
            content = tag.get('content')
            return substr.lower() in content.lower()
        return False

    def text_in_meta_og_site_name(self, txt):
        meta_og_site_name = self.soup.find('meta',
                                           property='og:site_name') or self.soup.select_one(
            'meta[name="og:site_name"]')
        return (meta_og_site_name
                and meta_og_site_name.get("content")
                and txt in meta_og_site_name.get("content")
                )

    def parse_author_meta_tags(self, corresponding_tag=None,
                               corresponding_class=None):
        results = []
        metas = self.soup.findAll("meta")

        corresponding_text = None
        if corresponding_tag and corresponding_class:
            corresponding_text = self.get_corresponding_text(
                corresponding_tag, corresponding_class
            )

        author_meta_keys = {'citation_author', 'dc.Creator', 'bepress_citation_author'}

        result = None
        for meta in metas:
            if 'name' in meta.attrs and meta['name'] in author_meta_keys or 'property' in meta.attrs and meta['property'] in author_meta_keys:
                if result:
                    # reset for next author
                    results.append(result)
                    result = None
                if not (name := meta.get('content')):
                    continue
                if corresponding_text and name.lower() in corresponding_text:
                    is_corresponding = True
                elif corresponding_text and name.lower() not in corresponding_text:
                    is_corresponding = False
                else:
                    is_corresponding = None
                result = {
                    "name": name.strip(),
                    "affiliations": [],
                    "is_corresponding": is_corresponding,
                }
            if meta.get("name", None) and meta[
                "name"] in ("citation_author_institution", "bepress_citation_author_institution"):
                # An institution with no named author open has no one to attach to: an empty
                # citation_author (OJS sites with blank author names, e.g. in-academy.uz) or a
                # tag before the first author. Drop it rather than crash the whole page
                # (Sentry PARSELAND-2, ~590 pages/day; oxjob #1794).
                if result is not None and meta.get("content") and meta["content"].strip():
                    result["affiliations"].append(meta["content"].strip())

        # append name from last loop
        if result:
            results.append(result)

        return results

    def parse_abstract_meta_tags(self, include_seo_tags: bool = True):
        # citation_abstract / dc.description are article-level metadata.
        # og:description and description are page-level SEO tags: on many
        # institutional repositories they carry the same site blurb on every
        # record page, not the paper's abstract (oxjob #23518 — 48,180 UTokyo
        # works published the repository description as their abstract, and
        # 42,928 of them were then given topics derived from it). Callers that
        # know their publisher emits an article-specific og:description keep
        # the default; the generic parser opts out.
        meta_tag_names = ["citation_abstract", "dc.description"]
        if include_seo_tags:
            meta_tag_names = [
                "citation_abstract",
                "og:description",
                "dc.description",
                "description",
            ]
        meta_property_names = ["property", "name"]

        # The first matching tag decides, as before, with one exception (oxjob #1800): a page can carry a
        # journal blurb in its first DC.Description and the article's abstract in the next one, so a
        # candidate that is not an abstract hands over to the next tag of the same name.
        for meta_tag_name in meta_tag_names:
            for meta_property_name in meta_property_names:
                for meta_tag in self.soup.find_all(
                        "meta", {
                            meta_property_name: re.compile(f"^{meta_tag_name}$",
                                                           re.I)}
                ):
                    description = meta_tag.get("content", '').strip()
                    if not (
                            len(description) > 200
                            and not description.endswith("...")
                            and not description.endswith("…")
                            and not description.startswith("http")
                    ):
                        break
                    if is_not_abstract(description):
                        continue
                    return re.sub(
                        r"^abstract[:.]?\s*", "", description,
                        flags=re.I
                    )

        return None

    @staticmethod
    def format_name(name):
        return " ".join(reversed(name.split(", ")))

    @staticmethod
    def merge_authors_affiliations(authors, affiliations):
        results = []
        for author in authors:
            author_affiliations = []
            if not isinstance(author, Author):
                results.append(author)
                continue

            # scenario 1 affiliations with ids
            for aff_id in author.aff_ids:
                for aff in affiliations:
                    if aff_id == aff.aff_id:
                        author_affiliations.append(str(aff.organization))

            # scenario 2 affiliations with no ids (applied to all authors)
            for aff in affiliations:
                if (len(author.aff_ids) == 0 and aff.aff_id is None) or (
                        len(affiliations) == 1 and len(
                    author_affiliations) == 0):
                    author_affiliations.append(str(aff.organization))

            results.append(
                AuthorAffiliations(
                    name=author.name,
                    affiliations=author_affiliations,
                    is_corresponding=author.is_corresponding,
                )
            )
        return results

    def format_ids(self, ids, chars_to_ignore=None):
        ids_cleaned = ids.strip()
        if chars_to_ignore:
            for char in chars_to_ignore:
                ids_cleaned = ids_cleaned.replace(f",{char}", "").replace(
                    f"{char}", "")
        ids_split = ids_cleaned.split(",")
        aff_ids = []
        for aff_id in ids_split:
            if aff_id and aff_id.isdigit():
                aff_ids.append(int(aff_id))
        return aff_ids

    def fallback_mark_corresponding_authors(self, authors):
        def func(tag):
            for attr, value in tag.attrs.items():
                if ('author' in str(value).lower() and
                        tag.select_one('a[href*=mailto]')):
                    return True
            return False

        tags = self.soup.find_all(func)

        # Return only smallest tags, we don't want any tags with class*= authors that may contain multiple author names
        final_tags = remove_parents(tags)

        for tag in final_tags:
            tag_str = str(tag)
            for author in authors:
                if author['name'] in tag_str:
                    author['is_corresponding'] = True
                elif ',' in author['name']:
                    if all([name.strip(' ') in tag_str for name in
                            author['name'].split(',')]):
                        author['is_corresponding'] = True
        return authors

    def fallback_parse_abstract(self):
        blacklisted_words = {'download options', 'please wait',
                             'copyright clearance center', 'procite',
                             'food funct', 'rsc publication'}
        startswith_blacklist = {'download'}
        for tag in self.soup.find_all():
            for attr, value in tag.attrs.items():
                if 'abstract' in str(value).lower() or (
                        tag.text.lower() == 'abstract' and is_h_tag(tag)):
                    for desc in tag.descendants:
                        abs_txt = strip_seq(r'\s',
                                            strip_prefix('abstract', desc.text,
                                                         flags=re.IGNORECASE))
                        if len(desc.text) > 100 and desc.name in {'p', 'div',
                                                                  'span',
                                                                  'section',
                                                                  'article'} \
                                and not any(
                            [abs_txt.lower().startswith(word) for word in
                             startswith_blacklist]) \
                                and not any([word in abs_txt.lower() for word in
                                             blacklisted_words]):
                            return abs_txt
        return None

    def parse_fulltext_locations(self):
        return parse_publisher_fulltext_location(self.soup, cleanup_soup(copy.deepcopy(self.soup)))


    test_cases = []
