"""Field matching for the Parseland gold set and gate (#1791). One module, three uses:
pass A vs pass B agreement, Parseland vs gold scoring, and grounding gold values in the page bytes.

A "record" is {"authors": [{"name", "affiliations": [str], "is_corresponding"}], "abstract", "pdf_url",
"pdf_alternates": [str], "license"}. Every field compares to a page-level right/wrong:

  authors         same number of authors and each position's name matches (order counts)
  affiliations    for every gold author, the affiliation set matches the aligned author's (strict: a partial
                  string is not a match); both empty is right
  corresponding   the set of corresponding authors matches (unmarked = false)
  abstract        both absent, or similarity >= 0.90 after whitespace and case normalisation
  pdf_url         both absent, or the candidate equals the gold link or one of its alternates (canonicalised)
  license         same slug ("none" when absent)

The back matter (#2215's output contract; scored since corpus v1.7, only on pages whose gold row lists them in
"fields", see score.py):

  acknowledgments    both absent, or similarity >= 0.90 after folding and dropping a leading heading word, and the
                     same digit-bearing tokens (grant numbers, years: a one-digit change scores ~0.99)
  funding_statement  same rule
  references         both lists called whole or both not (downstream takes a list only when it is whole, so a
                     partial list called whole is wrong, and two partial lists are right whatever their entries);
                     when both are whole: the same number of entries, >= 90% of entries holding the gold entry's
                     first and last 20 letters and digits (links and DOIs dropped; the gold is a model's
                     transcription, so formatting differs), no entry DOI that conflicts with the gold's, and >= 90% of
                     the gold's entry DOIs given
  references_safe    the precision side: right unless the candidate calls a list whole that isn't the gold's whole
                     list (as above, without the DOI share). A page wrong on references both before and after can
                     still turn unsafe; this field counts that as a loss, and wins on references never offset it.

Unlike June's scorer, a value the gold doesn't have counts as wrong (no dropped rows), and empty-vs-empty is
"right" but reported separately (see presence()).
"""
from __future__ import annotations

import html as htmllib
import re
import unicodedata
from urllib.parse import unquote, urljoin, urlsplit

from rapidfuzz import fuzz

FIELDS = ["authors", "affiliations", "corresponding", "abstract", "pdf_url", "license"]
# #2215's keys, scored where the gold has them; references_safe is the precision side of references (see compare())
BACK_MATTER = ["acknowledgments", "funding_statement", "references", "references_safe"]
ALL_FIELDS = FIELDS + BACK_MATTER
# the label keys a back-matter field reads: a gold row vouching for the field must carry them (score.page_fields)
GOLD_KEYS = {"acknowledgments": ["acknowledgments"], "funding_statement": ["funding_statement"],
             "references": ["references", "references_complete"],
             "references_safe": ["references", "references_complete"]}
LICENSES = {"cc-by", "cc-by-sa", "cc-by-nd", "cc-by-nc", "cc-by-nc-sa", "cc-by-nc-nd", "public-domain",
            "publisher-specific-oa", "other-oa", "unspecified-oa"}
ABSTRACT_MIN = 0.90
AFF_MIN = 90


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", htmllib.unescape(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().casefold()


DASHES = re.compile(r"[‐‑‒–—―−­-]")
QUOTES = re.compile(r"[‘’ʼ`´]")


def name_tokens(name: str) -> list[str]:
    # any dash splits (Garcia-Lopez == Garcia Lopez == Garcia‐Lopez); curly apostrophes become straight
    n = QUOTES.sub("'", DASHES.sub(" ", fold(name)))
    if "," in n:  # "Family, Given" -> "Given Family"
        fam, _, giv = n.partition(",")
        n = f"{giv} {fam}"
    n = re.sub(r"[^\w\s'-]", " ", n)
    toks = [t.strip("'-") for t in re.split(r"[\s]+", n) if t.strip("'-")]
    return [t for t in toks if t not in {"dr", "prof", "phd", "md", "msc", "bsc", "jr", "sr", "mr", "mrs", "ms"}]


def name_match(a: str, b: str) -> bool:
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return False
    if ta == tb or set(ta) == set(tb):
        return True
    ja, jb = "".join(ta), "".join(tb)
    if ja == jb:  # CJK names, spacing differences
        return True
    # same family name (shared longest token or last token) and compatible first initials
    full_a = {t for t in ta if len(t) > 1}
    full_b = {t for t in tb if len(t) > 1}
    shared = full_a & full_b
    if not shared:
        return False
    rest_a = [t for t in ta if t not in shared]
    rest_b = [t for t in tb if t not in shared]
    if not rest_a or not rest_b:
        return len(shared) >= 2 or (not rest_a and not rest_b)
    return rest_a[0][0] == rest_b[0][0]


