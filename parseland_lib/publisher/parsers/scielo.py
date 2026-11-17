import copy
import re
from urllib.parse import urlparse

from parseland_lib.publisher.parsers.generic import GenericPublisherParser
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import name_position, same_person, squash as _squash
from bs4.element import NavigableString, Tag
import unidecode

# A note that says an author is the corresponding one, in SciELO's three languages (oxjob #2149).
SCIELO_CORR_RE = re.compile(
    r"correspond(?:ing|ent)\s+author|autora?\s+(?:para\s+)?(?:correspondente|correspond[eê]ncia|corresponsal)|"
    r"author\s+for\s+correspondence|autor\s+para\s+quem|to\s+whom\s+correspondence", re.I)
# A label followed by the corresponding author's name: "Correspondence (to|address): X", "Correspondência: X",
# "Endereço para correspondência X", "Address for correspondence: X", and "Corresponding author: X" / "Autor
# correspondente: X" only with a colon (a bare "*Corresponding author" ends one author's block, before the next name).
SCIELO_NOTE_LABEL_RE = re.compile(
    r"(?:address\s+for\s+correspondence|send\s+correspondence\s+to|"
    r"endere[cç]o\s+(?:para\s+(?:envio\s+de\s+)?)?(?:de\s+)?correspond[eê]ncia|direcci[oó]n\s+para\s+correspondencia|"
    r"correspond[eê]ncia\s+para(?:\s*/\s*correspondence\s+to)?|correspondence\s+(?:to|address)|"
    # a bare "Correspondence" / "Correspondência" heading, not the end of "Autor para correspondência." or "... for
    # correspondence;" (that is one author's footnote, followed by the next author's name)
    r"(?<!para\s)(?<!for\s)(?<!de\s)(?<!of\s)(?<!the\s)(?:correspond[eê]ncia|correspondence)(?!\s*[.;,])|"
    r"(?:corresponding\s+author|autora?\s+(?:para\s+)?(?:correspondente|correspond[eê]ncia))\s*(?=:))"
    r"\s*[:.|/–-]?\s*(?:correspondence(?:\s+to)?\s*:?\s*)?(?:(?:dr|dra|prof|profa)\.?\s+)?", re.I)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def is_scielo_br_page(soup, resolved_url):
    """A www.scielo.br article page, by the URL it was fetched from, its own og:url or its canonical link."""
    def lookups():
        yield resolved_url
        og = soup.find("meta", attrs={"property": "og:url"})
        yield og.get("content") if og is not None else None
        canonical = soup.find("link", attrs={"rel": "canonical"})
        yield canonical.get("href") if canonical is not None else None

    for url in lookups():
        try:
            host = urlparse((url or "").strip()).netloc.lower()
        except ValueError:
            continue
        if host == "scielo.br" or host.endswith(".scielo.br"):
            return True
    return False


def _byline_text_before(footnote):
    """The byline text just before a footnote on a name: back to the previous ';' or the paragraph start."""
    parts = []
    for prev in footnote.previous_siblings:
        if getattr(prev, "name", None) == "sup":
            continue
        text = prev.get_text(" ") if hasattr(prev, "get_text") else str(prev)
        if ";" in text:
            parts.append(text.split(";")[-1])
            break
        parts.append(text)
        if len(" ".join(parts)) > 120:
            break
    # affiliation numerals glued to the name ("Luiz Eduardo Bassay BlumI,", "Victor GomesII,")
    return re.sub(r"(?<=[a-zà-ÿ])(?:I{1,3}|IV|VI{0,3}|IX|X)\b", "", _squash(" ".join(reversed(parts))))


