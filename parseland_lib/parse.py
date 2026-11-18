import copy
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from parseland_lib.back_matter import _YEAR, _numbering_whole, headed_back_matter, literatum_back_matter, \
    ojs_back_matter, plain_citation_tags, scielo_back_matter, springer_nature_back_matter
from parseland_lib.legacy_parse_utils.fulltext import parse_publisher_fulltext_location
from parseland_lib.legacy_parse_utils.pdf import is_not_pdf_file
from parseland_lib.legacy_parse_utils.fulltext import parse_repo_fulltext_location
from parseland_lib.abstract_language import english_part, is_english, is_other_language
from parseland_lib.not_abstract import clean_abstract, is_not_abstract
from parseland_lib.parse_publisher_authors_abstract import get_authors_and_abstract
from parseland_lib.publisher.parsers.aps import aps_abstract, aps_corresponding_names
from parseland_lib.publisher.parsers.copernicus import copernicus_corresponding_names
from parseland_lib.publisher.parsers.cup import cambridge_marked_openings, is_cambridge_core_page
from parseland_lib.publisher.parsers.frontiers import frontiers_corresponding_names
from parseland_lib.publisher.parsers.ieee import IEEE
from parseland_lib.publisher.parsers.highwire import highwire_corresponding_marks, is_highwire_page, \
    pick_highwire_corresponding
from parseland_lib.publisher.parsers.jci import jci_affiliations
from parseland_lib.publisher.parsers.lippincott import lww_corresponding_names
from parseland_lib.publisher.parsers.literatum import is_literatum_page, literatum_corresponding_marks, \
    pick_literatum_corresponding
from parseland_lib.publisher.parsers.ojs import is_ojs_page, ojs_abstract, ojs_abstract_blocks, \
    ojs_corresponding_marks, pick_ojs_corresponding
from parseland_lib.publisher.parsers.research_square import research_square_corresponding_names
from parseland_lib.publisher.parsers.springer import springer_corresponding_names
from parseland_lib.publisher.parsers.taylor import taylorfrancis_marked_opening
from parseland_lib.publisher.parsers.scielo import is_scielo_br_page, pick_scielo_corresponding, \
    scielo_corresponding_marks
from parseland_lib.publisher.parsers.parser import _ABSTRACT_HEADING, _CUT_ENDS, _in_other_works_block, \
    frontmatter_abstract, silverchair_abstract, silverchair_corresponding_names, world_scientific_abstract, \
    world_scientific_corresponding_names
from parseland_lib.publisher.parsers.utils import _letters_key, raw_has as _has, same_opening_text, same_person
from parseland_lib.publisher.parsers.utils import _name_tokens
from parseland_lib.utils import normalize_doi
from parseland_lib.publisher.parsers.generic import GenericPublisherParser

_BLOCK_LABELS = ("h1", "h2", "h3", "h4", "h5", "h6", "a")

# Namespaces whose pages get the generic abstract reader when the winning parser left them without one (#2239).
_GENERIC_ABSTRACT_FILL = ("pmh",)


# A peer-review report's own DOI or page: PLOS '10.1371/journal.pgph.0000105.r005' and '/peerReview?id=...', eLife's
# decision letters and author responses '10.7554/eLife.12345.sa1'. Its page carries the reviewed article's meta tags.
# Not "peer-reviewed" (repository paths: ".../peer-reviewed-articles/...").
# Also a report's own anchor on the reviewed work's page (eLife ".../articles/81573#sa2", SciPost
# ".../submissions/2106.05354v1/#report_2", NB Publish "...?id=79459#review_35150") and Publons' report pages
# ("publons.com/publon/51945721/": the "Abstract" they print is the reviewed article's) (#2239 phase 2).
_REVIEW_REPORT_URL = re.compile(
    r"peer-?review(?![a-z])|10\.1371/journal\.[a-z]+\.\d+\.r\d{3}\b|10\.7554/elife\.\d+\.sa\d\b"
    r"|#(?:sa\d+|(?:report|review)_\d+)$|//(?:www\.)?publons\.com/(?:wos-op/)?publon/\d", re.I)
# Publons: a DOI that resolves there is a peer review or an editor's decision ("10.1111/odi.14200/v2/decision1"); the
# abstract its page prints, and its description ("View 3 peer reviews of <title> on Publons"), are the reviewed
# article's or the site's (#2239 round 8: 3 of 3 on check1, gold none)
_PUBLONS_PAGE = re.compile(r"//(?:www\.)?publons\.com/(?:wos-op/)?publon/\d", re.I)


def _is_review_report_url(*urls):
    """A peer-review report's own page: its meta tags and printed abstract are the reviewed article's."""
    return any(url and _REVIEW_REPORT_URL.search(url) for url in urls)


# A part's own page (#2239 phase 2, round 3). A figure's, table's or supplement's DOI resolves to a view of that part
# (PLOS ".../article/figure?id=10.1371/journal.pone.0264292.g001", Pensoft ".../article/15061/element/2/120/") or to
# the article scrolled to it (PeerJ ".../articles/1234/#fig-1"): the page's meta tags and abstract are the whole
# article's, and a part has no abstract (78 of 33,557 sampled pages; the gold: none on both labelled ones).
_PART_PAGE_URL = re.compile(
    r"/article/figure\?id=|10\.1371/journal\.[a-z]+\.\d+\.[gts]\d{3}\b"
    r"|//[a-z0-9.-]+/article/\d+/element/\d+/\d+"
    r"|//peerj\.com/articles/(?:cs-)?\d+/?#(?:fig|table|supp)-\d+$", re.I)
# A PLOS figure or table view prints the part's own DOI under it, beside the article's in citation_doi.
_PLOS_PART_DOI = re.compile(
    r'class="article-id">\s*doi:\s*<a\s+href="https?://doi\.org/10\.1371/journal\.[a-z]+\.\d+\.[gts]\d{3}"', re.I)


def _has_no_abstract_of_its_own(soup, lp_content, *urls):
    """True when the page presents something that has no abstract, while its tags or text carry another item's: a
    review report (the reviewed article's), a part of an article (the article's), a person's profile (DSpace-CRIS
    researcher pages put the biography in citation_abstract and say og:type "profile")."""
    if any(url and (_REPORT_PAGE.search(url) or _PART_PAGE_URL.search(url) or _PUBLONS_PAGE.search(url))
           for url in urls):
        return True
    if _has(lp_content, 'class="article-id"') and _has(lp_content, "10.1371/journal.") and _PLOS_PART_DOI.search(
            lp_content if isinstance(lp_content, str) else lp_content.decode("utf-8", "replace")):
        return True
    if _has(lp_content, "og:type"):
        kind = soup.find("meta", attrs={"property": "og:type"})
        return kind is not None and (kind.get("content") or "").strip().lower() == "profile"
    return False