def norm_aff(s: str) -> str:
    s = fold(s)
    s = re.sub(r"^\s*[\(\[]?(\d{1,2}|[a-z])[\)\].,]?\s+", "", s)  # leading marker: "1 ", "(a) ", "2."
    return re.sub(r"[^\w]+", " ", s).strip()


ORG_WORD = re.compile(r"\b(universi\w*|univ|institut\w*|college|colegio|hospital\w*|klinik\w*|clinic\w*|academ\w*|"
                      r"cent(er|re|ro)|laborat\w*|ministr\w*|council|agency|company|corporation|inc|ltd|gmbh|"
                      r"foundation|fundac\w*|observator\w*|museum|library|unit|school|ecole|escuela|cnrs|inserm|"
                      r"csic|nih|mrc|polytechnic|politecnico|hochschule|instituto|istituto)\b")


def aff_match(a: str, b: str) -> bool:
    x, y = norm_aff(a), norm_aff(b)
    if not x or not y:
        return False
    if x == y:
        return True
    short, long_ = sorted((x, y), key=len)
    # One string is the other plus or minus an address line or a lead-in ("Professor X is director of ..."):
    # the same affiliation, as long as the shorter one still names an organisation. A bare fragment such as
    # "Department of Physics" is not the affiliation (chosen on the pilot and cross-family checks, 23 Oct).
    if set(short.split()) <= set(long_.split()) and ORG_WORD.search(short):
        return True
    if len(short) < 0.75 * len(long_):
        return False
    return fuzz.token_sort_ratio(x, y) >= AFF_MIN


def aff_sets_match(a: list[str], b: list[str]) -> bool:
    a = [s for s in a or [] if norm_aff(s)]
    b = [s for s in b or [] if norm_aff(s)]
    if len(a) != len(b):
        # pages that join several affiliations into one string: compare the concatenations
        return bool(a) and bool(b) and aff_match(" ".join(a), " ".join(b))
    used = set()
    for s in a:
        hit = next((j for j, t in enumerate(b) if j not in used and aff_match(s, t)), None)
        if hit is None:
            return False
        used.add(hit)
    return True


def align(gold_authors, cand_authors):
    """Map gold author index -> candidate index by name, preferring the same position."""
    out, used = {}, set()
    for i, g in enumerate(gold_authors):
        if i < len(cand_authors) and i not in used and name_match(g["name"], cand_authors[i]["name"]):
            out[i] = i; used.add(i); continue
        j = next((j for j, c in enumerate(cand_authors) if j not in used and name_match(g["name"], c["name"])), None)
        if j is not None:
            out[i] = j; used.add(j)
    return out


def canon_url(u: str | None, base: str | None = None) -> str | None:
    if not u:
        return None
    u = htmllib.unescape(u.strip())
    if base:
        u = urljoin(base, u)
    p = urlsplit(u)
    host = p.netloc.lower().removeprefix("www.")
    path = unquote(p.path).rstrip("/")
    path = re.sub(r"/doi/(pdfdirect|epdf|pdf|reader)/", "/doi/pdf/", path)
    q = "&".join(sorted(kv for kv in p.query.split("&") if kv and not re.match(r"(download|dl|utm_\w+|via)=", kv, re.I)))
    return f"{host}{path}" + (f"?{q}" if q else "")


def norm_license(v) -> str:
    v = (v or "").strip().lower()
    return v if v in LICENSES else "none"


def norm_abstract(s):
    s = fold(s or "")
    s = re.sub(r"^(abstract|summary)[\s:.-]+", "", s)
    return s or None


STATEMENT_HEADING = re.compile(
    r"^(acknowledge?ments?|funding( information| statement| sources?)?|financial support)(?:[\s:.-]+|$)")
DIGIT_TOKEN = re.compile(r"\S*\d\S*")


def norm_statement(s):
    """Acknowledgments or funding text, folded, without a leading heading word (as #2239's scorer, work/newfields.py);
    a heading alone is no statement."""
    return STATEMENT_HEADING.sub("", fold(s if isinstance(s, str) else "")) or None


def digit_tokens(s):
    """Grant numbers, years and other digit-bearing tokens, punctuation dropped: the facts a 0.90 ratio can miss."""
    return sorted(re.sub(r"[^\w]+", "", t) for t in DIGIT_TOKEN.findall(s or ""))


DOI_PREFIX = re.compile(r"^(?:doi:\s*)?(?:(?:https?:)?//(?:dx\.)?doi\.org/)?")


def norm_doi(d):
    d = fold(unquote(d)) if isinstance(d, str) else ""
    return DOI_PREFIX.sub("", d).strip() or None


