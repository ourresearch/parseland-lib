import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from parseland_lib.back_matter import _YEAR, _numbering_whole, headed_back_matter, literatum_back_matter, \
    ojs_back_matter, plain_citation_tags, scielo_back_matter, springer_nature_back_matter
from parseland_lib.legacy_parse_utils.fulltext import parse_publisher_fulltext_location
from parseland_lib.legacy_parse_utils.pdf import is_not_pdf_file
from parseland_lib.legacy_parse_utils.fulltext import parse_repo_fulltext_location
from parseland_lib.not_abstract import clean_abstract, is_not_abstract
from parseland_lib.parse_publisher_authors_abstract import get_authors_and_abstract
from parseland_lib.publisher.parsers.aps import aps_abstract, aps_corresponding_names
from parseland_lib.publisher.parsers.copernicus import copernicus_corresponding_names
from parseland_lib.publisher.parsers.cup import cambridge_marked_openings
from parseland_lib.publisher.parsers.frontiers import frontiers_corresponding_names
from parseland_lib.publisher.parsers.lippincott import lww_corresponding_names
from parseland_lib.publisher.parsers.literatum import is_literatum_page, literatum_corresponding_marks, \
    pick_literatum_corresponding
from parseland_lib.publisher.parsers.ojs import is_ojs_page, ojs_corresponding_marks, pick_ojs_corresponding
from parseland_lib.publisher.parsers.research_square import research_square_corresponding_names
from parseland_lib.publisher.parsers.springer import springer_corresponding_names
from parseland_lib.publisher.parsers.taylor import taylorfrancis_marked_opening
from parseland_lib.publisher.parsers.scielo import is_scielo_br_page, pick_scielo_corresponding, \
    scielo_corresponding_marks
from parseland_lib.publisher.parsers.parser import frontmatter_abstract, silverchair_abstract, \
    silverchair_corresponding_names, world_scientific_abstract, world_scientific_corresponding_names
from parseland_lib.publisher.parsers.utils import _letters_key, raw_has as _has, same_opening_text, same_person
from parseland_lib.utils import normalize_doi
from parseland_lib.publisher.parsers.generic import GenericPublisherParser

# Namespaces whose pages get the generic abstract reader when the winning parser left them without one (#2239).
_GENERIC_ABSTRACT_FILL = ("pmh",)


# A peer-review report's own DOI or page: PLOS '10.1371/journal.pgph.0000105.r005' and '/peerReview?id=...', eLife's
# decision letters and author responses '10.7554/eLife.12345.sa1'. Its page carries the reviewed article's meta tags.
# Not "peer-reviewed" (repository paths: ".../peer-reviewed-articles/...").
_REVIEW_REPORT_URL = re.compile(
    r"peer-?review(?![a-z])|10\.1371/journal\.[a-z]+\.\d+\.r\d{3}\b|10\.7554/elife\.\d+\.sa\d\b", re.I)


def _is_review_report_url(*urls):
    """A peer-review report's own page: its meta tags and printed abstract are the reviewed article's."""
    return any(url and _REVIEW_REPORT_URL.search(url) for url in urls)


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
            if not 40 <= len(text) <= 200 or text.endswith(("...", "…")) or text.startswith("http"):
                continue
            if len(text.split()) < 6 or is_not_abstract(text):
                continue
            if titles is None:
                titles = _page_titles(soup, metas)
            if _letters_key(text) not in titles:
                return text
    return None


def _page_titles(soup, named_metas):
    titles = {_letters_key(m.get("content")) for m in named_metas if _TITLE_TAG.search(m["name"])}
    titles |= {_letters_key(m.get("content")) for m in soup.find_all("meta", attrs={"property": "og:title"})}
    if soup.title and soup.title.string:
        titles.add(_letters_key(soup.title.string))
    return titles


def dublin_core_authors(soup, keys=("eprints.creators_name", "dc.creator", "dcterms.creator", "dc.creator.personalname")):
    """Creators from Dublin Core / EPrints tags, in page order (#2239). Creators only: dc.contributor holds advisors
    and editors. The first tag family a page uses wins, so a page that lists its creators twice (DC and EPrints)
    keeps one list."""
    names = []
    for key in keys:
        for meta in soup.find_all("meta", attrs={"name": re.compile(f"^{re.escape(key)}$", re.I)}):
            if (name := (meta.get("content") or "").strip()) and name not in names:
                names.append(name)
        if names:
            break
    if not names:
        for meta in soup.find_all("meta", attrs={"name": re.compile(r"^citation_authors$", re.I)}):
            names += [n.strip() for n in re.split(r"[;；]", meta.get("content") or "") if n.strip()]
    # Digitised-heritage portals (Biblioteca Digital de Andalucía, Hispana) put the holding or publishing body in
    # DC.creator ("Junta de Andalucía", "Ministerio de Cultura"); the page credits no author. People only here.
    names = [n for n in names if not _INSTITUTION_WORD.search(n)]
    return [{"name": n, "affiliations": [], "is_corresponding": None} for n in names]


_INSTITUTION_WORD = re.compile(
    r"\b(?:junta|ministerio|ministry|minist[eè]re|gobierno|government|biblioteca|library|biblioth[eè]que|bibliothek|"
    r"archivo|archives?|museo|museum|universi(?:ty|dad|dade|té|tät|tà)|institut[eo]?|instituto|department|"
    r"departamento|council|consejo|ayuntamiento|diputaci[oó]n|academ(?:y|ia)|society|sociedad|centro|cent(?:er|re))\b",
    re.I)


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


