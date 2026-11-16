import re

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import cleanup_raw_name

# The chapter panel's label for its authors, in the German and English page versions. Not "Herausgeber:innen" /
# "Editors": a chapter's editors are not its authors.
_AUTHORS_LABEL = re.compile(r"^(?:autor(?::innen|innen|en|in)?|authors?)\s*:?$", re.I)
_TITLES = re.compile(r"^(?:(?:prof|dr|pd)\.?\s+)+", re.I)  # "Prof. Dr. ", "PD Dr. "
# A card tag with a role in brackets is not an author: "Eric Hilgendorf (Hrsg.)", "Ole Petras (ed.)".
_ROLE = re.compile(r"\([^)]*\)\s*$")


def _clean(raw):
    return cleanup_raw_name(_TITLES.sub("", " ".join(raw.split())))


class NomosInlibra(PublisherParser):
    """Nomos eLibrary's platform (#2268): Inlibra's PDF viewer, and the older eLibrary chapter card.

    Inlibra (inlibra.com): a chapter or article DOI lands on the PDF viewer, whose citation_* meta tags describe the
    whole book or journal issue: a chapter gets its book's editors from them, an issue's article gets nobody. The
    viewer's chapter panel ("Kapitelinformationen", #panel-info) names the item's own authors; the bibliographic panel
    (#panel-bibinfo) lists the book's or the whole issue's people and is never read. The panel's "Kapitelvorschau"
    (a preview: the first page's text or image) is not an abstract.
    The older eLibrary (nomos-, beck-, tectum-, vdi-elibrary.de; stored pages from before the move to Inlibra) shows a
    chapter as a card "<chapter> in: <book>" whose person tags (links to the eLibrary's person search) are the
    chapter's authors, with no citation_author tag. Tags with a role ("(Hrsg.)", "(ed.)") are the book's editors. A
    card that has citation_author tags (older chapter cards: the chapter's author in the tag, the book's editors in
    the card) is left to them, and so is a book's own card (no "in:" line), whose page also lists every chapter.
    Claimed by each platform's own markup, not by a domain: both serve several publishers.
    """
    parser_name = "nomos_inlibra"
    prefer_publisher_authors_over_generic = True

    def _panel(self):
        main = self.soup.select_one('main.pdf-viewer[data-controller~="pdf-viewer"]')
        if not main or not main.select_one('div.pdf-viewer__panel#panel-bibinfo'):
            return None
        return main.select_one('div.pdf-viewer__panel#panel-info')

    def _card_tags(self):
        """The person tags of an older eLibrary card ([] when the page has none)."""
        card = self.soup.select_one('.pl-card--document')
        if card is None:
            return []
        return [a for a in card.select('.pl-card__tags a.pl-tag[href]')
                if 'page-search-location=eLibrary' in a['href'] and '&qa=' in a['href']]

    def is_publisher_specific_parser(self):
        return self._panel() is not None or bool(self._card_tags())

    def authors_found(self):
        return bool(self._authors())

    def _authors(self):
        return self._panel_authors() or self._card_authors()

    def _panel_authors(self):
        panel = self._panel()
        if panel is None:
            return []
        for dt in panel.select('dl dt'):
            if not _AUTHORS_LABEL.match(dt.get_text(" ", strip=True)):
                continue
            dd = dt.find_next_sibling('dd')
            if dd is None:
                return []
            names = []
            for tag in dd.select('button, a') or [dd]:
                for raw in tag.get_text(" ", strip=True).split("|"):
                    if (name := _clean(raw)) and name not in names:  # a link nested in a button is one person
                        names.append(name)
            return names
        return []

    def _card_authors(self):
        topline = self.soup.select_one('.pl-card--document .pl-card__topline')
        if topline is None or not topline.get_text(" ", strip=True).endswith("in:"):
            return []
        if self.soup.select_one('meta[name="citation_author"]'):
            return []
        names = []
        for tag in self._card_tags():
            raw = tag.get('data-tippy-content') or tag.get_text(" ", strip=True)
            if not _ROLE.search(raw) and (name := _clean(raw)):
                names.append(name)
        return names

    def parse(self):
        authors = [{"name": name, "affiliations": [], "is_corresponding": None} for name in self._authors()]
        return {"authors": authors, "abstract": None}