ALNUM = re.compile(r"[^0-9a-z]+")
LINKS = re.compile(r"(?:https?://|www\.|doi:\s*)\S*")
ENTRY_ENDS = 20  # alphanumerics compared at each end of an entry
ENTRIES_RIGHT = 0.9  # share of entries whose text and DOI must hold for a whole list to be right
DOI_RECALL = 0.9  # share of the gold's entry DOIs the candidate must give at the same positions


def entry_key(raw):
    """An entry's text as letters and digits only, links and DOIs dropped (they're checked on their own)."""
    return ALNUM.sub("", LINKS.sub(" ", fold(raw if isinstance(raw, str) else "")))


def entry_match(g, c) -> bool:
    """The candidate entry holds the gold entry's first and last alphanumerics: a cut entry ("a) ...; b) ..." kept to
    a)), an entry run into the next, markup or key=value text in place of the entry all miss (#2215 Test 3)."""
    x, y = entry_key(g.get("raw")), entry_key(c.get("raw"))
    if not x:
        return True  # the gold entry is a link or DOI alone: its DOI decides
    return x[:ENTRY_ENDS] in y and x[-ENTRY_ENDS:] in y


def whole_list(rec: dict) -> list | None:
    """The record's reference list if it is called whole, else None (downstream takes only whole lists; parse_page
    never calls an empty list whole)."""
    refs = rec.get("references")
    return refs if rec.get("references_complete") is True and isinstance(refs, list) and refs else None


def lists_match(g: list, c: list, doi_recall: bool = True) -> bool:
    """Same entry count, >= 90% of entries holding the gold entry's text, no DOI that differs from the gold's at the
    same position, and (doi_recall) >= 90% of the gold's entry DOIs given."""
    if len(g) != len(c):
        return False
    gd = [norm_doi(a.get("doi")) for a in g]
    cd = [norm_doi(b.get("doi")) for b in c]
    if any(x and y and x != y for x, y in zip(gd, cd)):
        return False
    if doi_recall and any(gd) and sum(1 for x, y in zip(gd, cd) if x and x == y) < DOI_RECALL * sum(map(bool, gd)):
        return False
    return sum(entry_match(a, b) for a, b in zip(g, c)) >= ENTRIES_RIGHT * len(g)


def compare(field: str, gold: dict, cand: dict) -> bool:
    if field in ("acknowledgments", "funding_statement"):
        x, y = norm_statement(gold.get(field)), norm_statement(cand.get(field))
        if not x or not y:
            return not x and not y
        return fuzz.ratio(x, y) / 100 >= ABSTRACT_MIN and digit_tokens(x) == digit_tokens(y)
    if field in ("references", "references_safe"):
        g, c = whole_list(gold), whole_list(cand)
        if field == "references_safe" and c is None:
            return True  # nothing called whole: nothing unsafe to ingest
        if g is None or c is None:
            return g is None and c is None
        # a whole list missing some entry DOIs is a poorer ingest, not a wrong one: safety doesn't ask for them
        return lists_match(g, c, doi_recall=field == "references")
    ga, ca = gold.get("authors") or [], cand.get("authors") or []
    if field == "authors":
        return len(ga) == len(ca) and all(name_match(g["name"], c["name"]) for g, c in zip(ga, ca))
    if field == "affiliations":
        if gold.get("affiliation_linking") == "unlinked":
            gu = sorted({a for g in ga for a in g.get("affiliations") or []})
            cu = sorted({a for c in ca for a in c.get("affiliations") or []})
            return aff_sets_match(gu, cu)
        m = align(ga, ca)
        for i, g in enumerate(ga):
            gaff = g.get("affiliations") or []
            caff = ca[m[i]].get("affiliations") or [] if i in m else []
            if not gaff and not caff:
                continue
            if not aff_sets_match(gaff, caff):
                return False
        if not ga:  # gold has no authors: candidate affiliations are wrong
            return not any(c.get("affiliations") for c in ca)
        return True
    if field == "corresponding":
        m = align(ga, ca)
        gset = {i for i, g in enumerate(ga) if g.get("is_corresponding")}
        cset = {i for i in m if ca[m[i]].get("is_corresponding")}
        extra = any(c.get("is_corresponding") for j, c in enumerate(ca) if j not in m.values())
        return gset == cset and not extra
    if field == "abstract":
        x, y = norm_abstract(gold.get("abstract")), norm_abstract(cand.get("abstract"))
        if not x or not y:
            return not x and not y
        return fuzz.ratio(x, y) / 100 >= ABSTRACT_MIN
    if field == "pdf_url":
        x = canon_url(gold.get("pdf_url"))
        y = canon_url(cand.get("pdf_url"))
        if not x or not y:
            return not x and not y
        alts = {x} | {canon_url(a) for a in gold.get("pdf_alternates") or [] if a}
        return y in alts
    if field == "license":
        return norm_license(gold.get("license")) == norm_license(cand.get("license"))
    raise KeyError(field)


