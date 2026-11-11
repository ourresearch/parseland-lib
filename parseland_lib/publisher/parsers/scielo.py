import re
from urllib.parse import urlparse

from parseland_lib.publisher.parsers.parser import PublisherParser
from bs4.element import NavigableString
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
NAME_SUFFIXES = {"filho", "junior", "jr", "neto", "sobrinho", "segundo"}
NAME_PARTICLES = {"de", "da", "do", "dos", "das", "del", "della", "di", "du", "e", "y", "van", "von", "der", "den", "la", "le"}


def is_scielo_br_page(soup, resolved_url):
    """A www.scielo.br article page, by its own og:url or canonical link, or the URL it was fetched from."""
    urls = [resolved_url or ""]
    og = soup.find("meta", attrs={"property": "og:url"})
    if og is not None:
        urls.append(og.get("content") or "")
    canonical = soup.find("link", attrs={"rel": "canonical"})
    if canonical is not None:
        urls.append(canonical.get("href") or "")
    for url in urls:
        try:
            host = urlparse(url.strip()).netloc.lower()
        except ValueError:
            continue
        if host == "scielo.br" or host.endswith(".scielo.br"):
            return True
    return False


def _fold(text):
    return re.sub(r"[^a-z]+", " ", unidecode.unidecode(text or "").lower()).strip()


def _squash(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _letters(words):
    """Initials a run of words spells: a word of up to 3 letters may itself be initials ("nrt", "mr"), longer words
    give their first letter."""
    return "".join(t if len(t) <= 3 else t[0] for t in words)


def _initials_span(tokens, givens, before):
    """How many of the words next to a surname (read back from it when before) spell the given names' initials, or 0.
    Single letters are always initials here, even 'e' and 'y'."""
    initials = _letters(givens)
    words = [t for t in tokens if len(t) == 1 or t not in NAME_PARTICLES]
    need = min(2, len(initials))
    for cut in range(len(words)):
        part = words[cut:] if before else words[:len(words) - cut]
        letters = _letters(part)
        if len(letters) >= need and initials.startswith(letters):
            return len(part)
    return 0


def name_position(name, text):
    """Where the author's name starts in text (folded), or None: the surname plus a given name, or the surname next to
    the given names' initials ('N.R.T. Damasceno', 'MCC NASCIMENTO'). Names come 'Last, First' or 'First Last'."""
    if "," in name:
        last, given = name.split(",", 1)
    else:
        tokens = name.split()
        while len(tokens) > 1 and _fold(tokens[-1]) in NAME_SUFFIXES:
            tokens = tokens[:-1]
        last, given = (tokens[-1], " ".join(tokens[:-1])) if len(tokens) > 1 else (name, "")
    surnames = [t for t in _fold(last).split() if len(t) >= 3 and t not in NAME_PARTICLES]
    givens = [t for t in _fold(given).split() if t not in NAME_PARTICLES]
    folded = _fold(text)
    best = None
    for surname in surnames:
        for m in re.finditer(r"\b" + re.escape(surname) + r"\b", folded):
            window = folded[max(0, m.start() - 45):m.end() + 45]
            ok = any(len(g) >= 3 and re.search(r"\b" + re.escape(g) + r"\b", window) for g in givens)
            pos = m.start()
            if ok:
                first = folded.find(givens[0]) if givens else -1
                pos = first if 0 <= first < m.start() else m.start()
            elif givens:  # given names as initials, either side: "N R T damasceno", "levy carvalho gomes", "damasceno N"
                before = folded[:m.start()].split()[-6:]
                n = _initials_span(before, givens, before=True)
                if n:
                    ok, pos = True, max(0, m.start() - len(" ".join(before[-n:])) - 1)
                else:
                    ok = bool(_initials_span(folded[m.end():].split()[:4], givens, before=False))
            if ok:
                best = pos if best is None else min(best, pos)
    return best


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
    heads = [_squash(box.get_text(" "))[:110] for box in soup.select("div.correspondence")]
    texts = [_squash(box.get_text(" ")) for box in soup.select("div.corresp, div.correspondence")]
    texts.append(_squash(soup.get_text(" ")))
    for text in texts:
        for m in SCIELO_NOTE_LABEL_RE.finditer(text):
            heads.append(text[m.end():m.end() + 110])
    return {"bylines": corr_bylines, "mail_bylines": mail_bylines, "heads": heads}


def pick_scielo_corresponding(author_names, marks):
    """Names among author_names that scielo_corresponding_marks marks as corresponding (oxjob #2149)."""
    if not marks or not author_names:
        return []
    if marks.get("names"):
        return marks["names"]

    def one_author_in(text):
        hits = [n for n in author_names if name_position(n, text) is not None]
        return hits[0] if len(hits) == 1 else None

    picked = list(dict.fromkeys(n for n in (one_author_in(t) for t in marks.get("bylines", [])) if n))
    if len(author_names) > 1 and len(picked) == len(author_names):
        picked = []  # the same note on every author marks no one
    if not picked and marks.get("mail_bylines"):
        mailed = {n for n in (one_author_in(t) for t in marks["mail_bylines"]) if n}
        picked = list(mailed) if len(mailed) == 1 else []
    if picked:
        return picked
    for head in marks.get("heads", []):
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
