import re
from urllib.parse import urlparse, urljoin


from parseland_lib.legacy_parse_utils.strings import decode_escaped_href, \
    normalized_strings_equal, strip_jsessionid_from_url, get_tree
from parseland_lib.publisher.parsers.utp import UniversityOfTorontoPress

repo_dont_scrape_list = [
    "ncbi.nlm.nih.gov",
    "europepmc.org",
    "/europepmc/",
    "pubmed",
    "elar.rsvpu.ru",  # these ones based on complaint in email
    "elib.uraic.ru",
    "elar.usfeu.ru",
    "elar.urfu.ru",
    "elar.uspu.ru"]


class DuckLink(object):
    def __init__(self, href, anchor):
        self.href = href
        self.anchor = anchor


def transform_pdf_url(url, html_str):
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
        if reference_pdf in html_str:
            return reference_pdf

    return url


def trust_publisher_license(url):
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

def _transform_meta_pdf(link, page):
    if link and link.href:
        link.href = re.sub('(https?://[\w\.]*onlinelibrary.wiley.com/doi/)pdf(/.+)', r'\1pdfdirect\2', link.href)
        link.href = re.sub('(^https?://drops\.dagstuhl\.de/.*\.pdf)/$', r'\1', link.href)
        # https://repository.ubn.ru.nl/bitstream/2066/47467/1/47467.pdf ->
        # https://repository.ubn.ru.nl/bitstream/handle/2066/47467/1/47467.pdf
        link.href = re.sub(r'^(https?://repository\.ubn\.ru\.nl/bitstream/)(\d+.*\.pdf)$', r'\1handle/\2', link.href)
        link.href = re.sub(r'^http://(journal\.nileuniversity.edu\.ng/?.*)', r'https://\1', link.href)
        link.href = re.sub(r'^http://virginialibrariesjournal\.org//articles', r'http://virginialibrariesjournal.org/articles', link.href)
        link.href = re.sub(r'^http://www.(ecologyandsociety.org/.*.pdf)', r'https://www.\1', link.href)

        # preview PDF
        nature_pdf = re.match(r'^https?://www\.nature\.com(/articles/[a-z0-9-]*.pdf)', link.href)
        if nature_pdf:
            reference_pdf = re.sub(r'\.pdf$', '_reference.pdf',  nature_pdf.group(1))
            if reference_pdf in page:
                link.href = reference_pdf

    return link

# For repo landing page
def find_version(url, page):
    hostname = urlparse(url).hostname

    if hostname and hostname.endswith('serval.unil.ch'):
        if "Version: Final published version" in page:
            return 'publishedVersion'
        if "Version: Author's accepted manuscript" in page:
            return 'acceptedVersion'

    if hostname and hostname.endswith('repository.lboro.ac.uk'):
        if "AM (Accepted Manuscript)" in page:
            return 'acceptedVersion'

    return None


def get_pdf_in_meta(page):
    if "citation_pdf_url" in page:

        tree = get_tree(page)
        if tree is not None:
            metas = tree.xpath("//meta")
            for meta in metas:
                meta_name = meta.attrib.get('name', None)
                meta_property = meta.attrib.get('property', None)

                if meta_name == "citation_pdf_url" or meta_property == "citation_pdf_url":
                    if "content" in meta.attrib:
                        link = DuckLink(href=meta.attrib["content"], anchor="<meta citation_pdf_url>")
                        return _transform_meta_pdf(link, page)
        else:
            # backup if tree fails
            regex = r'<meta name="citation_pdf_url" content="(.*?)">'
            matches = re.findall(regex, page)
            if matches:
                link = DuckLink(href=matches[0], anchor="<meta citation_pdf_url>")
                return _transform_meta_pdf(link, page)
    return None


