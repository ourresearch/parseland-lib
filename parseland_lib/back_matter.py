"""Back matter a platform's template prints the same way on every journal it hosts (oxjob #2239 round 6): reference
lists, acknowledgments and funding statements, for parse.py to fill where the winning parser returned none (#2215's
contract: each key from the parser that won the page, else from here, else nothing).

Every reader takes the page's soup before the parsers run (some parsers change it) and returns only the keys it
found: {"references": [...], "references_complete": bool, "acknowledgments": str, "funding_statement": str}.
"""
import copy
import re
import unicodedata
from itertools import islice
from urllib.parse import unquote

from bs4 import Comment

from parseland_lib.publisher.parsers.utils import raw_has, squash

_DOI = re.compile(r"\b(10\.\d{4,9}/\S+)")
# Where a DOI read from a text or a link stops (#2239): markup printed into the text ("...115117</li"), an encoded line
# break before the next link ("...06.005%0Ahttps://..."), a quote. Not a bare "<": old SICI DOIs carry "<0061:APG>".
_DOI_STOP = re.compile(r"</?[A-Za-z]|&lt;|%0[aAdD]|%09|[\"“”]")
_ENCODED_SPACE_END = re.compile(r"(?:%20)+$")
# a page of the cited work, not part of its DOI: ".../10.1111/j.x/abs/", ".../10.1515/9783110311075-026/html",
# "...3_17#Sec4" (a "#" alone ends SICI DOIs)
_DOI_PAGE = re.compile(r"/(?:full|abstract|abs|pdf|epdf|html)/?$|#[A-Za-z][\w.-]*$")
_GLUED_NAME = re.compile(r"(?<=\d)[A-Z][a-zà-ÿ]{2,}$")  # "...2012.11001Brini": the next reference, printed without a space
_CLOSERS = {")": "(", "]": "[", ">": "<"}


def _clean_doi(value, printed=False):
    """The first DOI in a text or link, without what a printed reference wraps it in ("<...doi/10.x/y/full>."), or
    None when what is left is a DOI cut short ("10.6008/cbpc2179-"). `printed`: the value is running text, where the
    next reference's first name can be glued to the DOI's end."""
    if not (m := _DOI.search(value or "")):
        return None
    found = _ENCODED_SPACE_END.sub("", m.group(1))
    if "%20" in found:
        return None  # "...um041v10i1p1%20-%2013": a DOI typed with spaces, and half of one is no DOI
    doi = _DOI_STOP.split(found, maxsplit=1)[0]
    if "%" in doi:
        doi = unquote(doi)  # a link printed as text: "10.1023/A%3A1009456825063"
    if doi.count("(") > doi.count(")"):
        doi = doi[:doi.rfind("(")]  # a note printed against the link: "...2020.1791506(open in a new window)"
    while doi and (doi[-1] in ".,;\"'" or (doi[-1] in _CLOSERS and doi.count(doi[-1]) > doi.count(_CLOSERS[doi[-1]]))):
        doi = doi[:-1]  # a closing bracket only when the DOI doesn't open it: "10.1061/(asce)0733-9429(1988)114:8(877)"
    doi = _DOI_PAGE.sub("", doi)
    if printed:
        doi = _GLUED_NAME.sub("", doi)
    return doi if "/" in doi and not doi.endswith(("/", "-", "_", "(")) else None


_DOI_REST = re.compile(r"(?=\S*\d)[A-Za-z0-9][\w.\-/()]*")  # "907601.", "2014.906716.", "devigilancia.2023.2"
_YEAR_ONLY = re.compile(r"(?:1[5-9]|20)\d{2}[a-z]?[.,;]?")


def _printed_doi(text):
    """The DOI a reference prints in its text, or None when the print breaks it in two ("doi.org/10.1080/13604813.
    2014.906716.", "doi:10.1177/1049909120 907601."): the rest can't be told from a following word, and half a DOI
    is another work's or nobody's (#2239). A DOI closed by a comma, or followed by the year, is whole
    (Copernicus: "https://doi.org/10.1002/qj.2297, 2014.")."""
    if not (m := _DOI.search(text or "")):
        return None
    rest = text[m.end():].strip()
    if rest and not m.group(1).endswith((",", ";")) and _DOI_REST.fullmatch(rest) and not _YEAR_ONLY.fullmatch(rest):
        return None  # one more piece and nothing after it
    return _clean_doi(m.group(1), printed=True)


