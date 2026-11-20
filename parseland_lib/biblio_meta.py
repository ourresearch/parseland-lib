"""Volume, issue and pages from a landing page's citation meta tags (oxjob #1098 step 2a).

Open Journal Systems repositories lose the volume and issue on the way in: OJS 3's oai_dc repeats dc:source (the
citation "Journal; Vol. 1 No. 1 (2025): ..." and then the ISSN) and walden keeps only the last value, so 3.46M works
from repository records have no volume. The article page itself states them in its Highwire tags (citation_volume,
citation_issue, citation_firstpage, citation_lastpage); PRISM tags are the fallback. This module reads them so walden
can store them beside the parsed page and fill an empty volume/issue (walden decides what to trust; this only reports
what the page says).
"""

# key -> meta names in order of preference (compared lower-case; "prism:" is read as "prism.")
_TAGS = {
    "volume": ("citation_volume", "prism.volume"),
    "issue": ("citation_issue", "prism.number", "prism.issueidentifier"),
    "first_page": ("citation_firstpage", "prism.startingpage"),
    "last_page": ("citation_lastpage", "prism.endingpage"),
}
_MAX_LEN = 50  # longer is a sentence or a whole citation, not a volume, issue or page


def _usable(value):
    if not value:
        return None
    value = " ".join(value.split())
    if not value or len(value) > _MAX_LEN or not any(ch.isalnum() for ch in value):
        return None
    return value


def meta_biblio(soup):
    """{volume, issue, first_page, last_page} from the page's meta tags, or None when the page states none of them.

    The first usable value of the most preferred tag wins for each key. Only <meta> attributes are read; the soup is
    not changed.
    """
    seen = {}
    for meta in soup.find_all("meta"):
        name = meta.get("name") or meta.get("property")
        if not isinstance(name, str):
            continue
        name = name.strip().lower().replace("prism:", "prism.")
        content = meta.get("content")
        if not isinstance(content, str):
            continue
        value = _usable(content)
        if value is not None and name not in seen:
            seen[name] = value
    biblio = {key: next((seen[n] for n in names if n in seen), None) for key, names in _TAGS.items()}
    return biblio if any(biblio.values()) else None