_STRUCTURED_PARTS = re.compile(r"\b(Methods?|Results?|Conclusions?)\s*:")
# A structured abstract's opening part, as the text's first word (#2239 round 8: a meeting abstract printed under
# "Extract" is cut after "Background: ... Purpose: ... Methods: ...", before its Results)
_STRUCTURED_OPENING = re.compile(r"(?:Background|Introduction|Purpose|Objectives?|Aims?|Rationale)\s*:\s")
_STRUCTURED_LATER = re.compile(r"(?<=[.!?)])\s+(?:Purpose|Objectives?|Aims?|Methods?|Results?|Conclusions?)\s*:\s")


def _is_structured_abstract(text):
    """True when a text has a structured abstract's parts: two of "Methods:", "Results:", "Conclusions:", or it opens
    with a part's label ("Background:") and a later sentence opens another."""
    if len({p.lower()[:5] for p in _STRUCTURED_PARTS.findall(text)}) >= 2:
        return True
    return bool(_STRUCTURED_OPENING.match(text) and _STRUCTURED_LATER.search(text))


_SHORT_ABSTRACT_TAGS = [re.compile(rf"^{re.escape(n)}$", re.I)
                        for n in ("citation_abstract", "dcterms.abstract", "dc.description.abstract")]
_TITLE_TAG = re.compile(r"^(?:citation_title|dc\.title|og:title)$", re.I)


def short_named_abstract(soup):
    """An abstract of 40-200 characters from a meta tag named for one (#2239).

    The meta-tag readers keep only texts over 200 characters (shorter ones were mostly notes and placeholders), so a
    one- or two-sentence abstract (HAL, Figshare items, OJS) was lost. Only tags whose name says abstract, not
    dc.description (on repositories a note: "Thesis (M.A.)..."); at least six words, not cut ("..."), not a link, not
    a known non-abstract, and not the page's own title repeated.
    """
    metas = soup.find_all("meta", attrs={"name": True})  # one scan of the page
    titles = None
    for name in _SHORT_ABSTRACT_TAGS:  # in this order: the first tag name that holds one wins
        for tag in metas:
            if not name.search(tag["name"]):
                continue
            text = re.sub(r"^abstract[:.]?\s*", "", (tag.get("content") or "").strip(), flags=re.I)
            if not 40 <= len(text) <= 200 or text.endswith(_CUT_ENDS) or text.startswith("http"):
                continue
            if len(text.split()) < 6 or is_not_abstract(text):
                continue
            if titles is None:
                titles = _page_titles(soup, metas)
            # ... nor the title with a label or the author's name around it ("Titolo: <title>", IRIS)
            key = _letters_key(text)
            if not any(len(t) >= 20 and t in key and len(t) >= 0.6 * len(key) for t in titles):
                return text
    return None


def _page_titles(soup, named_metas):
    titles = {_letters_key(m.get("content")) for m in named_metas if _TITLE_TAG.search(m["name"])}
    titles |= {_letters_key(m.get("content")) for m in soup.find_all("meta", attrs={"property": "og:title"})}
    if soup.title and soup.title.string:
        titles.add(_letters_key(soup.title.string))
    return titles


def _unmangled(text):
    """UTF-8 that was read as Latin-1 and stored that way (the two characters 'Ã©' for 'é'), put right (#2239); any
    other text as it is. Only a text that is such bytes from end to end changes. For reading a value, not for what
    we return: a page stored that way is labelled as it reads (Figshare names keep their 'Ã©')."""
    if not re.search("[\u00c2-\u00f4][\u0080-\u00bf]", text):
        return text
    for codec in ("latin-1", "cp1252"):
        try:
            return text.encode(codec).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    return text


# The tags a record page gives its item's title in. A page with creator tags and none of these describes itself.
_ITEM_TITLE_TAG = re.compile(r"^(?:(?:dc|dcterms|eprints|datacite)\.title|citation_title)$")
# "Pendurti, S (reprint author), Florida Int Univ, Dept Engn Mech, ... Miami, FL 33199 USA.": Web of Science's
# reprint address, which the Chinese Academy of Sciences repositories list as one more DC.creator
_ADDRESS_ENTRY = re.compile(r"\((?:reprint|corresponding) author\)", re.I)
_OUTSIDE_PARENTHESES_SEMICOLON = re.compile(r"[;；](?![^()]*\))")


def _creator_names(values, repeats=False):
    """One name per person from creator tag values, in page order (#2239).

    A tag may hold several people: 'WANG, I-JONG;CHEN, PEI-JER' (NTU's repository) and Bioline's
    'Rao, C. B.; Nadiger, R. K. & Guttal, S. S.', whose '&' joins two "Family, Given" names (never split without a
    comma on both sides: "Johnson & Johnson"). A ';' inside parentheses belongs to one name (the French National
    Library's 'Roux, Antoine (19..-.... ; pédagogue)'). `repeats` keeps a name that comes twice (two people who
    share initials: 'Wang Y').
    """
    names = []
    for value in values:
        for part in _OUTSIDE_PARENTHESES_SEMICOLON.split(value):
            pieces = re.split(r"\s+&\s+", part)
            if not all("," in piece for piece in pieces):
                pieces = [part]
            for piece in pieces:
                name = piece.strip()
                # ', ' (EPrints prints an empty creator row that way) holds no letter: not a name
                if re.search(r"[^\W\d_]", name) and (repeats or name not in names):
                    names.append(name)
    return names


def _comma_list(value, always=False):
    """The names of a citation_authors value that lists people with commas: 'A. Coccoli, A. Bondavalli, L. Simoncini'
    (#2239). `always`: the site writes its lists that way (CiteSeerX). Anywhere else only a value that can't be one
    "Family, Given" name: no ';', three or more parts, each of two or more words."""
    parts = [part for part in value.split(",") if part.strip()]
    if ";" in value or "；" in value or "(" in value or len(parts) < 2:
        return [value]
    if always or (len(parts) >= 3 and all(len(part.split()) >= 2 for part in parts)):
        return parts
    return [value]


