"""Psychopharmacology Institute (psychopharmacologyinstitute.com and its language subdomains, DOI prefix 10.64239),
oxjob #2339.

WordPress pages of CME lessons ("Quick Take" podcasts, slide lectures, expert interviews) and publications (drug guides,
interviews), with no citation_* meta tags. A lesson or publication page prints its byline in
<section class="author-details">: one card per author, the name with degrees in h2.author-name, then
"<job title> - <institution>" with the institution in span.author-affiliation-name. The byline is read from those
cards: the Yoast JSON-LD author is sometimes another person (a stale "Experts" entry). No byline marks a corresponding
author.

Interview pages ("Expert Consultations") give each card a role line (div.author-type, translated on the language
subdomains): "Guest" and "Interviewed by". The interviewer is the site's host and medical editor (the CME block lists
them under "Medical Editors"; the JSON-LD Interview node and the "Written by" meta credit only the guest), so only the
cards that share the first card's role are read. Their cards print no institution; the JSON-LD author entry of the same
person gives it.

The job title sometimes names an organisation ("Oregon Health & Science University", "Professor of Clinical
Psychiatry, Harvard Medical School"); those parts are affiliations too, a bare role ("Associate Professor of
Psychiatry") never is.

The abstract is left to parse_page's readers (they read what they read before this parser), and the pages show no
acknowledgments, funding statement or reference list of the work's own (a Quick Take's "Reference" is the one paper it
discusses). The home page, where many DOIs of the site resolve, shows author cards in its publication listings
(div.author-details): it presents no one work, and the parser never reads it.
"""
import json
import re
import unicodedata

from parseland_lib.publisher.parsers.parser import PublisherParser

_SITE_NAME = "Psychopharmacology Institute"
_DOMAIN = "psychopharmacologyinstitute.com"
# Words that make a job-title part name an organisation (the site's subdomains translate some institution names).
_ORG = re.compile(r"\b(universit\w*|universidad\w*|universidade\w*|universiteit\w*|uniwersytet\w*|üniversite\w*|"
                  r"hospital\w*|ospedale|ziekenhuis|school|college|institut\w*|istituto|instituto|clinic|clinics|"
                  r"cl[ií]nica|klinik\w*|cent(?:er|re|ro)s?|foundation|fundaci[oó]n|academ\w*)\b", re.I)
_HONORIFIC = re.compile(r"^(?:prof\.?|professor|dr\.?)\s+", re.I)


def _clean(text):
    return " ".join((text or "").split())


def _fold(name):
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^\w]+", " ", s).split())


def _head_meta(soup, prop):
    """The content of <meta property=prop> among <head>'s own children: a few dozen nodes, never a walk of the
    whole page (production asks every parser about every DOI page, oxjob #2239)."""
    html = soup.find("html", recursive=False)
    head = html.find("head", recursive=False) if html else None
    tag = head.find("meta", attrs={"property": prop}, recursive=False) if head else None
    return (tag.get("content") or "").strip() if tag else ""


def _job_title_orgs(job_title):
    """The organisations a job title names: each " - " part that names one, from its first comma-part that does
    ("Professor of Clinical Psychiatry, Harvard Medical School" -> "Harvard Medical School")."""
    out = []
    for part in re.split(r"\s+[-–—]\s+", job_title):
        pieces = [p.strip() for p in part.split(",")]
        start = next((i for i, p in enumerate(pieces) if _ORG.search(p)), None)
        if start is not None:
            out.append(", ".join(p for p in pieces[start:] if p))
    return out


class PsychopharmacologyInstitute(PublisherParser):
    parser_name = "psychopharmacologyinstitute"

    def is_publisher_specific_parser(self):
        if _head_meta(self.soup, "og:site_name") != _SITE_NAME:
            return False
        url = _head_meta(self.soup, "og:url").split("//", 1)[-1].split("/", 1)[0].lower()
        return url == _DOMAIN or url.endswith("." + _DOMAIN)

    def _cards(self):
        return self.soup.select("section.author-details .author-info")

    def authors_found(self):
        return self.is_publisher_specific_parser() and any(c.select_one(".author-name") for c in self._cards())

    def _json_ld_affiliations(self):
        """{folded person name: [affiliation names]} from the page's JSON-LD author entries."""
        out = {}
        for script in self.soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
            except ValueError:
                continue
            nodes = data.get("@graph", [data]) if isinstance(data, dict) else data
            for node in nodes if isinstance(nodes, list) else []:
                authors = node.get("author") if isinstance(node, dict) else None
                for person in authors if isinstance(authors, list) else [authors]:
                    if not isinstance(person, dict) or not isinstance(person.get("name"), str):
                        continue
                    affs = person.get("affiliation")
                    names = [_clean(a.get("name") if isinstance(a, dict) else a)
                             for a in (affs if isinstance(affs, list) else [affs])
                             if isinstance(a, (dict, str))]
                    names = [n for n in names if n]
                    if names:
                        out.setdefault(_fold(person["name"]), names)
        return out

    def parse(self):
        cards = self._cards()
        role = lambda c: _clean(t.get_text(" ")) if (t := c.select_one(".author-type")) else ""  # noqa: E731
        # Interview pages: the first card's role is the guest's; a card with another role is the interviewer.
        if cards and role(cards[0]):
            cards = [c for c in cards if role(c) == role(cards[0])]
        json_ld = None
        authors = []
        for card in cards:
            name_tag = card.select_one(".author-name")
            # "Paul S. Links, M.D., F.R.C.P.C.": the degrees follow the first comma; "Prof. Philip Cowen": the
            # honorific leads. shortcut: a suffix such as "Jr." after a comma would be cut too; none on the pages.
            name = _clean(name_tag.get_text(" ")).split(",")[0].strip() if name_tag else ""
            name = _HONORIFIC.sub("", name)
            if not name:
                continue
            job = _clean(t.get_text(" ")) if (t := card.select_one(".author-job-title")) else ""
            aff = _clean(t.get_text(" ")) if (t := card.select_one(".author-affiliation-name")) else ""
            # page order: the job title's organisations, then the institution (one that repeats it is dropped)
            affs = [o for o in _job_title_orgs(job) if _fold(o) not in _fold(aff)] + ([aff] if aff else [])
            if not affs:
                if json_ld is None:
                    json_ld = self._json_ld_affiliations()
                affs = list(json_ld.get(_fold(name), []))
            authors.append({"name": name, "affiliations": affs, "is_corresponding": False})
        return {
            "authors": authors,
            "abstract": None,
            "acknowledgments": None,
            "funding_statement": None,
            "references": None,
            "references_complete": False,
        }