def scielo_corresponding_marks(soup):
    """What a scielo.br page says about its corresponding author (oxjob #2149). parse_page reads it before the parsers
    run (some edit the soup) and fills the flag only when the winning parser marked no one; pick_scielo_corresponding
    ties it to the parsed authors. Three forms, strongest first:

    - "dropdown": the author's own byline dropdown holds the JATS corresp note (<div class="corresp">, "*Corresponding
      author", or only that author's e-mail), the current template;
    - "footnote": converted older pages put a footnote on a byline name ('Name<span class="ref footnote">...Autor para
      correspondência.</span>'); an e-mail footnote counts only when one author has one (#1791 label-v1);
    - "note": a correspondence label followed by the author's name ("Correspondence to: X", "Correspondência: X",
      "Endereço para correspondência X", "Address for correspondence: X"), or a div.correspondence that starts with it.
    """
    names = []
    for dropdown in soup.select("div.contribGroup span.dropdown"):
        link, box = dropdown.select_one("a"), dropdown.select_one("ul")
        if link is None or box is None:
            continue
        if box.select_one(".corresp") is not None or SCIELO_CORR_RE.search(_squash(box.get_text(" "))):
            name = _squash(link.get_text(" "))
            if name and name not in names:
                names.append(name)
    if names:
        return {"names": names}

    corr_bylines, mail_bylines = [], []
    for footnote in soup.select("span.ref.footnote"):
        text = _squash(" ".join([footnote.get_text(" ")] + [a.get("data-ref") or "" for a in footnote.select("[data-ref]")]))
        if SCIELO_CORR_RE.search(text):
            corr_bylines.append(_byline_text_before(footnote))
        elif EMAIL_RE.search(text) and len(text) < 200:
            mail_bylines.append(_byline_text_before(footnote))
    # the note texts are taken now (parsers edit the soup) and searched for labels only if the footnotes don't decide
    boxes = [(box, _squash(box.get_text(" "))) for box in soup.select("div.corresp, div.correspondence")]
    lead_heads = [text[:110] for box, text in boxes if "correspondence" in box.get("class", [])]
    texts = [text for _, text in boxes] + [_squash(soup.get_text(" "))]
    return {"bylines": corr_bylines, "mail_bylines": mail_bylines, "lead_heads": lead_heads, "texts": texts}


def _note_heads(marks):
    """The text right after each correspondence label, in page order: div.correspondence boxes first."""
    yield from marks["lead_heads"]
    for text in marks["texts"]:
        for m in SCIELO_NOTE_LABEL_RE.finditer(text):
            yield text[m.end():m.end() + 110]


def pick_scielo_corresponding(author_names, marks):
    """Names among author_names that scielo_corresponding_marks marks as corresponding (oxjob #2149)."""
    if not marks or not author_names:
        return []
    if marks.get("names"):
        return marks["names"]

    def one_author_in(text):
        hits = [n for n in author_names if name_position(n, text) is not None]
        return hits[0] if len(hits) == 1 else None

    picked = list(dict.fromkeys(n for n in (one_author_in(t) for t in marks["bylines"]) if n))
    if len(author_names) > 1 and len(picked) == len(author_names):
        picked = []  # the same note on every author marks no one
    if not picked:
        mailed = {n for n in (one_author_in(t) for t in marks["mail_bylines"]) if n}
        picked = list(mailed) if len(mailed) == 1 else []
    if picked:
        return picked
    for head in _note_heads(marks):
        found = sorted((p, n) for n in author_names if (p := name_position(n, head)) is not None)
        if found and found[0][0] <= 12 and (len(found) == 1 or found[1][0] > found[0][0]):
            return [found[0][1]]
    return []


class SciELO(PublisherParser):
    parser_name = "scielo"

    def is_publisher_specific_parser(self):
        return self.domain_in_meta_og_url('www.scielo.br')

    def authors_found(self):
        return bool(self.soup.select('div.contribGroup span.dropdown'))

    def parse_authors(self):
        authors_tags = self.soup.select('div.contribGroup span.dropdown')
        authors = []
        for tag in authors_tags:
            author = {
                'name': '',
                'is_corresponding': None,
                'affiliations': []
            }
            if name_tag := tag.select_one('a'):
                author['name'] = name_tag.text.strip()
            else:
                continue
            for aff_tag in tag.select_one('ul').children:
                if isinstance(aff_tag, NavigableString) and len(
                        aff_tag.text.strip()) > 5:
                    aff = unidecode.unidecode(aff_tag.text.strip('\n ,'))
                    aff = re.sub(r' +', ' ', aff.replace('\n', ' ')).replace(' , ', ', ').replace(',,', ',').strip(', \n')
                    author['affiliations'].append(aff)
            authors.append(author)
        return authors

    def parse(self):
        return {'authors': self.parse_authors(),
                'abstract': self.parse_abstract_meta_tags()}