def dublin_core_authors(soup, keys=("eprints.creators_name", "dc.creator", "dcterms.creator", "dc.creator.personalname")):
    """Creators from Dublin Core / EPrints tags, in page order (#2239). Creators only: dc.contributor holds advisors
    and editors. The first tag family a page uses wins, so a page that lists its creators twice (DC and EPrints)
    keeps one list.

    Phase 2 (the first fill was wrong on 37 of 404 sampled pages): the tags must describe the item, and each value
    must be one person.
    """
    tags = {}  # tag name, lower case -> its values in page order (one scan of the page)
    for meta in soup.find_all("meta", attrs={"name": True}):
        if value := (meta.get("content") or "").strip():
            tags.setdefault(meta["name"].lower(), []).append(value)
    # Creator tags with no title tag describe the site, not an item (the German National Library's URN resolver
    # credits its developer on every page). So do a LibGuides page's (the plural DC.Publishers is Springshare's own
    # tag): its DC.Creator is the librarian who keeps the guide a retired repository now redirects to.
    if not any(_ITEM_TITLE_TAG.match(name) for name in tags) or "dc.publishers" in tags:
        return []
    names = []
    for key in keys:
        if names := _creator_names(tags.get(key, [])):
            break
    citeseerx = (soup.title.get_text() if soup.title else "").lstrip().startswith("CiteSeerX")
    listed = _creator_names([name for value in tags.get("citation_authors", [])
                             for name in _comma_list(value, always=citeseerx)], repeats=True)
    # citation_authors is the page's one list for Google Scholar. When the creator tags hold all of it and more, the
    # rest is the same people again in another script ('Fouskas, Vasilios' beside 'Φούσκας, Βασίλειος'; four names
    # in Chinese, then the four in English), and the page prints the citation_authors ones.
    if not names or (listed and len(listed) < len(names) and len(names) % len(listed) == 0
                     and all(n in names for n in listed)):
        names = listed
    # A creator that repeats a title tag is the site naming itself (the Chinese Academy of Sciences repositories:
    # DCTERMS.creator = DCTERMS.title = the repository's name, on log-in walls too).
    titles = {_letters_key(v) for name, values in tags.items() if name.endswith("title") for v in values}
    # Digitised-heritage portals (Biblioteca Digital de Andalucía, Hispana) put the holding or publishing body in
    # DC.creator ("Junta de Andalucía", "Ministerio de Cultura"); the page credits no author. People only here.
    names = [n for n in names if _letters_key(n) not in titles and not _INSTITUTION_WORD.search(_unmangled(n))
             and not _ADDRESS_ENTRY.search(n)]
    # One Latin word alone is the platform's name ("Artstor" on every Artstor record), not a person's.
    if len(names) == 1 and re.fullmatch(r"[A-Za-z]+", names[0]):
        return []
    return _as_authors(names)


def _as_authors(names):
    return [{"name": n, "affiliations": [], "is_corresponding": None} for n in names]


_INSTITUTION_WORD = re.compile(
    r"\b(?:junta|ministerio|ministry|minist[eè]re|gobierno|government|gouvernement|biblioteca|library|"
    r"biblioth[eè]que|bibliothek|archivo|archives?|museo|museum|universi(?:ty|dad|dade|té|tät|tà)|institut[eo]?|"
    r"instituto|department|departamento|council|conseil|consejo|consejer[ií]a|ayuntamiento|diputaci[oó]n|"
    r"academ(?:y|ia)|society|sociedad|centro|cent(?:er|re)|lexi[ck]on)\b",
    re.I)


def pubmed_byline(soup):
    """PubMed's printed byline: full names, and a group author as its last entry (#2239). The page's
    citation_authors tag has surnames with initials and leaves the group out."""
    block = soup.select_one("div.inline-authors div.authors-list")
    if not block:
        return []
    return [name for a in block.select("span.authors-list-item a.full-name")
            if (name := re.sub(r"\s+", " ", a.get_text(" ", strip=True)).strip())]


def lexicon_signature(soup):
    """The signature that ends an entry of the Österreichisches Biographisches Lexikon: '(H. P. Hye)' in
    <div id="autor"> (#2239). Its DC.Creator is the lexicon's editorial body on every entry."""
    tag = soup.select_one("div#autor.autor")
    text = re.sub(r"\s+", " ", _unmangled(tag.get_text())).strip() if tag else ""
    if not (signed := re.fullmatch(r"\((.+)\)", text)):
        return []
    return [name for part in re.split(r"\s+[–-]\s+|/|;", signed.group(1)) if (name := part.strip())]


def microdata_authors(soup):
    """The schema.org Person items a record page marks as its item's authors (#2239): the NRC Publications Archive,
    whose only creator tag names the Government of Canada, and RWTH Publications. All under one item: a listing
    marks the authors of each of its works, and those are not one byline."""
    people = soup.select('[itemprop="author"][itemscope][itemtype*="schema.org/Person"]')
    if len({id(person.find_parent(attrs={"itemscope": True})) for person in people}) != 1:
        return []
    names = []
    for person in people:
        tag = person.select_one('[itemprop="name"]') or person
        name = re.sub(r"\s+", " ", tag.get("content") or tag.get_text(" ", strip=True)).strip()
        if name and name not in names and not _INSTITUTION_WORD.search(name):
            names.append(name)
    return names


def record_page_authors(soup, lp_content):
    """Authors for a record page no parser found any on (#2239): the site's own byline where its tags can't give
    it, else the page's Dublin Core / EPrints creators (EPrints' eprints.creators_name, DSpace's DC.creator in any
    case, citation_authors lists), else its schema.org author items."""
    if _has(lp_content, "pubmed.ncbi.nlm.nih.gov") and (names := pubmed_byline(soup)):
        return _as_authors(names)
    if _has(lp_content, "Biographisches Lexikon") and soup.find("meta", attrs={
            "name": re.compile(r"^dc\.creator$", re.I), "content": re.compile("Biographisches Lexikon")}):
        return _as_authors(lexicon_signature(soup))
    authors = dublin_core_authors(soup)
    # Figshare (and the institutional portals built on it) lists an item's creators as DataCite.contributor
    if not authors and _has(lp_content, "figshare"):
        authors = dublin_core_authors(soup, keys=("datacite.creator", "datacite.contributor"))
    if not authors and _has(lp_content, 'itemprop="author"'):
        authors = _as_authors(microdata_authors(soup))
    return authors


def _same_byline_name(parsed, tag):
    """A parsed byline name and a citation_author tag for one person: same_person, or the tag's name with a degree
    after it ('Ronald R. Grunstein FRACP, PhD' for 'Grunstein, Ronald R.')."""
    if same_person(parsed, tag):
        return True
    tag_tokens = _name_tokens(tag)
    return len(tag_tokens) >= 2 and set(tag_tokens) <= set(_name_tokens(parsed))


def _in_tag_order(authors, tag_names):
    """The parsed authors in the order of the page's citation_author tags, when the tags name the same people, each
    once (#2239). For a byline read from Springer Nature's "Authors and Affiliations" list, which groups the
    authors by affiliation (Springer, Nature, BMC: 73 of 2,199 sampled publisher pages, every one in the tags'
    order by the gold). Not a rule for every site: Juniper Publishers' tags are in another order than its byline."""
    if len(tag_names) != len(authors):
        return authors
    free = {}  # a tag's name tokens -> the places of the tags still unmatched, in page order
    for place, tag in enumerate(tag_names):
        free.setdefault(tuple(_name_tokens(tag)), []).append(place)
    # The same name first ('Wei Li' is not 'Wei Min Li'): one dict look-up each, so a 3,000-author byline costs little.
    places = []
    for author in authors:
        same = free.get(tuple(_name_tokens(author["name"])))
        places.append(same.pop(0) if same else None)
    left = sorted(place for unmatched in free.values() for place in unmatched)
    if len(left) > 100:  # shortcut: the looser match below compares every pair; past 100 leftovers, keep the order
        return authors
    for n, author in enumerate(authors):
        if places[n] is None:
            places[n] = next((place for place in left if _same_byline_name(author["name"], tag_names[place])), None)
            if places[n] is None:
                return authors
            left.remove(places[n])
    if places == sorted(places):
        return authors
    return [author for _, author in sorted(zip(places, authors), key=lambda pair: pair[0])]