def _pick_doi(*candidates):
    """The first DOI the entry gives, in the order passed: the ones on its links before the one it prints (#2239).
    The print is the weaker reading: pages glue the next label to it ("...008706pmid", "...1804.(2023)"), drop a
    SICI's "<", or print an erratum's DOI after the entry's own. But a DOI that goes on from the chosen one with a
    hyphen, or by one last digit, is the same DOI uncut: Springer's button data stops at a bracketed DOI's hyphen
    ("10.1061/(asce)0733"), and a link can end a digit early (<a href=".../1501741080246970">...</a>0.). Letters
    after it are the page's ("...915692Fg.")."""
    doi = next((c for c in candidates if c), None)
    for other in candidates:
        if doi and other and other.lower().startswith(doi.lower()) and _UNCUT_REST.match(other[len(doi):]):
            doi = other
    return doi


_UNCUT_REST = re.compile(r"-|\d$")


def _paragraphs(block):
    """A section body's text, one line per paragraph (or the whole block when it has no <p>)."""
    paragraphs = [squash(p.get_text()) for p in block.find_all("p")] or [squash(block.get_text())]
    return "\n".join(p for p in paragraphs if p) or None


_LIST_NUMBER = re.compile(r"^[\[(]?(\d+)[.)\]]?$")  # "1", "1.", "[1]", "(1)", "1)"


def _numbering_whole(labels):
    """False when the entries carry list numbers that don't run 1..n (endnote lists print only the notes that cite
    something: "2.", "3.", "8." ...). Labels that aren't list numbers ("p70_1)") or none at all say nothing."""
    numbers = [int(m.group(1)) if (m := _LIST_NUMBER.match((c or "").strip())) else None for c in labels]
    return all(n is None for n in numbers) or numbers == list(range(1, len(numbers) + 1))


_ACK_HEADING = re.compile(r"^acknowledge?ments?$", re.I)
_FUNDING_HEADING = re.compile(r"^(?:funding(?: information| sources?| statement)?|financial support|"
                              r"sources? of (?:funding|support))$", re.I)


def _key_for(title):
    """The back-matter key a section title names: "Acknowledgements" -> acknowledgments, "Funding" -> funding_statement."""
    title = squash(title).rstrip(":.")
    return "acknowledgments" if _ACK_HEADING.match(title) else (
        "funding_statement" if _FUNDING_HEADING.match(title) else None)


# Springer Nature's article template (link.springer.com, nature.com, BioMed Central, SpringerOpen): one
# <li class="c-article-references__item"> per entry, the entry's text in <p class="c-article-references__text">, its
# DOI on the "Article" button (data-doi) or as a doi.org link in the text; sections labelled by data-title.
_DOI_LINK = re.compile(r"doi\.org/10\.")


def _springer_entry_doi(item, text, raw):
    """The DOI on the entry's "Article" button, else its doi.org link's, else the one it prints as plain text."""
    link = text.find("a", href=_DOI_LINK)
    button = item.find("a", attrs={"data-doi": True})
    return _pick_doi(_clean_doi(button["data-doi"]) if button is not None else None,
                     _clean_doi(unquote(link["href"])) if link is not None else None, _printed_doi(raw))


_SUB_HEADINGS = ["h3", "h4", "h5"]
_BOLD = ["b", "strong"]


def _bold_label(tag):
    """The label a paragraph prints in bold and nothing else ("<p><b>Sources of support</b></p>"), else None: older
    BMC pages head the sub-sections of "Acknowledgments" this way (#2239). A bold sentence is text, and so is a
    label with its text run in after it."""
    if tag.name != "p" or (bold := tag.find(_BOLD)) is None:
        return None
    label = squash(tag.get_text())
    if not label or len(label) > 60 or label.count(" ") > 5 or label[-1] in ".!?":
        return None
    return label if label == squash(bold.get_text()) else None


