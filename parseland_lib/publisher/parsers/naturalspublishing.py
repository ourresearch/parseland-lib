"""Natural Sciences Publishing (naturalspublishing.com) article pages (oxjob #2339).

The site is a classic ASP table layout with no meta tags at all (no citation_*, no og:url, no canonical link), so the
generic parser read no authors on any of its pages. Every page is titled ".:: Natural Sciences Publishing ::.". On an
article page each field sits under a `td.Title` row ("Author(s)", "Abstract") with its value in the next `td.Content`
row; the byline is one link per author to Author.asp. The page shows no affiliations, no corresponding author and no
reference list (its "Referance(s)" block is commented out), so this parser returns the byline only and leaves the
abstract to parse_page's heading reader, which already reads it here.

Issue contents pages ("Authors:" label, one block per article, with affiliations) are not article pages and are left
alone: they carry an issue's DOI, not an article's.
"""
import re
import unicodedata

from parseland_lib.publisher.parsers.parser import PublisherParser

SITE_TITLE = "Natural Sciences Publishing"
AUTHOR_LINK = re.compile(r"^Author\.asp\?AuthID=\d+", re.I)
# a combining mark the site prints after a space ("Jua &#769;rez"): it belongs to the letter before the space
DETACHED_MARK = re.compile(r"\s+(?=[̀-ͯ])")


def _clean_name(text):
    name = DETACHED_MARK.sub("", " ".join(text.split())).strip(" ,;")
    return unicodedata.normalize("NFC", name)


class NaturalSciencesPublishing(PublisherParser):
    parser_name = "naturalspublishing"

    def is_publisher_specific_parser(self):
        # the page title only, reached through the top-level nodes (no soup-wide search on other sites' pages)
        root = self.soup.find("html", recursive=False)
        head = root.find("head", recursive=False) if root else None
        title = head.find("title", recursive=False) if head else None
        return bool(title and SITE_TITLE in title.get_text())

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._author_links())

    def _field_cell(self, label):
        """The `td.Content` cell in the rows after the `td.Title` row that reads exactly `label`."""
        for td in self.soup.find_all("td", class_="Title"):
            if td.get_text(strip=True) != label:
                continue
            row = td.find_parent("tr")
            for sibling in row.find_next_siblings("tr", limit=3) if row else []:
                if cell := sibling.find("td", class_="Content"):
                    return cell
            return None
        return None

    def _author_links(self):
        cell = self._field_cell("Author(s)")
        return cell.find_all("a", href=AUTHOR_LINK) if cell else []

    def parse(self):
        authors = []
        for link in self._author_links():
            if name := _clean_name(link.get_text(" ")):
                authors.append({"name": name, "affiliations": [], "is_corresponding": False})
        return {"authors": authors, "abstract": None}
