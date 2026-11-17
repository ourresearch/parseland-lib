"""IAFOR (The International Academic Forum): papers.iafor.org, its WordPress research archive of conference papers
(/submission<id>/), and its journals' article pages on iafor.org (/journal/<journal>/<issue>/article-<n>/) (oxjob #2339).

Until this parser the generic reading of these pages took the WordPress post's labels for authors ("Paper
Information", "Category: ...", "Posted by James Alexander Gordon", the site's poster) and the proceedings note
("This paper is part of the ECE2025 Conference Proceedings (View) ...") for the abstract, or the citation_author
tags alone, without affiliations. Each page lists its authors as plain lines "Name, Affiliation, Country" in
div.entry-content, under a label:

- current papers: <h3>Author Information</h3>, then <h3>Abstract</h3>;
- older papers (2020-2022, link rel=canonical and no og:url): <h4>Abstract</h4> first, then
  <strong>Author Information</strong><br> below it;
- journal articles: <p><strong>Author:</strong> one line, or <strong>Authors:</strong><br> one per line, ended by
  <strong>Email:</strong>; then <h4>Abstract</h4> and <h4>Keywords</h4>.
No layout marks a corresponding author (a journal page's single "Email:" line names nobody), and none prints a
reference list, acknowledgments or funding section. The parser returns no abstract: once it wins the page, parse_page's
own "Abstract" heading reader prints the right one (71 of 76 sample pages the same text, 4 differing in one space, one
left empty: 87 works, under the swarm's 1,000-work floor for a field's own code).
"""
import re

from bs4 import Comment, NavigableString, Tag

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import squash

_SITE = re.compile(r"^https?://(?:www\.|papers\.)?iafor\.org/", re.I)
_AUTHOR_LABEL = re.compile(r"^(?:author information|authors?)\s*:?$", re.I)
_SUFFIX = re.compile(r"^(?:jr|sr|ii|iii|iv)\.?$", re.I)
_LABEL_TAGS = ("h2", "h3", "h4", "h5", "strong", "b")
_INLINE = ("a", "span", "em", "i", "sup", "sub", "u", "font")


def _site_url(soup):
    """The page's own address on iafor.org, from link rel=canonical or og:url in <head>: the cheap first test of the
    claim. Every parser's claim runs on every page (#2239: under 0.5 ms a page it does not claim), so <head> is
    reached through direct children only and searched alone."""
    html = soup.find("html", recursive=False)
    head = (html or soup).find("head", recursive=False)
    if head is None:
        return None
    for tag in head.find_all(("link", "meta")):
        if tag.name == "link" and "canonical" in (tag.get("rel") or []):
            url = tag.get("href")
        elif tag.name == "meta" and tag.get("property") == "og:url":
            url = tag.get("content")
        else:
            continue
        if url and _SITE.match(url.strip()):
            return url
    return None


def _split_line(line):
    """'Hon-Sun Chiu, The Hong Kong Polytechnic University, Hong Kong' -> name, [affiliation with its country].
    The name is the text before the first comma, with a suffix the next part holds ('Harvey Henson, Jr., ...')."""
    parts = [squash(p) for p in line.split(",")]
    name, rest = parts[0], parts[1:]
    if rest and _SUFFIX.match(rest[0]):
        name = f"{name} {rest.pop(0).rstrip('.')}."
    aff = ", ".join(p for p in rest if p)
    return name, [aff] if aff else []


class IAFOR(PublisherParser):
    parser_name = "iafor"
    prefer_publisher_authors_over_generic = True  # the page's author lines carry affiliations; the tags carry none

    def _content(self):
        if (content := getattr(self, "_entry", False)) is False:  # computed once: authors_found() asks too
            content = self._entry = self.soup.select_one("article div.entry-content") if _site_url(self.soup) else None
        return content

    def _label(self, pattern):
        content = self._content()
        if content is None:
            return None
        for tag in content.find_all(_LABEL_TAGS):
            if pattern.match(squash(tag.get_text())):
                return tag
        return None

    def is_publisher_specific_parser(self):
        return self._content() is not None

    def authors_found(self):
        return self._label(_AUTHOR_LABEL) is not None

    def _author_lines(self):
        """The text after the label up to the next block or bold label, one line per <br>."""
        label = self._label(_AUTHOR_LABEL)
        lines, line = [], []
        for node in label.next_siblings:
            if isinstance(node, Comment):
                continue
            if isinstance(node, NavigableString):
                line.append(str(node))
            elif isinstance(node, Tag) and node.name == "br":
                lines.append(squash("".join(line)))
                line = []
            elif isinstance(node, Tag) and node.name in _INLINE:
                line.append(node.get_text())
            else:
                break
        lines.append(squash("".join(line)))
        return [l for l in lines if l]

    def parse_authors(self):
        authors = []
        for line in self._author_lines():
            name, affs = _split_line(line)
            if name:
                authors.append({"name": name, "affiliations": affs, "is_corresponding": False})
        return authors

    def parse(self):
        return {"authors": self.parse_authors(), "abstract": None}