# ---- Classic SciELO sites other than scielo.br (oxjob #2289, template scielo-intl) ----
# scielo.cl, scielo.isciii.es, scielo.org.za, scielo.pt, pepsic.bvsalud.org and ~30 more sites still run SciELO's classic
# platform: article pages at /scielo.php?script=sci_arttext&pid=... (sci_abstract for the abstract page). No parser
# claimed them, so the citation_author tags won and marked no corresponding author, though the page names one in a
# note ("Correspondencia: Dr. X", "Dirección para correspondencia: X", "Correspondence : X"). Pages built from the
# article's XML (<!--version=xml-file-->) also print the whole citation_author list twice, each institution twice.
_CLASSIC_URL_TAGS = ("citation_fulltext_html_url", "citation_abstract_html_url")
# "Autor correspondiente: Dr. X" (Spanish): SCIELO_NOTE_LABEL_RE has the Portuguese "correspondente" only, and is
# left as it is so scielo.br pages read exactly as before
_SPANISH_CORR_LABEL_RE = re.compile(r"autora?\s+correspondiente\s*:\s*(?:(?:dr|dra|prof|profa)\.?\s+)*", re.I)


def classic_scielo_urls(soup):
    """The page's own addresses on SciELO's classic platform (".../scielo.php?script=sci_arttext&pid=..."), from the
    head's canonical link and citation_*_html_url tags. Reads only the head's own children: production asks every
    parser on every page, so this must stay cheap (#2239)."""
    root = soup.html
    head = root.find("head", recursive=False) if root is not None else None
    if head is None:
        return []
    urls = []
    for tag in head.find_all(("link", "meta"), recursive=False):
        if tag.name == "link":
            url = tag.get("href") if "canonical" in (tag.get("rel") or []) else None
        else:
            url = tag.get("content") if tag.get("name") in _CLASSIC_URL_TAGS else None
        if url and "/scielo.php" in url and "script=sci_" in url:
            urls.append(url)
    return urls


_MANGLED = re.compile("[\u00c2-\u00f4][\u0080-\u00bf]")


def _unmangle(text):
    """UTF-8 stored as Latin-1 ('DirecciÃ³n' for 'Dirección') put right word by word, with parse.py's reader: a page
    stored that way still prints some characters right ('600 μm'), so the whole text never decodes at once."""
    if not _MANGLED.search(text):
        return text
    from parseland_lib.parse import _unmangled  # here, not at the top: parse.py imports this module
    return re.sub(r"\S+", lambda m: _unmangled(m.group()), text)


def _listed_once(authors):
    """The author list as the page prints it: a list that is one list twice over (same names in the same order, the
    XML-built pages) is kept once, and each author's affiliations once each. A name that comes twice in a list that
    is not repeated whole stays (two people may share a name)."""
    half = len(authors) // 2
    if half and len(authors) == 2 * half and [a["name"] for a in authors[:half]] == [a["name"] for a in authors[half:]]:
        authors = authors[:half]
    for author in authors:
        author["affiliations"] = list(dict.fromkeys(author["affiliations"]))
    return authors


# The tail of a byline affiliation that is the author's contact, not the institution: "Correo electrónico: x@y",
# "(correo-e: x@y)", "Email: x", "Correspondencia: x@y" (the e-mail itself is usually a Cloudflare-hidden link)
_AFF_CONTACT_RE = re.compile(
    r"[\s(\[.;,]*\b(?:correo(?:\s+electr\S*nico|-e)|e-?mail|correspond\S*ncia)\s*:.*$", re.I | re.S)


def _byline_aff_texts(soup):
    """The XML-built page's affiliations by anchor: <p class="aff"><a name="aff1"></a><sup>1</sup> text</p> -> {"aff1":
    text}, with the leading label and a trailing contact (e-mail) left off."""
    out = {}
    for para in soup.select("p.aff"):
        anchor = para.find("a", attrs={"name": True})
        if anchor is None or anchor["name"] in out:
            continue
        para = copy.copy(para)
        for tag in para.select('a.__cf_email__, a[href^="mailto:"]'):
            tag.decompose()
        for child in list(para.children):  # the label: the anchor and the "1" / "*" superscript before any text
            if isinstance(child, NavigableString):
                if child.strip():
                    break
            elif child.name == "a" and child.get("name") or child.name == "sup" and len(child.get_text(strip=True)) <= 4:
                child.extract()
            else:
                break
        text = _AFF_CONTACT_RE.sub("", re.sub(r"\s+", " ", para.get_text(" ")))
        text = re.sub(r"\[email\s*protected\]", "", text).strip(" .,;:-–(")
        if text:
            out[anchor["name"]] = text
    return out