def _section_parts(content):
    """(the section's own text, {key: text of a sub-section headed "Funding" or "Acknowledgements"}) (#2239). BMC and
    Adis pages print "Funding", "Author contributions", "Availability of data" ... as sub-headings inside the
    "Acknowledgements" section: the section's own text ends at the first of them."""
    children = content.find_all(True, recursive=False)
    labels = [_bold_label(child) for child in children]
    if content.find(_SUB_HEADINGS) is None and not any(labels):
        return _paragraphs(content), {}
    own, parts, key = [], {}, "own"
    for child, label in zip(children, labels):
        if child.name in _SUB_HEADINGS or label:
            key = _key_for(child.get_text())  # None: a sub-section that is neither (its text is dropped)
        elif child.find(_SUB_HEADINGS) is not None:
            key = None  # a sub-heading wrapped in a block: whatever it heads is not the text read so far
        elif key and (text := _paragraphs(child)):
            (own if key == "own" else parts.setdefault(key, [])).append(text)
    return "\n".join(own) or None, {k: "\n".join(v) for k, v in parts.items()}


# BioMed Central prints its "Pre-publication history" link in the reference list's markup, after the last entry
# (#2239 round 7): a notice, not a cited work, and not an entry the list lacks.
_PREPUB_NOTICE = re.compile(r"^The pre-publication history for this paper can be accessed here", re.I)


def springer_nature_back_matter(soup, lp_content=None):
    found = {}
    items, refs = [], []
    for item in soup.select("li.c-article-references__item"):
        text = item.select_one("p.c-article-references__text")
        raw = squash(text.get_text()) if text else ""
        if _PREPUB_NOTICE.match(raw):
            continue
        items.append(item)
        if not raw:
            continue
        refs.append({"raw": raw, "doi": _springer_entry_doi(item, text, raw)})
    if refs:
        found["references"] = refs
        # Every entry kept and, where the list numbers its entries, numbered 1..n: endnote lists ("Notes",
        # "Literatur") print only the notes that cite something, numbered with gaps.
        counters = [item.get("data-counter") for item in items]
        found["references_complete"] = len(refs) == len(items) and _numbering_whole(counters)
        # The text cites "[53]" and the list ends at 52: entries are missing from the page's list (#2239).
        if lp_content is not None and all(_LIST_NUMBER.match((c or "").strip()) for c in counters) \
                and raw_has(lp_content, f"[{len(items) + 1}]"):
            found["references_complete"] = False
    for section in soup.select("section[data-title]"):
        key = _key_for(section["data-title"])
        content = section.select_one("div.c-article-section__content")
        if key is None or content is None:
            continue
        own, parts = _section_parts(content)
        for part_key, text in [(key, own), *parts.items()]:
            if text and part_key not in found:
                found[part_key] = text
    return found


# Atypon Literatum (Wiley, Taylor & Francis, SAGE, Cell Press, ASM ...): three list shapes, one entry per element.
_LITERATUM_ENTRIES = (  # (raw marker checked first, so a page without the shape skips its whole-page search; selector)
    ("references-Section", "[id^=references-Section] ul.references > li"),  # Taylor & Francis: <li id="CIT0001">
    ("article-section__references", "section.article-section__references li[data-bib-id]"),  # Wiley
    ("citation-content", "section#references div.citation, #bibliography div.citation"),  # core template
    ("refnumber", "table.references tr[id^=bibr]"),  # SAGE's older template: <tr id="bibr1-..."><td class="refnumber">
)
# link buttons, labels and placeholders printed inside an entry: not its text
_LITERATUM_NOT_TEXT = (".xlinks-container, .googleScholar-container, .refLink-block, ul.getFTR, .external-links, "
                       ".extra-links, .citation-links, .label, .bullet, .ref-google, .ref-xLink, .ref-SFXLink, td.refnumber")