def find_normalized_license(text, is_dataset=False):
    if not text:
        return None

    normalized_text = text.replace(" ", "").replace("-", "").lower()

    # the lookup order matters
    # assumes no spaces, no dashes, and all lowercase
    # inspired by https://github.com/CottageLabs/blackbox/blob/fc13e5855bd13137cf1ef8f5e93883234fdab464/service/licences.py
    # thanks CottageLabs!  :)

    license_lookups = [
        ("koreanjpathol.org/authors/access.php", "cc-by-nc"),  # their access page says it is all cc-by-nc now
        ("elsevier.com/openaccess/userlicense", "publisher-specific-oa"),  #remove the - because is removed in normalized_text above
        ("pubs.acs.org/page/policy/authorchoice_termsofuse.html", "publisher-specific-oa"),
        ("open.canada.ca/en/opengovernmentlicencecanada", "other-oa"),

        ("creativecommons.org/licenses/byncnd", "cc-by-nc-nd"),
        ("creativecommonsattributionnoncommercialnoderiv", "cc-by-nc-nd"),
        ("ccbyncnd", "cc-by-nc-nd"),

        ("creativecommons.org/licenses/byncsa", "cc-by-nc-sa"),
        ("creativecommonsattributionnoncommercialsharealike", "cc-by-nc-sa"),
        ("ccbyncsa", "cc-by-nc-sa"),

        ("creativecommons.org/licenses/bynd", "cc-by-nd"),
        ("creativecommonsattributionnoderiv", "cc-by-nd"),
        ("ccbynd", "cc-by-nd"),

        ("creativecommons.org/licenses/bysa", "cc-by-sa"),
        ("creativecommonsattributionsharealike", "cc-by-sa"),
        ("ccbysa", "cc-by-sa"),

        ("creativecommons.org/licenses/bync", "cc-by-nc"),
        ("creativecommonsattributionnoncommercial", "cc-by-nc"),
        ("ccbync", "cc-by-nc"),

        ("creativecommons.org/licenses/by", "cc-by"),
        ("creativecommonsattribution", "cc-by"),
        ("ccby", "cc-by"),

        ("creativecommons.org/publicdomain/zero", "public-domain"),
        ("creativecommonszero", "public-domain"),

        ("creativecommons.org/publicdomain/mark", "public-domain"),
        ("publicdomain", "public-domain"),

        ("openaccess", "other-oa"),
        ("arxiv.orgperpetual", "publisher-specific-oa"),
        ("arxiv.orgnonexclusive", "publisher-specific-oa"),
    ]

    if is_dataset:
        license_lookups += [
            ("mit", "mit"),
            ("gpl3", "gpl-3"),
            ("gpl2", "gpl-2"),
            ("gpl", "gpl"),
            ("apache2", "apache-2.0"),
        ]

    for (lookup, license) in license_lookups:
        if lookup in normalized_text:
            if license == "public-domain":
                try:
                    if "worksnotinthepublicdomain" in normalized_text:
                        return None
                except:
                    # some kind of unicode exception
                    return None
            return license
    return None