def _byline_names(soup):
    """The XML-built page's byline as [(name, ["aff1", ...])]: one <p class="author"> per author, or (older pages) the
    names inline in <div class="autores">, separated by commas, each followed by its <sup><a href="#aff1">."""
    box = next((div for div in soup.select("div.autores") if div.get_text(strip=True)), None)
    if box is None:
        return []
    paras = box.select("p.author")
    if paras:
        return [((para.select_one("span.author-name") or para).get_text(" "),
                 [a["href"][1:] for a in para.select('a[href^="#aff"]')]) for para in paras]
    out, name, ids, closed = [], "", [], False
    for child in box.children:
        if isinstance(child, Tag) and child.name == "sup":
            ids += [a["href"][1:] for a in child.select('a[href^="#aff"]')]
            closed = True
            continue
        for i, part in enumerate((child.get_text(" ") if isinstance(child, Tag) else str(child)).split(",")):
            closed = closed or i > 0
            if not part.strip():
                continue
            if closed and name.strip():
                out.append((name, ids))
                name, ids = "", []
            name, closed = name + part, False
    return out + ([(name, ids)] if name.strip() else [])


def byline_affiliations(soup, names):
    """Each author's affiliations as the XML-built page prints them under the byline, or None when the byline does not
    list exactly these authors in this order. The citation_author_institution tags hold only a short form of each
    ("Comisión de Investigaciones Científicas de la Provincia de Buenos Aires, Buenos Aires, Argentina" for "Instituto
    Superior Experimental de Tecnología Alimentaria - Comisión de Investigaciones Científicas de la Provincia de Buenos
    Aires (ISETA-CIC). Buenos Aires, Argentina."); an author the byline links to no affiliation gets []."""
    byline = _byline_names(soup)
    if not byline or len(byline) != len(names):
        return None
    texts = _byline_aff_texts(soup)
    if not texts:
        return None
    for name, (printed, _) in zip(names, byline):
        printed = _unmangle(printed.replace("\u00c2\u00a0", " ")).replace("\xa0", " ")
        printed = re.sub(r"^\s*(?:and|y|e|&)\s+", "", printed).strip()
        if not same_person(_unmangle(name), printed):
            return None
    return [list(dict.fromkeys(texts[i] for i in ids if i in texts)) for _, ids in byline]


def classic_corresponding_names(soup, names):
    """The names among `names` a classic page's correspondence note names (pick_scielo_corresponding's note form), read
    with the page's mojibake put right, plus the Spanish "Autor correspondiente:" label."""
    marks = {key: [_unmangle(text) for text in values] for key, values in scielo_corresponding_marks(soup).items()}
    if "texts" in marks:
        spanish = [text[m.end():m.end() + 110] for text in marks["texts"] for m in _SPANISH_CORR_LABEL_RE.finditer(text)]
        marks["lead_heads"] = spanish + marks["lead_heads"]
    fixed = [_unmangle(name) for name in names]
    picked = pick_scielo_corresponding(fixed, marks)
    return [name for name, readable in zip(names, fixed) if any(same_person(readable, p) for p in picked)]


class SciELOClassic(PublisherParser):
    """Classic SciELO article and abstract pages on sites other than scielo.br (oxjob #2289). The meta-tag reading
    stays (names, institutions and abstract as the generic parser reads them), with the repeated list read once, the
    affiliations of XML-built pages as their byline prints them, and the corresponding author the page's note names
    marked."""
    parser_name = "scielo_classic"

    def is_publisher_specific_parser(self):
        if not hasattr(self, "_claim"):  # authors_found asks too: the head is read once per page
            urls = classic_scielo_urls(self.soup)
            hosts = [urlparse(url.strip()).netloc.lower() for url in urls]
            # scielo.br is #2149's (SciELO above): its classic pages keep the generic reading
            self._claim = bool(urls) and not any(h == "scielo.br" or h.endswith(".scielo.br") for h in hosts)
        return self._claim

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self.parse()["authors"])

    def parse(self):
        if not hasattr(self, "_parsed"):
            parsed = GenericPublisherParser(self.soup).parse()
            authors = _listed_once(copy.deepcopy(parsed["authors"]))
            printed = byline_affiliations(self.soup, [a["name"] for a in authors]) if authors else None
            for author, affiliations in zip(authors, printed or []):
                if affiliations:  # the byline's own text; an author it links to none keeps the meta tags' reading
                    author["affiliations"] = affiliations
            if authors and not any(a["is_corresponding"] for a in authors):
                marked = classic_corresponding_names(self.soup, [a["name"] for a in authors])
                for author in authors if marked else []:
                    author["is_corresponding"] = author["name"] in marked
            self._parsed = {**parsed, "authors": authors}
        return self._parsed
