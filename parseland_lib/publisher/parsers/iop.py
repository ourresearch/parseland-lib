import re

from parseland_lib.exceptions import UnusualTrafficError
from parseland_lib.publisher.parsers.parser import PublisherParser

from parseland_lib.publisher.parsers.utils import email_matches_name


class IOP(PublisherParser):
    parser_name = "IOP"

    def is_publisher_specific_parser(self):
        if "iopscience.iop.org" in str(
            self.soup
        ) and "your activity and behavior on this site made us think that you are a bot" in str(
            self.soup
        ):
            raise UnusualTrafficError(f"Page blocked within parser {self.parser_name}")
        if (
            self.domain_in_canonical_link("iopscience.iop.org")
            or self.domain_in_meta_og_url("iopscience.iop.org")
        ):
            return True
        for stylesheet in self.soup.find_all("link", {"rel": "stylesheet"}):
            if "static.iopscience.com" in stylesheet.get("href", ""):
                return True
        if tag := self.soup.find("meta", {"name": "citation_pdf_url"}):
            return "iopscience.iop.org" in tag.get("content", "")
        return False

    def authors_found(self):
        return (
            self.soup.find("meta", {"name": "citation_author"})
            or self.soup.find("meta", {"name": re.compile(r"^dc\.creator$", re.I)})
            or self.soup.select_one(".author-list__name")
            or self.soup.select_one('.wd-jnl-art-abstract')
        )

    def parse(self):
        authors = self.parse_author_meta_tags()
        if not authors:
            authors = self._parse_dc_creator_authors()
        self._apply_visible_affiliations(authors)
        self._mark_corresponding_authors(authors)
        # displayed author affiliations are not available in the content, so we have to use meta tags.
        return {'authors': authors, 'abstract': self.parse_abstract()}

    def _parse_dc_creator_authors(self):
        authors = []
        seen = set()
        for meta in self.soup.find_all("meta", {"name": re.compile(r"^dc\.creator$", re.I)}):
            name = meta.get("content", "").strip()
            if not name or not re.search(r"[A-Za-z]", name):
                continue
            key = re.sub(r"\s+", " ", name).casefold()
            if key in seen:
                continue
            seen.add(key)
            authors.append({"name": name, "affiliations": [], "is_corresponding": None})
        return authors

    def _apply_visible_affiliations(self, authors):
        if not authors:
            return
        affiliations = self._visible_affiliation_lines()
        if not affiliations:
            return
        if len(affiliations) == 1:
            for author in authors:
                if not author.get("affiliations"):
                    author["affiliations"] = affiliations[:]
            return
        if len(affiliations) == len(authors):
            for author, affiliation in zip(authors, affiliations):
                if not author.get("affiliations"):
                    author["affiliations"] = [affiliation]

    def _visible_affiliation_lines(self):
        block = self.soup.select_one(".wd-jnl-art-author-affiliations")
        if not block:
            return []
        text = block.get_text(" ", strip=True)
        text = re.sub(r"\s+", " ", text)
        if not text:
            return []
        numbered = re.findall(r"(?:^|\s)(\d+)\s+(.+?)(?=\s+\d+\s+|$)", text)
        if numbered:
            return [
                aff.strip()
                for _, aff in numbered
                if aff.strip()
                and "author to whom any correspondence should be addressed" not in aff.lower()
            ]
        if "author to whom any correspondence should be addressed" in text.lower():
            return []
        return [text]

    def _mark_corresponding_authors(self, authors):
        if not authors:
            return
        real_mailto_tags = self._real_mailto_tags()
        real_mailto_hrefs = []
        seen_mailto_hrefs = set()
        for tag in real_mailto_tags:
            href = tag.get("href", "").lower()
            if href not in seen_mailto_hrefs:
                seen_mailto_hrefs.add(href)
                real_mailto_hrefs.append(href)
        if len(real_mailto_hrefs) == 1:
            href = real_mailto_hrefs[0]
            for author in authors:
                if email_matches_name(href, author["name"]):
                    author["is_corresponding"] = True

        for name_tag in self.soup.select(".author-list__name"):
            name = name_tag.get_text(" ", strip=True)
            if not name:
                continue
            scope = name_tag.find_parent(class_=re.compile(r"author-list__(?:author|item|entry)"))
            if scope is None:
                scope = name_tag.parent
            text = scope.get_text(" ", strip=True).lower() if scope else ""
            has_correspondence_note = "author to whom any correspondence should be addressed" in text
            if has_correspondence_note:
                for author in authors:
                    if author["name"].strip().lower() == name.strip().lower():
                        author["is_corresponding"] = True

        for block in self.soup.select(".wd-jnl-art-author-affiliations, .wd-jnl-art-author-notes"):
            text = block.get_text(" ", strip=True)
            match = re.search(
                r"(?:^|\s)(\d+)\s+Author to whom any correspondence should be addressed",
                text,
                flags=re.I,
            )
            if match:
                self._mark_numbered_corresponding_author(authors, match.group(1))

    def _mark_numbered_corresponding_author(self, authors, note_number):
        matched_by_superscript = False
        page_text = self.soup.get_text(" ", strip=True)
        for author in authors:
            pattern = rf"(?<!\w){re.escape(author['name'])}(?!\w)\s+(?P<labels>\d(?:[\d,\s,]*\d)?)"
            for match in re.finditer(pattern, page_text, flags=re.I):
                labels = re.findall(r"\d+", match.group("labels"))
                if note_number in labels:
                    author["is_corresponding"] = True
                    matched_by_superscript = True
                    break
        if matched_by_superscript:
            return

        index = int(note_number) - 1
        if 0 <= index < len(authors):
            authors[index]["is_corresponding"] = True

    def _real_mailto_tags(self):
        return [
            tag
            for tag in self.soup.select('a[href^="mailto:"]')
            if "@" in tag.get("href", "") and not tag.get("href", "").startswith("mailto:?")
        ]

    def parse_abstract(self):
        if abstract := self.parse_abstract_meta_tags():
            return abstract

        for abstract_tag in self.soup.select('.wd-jnl-art-abstract'):
            paragraphs = [
                p.get_text(' ', strip=True)
                for p in abstract_tag.find_all('p')
                if p.get_text(' ', strip=True)
            ]
            abstract = ' '.join(paragraphs).strip()
            if not abstract:
                abstract = abstract_tag.get_text(' ', strip=True)
            if len(abstract) >= 15:
                return abstract
        return None

    # test not passing due to page being blocked
    # test_cases = [
    #     {
    #         "doi": "10.1088/1361-6560/ac212a",
    #         "result": [
    #             {
    #                 "name": "Nicolaus Kratochwil",
    #                 "affiliations": [
    #                     "CERN, Esplanade des Particules 1, 1211 Meyrin, Switzerland",
    #                     "University of Vienna, Universitaetsring 1, A-1010 Vienna, Austria",
    #                 ],
    #                 "is_corresponding": False,
    #             },
    #             {
    #                 "name": "Stefan Gundacker",
    #                 "affiliations": [
    #                     "CERN, Esplanade des Particules 1, 1211 Meyrin, Switzerland",
    #                     "Department of Physics of Molecular Imaging Systems, Institute for Experimental Molecular Imaging, RWTH Aachen University, Forckenbeckstrasse 55, D-52074 Aachen, Germany",
    #                 ],
    #                 "is_corresponding": False,
    #             },
    #             {
    #                 "name": "Etiennette Auffray",
    #                 "affiliations": [
    #                     "CERN, Esplanade des Particules 1, 1211 Meyrin, Switzerland"
    #                 ],
    #                 "is_corresponding": False,
    #             },
    #         ],
    #     },
    # ]
