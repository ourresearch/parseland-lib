import re
from urllib.parse import urlparse

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import name_position
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


def _squash(text):
    return re.sub(r"\s+", " ", text or "").strip()


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