_BLOCKS = ["div", "p", "br", "td", "li", "tr"]
_LINKOUT_KEY = re.compile(r"[?&]key=(10\.\d{4,9}/[^&\s]+)")
_REF_DOI_PARAM = re.compile(r"[?&](?:refDoi|doiOfLink)=(10\.\d{4,9}/[^&\s]+)")


def _entry_doi(entry, text):
    """The cited work's DOI: the one the entry's links carry, else the one it prints."""
    return _pick_doi(_linked_doi(entry), _printed_doi(text))


def _linked_doi(entry):
    """The cited work's DOI from the entry's own DOI data (data-doi, Wiley's hidden DOI span, T&F's getFTR target), a
    link parameter naming it (refDoi=, doiOfLink=, a Crossref linkout's key=) or a doi.org link.
    Never a link's bare doi= parameter: linkouts and Google Scholar wrappers put the CITING article's DOI there."""
    for tag in entry.select("[data-doi], span.data-doi, ul.getFTR[data-target]"):
        if doi := _clean_doi(tag.get("data-doi") or tag.get("data-target") or tag.get_text()):
            return doi
    for link in entry.find_all("a", href=True):
        href = unquote(link["href"])
        if match := _REF_DOI_PARAM.search(href):
            return match.group(1).rstrip(".,;")
        if "linkout" in href.lower():
            if "dbid=16" in href and (match := _LINKOUT_KEY.search(href)):  # dbid=16: the Crossref button
                return match.group(1).rstrip(".,;")
        elif "doi.org/10." in href and "scholar" not in href:
            return _clean_doi(href)
    return None


def _entry_text(entry):
    entry = copy.copy(entry)  # the parsers still read this soup
    for tag in entry.select(_LITERATUM_NOT_TEXT):
        tag.decompose()
    for block in entry.find_all(_BLOCKS):  # a space between block parts (the core template: author, title, journal
        block.append(" ")                 # in separate <div>s); inline markup joins as printed ("79-94", "(2016)")
    text = squash(entry.get_text())
    return re.sub(r"([(\[]) ", r"\1", re.sub(r" ([,.;:)\]])", r"\1", text))


def plain_citation_tags(soup):
    """citation_reference tags that hold each reference's printed text (Elsevier-hosted Literatum journals), not
    Highwire's key=value form ("citation_title=...; citation_author=..."): one entry per tag, in page order."""
    texts = [squash(m.get("content")) for m in soup.find_all("meta", attrs={"name": "citation_reference"})]
    if not texts or any(not t or "citation_" in t for t in texts):
        return {}
    texts, numbered = _without_list_numbers(texts)
    refs = [{"raw": t, "doi": _printed_doi(t)} for t in texts]
    return {"references": refs, "references_complete": numbered and not _has_broken_entry(texts)}


_PART_END = "␞"  # stands for a link block while a compound entry's text is read
_SUB_LABEL = re.compile(r"^[a-z]\)\s*")
_NEXT_SUB_LABEL = re.compile(r"\s[b-z]\)\s")


def _compound_entries(entry):
    """Wiley's chemistry and physics journals print several references under one number, lettered ("1 a) A. Kojima
    ...; b) A. K. Jena ..."), each followed by its own link block with its DOI: one entry per reference, in order
    (#2239). None when the entry is one reference, or an unlettered run of citations ("O. Kratky, Naturwiss. 42, 237
    (1955); Angew. Chem. 72, 467 (1960)": the later ones name no author, and stay one entry)."""
    if len(entry.select("div.extra-links")) < 2:
        return None
    entry, dois = copy.copy(entry), []  # a copy: the parsers still read this soup
    for block in entry.select("div.extra-links"):
        dois.append(_linked_doi(block))
        block.replace_with(_PART_END)
    texts = [squash(t) for t in _entry_text(entry).split(_PART_END)]
    if not _SUB_LABEL.match(texts[0]):
        return None
    parts = [{"raw": _SUB_LABEL.sub("", t), "doi": _pick_doi(doi, _printed_doi(t))} for t, doi in zip(texts, dois) if t]
    if texts[-1]:  # a last reference with no link block
        parts.append({"raw": _SUB_LABEL.sub("", texts[-1]), "doi": _printed_doi(texts[-1])})
    return parts