def _add_byline_groups(authors, soup, tag_names):
    """Silverchair prints a group author in the byline with no info card (<span class="al-author-by">WARCEF
    Investigators</span>), so a parser that reads the cards leaves it out (#2239). Added at its place among the
    page's citation_author tags; only a name the byline itself prints."""
    for span in soup.select(".al-authors-list span.al-author-by"):
        printed = _letters_key(span.get_text(" ", strip=True))
        for i, tag in enumerate(tag_names):
            if len(key := _letters_key(tag)) < 6 or key not in printed:
                continue
            if any(same_person(a["name"], tag) or _letters_key(a["name"]) == key for a in authors):
                continue
            place = sum(1 for earlier in tag_names[:i] if any(same_person(a["name"], earlier) for a in authors))
            marked = any(a["is_corresponding"] is not None for a in authors)
            authors.insert(place, {"name": tag, "affiliations": [], "is_corresponding": False if marked else None})
    return authors


def _is_doi_router_url(url):
    """True for bare DOI router URLs (doi.org / dx.doi.org)."""
    if not url:
        return False
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return False
    return host in ("doi.org", "dx.doi.org", "www.doi.org")


def _sniff_publisher_url(soup):
    """Try to recover the actual publisher landing-page URL from the HTML.

    Looks at <link rel="canonical">, then <meta property="og:url">. Returns
    None if neither is present or both still point at doi.org (some publishers
    set canonical to the DOI link).
    """
    try:
        canonical = soup.find("link", attrs={"rel": "canonical"})
        if canonical and canonical.get("href"):
            href = canonical.get("href").strip()
            if href and not _is_doi_router_url(href):
                return href
    except Exception:
        pass
    try:
        og = soup.find("meta", attrs={"property": "og:url"})
        if og and og.get("content"):
            href = og.get("content").strip()
            if href and not _is_doi_router_url(href):
                return href
    except Exception:
        pass
    return None


def _fill_affiliations_by_name(authors, pairs):
    """Give each (byline name, affiliations) pair to the one parsed author with that name, when the winning parser gave
    no author an affiliation (jci.org's byline pop-ups, #2252). A name spelled the same matches by lookup, the rest by
    same_person (N x N, but only for names spelled differently)."""
    if not pairs or any(a["affiliations"] for a in authors):
        return
    by_key = {}
    for a in authors:
        by_key.setdefault(_letters_key(a["name"]), []).append(a)
    for name, affs in pairs:
        matches = by_key.get(_letters_key(name)) or [a for a in authors if same_person(a["name"], name)]
        if name and len(matches) == 1 and not matches[0]["affiliations"]:
            matches[0]["affiliations"] = [{"name": aff} for aff in affs]


def _mark_corresponding_by_name(authors, names):
    """Fill the corresponding flag from a byline's marks when the winning parser marked no one (#1805).

    For bylines the winning parser can't read marks from: Silverchair (ACS and RSC moved there and no publisher
    parser claims the pages, so the meta-tag parser wins) and old-template Frontiers (the '*' sits outside <sup>).
    Each marked name sets the flag on the one parsed author with that name; a name that matches no author, or more
    than one, is skipped.
    """
    if not authors or any(a["is_corresponding"] for a in authors):
        return
    for name in names:
        matches = [a for a in authors if same_person(a["name"], name)]
        if len(matches) == 1:
            matches[0]["is_corresponding"] = True
    if any(a["is_corresponding"] for a in authors):
        for a in authors:
            if a["is_corresponding"] is None:
                a["is_corresponding"] = False




# Four keys every parser may return from parse() beside authors and abstract (oxjob #2215; contract in the job's
# README). A parser that doesn't read them returns none of them, and the response carries None and False.
MAX_SECTION_CHARS = 65535  # longer than any real acknowledgments or funding section: a parser that caught the page body
MAX_REFERENCES = 5000  # the most citations a work serves; a longer list is kept to this length and never called whole


# A review report's page: eLife's "#sa2" (author response) and ".sa2" DOIs, Copernicus's "#RC1" / "#AC2" and its
# "-discussion.html" page of comments, PLOS's "/peerReview?id=" and ".r001" DOIs. Narrower than _REVIEW_REPORT_URL
# (any "peer-review" in the address): this one takes values away from site parsers too.
_REPORT_PAGE = re.compile(r"#(?:sa\d+|(?:AC|RC|CC|EC|CEC)\d+)$|-discussion\.html(?:[?#]|$)|/peerReview\?id=|"
                          r"10\.1371/journal\.[a-z]+\.\d+\.r\d{3}\b|10\.7554/elife\.\d+\.sa\d\b", re.I)
_TEMPLATE_SLOT = re.compile(r"\{\{[^{}]*\}\}")  # "{{article.fundingStatement}}": a page template nobody filled in


