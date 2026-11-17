import re

from parseland_lib.publisher.parsers.parser import PublisherParser


# PUC-Rio's Maxwell digital library record pages (maxwell.vrac.puc-rio.br, DOI prefix 10.17771: theses, dissertations,
# monographs and the university's journals; oxjob #2338). The page has no citation_* meta tags: its fields are a
# label/value list (<span class="txtformNormal">Autor(es):</span> then <span class="txtNormal">). Each byline name is a
# link onclick="openCloseMenu('autor_N')" followed by a hidden pop-up card div#autor_N whose <pre> lists, one per line:
# the name as "Family, Given", a birth-year placeholder ("19-"), the person's role ("Aluna de Pós-Graduação", "Aluno de
# Graduação", "Professora") and then the unit and institution ("Programa de Pós-Graduação em Direito", "PUC-Rio").
# The unit and institution lines are the author's affiliation (both blind labellers on the build pages). A card that
# lists several roles ("Professor de Especialização ... Ex-Aluno de Pós-Graduação ...") is a biography, not an
# affiliation (both labellers on the build page that has one), and so is a card with no role line. Advisors
# ("Colaborador(es): ... - Orientador") are not authors. A journal credited as the author ("REVISTA ESCRITA") stays a
# group author, with no affiliation: its card has no "Family, Given" line. The abstract ("Resumo:") is left to
# parse_page's readers, which read it on 56 of the 62 record pages sampled; the works it would add are under the
# swarm's 1,000-work floor. The 11 KB "Verificando sua sessão" shells hold no record and are not read.
_HEAD_MARK = "maxwell.vrac.puc-rio.br/css/"
_AUTHOR_LABELS = {"Autor(es):", "Autor:", "Author(s):", "Author:"}
_CARD_ID = re.compile(r"openCloseMenu\(\s*'([^']+)'")
_BIRTH = re.compile(r"^\d{2,4}\s*-?\s*(\d{2,4})?$")
_ROLE = re.compile(r"^(ex-\s*)?(alun[oa]|professor|pesquisador|bolsista|funcion[aá]ri|t[eé]cnic|coordenador|"
                   r"doutorand|mestrand|p[oó]s-doutor|docente|servidor|estagi[aá]ri)", re.I)


def _card_affiliation(card):
    """The unit and institution a person's pop-up card gives, or None (no card, a biography, a group's card)."""
    pre = card.find("pre") if card is not None else None
    if pre is None:
        return None
    lines = [line.strip() for line in pre.get_text("\n").split("\n") if line.strip()]
    if not lines or "," not in lines[0]:
        return None  # not "Family, Given": a journal or other group credited as the author
    rest = lines[1:]
    if rest and _BIRTH.match(rest[0]):
        rest = rest[1:]
    if [i for i, line in enumerate(rest) if _ROLE.match(line)] != [0]:
        return None  # no role line, or several roles (a biography)
    return ", ".join(rest[1:]) or None


def _name_links(value):
    """The byline's name links: the value span's own <a> children (the cards' "Veja mais" and Lattes links sit deeper)."""
    return [a for a in value.find_all("a", recursive=False)
            if _CARD_ID.search(a.get("onclick") or "") or "strSecao=autor" in (a.get("href") or "")]


class PucRioMaxwell(PublisherParser):
    parser_name = "puc_rio_maxwell"
    prefer_publisher_authors_over_generic = True

    def _is_maxwell(self):
        # The cheap claim test, run on every DOI page (#2239: under 0.5 ms a page it does not claim): the library's
        # own stylesheets in <head>, nothing page-wide.
        if not hasattr(self, "_maxwell"):
            head = self.soup.head
            self._maxwell = head is not None and any(
                _HEAD_MARK in (tag.get("href") or "") for tag in head.find_all("link"))
        return self._maxwell

    def _byline(self):
        """The "Autor(es):" value span, found once; None on pages that have none (session-check shells). The search
        form's own "Autor:" label (followed by an input box, with or without a <label> around it) is passed over."""
        if not hasattr(self, "_value"):
            self._value = None
            if self._is_maxwell():
                for label in self.soup.find_all("span", class_="txtformNormal"):
                    if label.get_text(strip=True) not in _AUTHOR_LABELS:
                        continue
                    value = label.find_next_sibling(True)
                    if value is not None and value.name == "span" and _name_links(value):
                        self._value = value
                        break
        return self._value

    def _name_links(self):
        value = self._byline()
        return _name_links(value) if value is not None else []

    def is_publisher_specific_parser(self):
        return self._is_maxwell()

    def authors_found(self):
        return bool(self._name_links())

    def parse(self):
        value = self._byline()
        authors = []
        for link in self._name_links():
            name = " ".join(link.get_text(" ", strip=True).split())
            if not name:
                continue
            card_id = _CARD_ID.search(link.get("onclick") or "")
            card = value.find(id=card_id.group(1)) if card_id else None
            aff = _card_affiliation(card)
            authors.append({"name": name, "affiliations": [aff] if aff else [], "is_corresponding": None})
        return {"authors": authors, "abstract": None}