def literatum_back_matter(soup, lp_content):
    for marker, selector in _LITERATUM_ENTRIES:
        if raw_has(lp_content, marker) and (entries := soup.select(selector)):
            break
    else:
        return plain_citation_tags(soup) if raw_has(lp_content, "citation_reference") else {}
    refs, labels, whole = [], [], True
    for entry in entries:
        label = entry.select_one(".label, .bullet")
        labels.append(label.get_text(strip=True) if label else None)
        parts = _compound_entries(entry) if marker == "article-section__references" else None
        if parts is None:
            parts = [{"raw": raw, "doi": _entry_doi(entry, raw)}] if (raw := _entry_text(entry)) else []
        # an entry with no text, or a lettered one that still holds a second reference ("a) ...; b) ..." with no link
        # block to split it at): not a list of one entry per reference
        lettered = len(parts) > 1 or bool(parts and _SUB_LABEL.match(parts[0]["raw"]))
        whole = whole and bool(parts) and not (lettered and any(_NEXT_SUB_LABEL.search(p["raw"]) for p in parts))
        refs += parts
    if not refs:
        return {}
    # whole when every entry has text and, where the list numbers its entries, they run 1..n
    return {"references": refs, "references_complete": whole and _numbering_whole(labels)}


# Open Journal Systems: the article page's "References" item prints the journal's reference text one entry per <p>,
# <li> or line break, and the same entries go to citation_reference tags (plain text).
_LINE_BREAK = "\u2028"  # a <br> in the references text, before splitting it into entries
_YEAR = re.compile(r"\b(1[5-9]|20)\d{2}\b|\b[nN]\.\s?d\.")


_TYPED_NUMBER = re.compile(r"^[\[(]?(\d{1,3})[.)\]][\s.–-]*(?=\S)")  # a number the author typed: "12. ", "[12] ",
# "12) ", "15.-Tavares"
_URL_END = re.compile(r"(?:https?:|www\.|doi)\S*$|\S*[/@]\S*$", re.I)
_LETTER = re.compile(r"[^\W\d_]")


def _without_list_numbers(texts):
    """(the entries without the numbers their author typed, False when the numbering shows a break) (#2239).
    The contract's entry is the reference without its number. In a list typed "1. ... 36. ...", an entry with no
    number is the rest of the entry before it, and numbers that don't run 1..n are a list with a hole."""
    numbers = [m.group(1) if (m := _TYPED_NUMBER.match(t)) else None for t in texts]
    if sum(n is not None for n in numbers) < 0.8 * len(texts) or len(texts) < 3:
        return texts, True  # not a numbered list (a few entries that open with a year or a count)
    if None in numbers or not _numbering_whole(numbers):
        return texts, False
    return [_TYPED_NUMBER.sub("", t, count=1) for t in texts], True


def _sort_letter(text):
    """The letter a list sorts the entry by, without its mark: "Şişko" sorts with "S", before "Tabachnick"."""
    letter = _LETTER.search(text)
    return unicodedata.normalize("NFKD", letter.group(0))[0].casefold() if letter else ""


def _has_broken_entry(texts):
    """True when a list its author typed as plain text, in alphabetical order, shows an entry broken in two by a
    line break (#2239): the first half stops on a bare word, or on a comma, and the second half falls out of the
    order, against the first half ("Safitri, D. (2015) ... in Nbc News Online Mass" / "Media of Michael Brown's Case
    ..." / "Memon, N. ...") or against the entry after it ("Genette, Gerard. ... Traducido por Luciano Padilla
    López," / "México: Fondo de Cultura Económica, 2004." / "Landsberg, Alison. ...").
    A list in citation order gives no such sign (its numbers do: _without_list_numbers)."""
    if len(texts) < 7:
        return False  # too few lines to show an order
    first = [_sort_letter(t) for t in texts]
    if sum(b < a for a, b in zip(first, first[1:])) > max(1, 0.15 * (len(texts) - 1)):
        return False  # not an alphabetical list
    for i, text in enumerate(texts[:-1]):
        # an entry closed with a full stop, a bracket or its link is whole: a line out of order after it is mis-sorted
        open_ended = text[-1] == "," or (text[-1].isalpha() and not _URL_END.search(text))
        # the line after an open one sorts before it, or before the next entry while the open one doesn't
        if open_ended and (first[i + 1] < first[i] or (i + 2 < len(texts) and first[i] <= first[i + 2] < first[i + 1])):
            return True
    return False


