"""Editora Omnis Scientia (editoraomnisscientia.com.br) chapter and conference-paper pages (oxjob #2339).

The publisher's own WordPress theme ("post-artigo" pages). Every citation_author tag repeats one name, so the meta-tag
byline is wrong; the "Autores" tab lists the authors, one <li><p> each. The abstract is printed twice: in Portuguese,
unlabelled, under the title (div.ebook_topo), and in English after "ABSTRACT:" in the "Descrição" tab; the labels give
the English one, and the Portuguese one is the fallback when the English one is empty. Pages show no affiliations,
corresponding-author marks, acknowledgments, funding statements or reference lists. A book's own catalogue page
("Autor" tab listing every chapter's authors, "Artigos" tab) is left to the other readers: its text is a blurb.
"""
import re

from parseland_lib.publisher.parsers.parser import PublisherParser

PUBLISHER = "Editora Omnis Scientia"
ABSTRACT_LABEL = re.compile(r"^\s*abstract\s*:?\s*$", re.I)


def _text(tag):
    return re.sub(r"\s+", " ", tag.get_text(" ")).strip()


class EditoraOmnisScientia(PublisherParser):
    parser_name = "editora_omnis_scientia"
    # the citation_author tags repeat one name: the Autores tab must win over them
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        # one meta tag in <head>: cheap on every other site's page
        head = self.soup.head
        tag = head.find("meta", attrs={"name": "citation_publisher"}) if head else None
        return bool(tag) and (tag.get("content") or "").strip() == PUBLISHER

    def _authors_pane(self):
        for h3 in self.soup.select("div.tab__content > h3"):
            if h3.get_text(strip=True) == "Autores":
                return h3.parent
        return None

    def authors_found(self):
        if not self.is_publisher_specific_parser() or self.soup.select_one("div.ebook_topo h2") is None:
            return False
        pane = self._authors_pane()
        return bool(pane and pane.select_one("ul.ul-padrao li"))

    def parse_authors(self):
        authors = []
        for li in self._authors_pane().select("ul.ul-padrao > li"):
            name = _text(li)
            if name:
                authors.append({"name": name, "affiliations": [], "is_corresponding": False})
        return authors

    def parse_abstract(self):
        for strong in self.soup.select("div.tab__content p > strong"):
            if ABSTRACT_LABEL.match(strong.get_text()):
                para = strong.parent
                label = _text(strong)
                text = _text(para)
                text = text[len(label):].strip() if text.startswith(label) else text
                if text:
                    return text
                break
        topo = self.soup.select_one("div.ebook_topo h2")
        para = topo.find_next_sibling("p") if topo else None
        return (_text(para) or None) if para else None

    def parse(self):
        return {"authors": self.parse_authors(), "abstract": self.parse_abstract()}