def _section_text(value):
    """A section's text as the parser read it, or None when there is none or it can't be one."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or len(text) > MAX_SECTION_CHARS:
        return None
    return text


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
        if raw is None:
            continue
        kept.append({"position": len(kept) + 1, "raw": raw, "doi": normalize_doi(ref.get("doi"))})
    if not kept:
        return None, False
    return kept, (parsed.get("references_complete") is True and len(kept) == len(refs)
                  and _entries_look_whole([ref["raw"] for ref in kept]))


# Entries a whole list doesn't have, whichever parser read it (oxjob #2215, 15 Nov: 7 of 223 lists called whole on
# #2239's gold were broken in these ways; downstream uses a list only when it is whole).
_FRAGMENT_START = re.compile(r"^(?:[,;%)\]}]|[-–—]\s?\d)")  # "-197, 2016. Disponível em: ...", ",n.1,2023."
_CONTINUATION = re.compile(r"^(?:dispon[íi]vel|available (?:at|from|online)|retrieved (?:from|on)|acess(?:o|ado) em|"
                           r"accessed|https?:|www\.|doi:)", re.I)
# "...Gdynia.2. Cwilewicz, R., ...": a numbered entry starting inside another (not "Vol.42. No.253. P. 349")
_MERGED_ENTRY = re.compile(r"[^\d\s]\.\s?\d{1,3}\.\s+[A-ZÀ-ÖØ-Þ][\w'’-]+,\s")
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
    cop_names = copernicus_corresponding_names(soup) if namespace == "doi" and _has(lp_content, "copernicus.org") and (
        _has(lp_content, "CORRESPONDING AUTHOR") or _has(lp_content, "correspondence-statement")) and not (
        resolved_url and re.search(r"#(AC|RC|CC|EC|CEC)\d+$", resolved_url)) else []
    # Open Journal Systems sites mark the primary contact, a lone e-mail, a starred byline or "Author for correspondence"
    # (#2166); read before the parsers run, used only when the winning parser marked no one
    ojs_page = is_ojs_page(soup, lp_content)
    ojs_marks = ojs_corresponding_marks(soup, lp_content, ojs_page) if namespace == "doi" else []
    # Atypon Literatum sites name the corresponding author in a correspondence note or the author's own block (#2220);
    # read before the parsers run, used only when the winning parser marked no one
    literatum = namespace == "doi" and is_literatum_page(lp_content)
    literatum_marks = literatum_corresponding_marks(soup) if literatum and _has(lp_content, "orrespond") else None

    # Springer Link marks it on the byline link (data-corresp-id) (#2247); used only when the winning parser marked no one
    springer_names = springer_corresponding_names(soup) if namespace == "doi" and _has(
        lp_content, "data-corresp-id") else []

    # Springer Nature's reference list, acknowledgments and funding sections (#2239 round 6): read before the parsers
    # run, used for each key the winning parser left empty
    back_matter = springer_nature_back_matter(soup) if _has(lp_content, "c-article-references__item") or _has(
        lp_content, "c-article-section__content") else {}
    if not back_matter and literatum:
        back_matter = literatum_back_matter(soup, lp_content)
    if not back_matter and ojs_page:
        back_matter = ojs_back_matter(soup)
    if not back_matter and _has(lp_content, "scielo"):
        back_matter = scielo_back_matter(soup, lp_content)
    # any other page whose citation_reference tags print each reference's text (plain, not Highwire key=value)
    if "references" not in back_matter and _has(lp_content, "citation_reference"):
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
    openings = [o for o in openings if o]

    raw_authors_and_abstract = get_authors_and_abstract(soup, namespace)
    if namespace == "doi":
        fulltext_location = parse_publisher_fulltext_location(soup, resolved_url)
    elif namespace == "pmh":
        fulltext_location = parse_repo_fulltext_location(soup, resolved_url)
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
        if not chosen or is_not_abstract(chosen) or len(chosen) < 0.8 * len(front):
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
            # abstracts.
            if needs_abstract() and (headed := generic.parse_headed_abstract_section(main_article=True)):
                authors_and_abstract['abstract'] = headed
        # Last of all, a short abstract in a tag named for one (HAL, Figshare: one or two sentences): the meta-tag
        # readers keep only texts over 200 characters, so these were lost (14 of 1,000 sampled records).
        if not other_reader_decides and needs_abstract() and (short := short_named_abstract(soup)):
            authors_and_abstract['abstract'] = short

    # A record page no parser found authors on gets its Dublin Core / EPrints creators (EPrints'
    # eprints.creators_name, DSpace's DC.creator in any case, citation_authors lists) (#2239). Record pages only:
    # on publisher pages the creator tags would change which publisher parser wins.
    if namespace == "pmh" and not authors_and_abstract.get('authors'):
        authors_and_abstract['authors'] = dublin_core_authors(soup)
    # Figshare (and the institutional portals built on it) lists an item's creators as DataCite.contributor
    if namespace == "pmh" and not authors_and_abstract.get('authors') and _has(lp_content, "figshare"):
        authors_and_abstract['authors'] = dublin_core_authors(soup, keys=("datacite.creator", "datacite.contributor"))

    # A text the publisher marks on its page as the work's opening is body text, not its abstract, whichever parser
    # won the page: the generic parser reads the same opening from the meta tags (#2162). T&F books mark it
    # "first-paragraph" in their product data, Cambridge Core as an "extract".
    if (chosen := authors_and_abstract.get('abstract')) and any(same_opening_text(chosen, o) for o in openings):
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
        authors_and_abstract['authors'] = authors
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
        "abstract": clean_abstract(response.get("abstract")),
        # acknowledgments, funding statement and reference list from the same winning parse (#2215)
        "acknowledgments": _section_text(response.get("acknowledgments")),
        "funding_statement": _section_text(response.get("funding_statement")),
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