def _lines(value):
    items = value.find_all("li") or value.find_all("p")
    if items:
        return [squash(item.get_text()) for item in items]
    value = copy.copy(value)
    for br in value.find_all("br"):
        br.replace_with(_LINE_BREAK)
    return [squash(line) for line in value.get_text().split(_LINE_BREAK)]


def ojs_back_matter(soup):
    """For an Open Journal Systems page (parse.py checks with is_ojs_page)."""
    value = soup.select_one("section.item.references .value, div.item.references .value")
    lines = [line for line in _lines(value) if line] if value else []
    if not lines:
        return plain_citation_tags(soup)
    lines, numbered = _without_list_numbers(lines)
    refs = [{"raw": line, "doi": _printed_doi(line)} for line in lines]
    # A journal whose source text broke references across lines prints fragments ("Silica from Spent Hydrafluoric
    # Acid – How"): a list where many entries carry no year is not one we can call whole.
    undated = sum(not _YEAR.search(line) for line in lines)
    return {"references": refs, "references_complete": undated <= 0.2 * len(lines) and numbered
            and not _has_broken_entry(lines)}


# Any template: a section headed "Acknowledgments" or "Funding" (ScienceDirect's server-rendered body, Atypon's
# div.ack, PLOS, MDPI ...). The heading's own section: the paragraphs after it, up to the next heading.
_HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_HEADED_WORDS = ("cknowledg", "CKNOWLEDG", "unding", "UNDING", "inancial", "INANCIAL")
_CHROME_TAGS = {"nav", "footer"}  # not <aside>: Springer Nature leaves an ad <aside> open around the whole body
_CHROME_TOKENS = ("nav", "menu", "toc", "outline", "sidebar", "footer", "breadcrumb")
_CHROME_PREFIXES = tuple(t + "-" for t in _CHROME_TOKENS if t != "toc")  # not "toc-": PLOS's body is "toc-section"


def _in_navigation(heading):
    """Inside navigation, a table of contents, a sidebar or a footer (PLOS's article body is 'toc-section': not one)."""
    for node in heading.parents:
        if node.name in _CHROME_TAGS:
            return True
        for token in [node.get("id") or ""] + (node.get("class") or []):
            token = token.lower()
            if token in _CHROME_TOKENS or token.startswith(_CHROME_PREFIXES):
                return True
    return False


def _block_text(block):
    """A block's paragraphs: its <p>s, or its own text when it has none (ScienceDirect, Atypon and MDPI print
    paragraphs as <div>s). Copy-link buttons and financial-disclosure notes are not acknowledgment text."""
    if block.name in ("script", "style", "button", "form") or block.find("button") or block.get("data-type") == \
            "financial-disclosure" or any("copy" in c for c in block.get("class") or []):
        return []
    # A funder widget is metadata, not a statement (#2239): a table of funders and grant numbers after the text (Pure
    # portals), a label/value list of awards (Zenodo, ORA: "Funding agency for: ... Grant: ...").
    if block.name in ("table", "dl") or (block.find(["dt", "dd"]) is not None and block.find("p") is None):
        return []
    # Atypon's pop-up of a cited reference, hidden inside the text beside its "[24]" (Elsevier's society journals,
    # Cell Press): the reference is not part of the sentence that cites it (#2239).
    if block.find(class_="dropBlock__holder") is not None:
        block = copy.copy(block)  # the parsers still read this soup
        for pop_up in block.find_all(class_="dropBlock__holder"):
            pop_up.decompose()
    paragraphs = [] if block.name == "p" else block.find_all("p")
    texts = [squash(p.get_text()) for p in paragraphs] or [squash(block.get_text())]
    # a list of links (a funder widget: "+ Simons Foundation More from this funder") is not a statement
    link_chars = sum(len(squash(a.get_text())) for a in block.find_all("a"))
    return [] if link_chars > 0.5 * sum(len(t) for t in texts) else texts