def _trust_publisher_license(resolved_url):
    hostname = urlparse(resolved_url).hostname
    if not hostname:
        return True

    untrusted_hosts = [
        'indianjournalofmarketing.com',
        'rnajournal.cshlp.org',
        'press.umich.edu',
        'genome.cshlp.org',
        'press.umich.edu',
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

    for host in untrusted_hosts:
        if hostname.endswith(host):
            return False

    if hostname.endswith('rupress.org'):
        # landing pages have license text like "available after 6 months under ..."
        # we don't need this for new articles because the licenses are in Crossref
        volume_no = re.findall(r'rupress\.org/jcb/[^/]+/(\d+)', resolved_url)
        try:
            if volume_no and int(volume_no[0]) < 217:
                # 217 is the first volume in 2018, before that we need the license text but the delay is now irrelevant
                return True
            else:
                # 2018 or later, ignore the license and get it from Crossref
                return False
        except ValueError:
            return False

    return True


def get_useful_links(page):
    links = []

    tree = get_tree(page)
    if tree is None:
        return []

    # remove related content sections

    bad_section_finders = [
        # references and related content sections

        "//div[@class=\'relatedItem\']",  #http://www.tandfonline.com/doi/abs/10.4161/auto.19496
        "//ol[@class=\'links-for-figure\']",  #http://www.tandfonline.com/doi/abs/10.4161/auto.19496
        "//div[@class=\'citedBySection\']",  #10.3171/jns.1966.25.4.0458
        "//div[@class=\'references\']",  #https://www.emeraldinsight.com/doi/full/10.1108/IJCCSM-04-2017-0089
        "//div[@class=\'moduletable\']",  # http://vestnik.mrsu.ru/index.php/en/articles2-en/80-19-1/671-10-15507-0236-2910-029-201901-1
        "//div[contains(@class, 'ref-list')]", #https://www.jpmph.org/journal/view.php?doi=10.3961/jpmph.16.069
        "//div[contains(@class, 'references')]", #https://venue.ep.liu.se/article/view/1498
        "//div[@id=\'supplementary-material\']", #https://www.jpmph.org/journal/view.php?doi=10.3961/jpmph.16.069
        "//div[@id=\'toc\']",  # https://www.elgaronline.com/view/edcoll/9781781004326/9781781004326.xml
        "//div[contains(@class, 'cta-guide-authors')]",  # https://www.journals.elsevier.com/physics-of-the-dark-universe/
        "//div[contains(@class, 'footer-publication')]",  # https://www.journals.elsevier.com/physics-of-the-dark-universe/
        "//d-appendix",  # https://distill.pub/2017/aia/
        "//dt-appendix",  # https://distill.pub/2016/handwriting/
        "//div[starts-with(@id, 'dt-cite')]",  # https://distill.pub/2017/momentum/
        "//ol[contains(@class, 'ref-item')]",  # http://www.cjcrcn.org/article/html_9778.html
        "//div[contains(@class, 'NLM_back')]",      # https://pubs.acs.org/doi/10.1021/acs.est.7b05624
        "//div[contains(@class, 'NLM_citation')]",  # https://pubs.acs.org/doi/10.1021/acs.est.7b05624
        "//div[@id=\'relatedcontent\']",            # https://pubs.acs.org/doi/10.1021/acs.est.7b05624
        "//div[@id=\'author-infos\']",  # https://www.tandfonline.com/doi/full/10.1080/01639374.2019.1670767
        "//ul[@id=\'book-metrics\']",   # https://link.springer.com/book/10.1007%2F978-3-319-63811-9
        "//section[@id=\'article_references\']",   # https://www.nejm.org/doi/10.1056/NEJMms1702111
        "//section[@id=\'SupplementaryMaterial\']",   # https://link.springer.com/article/10.1057%2Fs41267-018-0191-3
        "//div[@id=\'attach_additional_files\']",   # https://digitalcommons.georgiasouthern.edu/ij-sotl/vol5/iss2/14/
        "//span[contains(@class, 'fa-lock')]",  # https://www.dora.lib4ri.ch/eawag/islandora/object/eawag%3A15303
        "//ul[@id=\'reflist\']",  # https://elibrary.steiner-verlag.de/article/10.25162/sprib-2019-0002
        "//div[@class=\'listbibl\']",  # http://sk.sagepub.com/reference/the-sage-handbook-of-television-studies
        "//div[contains(@class, 'summation-section')]",  # https://www.tandfonline.com/eprint/EHX2T4QAGTIYVPK7MJBF/full?target=10.1080/20507828.2019.1614768
        "//ul[contains(@class, 'references')]",  # https://www.tandfonline.com/eprint/EHX2T4QAGTIYVPK7MJBF/full?target=10.1080/20507828.2019.1614768
        "//p[text()='References']/following-sibling::p", # http://researcherslinks.com/current-issues/Effect-of-Different-Temperatures-on-Colony/20/1/2208/html
        "//span[contains(@class, 'ref-lnk')]",  # https://www.tandfonline.com/doi/full/10.1080/19386389.2017.1285143
        "//div[@id=\'referenceContainer\']",  # https://www.jbe-platform.com/content/journals/10.1075/ld.00050.kra
        "//div[contains(@class, 'table-of-content')]",  # https://onlinelibrary.wiley.com/doi/book/10.1002/9781118897126
        "//img[contains(@src, 'supplementary_material')]/following-sibling::p", # https://pure.mpg.de/pubman/faces/ViewItemOverviewPage.jsp?itemId=item_2171702
        "//span[text()[contains(., 'Supplemental Material')]]/parent::td/parent::tr",  # https://authors.library.caltech.edu/56142/
        "//div[@id=\'utpPrimaryNav\']",  # https://utpjournals.press/doi/10.3138/jsp.51.4.10
        "//p[@class=\'bibentry\']",  # http://research.ucc.ie/scenario/2019/01/Voelker/12/de
        "//a[contains(@class, 'cover-out')]",  # https://doi.org/10.5152/dir.2019.18142
        "//div[@class=\'footnotes\']",  # https://mhealth.jmir.org/2020/4/e19359/
        "//h2[text()='References']/following-sibling::ul",  # http://hdl.handle.net/2027/spo.17063888.0037.114
        "//section[@id=\'article-references\']",  # https://journals.lww.com/academicmedicine/Fulltext/2015/05000/Implicit_Bias_Against_Sexual_Minorities_in.8.aspx
        "//div[@class=\'refs\']",  # https://articles.math.cas.cz/10.21136/AM.2020.0344-19
        "//div[@class=\'citation-content\']",  # https://cdnsciencepub.com/doi/10.1139/cjz-2019-0247
        "//li[@class=\'refbiblio\']",  # https://www.erudit.org/fr/revues/documentation/2021-v67-n1-documentation05867/1075634ar/
        "//div[@class=\'Citation\']", # https://mijn.bsl.nl/seksualiteit-kinderwens-vruchtbaarheidsproblemen-en-vruchtbaarhe/16090564
        "//section[@id=\'ej-article-sam-container\']", # https://journals.lww.com/epidem/Fulltext/2014/09000/Elemental_Composition_of_Particulate_Matter_and.5.aspx
        "//h4[text()='References']/following-sibling::p",  # https://editions.lib.umn.edu/openrivers/article/mapping-potawatomi-presences/
        "//li[contains(@class, 'article-references')]",  # https://www.nejm.org/doi/10.1056/NEJMc2032052
        "//section[@id=\'supplementary-materials']", # https://www.science.org/doi/pdf/10.1126/science.aan5893
        "//td[text()='References']/following-sibling::td", # http://www.rudmet.ru/journal/2021/article/33922/?language=en
        "//article[@id=\'ej-article-view\']//div[contains(@class, 'ejp-fulltext-content')]//p[contains(@id, 'JCL-P')]",  # https://journals.lww.com/oncology-times/Fulltext/2020/11200/UpToDate.4.aspx
        "//span[contains(@class, 'ref-list')]//span[contains(@class, 'reference')]", #  https://www.degruyter.com/document/doi/10.1515/ijamh-2020-0111/html
        "//div[contains(@class, 'ncbiinpagenav')]",  # https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6657953/
        "//h4[text()[contains(., 'Multimedia Appendix')]]/following-sibling::a",  # https://www.researchprotocols.org/2019/1/e11540/
        "//section[contains(@class, 'references')]",  # http://ojs.ual.es/ojs/index.php/eea/article/view/5974
        "//h3[text()='Acknowledgements']/following-sibling::p",  # https://www.tandfonline.com/doi/full/10.1080/02635143.2016.1248928
        "//div[@id=\'references-list\']",  # https://www.cambridge.org/core/books/abs/juries-lay-judges-and-mixed-courts/worldwide-perspective-on-lay-participation/E0CA7057A55D03C4500371752E352571
        "//h2[text()='Notes']/following-sibling::ol//p[@class=\'alinea\']", # https://www.erudit.org/fr/revues/im/2015-n26-im02640/1037312ar/
        "//h2[text()='Policies and information']/following-sibling::ul",  # https://www.emerald.com/insight/content/doi/10.1108/RSR-06-2021-0025/full/html

        # can't tell what chapter/section goes with what doi
        "//div[@id=\'booktoc\']",  # https://link.springer.com/book/10.1007%2F978-3-319-63811-9
        "//div[@id=\'tocWrapper\']",  # https://www.elgaronline.com/view/edcoll/9781786431417/9781786431417.xml
        "//tr[@class=\'bookTocEntryRow\']",  # https://www.degruyter.com/document/doi/10.3138/9781487514976/html
    ]

    for section_finder in bad_section_finders:
        for bad_section in tree.xpath(section_finder):
            bad_section.clear()

    # now get the links
    link_elements = tree.xpath("//a")

    for link in link_elements:
        link_text = link.text_content().strip().lower()
        if link_text:
            link.anchor = link_text
            if "href" in link.attrib:
                link.href = link.attrib["href"]
        elif "data-tooltip" in link.attrib and 'download pdf' in link.attrib['data-tooltip'].lower():
            link.anchor = link.attrib['data-tooltip']
            if 'href' in link.attrib:
                link.href = link.attrib['href']
        elif 'title' in link.attrib and 'download fulltext' in link.attrib['title'].lower():
            link.anchor = 'title: {}'.format(link.attrib['title'])
            if 'href' in link.attrib:
                link.href = link.attrib['href']
        elif 'href' in link.attrib and '?create_pdf_query' in link.attrib['href'].lower():
            link.anchor = 'pdf_generator'
            link.href = link.attrib['href']
        else:
            # also a useful link if it has a solo image in it, and that image includes "pdf" in its filename
            link_content_elements = [l for l in link]
            if len(link_content_elements) == 1:
                link_insides = link_content_elements[0]
                if link_insides.tag == "img":
                    if "src" in link_insides.attrib and "pdf" in link_insides.attrib["src"]:
                        link.anchor = "image: {}".format(link_insides.attrib["src"])
                        if "href" in link.attrib:
                            link.href = link.attrib["href"]

        if hasattr(link, "anchor") and hasattr(link, "href"):
            links.append(link)

    return links


def is_purchase_link(link):
    # = closed journal http://www.sciencedirect.com/science/article/pii/S0147651300920050
    if "purchase" in link.anchor:
        return True
    return False


def has_bad_href_word(href):
    href_blacklist = [
        # = closed 10.1021/acs.jafc.6b02480
        # editorial and advisory board
        "/eab/",

        # = closed 10.1021/acs.jafc.6b02480
        "/suppl_file/",

        # https://lirias.kuleuven.be/handle/123456789/372010
        "supplementary+file",

        # http://www.jstor.org/action/showSubscriptions
        "showsubscriptions",

        # 10.7763/ijiet.2014.v4.396
        "/faq",

        # 10.1515/fabl.1988.29.1.21
        "{{",

        # 10.2174/1389450116666150126111055
        "cdt-flyer",

        # 10.1111/fpa.12048
        "figures",

        # https://www.crossref.org/iPage?doi=10.3138%2Fecf.22.1.1
        "price-lists",

        # https://aaltodoc.aalto.fi/handle/123456789/30772
        "aaltodoc_pdf_a.pdf",

        # prescribing information, see http://www.nejm.org/doi/ref/10.1056/NEJMoa1509388#t=references
        "janssenmd.com",

        # prescribing information, see http://www.nejm.org/doi/ref/10.1056/NEJMoa1509388#t=references
        "community-register",

        # prescribing information, see http://www.nejm.org/doi/ref/10.1056/NEJMoa1509388#t=references
        "quickreference",

        # 10.4158/ep.14.4.458
        "libraryrequestform",

        # http://www.nature.com/nutd/journal/v6/n7/full/nutd201620a.html
        "iporeport",

        #https://ora.ox.ac.uk/objects/uuid:06829078-f55c-4b8e-8a34-f60489041e2a
        "no_local_copy",

        ".zip",

        # https://zenodo.org/record/1238858
        ".gz",

        # https://zenodo.org/record/1238858
        ".tar.",

        # http://www.bioone.org/doi/full/10.1642/AUK-18-8.1
        "/doi/full/10.1642",

        # dating site :(  10.1137/S0036142902418680 http://citeseerx.ist.psu.edu/viewdoc/summary?doi=10.1.1.144.7627
        "hyke.org",

        # is a citation http://orbit.dtu.dk/en/publications/autonomous-multisensor-microsystem-for-measurement-of-ocean-water-salinity(1dea807b-c309-40fd-a623-b6c28999f74f).html
        "&rendering=",

        ".fmatter",

        "/samples/",

        # http://ira.lib.polyu.edu.hk/handle/10397/78907
        "letter_to_publisher",

        # https://www.sciencedirect.com/science/article/abs/pii/S1428226796700911?via%3Dihub
        'first-page',

        # https://www.mitpressjournals.org/doi/abs/10.1162/evco_a_00219
        'lib_rec_form',

        # http://www.eurekaselect.com/107875/chapter/climate-change-and-snow-cover-in-the-european-alp
        'ebook-flyer',

        # http://digital.csic.es/handle/10261/134122
        'accesoRestringido',

        # https://www.springer.com/statistics/journal/11222
        '/productFlyer/',

        # https://touroscholar.touro.edu/nymc_fac_pubs/622/
        '/author_agreement',

        # http://orca.cf.ac.uk/115888/
        'supinfo.pdf',

        # http://orca.cf.ac.uk/619/
        '/Appendix',

        # https://digitalcommons.fairfield.edu/business-facultypubs/31/
        'content_policy.pdf',

        # http://cds.cern.ch/record/1338672
        'BookTOC.pdf',
        'BookBackMatter.pdf',

        # https://www.goodfellowpublishers.com/academic-publishing.php?content=doi&doi=10.23912/9781911396512-3599
        'publishers-catalogue',

        # https://orbi.uliege.be/handle/2268/212705
        "_toc_",

        # https://pubs.usgs.gov/of/2004/1004/
        "adobe.com/products/acrobat",

        # https://physics.aps.org/articles/v13/31
        "featured-article-pdf",

        # http://www.jstor.org.libezproxy.open.ac.uk/stable/1446650
        "modern-slavery-act-statement.pdf",

        # https://pearl.plymouth.ac.uk/handle/10026.1/15597
        "Deposit_Agreement",

        # https://www.e-elgar.com/shop/gbp/the-elgar-companion-to-social-economics-second-edition-9781783478538.html
        '/product_flyer/',

        # https://journals.lww.com/jbjsjournal/FullText/2020/05200/Better_Late_Than_Never,_but_Is_Early_Best__.15.aspx
        'links.lww.com/JBJS/F791',

        # https://ctr.utpjournals.press/doi/10.3138/ctr.171.005
        'ctr_media_kit',
        'ctr_advertising_rates',

        # https://www.taylorfrancis.com/books/9780429465307
        'format=googlePreviewPdf',
        'type=googlepdf',

        # https://doaj.org/article/09fd431c6c99432490d9c4dfbfb2be98
        'guide_authors',

        # http://cds.cern.ch/record/898845/files/
        '_TOC.pdf',
        '_BookBackMatter.pdf',
        '_BookTOC.pdf',

        # https://www.econometricsociety.org/publications/econometrica/2019/05/01/distributional-framework-matched-employer-employee-data
        '-supplement.pdf',

        # https://www.thebhs.org/publications/the-herpetological-journal/volume-29-number-3-july-2019/1935-06-observations-of-threatened-asian-box-turtles-i-cuora-i-spp-on-trade-in-vietnam
        'ethicspolicy.pdf',

        # https://journals.lww.com/annalsofsurgery/Abstract/9000/Frailty_in_Older_Patients_Undergoing_Emergency.95070.aspx
        'coi_disclosure.pdf',

        # https://doi.org/10.1504/ijbge.2020.10028180
        '_leaflet.pdf',

        # https://search.mandumah.com/Record/1037229
        'User-manual.pdf',

        # https://dspace.stir.ac.uk/handle/1893/27593
        'table_final.pdf',

        # https://www.jmcp.org/doi/full/10.18553/jmcp.2019.25.7.817
        '/doi/full/10.18553/jmcp.',

        # http://repository.bilkent.edu.tr/handle/11693/75891
        'Bilkent-research-paper.pdf',

        # http://repositorio.conicyt.cl/handle/10533/172208
        'guia_busquedas_avanzadas.pdf',

        # https://journals.physiology.org/doi/abs/10.1152/ajplegacy.1910.26.6.413
        'PDFs/2017-Legacy-1516816496183.pdf',

        # https://opendocs.ids.ac.uk/opendocs/handle/20.500.12413/14067
        'TermsOfUse.pdf',

        # https://www.techscience.com/cmc/v70n3/44999
        'javascript:void',

        # https://www.nowpublishers.com/article/Details/FIN-015
        '/DownloadSummary/',

        # https://repositorio.unesp.br/handle/11449/161850
        'WOS000382116900027.pdf',
    ]

    href_whitelist = [
        # https://zenodo.org/record/3831263
        '190317_MainText_Figures_JNNP.pdf',
        # https://archive.nyu.edu/handle/2451/34777?mode=full
        'Using%20Google%20Forms%20to%20Track%20Library%20Space%20Usage%20w%20figures.pdf',
    ]

    for good_word in href_whitelist:
        if good_word.lower() in href.lower():
            return False

    for bad_word in href_blacklist:
        if bad_word.lower() in href.lower():
            return True

    bad_patterns = [
        r'jmir_v[a-z0-9]+_app\d+\.pdf',  # https://www.jmir.org/2019/9/e15011
    ]

    for bad_pattern in bad_patterns:
        if re.findall(bad_pattern, href, re.IGNORECASE):
            return True

    return False


def has_bad_anchor_word(anchor_text):
    anchor_blacklist = [
        # = closed repo https://works.bepress.com/ethan_white/27/
        "user",
        "guide",

        # = closed 10.1038/ncb3399
        "checklist",

        # wrong link
        "abstracts",

        # http://orbit.dtu.dk/en/publications/autonomous-multisensor-microsystem-for-measurement-of-ocean-water-salinity(1dea807b-c309-40fd-a623-b6c28999f74f).html
        "downloaded publications",

        # https://hal.archives-ouvertes.fr/hal-00085700
        "metadata from the pdf file",
        "récupérer les métadonnées à partir d'un fichier pdf",

        # = closed http://europepmc.org/abstract/med/18998885
        "bulk downloads",

        # http://www.utpjournals.press/doi/pdf/10.3138/utq.35.1.47
        "license agreement",

        # = closed 10.1021/acs.jafc.6b02480
        "masthead",

        # closed http://eprints.soton.ac.uk/342694/
        "download statistics",

        # no examples for these yet
        "supplement",
        "figure",
        "faq",

        # https://www.biodiversitylibrary.org/bibliography/829
        "download MODS",
        "BibTeX citations",
        "RIS citations",

        'ACS ActiveView PDF',

        # https://doi.org/10.11607/jomi.4336
        'Submission Form',

        # https://doi.org/10.1117/3.651915
        'Sample Pages',

        # https://babel.hathitrust.org/cgi/pt?id=uc1.e0000431916&view=1up&seq=24
        'Download this page',
        'Download left page',
        'Download right page',

        # https://touroscholar.touro.edu/nymc_fac_pubs/622/
        'author agreement',

        # https://www.longwoods.com/content/25849
        'map to our office',

        # https://www.e-elgar.com/shop/the-art-of-mooting
        'download flyer',

        # https://www.nowpublishers.com/article/Details/ENT-062
        'download extract',

        # https://utpjournals.press/doi/full/10.3138/jsp.48.3.137
        'Call for Papers',

        # https://brill.com/view/title/14711
        'View PDF Flyer',

        # https://doi.org/10.17582/journal.pjz/20190204150214
        'Full Text HTML',

        # https://openresearch-repository.anu.edu.au/password-login
        'Submitting an item to the Open Research repository',

        # https://www.wageningenacademic.com/doi/10.3920/BM2020.0057
        'Download our catalogue',

        # https://onlinelibrary.wiley.com/toc/15213994/1877/89/22
        'Reprint Order Form',
        'Cost Confirmation and Order Form',
    ]
    for bad_word in anchor_blacklist:
        if bad_word.lower() in anchor_text.lower():
            return True

    return False


def is_known_bad_link(resolved_url, link: DuckLink):
    if re.search(r'^https?://repositorio\.uchile\.cl/handle', resolved_url):
        # these are abstracts
        return re.search(r'item_\d+\.pdf', link.href or '')

    if re.search(r'^https?://dial\.uclouvain\.be', resolved_url):
        # disclaimer parameter is an unstable key
        return re.search(r'downloader\.php\?.*disclaimer=', link.href or '')

    if re.search(r'^https?://(?:www)?\.goodfellowpublishers\.com', resolved_url):
        return re.search(r'free_files/', link.href or '', re.IGNORECASE)

    if re.search(r'^https?://(?:www)?\.intellectbooks\.com', resolved_url):
        return re.search(r'_nfc', link.href or '', re.IGNORECASE)

    if re.search(r'^https?://philpapers.org/rec/FISBAI', resolved_url):
        return link.href and link.href.endswith('FISBAI.pdf')

    if re.search(r'^https?://eresearch\.qmu\.ac\.uk/', resolved_url):
        return link.href and 'appendix.pdf' in link.href

    bad_meta_pdf_links = [
        r'^https?://cora\.ucc\.ie/bitstream/',
        # https://cora.ucc.ie/handle/10468/3838
        r'^https?://zefq-journal\.com/',
        # https://zefq-journal.com/article/S1865-9217(09)00200-1/pdf
        r'^https?://www\.nowpublishers\.com/',
        # https://www.nowpublishers.com/article/Details/ENT-062
        r'^https://dsa\.fullsight\.org/api/v1/'
    ]

    if link.anchor == '<meta citation_pdf_url>':
        for url_pattern in bad_meta_pdf_links:
            if re.search(url_pattern, link.href or ''):
                return True

    bad_meta_pdf_sites = [
        # https://researchonline.federation.edu.au/vital/access/manager/Repository/vital:11142
        r'^https?://researchonline\.federation\.edu\.au/vital/access/manager/Repository/',
        r'^https?://www.dora.lib4ri.ch/[^/]*/islandora/object/',
        r'^https?://ifs\.org\.uk/publications/',
        # https://ifs.org.uk/publications/14795
        r'^https?://ogma\.newcastle\.edu\.au',
        # https://nova.newcastle.edu.au/vital/access/manager/Repository/uon:6800/ATTACHMENT01
        r'^https?://cjon\.ons\.org',
        # https://cjon.ons.org/file/laursenaugust2020cjonpdf/download
        r'^https?://nowpublishers\.com',
        # https://nowpublishers.com/article/Details/ENT-085-2
        r'^https?://dspace\.library\.uu\.nl',
        # a better link with no redirect is in the page body
    ]

    if link.anchor == '<meta citation_pdf_url>':
        for url_pattern in bad_meta_pdf_sites:
            if re.search(url_pattern, resolved_url or ''):
                return True

    if link.href == 'https://dsq-sds.org/article/download/298/345':
        return True

    return False

def get_pdf_from_javascript(page):
    matches = re.findall('"pdfUrl":"(.*?)"', page)
    if matches:
        link = DuckLink(href=decode_escaped_href(matches[0]), anchor="pdfUrl")
        return link

    matches = re.findall('"exportPdfDownloadUrl": ?"(.*?)"', page)
    if matches:
        link = DuckLink(href=decode_escaped_href(matches[0]), anchor="exportPdfDownloadUrl")
        return link

    return None

def find_pdf_link(resolved_url, soup, page_with_scripts=None) -> DuckLink:

    # before looking in links, look in meta for the pdf link
    # = open journal http://onlinelibrary.wiley.com/doi/10.1111/j.1461-0248.2011.01645.x/abstract
    # = open journal http://doi.org/10.1002/meet.2011.14504801327
    # = open repo http://hdl.handle.net/10088/17542
    # = open http://handle.unsw.edu.au/1959.4/unsworks_38708 cc-by

    # logger.info(page)
    page = str(soup)

    links = [get_pdf_in_meta(page)] + [get_pdf_from_javascript(page_with_scripts or page)] + get_useful_links(page)
    links = [link for link in links if link is not None]

    for link in links:

        if is_known_bad_link(resolved_url, link):
            continue

        # there are some links that are SURELY NOT the pdf for this article
        if has_bad_anchor_word(link.anchor):
            continue

        # there are some links that are SURELY NOT the pdf for this article
        if has_bad_href_word(link.href):
            continue

        # don't include links with newlines
        if link.href and "\n" in link.href and not any(s in link.href for s in [
            'securityanddefence.pl'
        ]):
            continue

        if link.href.startswith('#'):
            continue

        # download link ANCHOR text is something like "manuscript.pdf" or like "PDF (1 MB)"
        # = open repo http://hdl.handle.net/1893/372
        # = open repo https://research-repository.st-andrews.ac.uk/handle/10023/7421
        # = open repo http://dro.dur.ac.uk/1241/
        if link.anchor and "pdf" in link.anchor.lower():
            # handle https://utpjournals.press/doi/full/10.3138/tjt-2021-0016
            if (
                UniversityOfTorontoPress(soup).is_publisher_specific_parser()
                and "epdf" in link.href
            ):
                continue
            else:
                return link

        # button says download
        # = open repo https://works.bepress.com/ethan_white/45/
        # = open repo http://ro.uow.edu.au/aiimpapers/269/
        # = open repo http://eprints.whiterose.ac.uk/77866/
        if "download" in link.anchor or "télécharger" in link.anchor:
            if "citation" in link.anchor:
                pass
            else:
                return link

        # want it to match for this one https://doi.org/10.2298/SGS0603181L
        # but not this one: 10.1097/00003643-201406001-00238
        if (
            not soup.find('meta', {'name': lambda x: 'wkhealth' in x})
            and not UniversityOfTorontoPress(soup).is_publisher_specific_parser()
        ):
            if link.anchor and "full text" in link.anchor.lower():
                return link

            # "article text"
            if link.anchor and 'текст статьи' in link.anchor.lower():
                return link

        # https://www.oclc.org/research/publications/2020/resource-discovery-twenty-first-century-library.html
        if (
            re.search(r'^https?://(www\.)?oclc\.org', resolved_url)
            and link.href and link.href.endswith('.pdf')
            and link.anchor and ('download' in link.anchor.lower() or 'read' in link.anchor.lower())
        ):
            return link

        # https://www.aida-itea.org/index.php/revista-itea/contenidos?idArt=911&lang=esp
        if "aida-itea.org" in resolved_url and "pdf" in link.href:
            return link

        # http://www.rudmet.ru/journal/2021/article/33922/?language=en
        if (
            re.search(r'^https?://(www\.)?rudmet\.ru/journal/', resolved_url)
            and link.href and re.search(r'^https?://(www\.)?rudmet\.net/media/articles/.*\.pdf$', link.href)
        ):
            return link

        # https://dspace.library.uu.nl/handle/1874/354530
        # https://dspace.library.uu.nl/handle/1874/383562
        if (
            re.search(r'^https?://dspace\.library\.uu\.nl/', resolved_url)
            and link.anchor and  'open access version via utrecht university repository' in link.anchor.lower()
        ):
            return link


        # download link is identified with an image
        for img in link.findall(".//img"):
            try:
                if "pdf" in img.attrib["src"].lower() or "pdf" in img.attrib["class"].lower():
                    return link
            except KeyError:
                pass

        try:
            if "pdf" in link.attrib["title"].lower():
                return link
            if "download/pdf" in link.href:
                return link
        except KeyError:
            pass

        anchor = link.anchor or ''
        href = link.href or ''
        version_labels = ['submitted version', 'accepted version', 'published version']

        if (
            any(re.match(r'^{}(?:\s+\([0-9.,gmkb ]+\))?$'.format(label), anchor.lower()) for label in version_labels)
            and (href.lower().endswith('.pdf') or '.pdf?' in href.lower())
        ):
            return link

    return None


def get_link_target(url, base_url, strip_jsessionid=True):
    if strip_jsessionid:
        url = strip_jsessionid_from_url(url)
    if base_url:
        url = urljoin(base_url, url)
    return url


def clean_pdf_url(pdf_url, pdf_download_link):
    replacements = [
        (r'https?://recyt\.fecyt\.es/index\.php/EPI/article/view/', '/article/view/', '/article/download/'),
        (r'https?://(www\.)?(mitpressjournals\.org|journals\.uchicago\.edu)/doi/full/10\.+', '/doi/full/', '/doi/pdf/'),
        (r'https?://(www\.)?ascopubs\.org/doi/full/10\.+', '/doi/full/', '/doi/pdfdirect/'),
        (r'https?://(www\.)?(ahajournals\.org|journals\.sagepub\.com)/doi/reader/10\..+', '/doi/reader/', '/doi/pdf/'),
        (r'https?://(www\.)?(tandfonline\.com|ajronline\.org|pubs\.acs\.org|royalsocietypublishing\.org)/doi/epdf/10\..+', '/doi/epdf/', '/doi/pdf/'),
        (r'https?://(www\.)?onlinelibrary\.wiley\.com/doi/epdf/10\..+', '/epdf/', '/pdfdirect/'),
        (r'https?://(journals\.)?healio\.com/doi/epdf/10\..+', '/doi/epdf/', '/doi/pdf/'),
        (r'https?://(pubs\.)?rsna\.org/doi/epdf/10\..+', '/doi/epdf/', '/doi/pdf/')
    ]

    for pattern, old, new in replacements:
        if re.match(pattern, pdf_url):
            pdf_url = pdf_url.replace(old, new)
            pdf_download_link.href = pdf_download_link.href.replace(old, new)
            break

    return pdf_url, pdf_download_link


def discard_pdf_url(pdf_url, landing_url):

    parsed_pdf_url = urlparse(pdf_url)

    # PDF URLs work but aren't stable
    if parsed_pdf_url.hostname and parsed_pdf_url.hostname.endswith('exlibrisgroup.com') \
            and parsed_pdf_url.query and 'Expires=' in parsed_pdf_url.query:
        return True

    # many papers on the same page
    if landing_url == 'https://www.swarthmore.edu/donna-jo-napoli/publications-available-download':
        return True

    return False

def find_doc_download_link(page):
    for link in get_useful_links(page):
        # there are some links that are FOR SURE not the download for this article
        if has_bad_href_word(link.href):
            continue

        if has_bad_anchor_word(link.anchor):
            continue

        # = open repo https://lirias.kuleuven.be/handle/123456789/372010
        if ".doc" in link.href or ".doc" in link.anchor:
            return link

    return None


def find_bhl_view_link(url, page_content):
    hostname = urlparse(url).hostname
    if not (hostname and hostname.endswith('biodiversitylibrary.org')):
        return None

    view_links = [link for link in get_useful_links(page_content) if link.anchor == 'view article']
    return view_links[0] if view_links else None


def try_pdf_link_as_doc(resolved_url):
    hostname = urlparse(resolved_url).hostname
    if not hostname:
        return False

    doc_hosts = [
        'paleorxiv.org',
        'osf.io',
    ]

    for host in doc_hosts:
        if hostname.endswith(host):
            return True

    return False

def trust_repo_license(resolved_url):
    hostname = urlparse(resolved_url).hostname
    if not hostname:
        return False

    trusted_hosts = [
        'babel.hathitrust.org',
        'quod.lib.umich.edu',
        'taju.uniarts.fi',
    ]

    for host in trusted_hosts:
        if hostname.endswith(host):
            return True

    return False