def _section_text(value):
    """A section's text as the parser read it, or None when there is none or it can't be one."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or len(text) > MAX_SECTION_CHARS:
        return None
    return text


def _statement(value):
    """An acknowledgments or funding text, or None: a template slot nobody filled in is not one (#2239)."""
    text = _section_text(value)
    return None if text and _TEMPLATE_SLOT.search(text) else text


def _references(parsed):
    """(references, references_complete) in page order. Every value is type-checked, so a malformed one can't raise.

    `references_complete` stays True only when the parser said True and every entry it returned is kept: an entry
    with no text, or a list cut at MAX_REFERENCES, makes the list one we can't call whole.
    """
    refs = parsed.get("references")
    if not isinstance(refs, list):
        return None, False
    kept = []
    for ref in refs[:MAX_REFERENCES]:
        raw = _section_text(ref.get("raw")) if isinstance(ref, dict) else None
        if raw is None or not any(map(str.isalpha, raw)):
            continue  # no text, or no letter: "-", ".", "***" typed where the form wanted a reference (#2239)
        kept.append({"position": len(kept) + 1, "raw": raw, "doi": normalize_doi(ref.get("doi"))})
    if not kept:
        return None, False
    return kept, (parsed.get("references_complete") is True and len(kept) == len(refs)
                  and _entries_look_whole([ref["raw"] for ref in kept]))


# Entries a whole list doesn't have, whichever parser read it (oxjob #2215, 15 Nov: 7 of 223 lists called whole on
# #2239's gold were broken in these ways; downstream uses a list only when it is whole).
_FRAGMENT_START = re.compile(r"^(?:[,;%)\]}]|[-–—]\s?\d|\.{2}|…)")  # "-197, 2016. Disponível em: ...", ",n.1,2023.",
# "....citação referencia 1....." (a template's placeholder; one leading dot is a list number's, and fine)
_CONTINUATION = re.compile(r"^(?:dispon[íi]vel|available (?:at|from|online)|retrieved (?:from|on)|acess(?:o|ado) em|"
                           r"accessed|https?:|www\.|doi:)", re.I)
# "...Gdynia.2. Cwilewicz, R., ...": a numbered entry starting inside another (not "Vol.42. No.253. P. 349")
_MERGED_ENTRY = re.compile(r"[^\d\s]\.\s?\d{1,3}\.\s+[A-ZÀ-ÖØ-Þ][\w'’-]+,\s")
_HAS_DIGIT_OR_STOP = re.compile(r"[\d.,;:()]")
_LIST_HEADING = re.compile(r"referen|bibliogr|literatur|sources?\b|fuentes|kaynak|pustaka|литератур|источник", re.I)
_GLUED_ENTRY = re.compile(r"10\.\d{4,9}/\S*\d[A-ZÀ-ÖØ-Þ][a-zà-ÿ]{2,},\s")
_LEADING_NUMBER = re.compile(r"^[\[(]?(\d{1,3})[.)\]]?\s+\S")  # "1 Whitehead ...", "[12] Smith ..."
_MARKUP = re.compile(r"<[a-z][a-z0-9]*[\s>/]", re.I)  # "<strong>2024</strong>, <em>13</em>(7), 921;": a page's own
# citation in a tag, not a reference


def _entries_look_whole(texts):
    """False for a list with a sign that it isn't the page's whole reference list, one entry per reference."""
    for text in texts:
        if _FRAGMENT_START.match(text) or _CONTINUATION.match(text):
            return False  # the rest of the entry before it, on its own line
        if text[0].islower() and not _YEAR.search(text):
            return False  # "de Derecho y Sociedad."; a dated "de Souza, A. (2019)" is an entry
        if text.endswith(":") and len(text) < 40:
            return False  # a sub-heading inside the list ("Jurnal :", "Artikel in Press :")
        if len(_MERGED_ENTRY.findall(text)) >= 2 or _MARKUP.search(text):
            return False  # several numbered entries read as one, or markup that no printed reference carries
        if _GLUED_ENTRY.search(text):
            return False  # two entries on one line: "...https://doi.org/10.4236/ajcc.2012.11001Brini, R. (2021). ..."
    # Sub-headings printed inside the list ("Список источников" ... "Список литературы"; "Fuentes" ... "Referencias
    # bibliográficas") read as entries (#2239): two bare short lines, or one that names a list. One alone can be a
    # reference ("Summa Theologiae"), and so is "Solidworks; n.d.".
    bare = [text for text in texts if len(text) < 40 and not _HAS_DIGIT_OR_STOP.search(text)]
    if len(bare) >= 2 or any(_LIST_HEADING.search(text) for text in bare):
        return False
    numbers = [m.group(1) for text in texts if (m := _LEADING_NUMBER.match(text))]
    # every entry printed with its number: they must run 1..n (footnotes cited by a page carry gaps)
    return len(numbers) < len(texts) or _numbering_whole(numbers)


def parse_page(lp_content, namespace, resolved_url=None):
    soup = BeautifulSoup(lp_content, parser='lxml', features='lxml')
    given_url = resolved_url  # before the doi.org sniff below: a review report's DOI is only in this one

    # If the caller passed a bare doi.org link, the relative-PDF-URL joiner
    # downstream produces broken hosts like https://doi.org/doi/pdf/... .
    # Sniff the HTML's canonical / og:url meta to recover the actual landing
    # URL. Falls through to the original resolved_url if neither is present.
    if namespace == "doi" and _is_doi_router_url(resolved_url):
        sniffed = _sniff_publisher_url(soup)
        if sniffed:
            resolved_url = sniffed

    # read before the parsers run: Lippincott.get_authors removes the byline's <sup> marks from this soup (#2128)
    lww_names = lww_corresponding_names(soup) if namespace == "doi" and _has(
        lp_content, "ejp-article-authors-info-holder") else []
    # read before the parsers run: APS.parse_affs_2 removes <sup> marks from this soup (#2146)
    aps_names = aps_corresponding_names(soup) if namespace == "doi" and _has(lp_content, "contrib-notes") else []
    aps_abs = aps_abstract(soup) if namespace == "doi" and _has(lp_content, "journals.aps.org") else None
    # scielo.br marks the corresponding author in the byline dropdown, a footnote or a correspondence note (#2149)
    scielo_marks = scielo_corresponding_marks(soup) if namespace == "doi" and _has(lp_content, "scielo.br") \
        and is_scielo_br_page(soup, resolved_url) else None
    # World Scientific marks it "Corresponding author." in the author's info card (#2211); read before the parsers
    # run (the World Scientific parser removes parts of the cards from this soup)
    ws_names = world_scientific_corresponding_names(soup) if namespace == "doi" and _has(
        lp_content, "loa-wrapper") and _has(lp_content, "wspc-site") else []
    # Copernicus marks it "CORRESPONDING AUTHOR" in the author's pop-up, or in a "Correspondence:" statement (#2218);
    # the current template's pages go to the meta-tag parser, which marks no one. A referee or author comment's DOI
    # resolves to the discussed preprint's page (".../egusphere-2025-3710/#AC1"): those marks are the preprint's.
    copernicus_comment = bool(namespace == "doi" and resolved_url and re.search(
        r"#(AC|RC|CC|EC|CEC)\d+$", resolved_url) and _has(lp_content, "copernicus.org"))
    cop_names = copernicus_corresponding_names(soup) if namespace == "doi" and _has(lp_content, "copernicus.org") and (
        _has(lp_content, "CORRESPONDING AUTHOR") or _has(lp_content, "correspondence-statement")) and not (
        copernicus_comment) else []
    # Open Journal Systems sites mark the primary contact, a lone e-mail, a starred byline or "Author for correspondence"
    # (#2166); read before the parsers run, used only when the winning parser marked no one
    ojs_page = is_ojs_page(soup, lp_content)
    ojs_marks = ojs_corresponding_marks(soup, lp_content, ojs_page) if namespace == "doi" else []
    # and print the abstract in the theme's own block (#2267). On a page that has that block the OJS reader alone
    # decides what is printed in it: the generic heading reader is kept off it below (#2239 round 4)
    ojs_blocks = ojs_abstract_blocks(soup, lp_content) if namespace == "doi" and ojs_page else []
    ojs_abs = ojs_abstract(soup, lp_content, ojs_blocks) if namespace == "doi" and ojs_page else None
    # Atypon Literatum sites name the corresponding author in a correspondence note or the author's own block (#2220);
    # read before the parsers run, used only when the winning parser marked no one
    literatum = namespace == "doi" and is_literatum_page(lp_content)
    literatum_marks = literatum_corresponding_marks(soup) if literatum and _has(lp_content, "orrespond") else None

    # Springer Link marks it on the byline link (data-corresp-id) (#2247); used only when the winning parser marked no one
    springer_names = springer_corresponding_names(soup) if namespace == "doi" and _has(
        lp_content, "data-corresp-id") else []
    # HighWire marks it by a byline link to a correspondence footnote, a "Correspondence to" note, or an e-mail tag on
    # that author only (#2252); used only when the winning parser marked no one
    highwire_marks = highwire_corresponding_marks(soup, lp_content) if namespace == "doi" and is_highwire_page(
        lp_content) else None
    # jci.org shows each author's affiliations in a byline pop-up and writes no institution tags (#2252); read before
    # the parsers run (the JCI parser removes the byline's <sup> labels), used only when no author got an affiliation
    jci_pairs = jci_affiliations(soup) if namespace == "doi" and _has(
        lp_content, 'data-dropdown="author-affiliation-') and _has(lp_content, "jci.org") else []

    # Springer Nature's reference list, acknowledgments and funding sections (#2239 round 6): read before the parsers
    # run, used for each key the winning parser left empty
    back_matter = springer_nature_back_matter(soup, lp_content) if _has(lp_content, "c-article-references__item") \
        or _has(lp_content, "c-article-section__content") else {}
    if not back_matter and literatum:
        back_matter = literatum_back_matter(soup, lp_content)
    if not back_matter and ojs_page:
        back_matter = ojs_back_matter(soup)
    if not back_matter and _has(lp_content, "scielo"):
        back_matter = scielo_back_matter(soup, lp_content)
    # any other page whose citation_reference tags print each reference's text (plain, not Highwire key=value);
    # never Cambridge Core's: its tags hold the article's footnotes, or only the entries the site resolved, never the
    # whole list, and cup.py reads the page's own list (#2222)
    if "references" not in back_matter and _has(lp_content, "citation_reference") and not (
            _has(lp_content, "cambridge.org") and is_cambridge_core_page(soup)):
        back_matter = {**plain_citation_tags(soup), **back_matter}
    # then any page's own "Acknowledgments" / "Funding" sections, for the keys still empty
    if not ("acknowledgments" in back_matter and "funding_statement" in back_matter):
        back_matter = {**headed_back_matter(soup, lp_content), **back_matter}

    # read before the parsers run (the fulltext step changes this soup): openings the page marks as such (#2162)
    openings = []
    if namespace == "doi" and _has(lp_content, "taylorfrancis.com") and _has(lp_content, "first-paragraph"):
        openings.append(taylorfrancis_marked_opening(soup))
    if namespace == "doi" and _has(lp_content, "cambridge.org") and (
            _has(lp_content, 'data-abstract-type="extract"') or _has(lp_content, "Extract</h2>")):
        openings.extend(cambridge_marked_openings(soup))
    # Oxford Academic prints the opening of a work that has no abstract (a book review, a poem) under "Extract"
    # (#2239 phase 2: 2 of 2 such pages, gold none); its meta description repeats it
    # ... unless it is a structured abstract: a meeting abstract is printed under "Extract" too ("Introduction: ...
    # Methods: ... Results: ..."; European Heart Journal's congress supplements). Not the opening rule's wider
    # "says what the work does" exception: a book review's opening says what the reviewed book does (round 3: of 11
    # labelled "Extract" pages the gold has an abstract on this one kind only).
    if namespace == "doi" and _has(lp_content, "at-Extract-Title"):
        openings.extend(text for tag in soup.select("section.abstract.extract")
                        if not _is_structured_abstract(text := tag.get_text(" ", strip=True)))
    openings = [o for o in openings if o]

    raw_authors_and_abstract = get_authors_and_abstract(soup, namespace)
    # ojs_page: an OJS journal's footer may state the journal's own licence (#2239, round 5)
    if namespace == "doi":
        fulltext_location = parse_publisher_fulltext_location(soup, resolved_url, ojs_page)
    elif namespace == "pmh":
        fulltext_location = parse_repo_fulltext_location(soup, resolved_url, ojs_page)
    else:
        fulltext_location = None

    if raw_authors_and_abstract is None:
        authors_and_abstract = {'authors': [], 'abstract': None}
    elif isinstance(raw_authors_and_abstract, list):
        authors_and_abstract = {'authors': raw_authors_and_abstract, 'abstract': None}
    else:
        authors_and_abstract = raw_authors_and_abstract

    # Atypon's front-matter block holds the publisher's full abstract; whichever parser won the page may only
    # have its cut meta tag (RSNA, Neurology: first 200 characters or first section), so a clearly longer
    # front-matter abstract wins (#1800). "Clearly": the block's get_text adds spaces inside inline markup, so a
    # parser's own, equally complete text is a few characters shorter and must stay.
    if (front := frontmatter_abstract(soup)) and not is_not_abstract(front):
        chosen = authors_and_abstract.get('abstract')
        # ... but never another language's version over the English one ("If several language versions are shown,
        # give the English one": SAGE prints a French "Résumé" in the block beside the English "Abstract") (round 8)
        if chosen and is_english(chosen) and is_other_language(front):
            pass
        elif not chosen or is_not_abstract(chosen) or len(chosen) < 0.8 * len(front):
            authors_and_abstract['abstract'] = front

    # Silverchair's abstract section fills a page the winning parser left without one (pubs.aip.org) (#1800).
    if not authors_and_abstract.get('abstract') or is_not_abstract(authors_and_abstract['abstract']):
        if (silver := silverchair_abstract(soup)) and not is_not_abstract(silver):
            authors_and_abstract['abstract'] = silver

    # World Scientific's own abstract block fills a page the winning parser left without one (#2145).
    if not authors_and_abstract.get('abstract') or is_not_abstract(authors_and_abstract['abstract']):
        if (ws := world_scientific_abstract(soup)) and not is_not_abstract(ws):
            authors_and_abstract['abstract'] = ws

    # APS's description meta tag (its abstract) fills a page the winning generic parser left without one (#2146).
    if not authors_and_abstract.get('abstract') or is_not_abstract(authors_and_abstract['abstract']):
        if aps_abs and not is_not_abstract(aps_abs):
            authors_and_abstract['abstract'] = aps_abs

    # IEEE Xplore's abstract (its og:description, when the page's own record says it has one) fills a page whose
    # record lists no authors, so that the IEEE parser never ran: proceedings volumes, discussions (#2239 phase 2).
    if not authors_and_abstract.get('abstract') and namespace == "doi" and _has(
            lp_content, "xplGlobal.document.metadata") and _has(lp_content, '"sections":{"abstract":"true"'):
        if (ieee := IEEE(soup).get_abstract()) and not is_not_abstract(ieee):
            authors_and_abstract['abstract'] = ieee

    # Fills after every site's own reader (#2239), each only while the page still has no abstract. Never on a
    # peer-review report's page (it carries the reviewed article's tags and abstract) nor on World Scientific pages,
    # whose own reader above decides there (it turns down chapter previews printed under "Abstract:").
    def needs_abstract():
        chosen = authors_and_abstract.get('abstract')
        return not chosen or is_not_abstract(chosen)

    if needs_abstract():
        other_reader_decides = _is_review_report_url(given_url, resolved_url) or _has(lp_content, "wspc-site")
        generic = GenericPublisherParser(soup)
        if namespace in _GENERIC_ABSTRACT_FILL:
            # A record page whose winning parser reads no abstract (the DOAJ, HAL, DergiPark ... repository parsers
            # return authors only) gets the generic reader's: an article-level meta tag, a structured abstract
            # section, or a description tag the page prints (DOAJ record pages printed their abstract and lost it).
            if needs_abstract():
                filled = (generic.parse_abstract_meta_tags(include_seo_tags=False)
                          or generic.parse_structured_abstract_section() or generic.parse_printed_seo_description())
                if filled and not is_not_abstract(filled):
                    authors_and_abstract['abstract'] = filled
            # Then the text the page prints under its own "Abstract" heading (DOAJ, PMC, Pure portals, Redalyc ...
            # whose meta tags hold a cut snippet or nothing).
            if needs_abstract() and (headed := generic.parse_headed_abstract_section()):
                authors_and_abstract['abstract'] = headed
        elif namespace == "doi" and not other_reader_decides:
            # A publisher page whose winning parser reads authors only (PLOS returns its byline and nothing else) gets
            # the page's article-level abstract tag: citation_abstract, dcterms.abstract, dc.description. Not the
            # structured-section or printed-description readers: on publisher pages those also find related-article
            # panels and openings.
            if needs_abstract():
                filled = generic.parse_abstract_meta_tags(include_seo_tags=False)
                if filled and not is_not_abstract(filled):
                    authors_and_abstract['abstract'] = filled
            # Then the "Abstract" heading, with a main-article guard: not inside a block of other works (related
            # articles, recommendations, listings, peer-review reports), not when the page shows two different
            # abstracts. Not on an OJS page that prints the theme's abstract block: the OJS reader below decides
            # that block (it tells a book review's reference or a citation line in the abstract field from an
            # abstract, and picks among language versions). Until round 4 the heading reader never saw these blocks:
            # OJS 3's `has_sidebar` column read as chrome (#2239 phase 2).
            if needs_abstract() and not ojs_blocks and (
                    headed := generic.parse_headed_abstract_section(main_article=True)):
                authors_and_abstract['abstract'] = headed
        # Last of all, a short abstract in a tag named for one (HAL, Figshare: one or two sentences): the meta-tag
        # readers keep only texts over 200 characters, so these were lost (14 of 1,000 sampled records).
        if not other_reader_decides and needs_abstract() and (short := short_named_abstract(soup)):
            authors_and_abstract['abstract'] = short
        # And after every other reader, the description tag when it is about this item: pages that render their
        # abstract with JavaScript (DSpace 7, Redalyc, Cureus, IEEE Xplore) hold it nowhere else (#2215).
        if not other_reader_decides and needs_abstract() and (titled := generic.parse_titled_seo_description()):
            authors_and_abstract['abstract'] = titled

    # Last of all, the abstract an Open Journal Systems theme prints in its own block, on pages where no reader above
    # found one: the generic heading reader leaves that block to this one (#2267)
    if ojs_abs and needs_abstract() and not _is_review_report_url(given_url, resolved_url):
        authors_and_abstract['abstract'] = ojs_abs

    # A meta tag may hold one part of the abstract the page prints whole in its abstract block (PubMed's description:
    # the last part of a structured abstract; RAND's citation_abstract: two sentences of three) (#2239 phase 2, round 3)
    reader = None
    chosen = authors_and_abstract.get('abstract')
    not_its_own = bool(chosen) and _has_no_abstract_of_its_own(soup, lp_content, given_url, resolved_url)
    if chosen and isinstance(chosen, str) and not not_its_own:
        reader = GenericPublisherParser(soup)
        if whole := reader.whole_printed_abstract(chosen):
            authors_and_abstract['abstract'] = whole

    # "If several language versions are shown, give the English one": when the abstract chosen so far is in another
    # language and the page marks an abstract block as English (HAL: <div class="abstract-content en" lang="en">
    # beside its lang="fr" twin; the meta tags hold the French one only), that block is the abstract (#2239 phase 2).
    # Springer's German journals mark it <section data-title="Abstract" lang="en"> after the "Zusammenfassung".
    other_language = bool(chosen := authors_and_abstract.get('abstract')) and is_other_language(chosen)
    if other_language and _has(lp_content, 'lang="en"'):
        for block in soup.select('[class*="abstract"][lang^="en"], section[data-title="Abstract"][lang^="en"]'):
            if _in_other_works_block(block):
                continue
            block = copy.copy(block)  # never edit the page: the block's own "Abstract" heading and its language
            for tag in block.find_all(_BLOCK_LABELS):  # switch ("en") are labels, not abstract text
                if _ABSTRACT_HEADING.match(tag.get_text()) or (tag.name == "a" and tag.get("hreflang")):
                    tag.decompose()
            text = " ".join(block.get_text(" ", strip=True).split())
            if len(text) > 200 and is_english(text):
                authors_and_abstract['abstract'] = text
                other_language = False
                break
    # ... or prints the versions as values of one field, each in its own element (DSpace 7: the tags hold the first)
    if other_language and reader is not None and (twin := reader.english_sibling_version(chosen)):
        authors_and_abstract['abstract'] = twin

    # A record page no parser found authors on gets its Dublin Core / EPrints creators (EPrints'
    # eprints.creators_name, DSpace's DC.creator in any case, citation_authors lists) (#2239). Record pages only:
    # on publisher pages the creator tags would change which publisher parser wins.
    if namespace == "pmh" and not authors_and_abstract.get('authors'):
        authors_and_abstract['authors'] = record_page_authors(soup, lp_content)

    # A text the publisher marks on its page as the work's opening is body text, not its abstract, whichever parser
    # won the page: the generic parser reads the same opening from the meta tags (#2162). T&F books mark it
    # "first-paragraph" in their product data, Cambridge Core as an "extract".
    if (chosen := authors_and_abstract.get('abstract')) and any(same_opening_text(chosen, o) for o in openings):
        authors_and_abstract['abstract'] = None
    # Nor is another item's abstract this page's, whichever reader found it: a review report's page carries the
    # reviewed article's, a figure's or table's page the whole article's, a person's profile a biography (round 3).
    if not_its_own:
        authors_and_abstract['abstract'] = None

    if authors_and_abstract and authors_and_abstract.get('authors'):
        authors = []
        for author in authors_and_abstract['authors']:
            # handle both dict and object formats
            name = author.get("name", "") if isinstance(author, dict) else getattr(author, "name", "")
            affiliations = (
                [{"name": aff} for aff in author.get("affiliations", [])]
                if isinstance(author, dict)
                else [{"name": aff} for aff in getattr(author, "affiliations", [])]
            )
            is_corresponding = (
                author.get("is_corresponding", None)
                if isinstance(author, dict)
                else getattr(author, "is_corresponding", None)
            )
            authors.append({
                "name": name,
                "affiliations": affiliations,
                "is_corresponding": is_corresponding,
            })
        # Two bylines the page's citation_author tags put right (#2239): Springer Nature's affiliation list gives
        # the authors grouped by affiliation, and Silverchair prints a group author no info card holds.
        grouped = len(authors) > 1 and _has(lp_content, "c-article-author-affiliation__list")
        byline_group = _has(lp_content, "al-author-by")
        if namespace == "doi" and (grouped or byline_group) and _has(lp_content, "citation_author"):
            tag_names = [name for meta in soup.find_all("meta", attrs={"name": "citation_author"})
                         if (name := (meta.get("content") or "").strip())]
            if byline_group:
                authors = _add_byline_groups(authors, soup, tag_names)
            if grouped:
                authors = _in_tag_order(authors, tag_names)
        authors_and_abstract['authors'] = authors
        _fill_affiliations_by_name(authors, jci_pairs)
        # Copernicus pages mark the corresponding authors themselves (#2218): those marks replace any the winning
        # parser guessed (the meta-tag parser marks only the authors its e-mail tags pair with, often one of two)
        if cop_names and any(same_person(a["name"], n) for a in authors for n in cop_names):
            for a in authors:
                a["is_corresponding"] = None
            _mark_corresponding_by_name(authors, cop_names)
        if authors and not any(a["is_corresponding"] for a in authors):
            if _has(lp_content, "al-author-name"):
                _mark_corresponding_by_name(authors, silverchair_corresponding_names(soup))
            elif _has(lp_content, '<div class="authors"') and _has(lp_content, "/10.3389/"):
                _mark_corresponding_by_name(authors, frontiers_corresponding_names(soup))
            elif lww_names:
                _mark_corresponding_by_name(authors, lww_names)
            elif aps_names:
                _mark_corresponding_by_name(authors, aps_names)
            elif scielo_marks:
                _mark_corresponding_by_name(
                    authors, pick_scielo_corresponding([a["name"] for a in authors], scielo_marks))
            elif namespace == "doi" and _has(lp_content, '"correspondingAuthor"'):
                # Research Square flags it in the page's embedded Next.js data, not in the byline HTML (#2153)
                _mark_corresponding_by_name(authors, research_square_corresponding_names(lp_content))
            elif ws_names:
                _mark_corresponding_by_name(authors, ws_names)
            elif literatum_marks:
                _mark_corresponding_by_name(
                    authors, pick_literatum_corresponding([a["name"] for a in authors], literatum_marks))
            elif springer_names:
                _mark_corresponding_by_name(authors, springer_names)
            elif ojs_marks:
                _mark_corresponding_by_name(authors, pick_ojs_corresponding([a["name"] for a in authors], ojs_marks))
            elif highwire_marks:
                _mark_corresponding_by_name(
                    authors, pick_highwire_corresponding([a["name"] for a in authors], highwire_marks))
        # On a Copernicus comment's page every mark is the discussed preprint's, whichever reader found it: the
        # meta-tag parser reads the same pop-up as the Copernicus reader that is switched off above (#2239)
        if copernicus_comment and any(a["is_corresponding"] for a in authors):
            for a in authors:
                a["is_corresponding"] = None

    # Merge into a single response
    response = authors_and_abstract
    response.update(fulltext_location or {})
    # Figshare's "Download" link serves whatever the item's file is (a TIFF figure, a spreadsheet): it is a PDF link
    # only when the item lists a PDF file (#2239: 15 of 1,000 sampled records were figures and datasets).
    if (namespace == "pmh" and "/ndownloader/files/" in (response.get("pdf_url") or "")
            and not _has(lp_content, "application\\u002Fpdf") and not _has(lp_content, "application/pdf")):
        response["pdf_url"] = None

    # A link to an image, archive, data or media file is never the PDF, whichever reader found it (#2239 round 6:
    # Zenodo figure records offered their .jpg download, InvenioRDM records a zip of every file).
    # (the PDF finder already skips such links; this guards the other paths: doc links, BHL views)
    if is_not_pdf_file(response.get("pdf_url")):
        response["pdf_url"] = None

    urls = []
    if response.get("pdf_url"):
        urls.append({"url": response["pdf_url"], "content_type": "pdf"})
    if response.get("resolved_url"):
        urls.append({"url": response["resolved_url"], "content_type": "html"})

    # A peer-review report's own page (an eLife author response, a Copernicus referee comment, a PLOS review) prints
    # the reviewed article's reference list, acknowledgments and funding, not the report's: none of them is the
    # report's, whichever reader found them (#2239).
    if any(url and _REPORT_PAGE.search(url) for url in (given_url, resolved_url)):
        back_matter = {}
        response.update(acknowledgments=None, funding_statement=None, references=None, references_complete=False)
    # the page template's back matter fills each key the winning parser left empty (#2239 round 6)
    for key in ("acknowledgments", "funding_statement"):
        if not response.get(key) and back_matter.get(key):
            response[key] = back_matter[key]
    if not response.get("references") and back_matter.get("references"):
        response["references"] = back_matter["references"]
        response["references_complete"] = back_matter["references_complete"]

    references, references_complete = _references(response)

    # reorder the response
    ordered_response = {
        "authors": response.get("authors", []),
        "urls": urls,
        "license": response.get("license"),
        "version": response.get("version"),
        # one check for every parser: placeholders, site blurbs and SEO templates are not abstracts (#1800)
        # ... and of several language versions run together, the English one (#2239 phase 2)
        "abstract": clean_abstract(english_part(response.get("abstract"))),
        # acknowledgments, funding statement and reference list from the same winning parse (#2215)
        "acknowledgments": _statement(response.get("acknowledgments")),
        "funding_statement": _statement(response.get("funding_statement")),
        "references": references,
        "references_complete": references_complete,
    }

    return ordered_response

def find_pdf_link(lp_content, namespace, resolved_url):
    soup = BeautifulSoup(lp_content, parser='lxml', features='lxml')
    if namespace == "doi":
        fulltext_location = parse_publisher_fulltext_location(soup, resolved_url)
    elif namespace == "pmh":
        fulltext_location = parse_repo_fulltext_location(soup, resolved_url)
    else:
        fulltext_location = None
    return fulltext_location.get("pdf_url") if fulltext_location else None