# A paragraph that opens with another section's label, printed run-in instead of as a heading (#2239). Under
# "Funding" it ends the statement (OUP: "<em>Conflict of interest statement.</em> None declared." after the funding
# paragraph). Under "Acknowledgments" such paragraphs are part of the section as printed ("Author contributions: ...",
# "Conflict of interest: ..."), except what AAS journals list after them: "Facilities: ...", "Software: ...".
_RUN_IN_LABEL = {
    "funding_statement": re.compile(
        r"^(?:conflicts? of interests?(?: statement)?|competing (?:financial )?interests?(?: statement)?|"
        r"declaration of (?:competing )?interests?|disclosures?(?: statement)?|"
        r"authors?['’]?s?['’]? contributions?(?: statement)?|credit author(?:ship)? (?:contribution )?statement|"
        r"data (?:and (?:code|materials?) )?availability(?: statement)?|availability of data(?: and materials?)?|"
        r"ethic(?:s|al) (?:approval|statement))\s*[.:]", re.I),
    "acknowledgments": re.compile(r"^(?:facilit(?:y|ies)|software)\s*[.:]", re.I),
}


# A paragraph that is only a bold label naming another section (_bold_label: "<p><strong>Declaration of conflicting
# interests</strong></p>", "Patient consent", "Provenance and peer review") heads that section: under "Funding" it ends
# the statement (#2239 round 7: a journal printing BMJ's back-matter labels inside its "Funding" block). A bold funder
# name or funding label is not one.
_OTHER_SECTION = re.compile(
    r"^(?:declarations?\b|conflicts? of interests?|competing (?:financial )?interests?|(?:patient |informed )?consent|"
    r"ethic(?:s|al)\b|provenance\b|authors?['’]?s?['’]? contributions?|"
    r"(?:data|code|materials?) (?:and \w+ )?availability|availability of\b|disclosures?\b|acknowledge?ments?\b)", re.I)


def _other_section_labels(block):
    """The texts of the block's paragraphs that are a bold label alone naming another section."""
    paragraphs = [block] if block.name == "p" else block.find_all("p")
    return {label for p in paragraphs if (label := _bold_label(p)) and _OTHER_SECTION.match(label)}


def _section_header(heading):
    """The block that holds a heading and its section tools, when the template wraps them together (ACS:
    div.article_content-header > ... > h2 beside an "ARTICLE SECTIONS / Jump To" menu): the section's text follows
    that block, not the heading (#2239). The heading itself when it stands alone."""
    block, limit = heading, len(squash(heading.get_text())) + 40
    if any(sibling.get_text(strip=True) for sibling in heading.find_next_siblings()):
        return heading  # its text follows it directly
    for parent in islice(heading.parents, 3):
        if len(squash(parent.get_text())) > limit:
            break
        if any("header" in token.lower() for token in parent.get("class") or []) or parent.name == "header":
            block = parent
    return block


def _section_after(heading, key):
    header = _section_header(heading)
    siblings = header.find_next_siblings()
    if not siblings and not squash(heading.parent.get_text()).replace(squash(heading.get_text()), "").strip():
        siblings = heading.parent.find_next_siblings()  # a heading wrapped alone in its own block
    paragraphs = []
    for sibling in siblings:
        if sibling.name in _HEADINGS or any(d.name in _HEADINGS for d in sibling.descendants):
            break
        texts = _block_text(sibling)
        labels = _other_section_labels(sibling) if key == "funding_statement" and texts else ()
        for i, text in enumerate(texts):
            if (_RUN_IN_LABEL[key].match(text) or text in labels) and (paragraphs or i):
                return "\n".join(p for p in paragraphs + texts[:i] if p) or None
        paragraphs += texts
    return "\n".join(p for p in paragraphs if p) or None