def present(field: str, rec: dict) -> bool:
    a = rec.get("authors") or []
    return {
        "authors": bool(a),
        "affiliations": any(x.get("affiliations") for x in a),
        "corresponding": any(x.get("is_corresponding") for x in a),
        "abstract": bool(norm_abstract(rec.get("abstract"))),
        "pdf_url": bool(rec.get("pdf_url")),
        "license": norm_license(rec.get("license")) != "none",
        "acknowledgments": bool(norm_statement(rec.get("acknowledgments"))),
        "funding_statement": bool(norm_statement(rec.get("funding_statement"))),
        "references": whole_list(rec) is not None,  # present = a whole list, the only kind downstream takes
        "references_safe": whole_list(rec) is not None,
    }[field]


def _refs(refs):
    if not isinstance(refs, list):
        return None
    return [{"raw": r.get("raw") or "", "doi": r.get("doi")} for r in refs if isinstance(r, dict)]


def from_label(label: dict) -> dict:
    """Gold label (labeller schema) -> record."""
    return {
        "authors": [{"name": a["name"], "affiliations": a.get("affiliations") or [],
                     "is_corresponding": bool(a.get("is_corresponding"))} for a in label.get("authors") or []],
        "affiliation_linking": label.get("affiliation_linking"),
        "abstract": label.get("abstract"),
        "pdf_url": label.get("pdf_url"),
        "pdf_alternates": label.get("pdf_url_alternates") or [],
        "license": label.get("license"),
        "acknowledgments": label.get("acknowledgments"),
        "funding_statement": label.get("funding_statement"),
        "references": _refs(label.get("references")),
        "references_complete": label.get("references_complete") is True,
    }


def from_parseland(out: dict) -> dict:
    """parse_page() response -> record."""
    pdf = next((u["url"] for u in out.get("urls") or [] if u.get("content_type") == "pdf"), None)
    return {
        "authors": [{"name": a.get("name") or "", "affiliations": [x.get("name") for x in a.get("affiliations") or []
                                                                   if x.get("name")],
                     "is_corresponding": bool(a.get("is_corresponding"))} for a in out.get("authors") or []],
        "abstract": out.get("abstract"),
        "pdf_url": pdf,
        "license": out.get("license"),
        "acknowledgments": out.get("acknowledgments"),
        "funding_statement": out.get("funding_statement"),
        "references": _refs(out.get("references")),
        "references_complete": out.get("references_complete") is True,
    }


# ---- grounding: is each gold value actually in the stored page? ----

def page_text(html: str) -> str:
    """Folded text of the page including attribute values and script JSON (where values can legitimately live)."""
    t = htmllib.unescape(html)
    t = t.replace("\\/", "/").replace('\\"', '"')
    t = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), t)
    t = re.sub(r"<[^>]+?>", " ", t) + " " + " ".join(re.findall(r'(?:href|src|content|data-[\w-]+)="([^"]*)"', html))
    return re.sub(r"[^\w]+", " ", fold(t))


def grounded(value: str, text: str, min_share: float = 1.0) -> bool:
    toks = [t for t in re.sub(r"[^\w]+", " ", fold(value)).split() if t]
    if not toks:
        return True
    hay = f" {text} "
    if f" {' '.join(toks)} " in hay:
        return True
    found = sum(1 for t in toks if f" {t} " in hay)
    return found / len(toks) >= min_share


def grounding(label: dict, html: str) -> dict:
    text = page_text(html)
    rec = from_label(label)
    out = {}
    names = [a["name"] for a in rec["authors"]]
    out["authors"] = all(grounded(n, text, 0.99) for n in names) if names else None
    affs = [x for a in rec["authors"] for x in a["affiliations"]]
    out["affiliations"] = all(grounded(x, text, 0.85) for x in affs) if affs else None
    ab = rec["abstract"]
    out["abstract"] = grounded(ab[:300], text, 0.9) and grounded(ab[-200:], text, 0.9) if ab else None
    pdf = label.get("pdf_url")
    if pdf:
        path = urlsplit(pdf).path
        out["pdf_url"] = grounded(path, text, 1.0) or grounded(pdf, text, 1.0)
    else:
        out["pdf_url"] = None
    ev = label.get("license_evidence")
    out["license"] = grounded(ev, text, 0.85) if ev and label.get("license") != "none" else None
    return out
