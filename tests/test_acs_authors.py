"""In-process tests for ACS author separator filtering.

ACS author lists (ul.loa) interleave separator <li> elements (", " and
" and ") between the real author <li>s. Without a loa-info-name div these fell
through to author.text and were emitted as junk authors ("," / "and"), tanking
author precision (Authors F1 ~0.84 on the gold slice; many rows 0.71-0.80).
ACS.parse() now skips any <li> whose text is just a separator.

Hand-crafted HTML — no Taxicab, no network.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from parseland_lib.publisher.parsers.acs import ACS

ACS_OG = '<meta property="og:url" content="https://pubs.acs.org/doi/10.1021/x" />'


def _wrap(loa_inner: str) -> str:
    return (
        f"<html><head>{ACS_OG}</head><body>"
        f'<ul class="loa">{loa_inner}</ul>'
        "</body></html>"
    )


def _names(authors):
    out = []
    for a in authors:
        out.append(a.get("name") if isinstance(a, dict) else getattr(a, "name", None))
    return out


def test_separator_lis_are_skipped():
    # Two real authors separated by a ", " and an " and " li (nbsp like the real
    # markup).
    loa = (
        '<li><div class="loa-info-name">Jane A. Smith</div></li>'
        "<li>,\xa0</li>"
        '<li><div class="loa-info-name">John B. Doe</div></li>'
        "<li>\xa0and\xa0</li>"
        '<li><div class="loa-info-name">Mary C. Lee</div></li>'
    )
    out = ACS(BeautifulSoup(_wrap(loa), "lxml")).parse()
    assert _names(out["authors"]) == ["Jane A. Smith", "John B. Doe", "Mary C. Lee"]


def test_plain_comma_and_separators_without_name_div():
    # Older template: names are bare li text, separators are bare too.
    loa = "<li>Jane A. Smith</li><li>, </li><li>and </li><li>John B. Doe</li>"
    out = ACS(BeautifulSoup(_wrap(loa), "lxml")).parse()
    assert _names(out["authors"]) == ["Jane A. Smith", "John B. Doe"]


def test_real_author_named_anderson_not_dropped():
    # Guard against an over-eager "and" filter: "Anderson" must survive.
    loa = (
        '<li><div class="loa-info-name">Kurt Andersson</div></li>'
        "<li>\xa0and\xa0</li>"
        '<li><div class="loa-info-name">Lee Anderson</div></li>'
    )
    out = ACS(BeautifulSoup(_wrap(loa), "lxml")).parse()
    assert _names(out["authors"]) == ["Kurt Andersson", "Lee Anderson"]


# --- alternate template: hlFld-ContribAuthor names + shared aff-info ---------


def _affs(author):
    return (
        author.get("affiliations")
        if isinstance(author, dict)
        else getattr(author, "affiliations", [])
    )


def test_alternate_template_clean_name_and_shared_affiliation():
    # No loa-info-name / loa-info-affiliations. Name comes from
    # hlFld-ContribAuthor (clean, no xref symbol); affiliation from the
    # page-level aff-info span.aff-text, shared across authors.
    html = (
        f"<html><head>{ACS_OG}</head><body>"
        '<ul class="loa">'
        '<li><span><span class="hlFld-ContribAuthor">Boris Le Guennic</span>'
        '<span class="author-xref-symbol"><sup>†</sup></span></span></li>'
        '<li class="comma-separator"><span class="comma-separator"> and </span></li>'
        '<li><span><span class="hlFld-ContribAuthor">Tavon Floyd</span></span></li>'
        "</ul>"
        '<div class="affiliations"><div class="aff-info">'
        '<span class="aff-symbol"></span> '
        '<span class="aff-text">Department of Chemistry, University at Buffalo</span>'
        "</div></div>"
        "</body></html>"
    )
    out = ACS(BeautifulSoup(html, "lxml")).parse()
    # name is clean (no trailing dagger), separator li dropped
    assert _names(out["authors"]) == ["Boris Le Guennic", "Tavon Floyd"]
    # shared affiliation assigned to both
    for a in out["authors"]:
        assert _affs(a) == ["Department of Chemistry, University at Buffalo"]


def _corr(author):
    return (
        author.get("is_corresponding")
        if isinstance(author, dict)
        else getattr(author, "is_corresponding", None)
    )


def test_corresponding_from_xref_star():
    # Alternate template: corresponding author marked by '*' in
    # author-xref-symbol, not <strong>*</strong>.
    html = (
        f"<html><head>{ACS_OG}</head><body>"
        '<ul class="loa">'
        '<li><span><span class="hlFld-ContribAuthor">Kungen Teii</span>'
        '<span class="author-xref-symbol"><sup>*</sup></span>'
        '<span class="author-xref-symbol"><sup>†</sup></span></span></li>'
        '<li><span><span class="hlFld-ContribAuthor">Takuro Hori</span>'
        '<span class="author-xref-symbol"><sup>†</sup></span></span></li>'
        "</ul></body></html>"
    )
    out = ACS(BeautifulSoup(html, "lxml")).parse()
    flagged = [
        (a.get("name") if isinstance(a, dict) else a.name) for a in out["authors"] if _corr(a)
    ]
    assert flagged == ["Kungen Teii"]


def test_non_star_xref_not_flagged_corresponding():
    # Authors with only a dagger xref (affiliation marker) must NOT be flagged.
    html = (
        f"<html><head>{ACS_OG}</head><body>"
        '<ul class="loa"><li><span>'
        '<span class="hlFld-ContribAuthor">Takuro Hori</span>'
        '<span class="author-xref-symbol"><sup>†</sup></span></span></li></ul>'
        "</body></html>"
    )
    out = ACS(BeautifulSoup(html, "lxml")).parse()
    assert _corr(out["authors"][0]) is False


def test_corresponding_from_cloudflare_protected_email():
    html = (
        f"<html><head>{ACS_OG}</head><body>"
        '<ul class="loa">'
        '<li><span class="hlFld-ContribAuthor">P. Pandit</span></li>'
        '<li><span class="comma-separator">and</span></li>'
        '<li><span class="hlFld-ContribAuthor">S. Basu</span></li>'
        "</ul>"
        '<div class="fnGroupItem"><p>* Corresponding author telephone: '
        '<a href="/cdn-cgi/l/email-protection" class="__cf_email__" '
        'data-cfemail="84f7e6e5f7f1c4e7ece1e9ede7e5e8aaededf0e0aae1f6eae1f0aaedea">'
        "[email protected]</a>.</p></div>"
        "</body></html>"
    )
    out = ACS(BeautifulSoup(html, "lxml")).parse()
    assert [(a.name, _corr(a)) for a in out["authors"]] == [
        ("P. Pandit", False),
        ("S. Basu", True),
    ]


def test_corresponding_from_old_template_mailto_name_match():
    html = (
        f"<html><head>{ACS_OG}</head><body>"
        '<ul class="loa">'
        '<li><span class="hlFld-ContribAuthor">Matt Hengel</span></li>'
        '<li><span class="hlFld-ContribAuthor">B. Hung</span></li>'
        "</ul>"
        '<p>* Author to whom correspondence should be addressed '
        '<a href="mailto:mjhengel@ucdavis.edu">email</a>.</p>'
        "</body></html>"
    )
    out = ACS(BeautifulSoup(html, "lxml")).parse()
    assert [(a.name, _corr(a)) for a in out["authors"]] == [
        ("Matt Hengel", True),
        ("B. Hung", False),
    ]


def test_corresponding_from_unique_initials_email():
    html = (
        f"<html><head>{ACS_OG}</head><body>"
        '<ul class="loa">'
        '<li><span class="hlFld-ContribAuthor">Frank Preugschat</span></li>'
        '<li><span class="hlFld-ContribAuthor">Dana P. Danger</span></li>'
        "</ul>"
        '<p>* To whom correspondence should be addressed. '
        '<a href="mailto:FP41724@glaxowellcome.com">email</a>.</p>'
        "</body></html>"
    )
    out = ACS(BeautifulSoup(html, "lxml")).parse()
    assert [(a.name, _corr(a)) for a in out["authors"]] == [
        ("Frank Preugschat", True),
        ("Dana P. Danger", False),
    ]


def test_invalid_or_ambiguous_correspondence_email_not_flagged():
    invalid_html = (
        f"<html><head>{ACS_OG}</head><body>"
        '<ul class="loa"><li><span class="hlFld-ContribAuthor">Min Shi</span></li></ul>'
        '<p>* To whom correspondence should be addressed. '
        '<a href="mailto:KCC-1@NH2">email</a>.</p>'
        "</body></html>"
    )
    invalid_out = ACS(BeautifulSoup(invalid_html, "lxml")).parse()
    assert _corr(invalid_out["authors"][0]) is False

    ambiguous_html = (
        f"<html><head>{ACS_OG}</head><body>"
        '<ul class="loa">'
        '<li><span class="hlFld-ContribAuthor">Frank Preugschat</span></li>'
        '<li><span class="hlFld-ContribAuthor">Fiona Park</span></li>'
        "</ul>"
        '<p>* Corresponding author. <a href="mailto:fp41724@example.org">email</a>.</p>'
        "</body></html>"
    )
    ambiguous_out = ACS(BeautifulSoup(ambiguous_html, "lxml")).parse()
    assert [(a.name, _corr(a)) for a in ambiguous_out["authors"]] == [
        ("Frank Preugschat", False),
        ("Fiona Park", False),
    ]


def test_modern_template_per_author_affs_not_overridden_by_shared():
    # Modern template has per-author loa-info-affiliations; the shared aff-info
    # fallback must NOT fire.
    html = (
        f"<html><head>{ACS_OG}</head><body>"
        '<ul class="loa"><li>'
        '<div class="loa-info-name">Jane Smith</div>'
        '<div class="loa-info-affiliations"><div>Dept A, Uni X</div></div>'
        "</li></ul>"
        '<div class="aff-info"><span class="aff-text">SHOULD NOT WIN</span></div>'
        "</body></html>"
    )
    out = ACS(BeautifulSoup(html, "lxml")).parse()
    assert _affs(out["authors"][0]) == ["Dept A, Uni X"]