def headed_back_matter(soup, lp_content):
    if not any(raw_has(lp_content, word) for word in _HEADED_WORDS):
        return {}
    found = {}
    # a name-set scan of the tree: find_all() with a list of names is ~15x slower on large pages
    for heading in [tag for tag in soup.descendants if tag.name in _HEADINGS]:
        key = _key_for(heading.get_text())
        if key is None or key in found or _in_navigation(heading):
            continue
        if (text := _section_after(heading, key)) and len(text) >= 20:
            found[key] = text
    return found


# SciELO: the newer template lists references as div.ref-list ul.refList > li (number in sup.xref, text in a <div>);
# the classic one prints each as the <p> after an <!-- ref --> comment, number first ("1. Biermann JS. ..."), with a
# "[ Links ]" button.
_LEADING_NUMBER = re.compile(r"^(\d{1,4})\s*[.)]\s+")
_LINKS_BUTTON = re.compile(r"\[\s*(?:Links)?\s*\]")


_REFERENCES_ANCHOR = re.compile(r"refer|bibliogr|literat", re.I)
# How a reference opens: a surname, then initials ("Guimarães, f. H., A. P. do Prado ...", "Silva AB, Souza C. ...")
_ENTRY_OPENING = re.compile(r"[A-ZÀ-Þ][\w'’-]+(?: [A-ZÀ-Þ][\w'’-]+){0,2},? (?:[A-Za-z]\.|[A-Z]{1,3}[,.;]? )")


def _reads_like_entry(text):
    """A paragraph that reads like a reference: it opens with a name and its initials and carries a year."""
    return len(text) <= 1000 and bool(_ENTRY_OPENING.match(text)) and bool(_YEAR.search(text))


def _scielo_reference_list(soup):
    """(entries, sure): the article's reference list among the page's ref-list blocks (footnotes and table notes use
    the same markup): the one in a section named for references, else the longest, unsure when two real lists compete
    or when a reference is printed outside it."""
    blocks = [items for block in soup.select("div.ref-list") if (items := block.select("ul.refList > li"))]
    named = [block.select("ul.refList > li") for block in soup.select("div.articleSection[data-anchor] div.ref-list")
             if _REFERENCES_ANCHOR.search(block.find_parent("div", class_="articleSection")["data-anchor"])]
    if named and named[0]:
        return named[0], True
    if not blocks:
        return [], False
    longest = max(blocks, key=len)
    # No heading says where this list starts, and SciELO's markup of older articles leaves out references it could
    # not read: one printed as a plain paragraph right before the list is an entry the list lacks (#2239).
    before = next((text for p in longest[0].find_all_previous("p", limit=8) if (text := squash(p.get_text()))), "")
    return longest, sum(len(items) >= 2 for items in blocks) <= 1 and not _reads_like_entry(before)


def scielo_back_matter(soup, lp_content):
    labels, texts, sure = [], [], True
    if raw_has(lp_content, "refList") and (found := _scielo_reference_list(soup))[0]:
        items, sure = found
        for item in items:
            item = copy.copy(item)  # the parsers still read this soup
            number = item.find("sup", class_="xref")
            labels.append(number.extract().get_text(strip=True) if number else None)
            texts.append(squash(item.get_text(" ")))
    elif raw_has(lp_content, "<!-- ref -->"):
        for marker in soup.find_all(string=lambda s: isinstance(s, Comment) and s.strip() == "ref"):
            entry = marker.find_next_sibling()
            text = _LINKS_BUTTON.sub("", squash(entry.get_text(" "))) if entry is not None else ""
            number = _LEADING_NUMBER.match(text)
            labels.append(number.group(1) if number else None)
            texts.append(squash(text[number.end():] if number else text))
    refs = [{"raw": text, "doi": _printed_doi(text)} for text in texts if text]
    if not refs:
        return {}
    return {"references": refs, "references_complete": sure and len(refs) == len(texts) and _numbering_whole(labels)}
