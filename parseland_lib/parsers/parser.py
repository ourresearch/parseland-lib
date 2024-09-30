import copy
import re
from abc import ABC, abstractmethod
from urllib.parse import urljoin, urlparse

from parseland_lib.elements import AuthorAffiliations, Author
from parseland_lib.parsers.utils import remove_parents, strip_seq, strip_prefix, \
    is_h_tag


class Parser(ABC):

    @abstractmethod
    def parse(self):
        pass

    @staticmethod
    @abstractmethod
    def no_authors_output():
        pass


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

        author_meta_keys = {'citation_author', 'dc.Creator'}

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
                "name"] == "citation_author_institution":
                if meta.get("content") and meta["content"].strip():
                    result["affiliations"].append(meta["content"].strip())

        # append name from last loop
        if result:
            results.append(result)

        return results

    def parse_abstract_meta_tags(self):
        meta_tag_names = [
            "citation_abstract",
            "og:description",
            "dc.description",
            "description",
        ]
        meta_property_names = ["property", "name"]

        for meta_tag_name in meta_tag_names:
            for meta_property_name in meta_property_names:
                if meta_tag := self.soup.find(
                        "meta", {
                            meta_property_name: re.compile(f"^{meta_tag_name}$",
                                                           re.I)}
                ):
                    if description := meta_tag.get("content", '').strip():
                        if (
                                len(description) > 200
                                and not description.endswith("...")
                                and not description.endswith("…")
                                and not description.startswith("http")
                        ):
                            description = re.sub(
                                r"^abstract[:.]?\s*", "", description,
                                flags=re.I
                            )
                            return description

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
                        abs_txt = strip_seq('\s',
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

    def parse_pdf_link(self, soup, resolved_url=None, publisher=None):
        pdf_info = {
            'pdf_url': None,
            'anchor_text': None,
            'source': None
        }

        def transform_pdf_url(url):
            transformations = [
                (r'(https?://[\w\.]*onlinelibrary\.wiley\.com/doi/)pdf(/.+)',
                 r'\1pdfdirect\2'),
                (r'(^https?://drops\.dagstuhl\.de/.*\.pdf)/$', r'\1'),
                (r'^(https?://repository\.ubn\.ru\.nl/bitstream/)(\d+.*\.pdf)$',
                 r'\1handle/\2'),
                (r'^http://(journal\.nileuniversity\.edu\.ng/?.*)',
                 r'https://\1'),
                (r'^http://virginialibrariesjournal\.org//articles',
                 r'http://virginialibrariesjournal.org/articles'),
                (r'^http://www.(ecologyandsociety.org/.*.pdf)',
                 r'https://www.\1'),
                (r'^https?://recyt\.fecyt\.es/index\.php/EPI/article/view/',
                 lambda m: m.group(0).replace('/article/view/',
                                              '/article/download/')),
                (r'^https?://(www\.)?mitpressjournals\.org/doi/full/10\.',
                 lambda m: m.group(0).replace('/doi/full/', '/doi/pdf/')),
                (r'^https?://(www\.)?journals\.uchicago\.edu/doi/full/10\.',
                 lambda m: m.group(0).replace('/doi/full/', '/doi/pdf/')),
                (r'^https?://(www\.)?ascopubs\.org/doi/full/10\.',
                 lambda m: m.group(0).replace('/doi/full/', '/doi/pdfdirect/')),
                (r'^https?://(www\.)?ahajournals\.org/doi/reader/10\.',
                 lambda m: m.group(0).replace('/doi/reader/', '/doi/pdf/')),
                (r'^https?://(www\.)?journals\.sagepub\.com/doi/reader/10\.',
                 lambda m: m.group(0).replace('/doi/reader/', '/doi/pdf/')),
                (r'^https?://(www\.)?tandfonline\.com/doi/epdf/10\.',
                 lambda m: m.group(0).replace('/doi/epdf/', '/doi/pdf/')),
                (r'^https?://(www\.)?ajronline\.org/doi/epdf/10\.',
                 lambda m: m.group(0).replace('/doi/epdf/', '/doi/pdf/')),
                (r'^https?://(www\.)?pubs\.acs\.org/doi/epdf/10\.',
                 lambda m: m.group(0).replace('/doi/epdf/', '/doi/pdf/')),
                (r'^https?://(www\.)?royalsocietypublishing\.org/doi/epdf/10\.',
                 lambda m: m.group(0).replace('/doi/epdf/', '/doi/pdf/')),
                (r'^https?://(www\.)?onlinelibrary\.wiley\.com/doi/epdf/10\.',
                 lambda m: m.group(0).replace('/epdf/', '/pdfdirect/')),
                (r'^https?://(journals\.)?healio\.com/doi/epdf/10\.',
                 lambda m: m.group(0).replace('/doi/epdf/', '/doi/pdf/')),
                (r'^https?://(pubs\.)?rsna\.org/doi/epdf/10\.',
                 lambda m: m.group(0).replace('/doi/epdf/', '/doi/pdf/')),
            ]

            for pattern, replacement in transformations:
                if callable(replacement):
                    url = replacement(re.match(pattern, url))
                else:
                    url = re.sub(pattern, replacement, url)

            # Handle Nature PDFs
            if url.startswith(
                    'https://www.nature.com/articles/') and url.endswith(
                    '.pdf'):
                reference_pdf = re.sub(r'\.pdf$', '_reference.pdf', url)
                if reference_pdf in str(soup):
                    return reference_pdf

            return url

        def is_valid_pdf_link(href, anchor_text):
            """Check if the link is a valid PDF link based on href and anchor text."""
            if not href:
                return False

            # Blacklist of bad href words/patterns
            bad_href_patterns = [
                "/eab/", "/suppl_file/", "supplementary+file",
                "showsubscriptions", "/faq", "{{",
                "cdt-flyer", "figures", "price-lists", "aaltodoc_pdf_a.pdf",
                "janssenmd.com",
                "community-register", "quickreference", "libraryrequestform",
                "iporeport",
                "no_local_copy", ".zip", ".gz", ".tar.", "/doi/full/10.1642",
                "hyke.org",
                "&rendering=", ".fmatter", "/samples/", "letter_to_publisher",
                "first-page",
                "lib_rec_form", "ebook-flyer", "accesoRestringido",
                "/productFlyer/",
                "/author_agreement", "supinfo.pdf", "/Appendix", "BookTOC.pdf",
                "BookBackMatter.pdf",
                "publishers-catalogue", "_toc_", "adobe.com/products/acrobat",
                "featured-article-pdf",
                "modern-slavery-act-statement.pdf", "Deposit_Agreement",
                "/product_flyer/",
                "links.lww.com/JBJS/F791", "ctr_media_kit",
                "ctr_advertising_rates",
                "format=googlePreviewPdf", "type=googlepdf", "guide_authors",
                "_TOC.pdf",
                "_BookBackMatter.pdf", "_BookTOC.pdf", "-supplement.pdf",
                "ethicspolicy.pdf",
                "coi_disclosure.pdf", "_leaflet.pdf", "User-manual.pdf",
                "table_final.pdf",
                "/doi/full/10.18553/jmcp.", "Bilkent-research-paper.pdf",
                "guia_busquedas_avanzadas.pdf",
                "PDFs/2017-Legacy-1516816496183.pdf", "TermsOfUse.pdf",
                "javascript:void",
                "/DownloadSummary/", "WOS000382116900027.pdf"
            ]

            if any(pattern in href.lower() for pattern in bad_href_patterns):
                return False

            # Blacklist of bad anchor text words/patterns
            bad_anchor_patterns = [
                "user", "guide", "checklist", "abstracts",
                "downloaded publications",
                "metadata from the pdf file",
                "récupérer les métadonnées à partir d'un fichier pdf",
                "bulk downloads", "license agreement", "masthead",
                "download statistics",
                "supplement", "figure", "faq", "download MODS",
                "BibTeX citations", "RIS citations",
                "ACS ActiveView PDF", "Submission Form", "Sample Pages",
                "Download this page",
                "Download left page", "Download right page", "author agreement",
                "map to our office",
                "download flyer", "download extract", "Call for Papers",
                "View PDF Flyer",
                "Full Text HTML",
                "Submitting an item to the Open Research repository",
                "Download our catalogue", "Reprint Order Form",
                "Cost Confirmation and Order Form"
            ]

            if any(pattern.lower() in anchor_text.lower() for pattern in
                   bad_anchor_patterns):
                return False

            return True

        # Check for citation_pdf_url in meta tags
        meta_pdf = self.soup.find('meta', attrs={'name': 'citation_pdf_url'}) or \
                   self.soup.find('meta', attrs={'property': 'citation_pdf_url'})
        if meta_pdf and 'content' in meta_pdf.attrs:
            pdf_url = transform_pdf_url(meta_pdf['content'])
            if is_valid_pdf_link(pdf_url, '<meta citation_pdf_url>'):
                pdf_info['pdf_url'] = pdf_url
                pdf_info['anchor_text'] = '<meta citation_pdf_url>'
                pdf_info['source'] = 'meta'
                return pdf_info

        # Check for PDF link in anchors
        for link in self.soup.find_all('a', href=True):
            href = link['href']
            anchor_text = link.get_text(strip=True)

            if href.lower().endswith('.pdf') or 'pdf' in anchor_text.lower():
                full_url = urljoin(resolved_url, href) if resolved_url else href
                if is_valid_pdf_link(full_url, anchor_text):
                    pdf_info['pdf_url'] = transform_pdf_url(full_url)
                    pdf_info['anchor_text'] = anchor_text
                    pdf_info['source'] = 'anchor'
                    return pdf_info

        # Check for PDF link in JavaScript
        script_content = self.soup.find('script', text=re.compile(
            r'pdfUrl|exportPdfDownloadUrl'))
        if script_content:
            match = re.search(r'"(pdfUrl|exportPdfDownloadUrl)":\s*"(.+?)"',
                              script_content.string)
            if match:
                pdf_url = transform_pdf_url(match.group(2))
                if is_valid_pdf_link(pdf_url, match.group(1)):
                    pdf_info['pdf_url'] = pdf_url
                    pdf_info['anchor_text'] = match.group(1)
                    pdf_info['source'] = 'javascript'
                    return pdf_info

        # Additional checks for specific sites
        if resolved_url:
            parsed_url = urlparse(resolved_url)

            if 'citeseerx.ist.psu.edu' in parsed_url.netloc:
                download_link = self.soup.find('h3', text='Download Links')
                if download_link and download_link.find_next('a'):
                    pdf_info['pdf_url'] = download_link.find_next('a')['href']
                    pdf_info['anchor_text'] = 'Download'
                    pdf_info['source'] = 'citeseer'
            elif 'osf.io' in parsed_url.netloc or 'osf-cookie' in str(soup):
                pdf_info['pdf_url'] = f"{resolved_url.rstrip('/')}/download"
                pdf_info['anchor_text'] = 'OSF Download'
                pdf_info['source'] = 'osf'
            elif parsed_url.netloc.endswith('contentdm.oclc.org'):
                match = re.search(r'/id/(\d+)', parsed_url.path)
                if match:
                    pdf_info[
                        'pdf_url'] = f'/digital/api/collection/IR/id/{match.group(1)}/download'
                    pdf_info['anchor_text'] = 'OCLC Download'
                    pdf_info['source'] = 'oclc'

        return pdf_info

    def try_parse_license(self, resolved_url=None):

        def find_normalized_license(text):
            # This function should contain the logic to normalize license text
            # For the purpose of this example, we'll use a simplified version
            license_patterns = [
                (r"creativecommons\.org/licenses/([a-z\-]+)", r"cc-\1"),
                (r"Creative Commons Attribution( \d\.\d)? License", "cc-by"),
                (
                r"Creative Commons Attribution-NonCommercial( \d\.\d)? License",
                "cc-by-nc"),
                (r"Creative Commons Attribution-ShareAlike( \d\.\d)? License",
                 "cc-by-sa"),
                (
                r"Creative Commons Attribution-NonCommercial-ShareAlike( \d\.\d)? License",
                "cc-by-nc-sa"),
                (
                r"Creative Commons Attribution-NonCommercial-NoDerivs( \d\.\d)? License",
                "cc-by-nc-nd"),
                (r"Open Access", "unspecified-oa")
            ]

            for pattern, normalized in license_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return normalized
            return None

        def _trust_publisher_license(url):
            if not url:
                return True  # Trust by default if no URL is provided

            hostname = url.split('//')[-1].split('/')[0]
            untrusted_hosts = [
                'indianjournalofmarketing.com',
                'rnajournal.cshlp.org',
                'press.umich.edu',
                'genome.cshlp.org',
                'medlit.ru',
                'journals.eco-vector.com',
                'alife-robotics.co.jp',
                'un-pub.eu',
                'zniso.fcgie.ru',
                'molbiolcell.org',
                'jcog.com.tr',
                'aimsciences.org',
                'soed.in',
                'berghahnjournals.com',
                'ojs.ual.es',
                'cjc-online.ca',
            ]

            if any(host in hostname for host in untrusted_hosts):
                return False

            if 'rupress.org' in hostname:
                volume_no = re.findall(r'rupress\.org/jcb/[^/]+/(\d+)', url)
                try:
                    if volume_no and int(volume_no[0]) < 217:
                        return True
                    else:
                        return False
                except ValueError:
                    return False

            return True

        if not _trust_publisher_license(resolved_url):
            return None

        # Create a deep copy of the soup object to avoid modifying the original
        soup_copy = copy.deepcopy(self.soup)

        # Remove script tags and specific div classes
        for script in soup_copy(["script", "style"]):
            script.decompose()
        for div in soup_copy.find_all("div", {
            'class': ['table-of-content', 'article-tools']}):
            div.decompose()

        license_search_text = soup_copy.get_text()

        license_patterns = [
            r"(creativecommons.org/licenses/[a-z\-]+)",
            r"distributed under the terms (.*) which permits",
            r"This is an open access article under the terms (.*) which permits",
            r"This is an open-access article distributed under the terms (.*), where it is permissible",
            r"This is an open access article published under (.*) which permits",
            r'<div class="openAccess-articleHeaderContainer(.*?)</div>',
            r'this article is published under the creative commons (.*) licence',
            r'This work is licensed under a Creative Commons (.*), which permits ',
        ]

        for pattern in license_patterns:
            matches = re.findall(pattern, license_search_text, re.IGNORECASE)
            if matches:
                normalized_license = find_normalized_license(matches[0])
                if normalized_license:
                    return normalized_license
                else:
                    return "unspecified-oa"

        return None

    test_cases = []
